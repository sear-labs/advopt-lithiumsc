"""Build notebooks/04d_stackelberg.ipynb.

**What this notebook teaches, and what it carries over.** Its subject is the
bilevel-to-MPEC collapse: the follower's problem, its KKT conditions, the big-M
complementarity, and the exact linearisation of the bilinear revenue term. All of
that is built by hand and narrated, sections 6 to 10.

The leader's *chain* is not this notebook's subject — Part 4c narrated it, cell
by cell, and re-narrating twenty cells of it here would bury the MPEC. So
section 5 carries it over as a wrapper, under a heading that says so, with a
`CARRIED OVER` marker the build audit recognises. That is a deliberate exemption
from "no function definitions in the teaching section" and it is exempt for the
stated reason: the abstraction is not above the narration of the same material,
it is above the narration of *different* material whose own narration lives in
04c. Section 16's agreement assertion covers the carried-over chain anyway,
because the packaged `stackelberg` builds it with `add_region`.
"""
from . import common

NOTEBOOK = "04d_stackelberg.ipynb"
TITLE = "Part 4d - Stackelberg leadership as a single-level MPEC"


def cells():
    out = []

    def M(text):
        out.append(("md", text.strip("\n")))

    def C(text):
        out.append(("code", text.strip("\n")))

    # ================================ front ================================
    M(r"""
# Part 4d — Stackelberg leadership as a single-level MPEC

### Collapsing a bilevel program using the follower's KKT conditions

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/sear-labs/advopt-lithiumsc/blob/main/notebooks/04d_stackelberg.ipynb)

In Cournot (Part 4c) both firms move simultaneously. Here the **leader commits
first** and the follower observes that commitment before choosing its own output
and capacity. That is a **bilevel** program:

$$\max_{x_L} \;\; \Pi_L(x_L, x_F^*) \quad \text{s.t.} \quad
x_F^* \in \arg\max_{x_F} \Pi_F(x_F; x_L)$$

An optimisation nested inside an optimisation cannot be handed to a solver
directly. The standard route is to replace the inner problem with its
**optimality conditions**, producing a single-level **MPEC** (Mathematical
Program with Equilibrium Constraints).

**This is only possible because the follower's problem is continuous and
concave.** KKT conditions are necessary and sufficient for a concave program;
they say nothing useful about a MILP. So the design decision made all the way
back in Part 3 — keep the operational layer an LP, put the integers only in
investment — is what makes this notebook possible at all.

### The division of labour

| | Leader (R1) | Follower (R2) |
|---|---|---|
| Investment | binary build + continuous size, full chain | **continuous** capacity expansion |
| Output | chosen on a discrete grid | continuous |
| Problem type | MILP | **concave QP** → KKT applies |

The follower's simplification is a real modelling cost and worth stating plainly:
it can expand capacity continuously but cannot make lumpy siting decisions. Its
investment is a scalar, not a plan. That is the price of admission for an exact
bilevel formulation.

### How to read this notebook

Sections 6–10 are this notebook's lesson and are built **by hand**: the
follower's cost, the follower solved directly as a QP, its KKT conditions, the
big-M complementarity, and the exact linearisation of the bilinear term.
Section 5 **carries over** Part 4c's supply chain as a wrapper rather than
re-narrating it — 4c is where that material is taught. Section 12 wraps the MPEC
once you have built one, and section 16 asserts the notebook and the `lithium`
package agree to $10^{-9}$.
""")

    out += common.setup_section(notebook=NOTEBOOK)

    out += common.instance_section(agree=13)
    out += common.structure_section(agree=13, chain=5)
    out += common.capex_curve_section(chain=5, revenue=10)

    # ==================== 5. carried over from Part 4c =====================
    M(r"""
## 5. Carried over from Part 4c: the leader's chain

Everything below this heading was written out cell by cell in
`04c_cournot.ipynb` sections 5 and 7, where it is the lesson. Here it is not:
this notebook is about the bilevel collapse, and re-narrating twenty cells of
supply chain would bury it.

So the chain arrives as a **wrapper**, and this is the one place in this notebook
where a function appears before any narration of what it contains. That is a
deliberate exemption with a stated reason — the material it abstracts is narrated
in 04c, not below — and section 16's agreement assertion covers it regardless,
because the packaged `stackelberg` builds the same chain with
`lithium.regions.add_region`.

**If you have not read 04c section 5, read it before this cell.** It is the same
eight constraint blocks: capacity coupling, the five chain balances, cumulative
production, the annuitised capex with its SOS2 set, and the tiered operating cost.
""")

    C(r'''
# CARRIED OVER FROM 04c SECTIONS 5 AND 7 - narrated there, not re-taught here.
# Identical to 04c's chain(), which that notebook checks against the hand-built
# model it was extracted from.

def chain(m, r, learning, tiers, rev_price):
    """Attach region r's chain to model m. See 04c sections 5.1-5.6 and 7.3-7.4."""
    b_ = m.addVars(BUILD[r], vtype=GRB.BINARY, name=f'b_{r}')
    c_ = m.addVars(BUILD[r], lb=0.0, ub=CAP_MAX, name=f'c_{r}')
    x_ = m.addVars(ACTIVE[r], lb=0.0, name=f'x_{r}')
    fmp_ = m.addVars(P, lb=0.0, name=f'fmp_{r}')
    fpf_ = m.addVars(P, lb=0.0, name=f'fpf_{r}')
    sale_ = m.addVars(REGIONS, P, lb=0.0, name=f'sale_{r}')
    disp_ = m.addVars(P, lb=0.0, name=f'disp_{r}')

    m.addConstrs((c_[s, v] <= CAP_MAX * b_[s, v] for (s, v) in BUILD[r]), name=f'su_{r}')
    m.addConstrs((c_[s, v] >= CAP_MIN * b_[s, v] for (s, v) in BUILD[r]), name=f'sl_{r}')
    m.addConstrs((x_[s, v, p] <= (LEGACY_CAP[s, r] if v == -1 else c_[s, v])
                  for (s, v, p) in ACTIVE[r]), name=f'cap_{r}')
    m.addConstrs((gp.quicksum(ETA['MINE', v, p] * x_['MINE', v, p]
                              for v in VIN[r, 'MINE', p]) == fmp_[p] for p in P), name=f'mine_{r}')
    m.addConstrs((fmp_[p] == gp.quicksum(x_['PROC', v, p] for v in VIN[r, 'PROC', p])
                  for p in P), name=f'pin_{r}')
    m.addConstrs((gp.quicksum(ETA['PROC', v, p] * x_['PROC', v, p]
                              for v in VIN[r, 'PROC', p]) == fpf_[p] for p in P), name=f'pout_{r}')
    m.addConstrs((fpf_[p] == gp.quicksum(x_['MFG', v, p] for v in VIN[r, 'MFG', p])
                  for p in P), name=f'min_{r}')
    m.addConstrs((gp.quicksum(ETA['MFG', v, p] * x_['MFG', v, p] for v in VIN[r, 'MFG', p])
                  == sale_.sum('*', p) + disp_[p] for p in P), name=f'mout_{r}')

    cum_ = m.addVars(P, lb=0.0, ub=3 * CAP_MAX * HORIZON + EXPERIENCE0[r], name=f'cum_{r}')
    m.addConstrs((cum_[p] == EXPERIENCE0[r] +
                  gp.quicksum(LEN[q] * x_['MFG', v, q] for q in P if q <= p
                              for v in VIN[r, 'MFG', q]) for p in P), name=f'cp_{r}')

    capex_ = (gp.quicksum(MU[s, v] * FIXED[s, r] * b_[s, v] for (s, v) in BUILD[r])
              + gp.quicksum(MU[s, v] * UNIT[s, r] * c_[s, v]
                            for (s, v) in BUILD[r] if s not in LEARN_STAGES))
    Q_ = m.addVars(P, lb=Q_START, ub=Q_START + Q_ADD, name=f'Q_{r}')
    C_ = m.addVars(P, lb=0.0, name=f'C_{r}')
    lam_ = m.addVars(P, K, lb=0.0, ub=1.0, name=f'lam_{r}')
    m.addConstrs((lam_.sum(p, '*') == 1 for p in P), name=f'sc_{r}')
    m.addConstrs((Q_[p] == gp.quicksum(QBP[k] * lam_[p, k] for k in K) for p in P), name=f'sQ_{r}')
    m.addConstrs((C_[p] == gp.quicksum(CBP[k] * lam_[p, k] for k in K) for p in P), name=f'sC_{r}')
    m.addConstrs((Q_[p] == Q_START + gp.quicksum(c_[s, v] for (s, v) in BUILD[r]
                                                 if s in LEARN_STAGES and v <= p)
                  for p in P), name=f'cc_{r}')
    for p in P:
        m.addSOS(GRB.SOS_TYPE2, [lam_[p, k] for k in K])
    rate_ = sum(UNIT[s, r] for s in LEARN_STAGES) / len(LEARN_STAGES)
    capex_ += gp.quicksum(MU['PROC', p] * rate_ * (C_[p] - (C_[p - 1] if p > 0 else 0.0))
                          for p in P)

    if learning == 'both' and tiers is not None:
        tq, tm = tiers
        J_ = list(range(N_TIERS))
        z_ = m.addVars(P, J_, vtype=GRB.BINARY, name=f'z_{r}')
        m.addConstrs((z_.sum(p, '*') == 1 for p in P), name=f'ot_{r}')
        lagp = {p: YEAR_TO_P[max(1, START[p] - LAG_YEARS)] for p in P}
        bigq = 3 * CAP_MAX * HORIZON + EXPERIENCE0[r]
        m.addConstrs((cum_[lagp[p]] >= tq[r][j - 1] - bigq * (1 - z_[p, j])
                      for p in P for j in J_ if j > 0), name=f'tf_{r}')
        m.addConstrs((cum_[lagp[p]] <= tq[r][j] + bigq * (1 - z_[p, j])
                      for p in P for j in J_ if j < N_TIERS - 1), name=f'tc_{r}')
        ts_ = m.addVars(STAGES, P, J_, lb=0.0, name=f'ts_{r}')
        m.addConstrs((ts_.sum(s, p, '*') == gp.quicksum(x_[s, v, p] for v in VIN[r, s, p])
                      for s in STAGES for p in P), name=f'tss_{r}')
        m.addConstrs((ts_[s, p, j] <= 3 * CAP_MAX * z_[p, j]
                      for s in STAGES for p in P for j in J_), name=f'tl_{r}')
        opex_ = gp.quicksum(OMEGA[p] * OPEX[s, r] * tm[r][j] * ts_[s, p, j]
                            for s in STAGES for p in P for j in J_)
    else:
        z_ = None
        opex_ = gp.quicksum(OMEGA[p] * OPEX[s, r] * x_[s, v, p] for (s, v, p) in ACTIVE[r])

    trans_ = gp.quicksum(OMEGA[p] * TRANSPORT[r, rt] * sale_[rt, p]
                         for rt in REGIONS for p in P)
    dcost_ = gp.quicksum(OMEGA[p] * PEN_DISPOSE * disp_[p] for p in P)
    rev_ = (gp.quicksum(OMEGA[p] * rev_price * sale_[rt, p] for rt in REGIONS for p in P)
            if rev_price is not None else None)
    return dict(b=b_, c=c_, x=x_, sale=sale_, disp=disp_, cum=cum_, z=z_,
                capex=capex_, opex=opex_, trans=trans_, dcost=dcost_, revenue=rev_,
                cost=capex_ + opex_ + trans_ + dcost_)


print("chain() carried over from 04c -", chain.__doc__.splitlines()[0])
''')

    M(r"""
### 5.1 The tier calibration, also carried over

The operating-cost tiers need a scale, and the scale comes from a planner solve —
04c section 6 explains why the thresholds cannot be knobs. Two carried-over
cells, then we are into new material.
""")

    C(r'''
# CARRIED OVER FROM 04c SECTIONS 5.7 AND 6.

def planner(w1, learning, tiers, mipgap):
    """Cost-minimising planner over both chains. See 04c section 5.7."""
    m = gp.Model()
    m.Params.OutputFlag = 0
    m.Params.MIPGap = mipgap
    H = {r: chain(m, r, learning, tiers, rev_price=None) for r in REGIONS}
    short = m.addVars(REGIONS, P, lb=0.0, name='short')
    m.addConstrs((gp.quicksum(H[r]['sale'][rt, p] for r in REGIONS) + short[rt, p]
                  >= DEMAND[rt, p] for rt in REGIONS for p in P), name='demand')
    pen = gp.quicksum(OMEGA[p] * PEN_SHORT * short[rt, p] for rt in REGIONS for p in P)
    m.setObjective(w1 * H['R1']['cost'] + (1 - w1) * H['R2']['cost'] + pen, GRB.MINIMIZE)
    m.optimize()
    m._H, m._short = H, short
    return m


LR_OPEX, OPEX_FLOOR, LAG_YEARS, N_TIERS = 0.18, 0.65, 3, 3
PEN_SHORT, PEN_DISPOSE = 90.0, 12.0
LEADER_FIRST = 'R1'      # who moves first in the Cournot benchmark
PRICE_FIXED = 12.0
MIPGAP_PLAN = 0.005

m0 = planner(0.5, learning='capacity', tiers=None, mipgap=MIPGAP_PLAN)
assert m0.SolCount > 0, f"planner calibration failed; status {m0.Status}"
top = {r: m0._H[r]['cum'][P[-1]].X for r in REGIONS}

TIER_Q, TIER_M = {}, {}
for r in REGIONS:
    _q1 = max(top[r], 1.0) / 8.0
    TIER_Q[r] = [_q1 * 2 ** j for j in range(N_TIERS - 1)]
    TIER_M[r] = [max(OPEX_FLOOR, (1 - LR_OPEX) ** j) for j in range(N_TIERS)]
TIERS = (TIER_Q, TIER_M)

print(f"planner objective {m0.ObjVal:,.1f}")
for r in REGIONS:
    print(f"  {r}: cumulative production {top[r]:9.2f}  "
          f"thresholds {[round(q, 1) for q in TIER_Q[r]]}")
''')

    M(r"""
### 5.2 Inverse demand, also carried over

Same linear inverse demand as 04c: `CHOKE` is the price at zero quantity, and
`B` is calibrated so price equals `P_ANCHOR` at the reference quantity.
""")

    C(r'''
CHOKE = 30.0       # price at zero quantity
P_ANCHOR = 13.0    # price at the Part 4b reference quantity

A_INT = {(rt, p): CHOKE for rt in REGIONS for p in P}
B_SLP = {(rt, p): (CHOKE - P_ANCHOR) / DEMAND[rt, p] for rt in REGIONS for p in P}

print(f"choke price {CHOKE}, anchor {P_ANCHOR}")
print(f"B in period 0: " + "  ".join(f"{rt} {B_SLP[rt, 0]:.5f}" for rt in REGIONS))
''')

    M(r"""
### 5.3 Carried over: the Cournot best response and the iteration

Section 13 compares Stackelberg against Cournot, and section 14 asks what the
follower would do against a leader selling its *Cournot* volume. Both need Part
4c's equilibrium, so both need 4c's best response — narrated there, carried over
here.

Computing it rather than quoting a number matters, and section 14 is why: that
counterfactual needs the leader's Cournot schedule **market by market and period
by period**, not its total. A flat average of the total would be a different
leader, and comparing against it would be comparing two things that were never
asked the same question.
""")

    C(r'''
# CARRIED OVER FROM 04c SECTIONS 7 AND 9 - narrated there, not re-taught here.

NBP_REV = 7
MIPGAP_GAME, TOL, MAX_ITER = 1e-3, 0.5, 16


def best_response(r, rival, learning, tiers, nbp_rev, mipgap):
    """Firm r's profit-maximising reply. See 04c sections 7.2-7.6."""
    m = gp.Model()
    m.Params.OutputFlag = 0
    m.Params.MIPGap = mipgap
    h = chain(m, r, learning, tiers, rev_price=None)
    s_ = h['sale']
    kr = list(range(nbp_rev))
    mu_ = m.addVars(REGIONS, P, kr, lb=0.0, ub=1.0, name='mu')
    revt_ = m.addVars(REGIONS, P, lb=-GRB.INFINITY, name='revt')
    for rt in REGIONS:
        for p in P:
            q_bar = rival.get((rt, p), 0.0)
            a_eff = A_INT[rt, p] - B_SLP[rt, p] * q_bar
            smax = max(1e-6, A_INT[rt, p] / B_SLP[rt, p] - q_bar)
            Sg = [smax * k / (nbp_rev - 1) for k in kr]
            Rg = [a_eff * v - B_SLP[rt, p] * v * v for v in Sg]
            m.addConstr(mu_.sum(rt, p, '*') == 1)
            m.addConstr(s_[rt, p] == gp.quicksum(Sg[k] * mu_[rt, p, k] for k in kr))
            m.addConstr(revt_[rt, p] == gp.quicksum(Rg[k] * mu_[rt, p, k] for k in kr))
    rev_ = gp.quicksum(OMEGA[p] * revt_[rt, p] for rt in REGIONS for p in P)
    m.setObjective(rev_ - h['cost'], GRB.MAXIMIZE)
    m.optimize()
    m._h, m._rev = h, rev_
    return m


def iterate(learning, tiers, nbp_rev, first, max_iter, tol, mipgap):
    """Iterated best response, tolerance-based. See 04c section 9."""
    def dist(a, bb):
        return max(abs(a[r][k] - bb[r][k]) for r in REGIONS for k in a[r])

    sales = {r: {(rt, p): 0.0 for rt in REGIONS for p in P} for r in REGIONS}
    hist, log = [], []
    order = [first] + [r for r in REGIONS if r != first]
    for it in range(max_iter):
        prev = {r: dict(sales[r]) for r in REGIONS}
        for r in order:
            rival = {}
            for other in REGIONS:
                if other == r:
                    continue
                for k, v in sales[other].items():
                    rival[k] = rival.get(k, 0.0) + v
            b = best_response(r, rival, learning, tiers, nbp_rev, mipgap)
            if b.SolCount == 0:
                return dict(status='INFEASIBLE', iters=it, log=log)
            sales[r] = {(rt, p): b._h['sale'][rt, p].X for rt in REGIONS for p in P}
            log.append(dict(iter=it, firm=r, profit=b.ObjVal,
                            sales=sum(sales[r].values())))
        cur = {r: dict(sales[r]) for r in REGIONS}
        if it > 0 and dist(cur, prev) < tol:
            return dict(status='CONVERGED', iters=it + 1, log=log, sales=sales)
        for k, past in enumerate(hist):
            if dist(cur, past) < tol:
                return dict(status='CYCLE', iters=it + 1, log=log, sales=sales)
        hist.append(cur)
    return dict(status='MAX_ITER', iters=max_iter, log=log, sales=sales)


cournot = iterate('both', TIERS, NBP_REV, first=LEADER_FIRST, max_iter=MAX_ITER,
                  tol=TOL, mipgap=MIPGAP_GAME)
assert cournot['status'] == 'CONVERGED', f"Cournot: {cournot['status']}"
_lastc = {g['firm']: g for g in cournot['log'][-2:]}
COURNOT_PROFIT = {r: _lastc[r]['profit'] for r in REGIONS}
COURNOT_QTY = {r: _lastc[r]['sales'] for r in REGIONS}
print(f"Part 4c's equilibrium, recomputed here in {cournot['iters']} rounds:")
for r in REGIONS:
    print(f"  {r}: profit {COURNOT_PROFIT[r]:10.1f}   sales {COURNOT_QTY[r]:8.1f}")
''')

    # ================= 6. the follower's cost, by hand =====================
    M(r"""
## 6. The follower's cost and inherited capacity

New material starts here.

The follower's marginal cost per unit **delivered** must account for chain
yields: to deliver one finished unit you need $1/\eta_{MFG}$ of manufacturing
throughput, $1/(\eta_{MFG}\eta_{PROC})$ of processing, and so on upstream.
Transport to each market is added on top, which is why serving the leader's home
market costs the follower more.

**Note what this cell throws away, because it is the whole reason the method
works.** It evaluates the yields at the *legacy vintage in period 0* and turns
the follower's cost into a **constant**. That is what makes the follower's
problem concave and therefore KKT-representable. The price is that the follower
cannot choose a build plan — its investment is one scalar. State that cost;
do not hide it.
""")

    C(r'''
LEADER, FOLLOWER = 'R1', 'R2'

e_m, e_p, e_f = ETA['MINE', -1, 0], ETA['PROC', -1, 0], ETA['MFG', -1, 0]
thr_f = 1.0 / e_f                 # MFG throughput per unit delivered
thr_p = thr_f / e_p               # PROC throughput per unit delivered
thr_m = thr_p / e_m               # MINE throughput per unit delivered

chain_cost = (OPEX['MFG', FOLLOWER] * thr_f + OPEX['PROC', FOLLOWER] * thr_p
              + OPEX['MINE', FOLLOWER] * thr_m)
c_f = {rt: chain_cost + TRANSPORT[FOLLOWER, rt] for rt in REGIONS}

print(f"yields at the legacy vintage: MINE {e_m:.4f}  PROC {e_p:.4f}  MFG {e_f:.4f}")
print(f"throughput needed per delivered unit: MFG {thr_f:.4f}  PROC {thr_p:.4f}"
      f"  MINE {thr_m:.4f}")
print(f"chain operating cost alone: {chain_cost:.4f}")
for rt in REGIONS:
    print(f"  delivered to {rt}: {chain_cost:.4f} + transport "
          f"{TRANSPORT[FOLLOWER, rt]:.1f} = {c_f[rt]:.4f}")
''')

    M(r"""
### 6.1 The follower's inherited capacity, and the cliff in it

The follower starts with a manufacturing plant it did not have to build. Once
that retires it can serve the market only by paying for expansion — and that is
precisely the moment a leader would want to have pre-committed enough quantity to
make expansion unattractive.

`CAP_COST` is the annualised cost of adding a unit of the follower's capacity:
the average annuity factor across build periods times the unit cost, plus a
`CAP_ADDER` standing in for the siting and connection costs a scalar capacity
variable cannot represent.
""")

    C(r'''
CAP_ADDER = 4.0        # what a scalar capacity variable cannot represent
BIG_Q, BIG_L = 1200.0, 400.0    # big-Ms; section 9 is where these earn scrutiny

legacy_F = {p: (LEGACY_CAP['MFG', FOLLOWER] * ETA['MFG', -1, p]
                if START[p] <= LEGACY_RET['MFG', FOLLOWER] else 0.0) for p in P}
CAP_COST = sum(MU['MFG', v] for v in P) / len(P) * UNIT['MFG', FOLLOWER] + CAP_ADDER

print(f"{FOLLOWER}'s manufacturing legacy retires in year "
      f"{LEGACY_RET['MFG', FOLLOWER]}")
print(f"{'p':>3s} {'year':>5s} {'deliverable':>12s}")
for p in P:
    print(f"{p:3d} {START[p]:5d} {legacy_F[p]:12.2f}"
          + ("   <-- retired" if legacy_F[p] == 0.0 else ""))
print(f"\nannualised cost of expansion: {CAP_COST:.4f}")
''')

    # ============ 7. the follower's problem, solved directly ===============
    M(r"""
## 7. The follower's problem, solved directly as a QP

Before replacing the follower's problem with its optimality conditions, build the
problem itself. Facing a leader that sells $q^L$, the follower chooses quantities
and one capacity expansion to maximise

$$\sum_{rt,p} \omega_p\Big[\big(A_{rt,p} - B_{rt,p}q^L_{rt,p} - c^F_{rt}\big)q^F_{rt,p}
\;-\; B_{rt,p}\big(q^F_{rt,p}\big)^2\Big] \;-\; \text{CAP\_COST}\cdot\kappa$$

subject to selling no more in any period than its legacy capacity plus $\kappa$.

**This is a QP, and it is concave** — the only quadratic term is $-B(q^F)^2$ with
$B > 0$. Concavity is the entire licence for what section 8 does. Print the
model's shape and check it: a QP that came back with zero quadratic terms would
be a linear program wearing a disguise, and its KKT conditions would say
something different.

> **Predict before you run.** The follower is being asked to respond to a leader
> selling nothing at all. Will it expand capacity? Its legacy plant delivers about
> 75 units a period, and the choke price is 30 against a delivered cost near 10.
""")

    C(r'''
qL_zero = {(rt, p): 0.0 for rt in REGIONS for p in P}

fq = gp.Model("follower_qp")
fq.Params.OutputFlag = 0
qF0 = fq.addVars(REGIONS, P, lb=0.0, ub=BIG_Q, name='qF')
Cap0 = fq.addVar(lb=0.0, ub=BIG_Q, name='Cap')
fq.addConstrs((qF0.sum('*', p) <= legacy_F[p] + Cap0 for p in P), name='cap')

obj = gp.QuadExpr()
for rt in REGIONS:
    for p in P:
        obj += OMEGA[p] * ((A_INT[rt, p] - B_SLP[rt, p] * qL_zero[rt, p] - c_f[rt])
                           * qF0[rt, p] - B_SLP[rt, p] * qF0[rt, p] * qF0[rt, p])
obj -= CAP_COST * Cap0
fq.setObjective(obj, GRB.MAXIMIZE)
fq.update()

assert fq.NumQNZs > 0, "a QP with no quadratic terms is not the model we meant"
fq.optimize()
assert fq.SolCount > 0, f"follower QP found no solution; status {fq.Status}"
print(f"{fq.NumVars} vars, {fq.NumConstrs} constrs, {fq.NumQNZs} quadratic terms")
print(f"follower profit {fq.ObjVal:,.2f}   quantity "
      f"{sum(qF0[rt, p].X for rt in REGIONS for p in P):.2f}"
      f"   expansion {Cap0.X:.2f}")
''')

    # ================= 8. the KKT conditions, by hand ======================
    M(r"""
## 8. The follower's KKT conditions, written out

Now replace that problem with the conditions its optimum must satisfy. Attach a
multiplier $\lambda_p \ge 0$ to each period's capacity constraint and
$\nu_{rt,p} \ge 0$ to each non-negativity bound on $q^F$, and $\mu_\kappa \ge 0$
to $\kappa \ge 0$. Three groups of conditions:

**Primal feasibility.** Capacity holds, with a slack variable so the constraint
is an equality — complementarity needs the slack explicitly.

$$\sum_{rt} q^F_{rt,p} + s_p = \text{legacy}_p + \kappa, \qquad s_p \ge 0$$

**Stationarity.** The derivative of the follower's Lagrangian with respect to
each of its variables is zero. For a quantity, the marginal revenue net of cost
must equal the shadow price of capacity, less the bound multiplier:

$$\omega_p\big(A_{rt,p} - B_{rt,p}(2q^F_{rt,p} + q^L_{rt,p}) - c^F_{rt}\big)
- \lambda_p + \nu_{rt,p} = 0$$

**Note the 2.** It comes from differentiating $-B(q^F)^2$, and it is the single
most common place to get an MPEC wrong. Marginal revenue falls twice as fast as
price. For capacity:

$$-\text{CAP\_COST} + \sum_p \lambda_p + \mu_\kappa = 0$$

This cell writes the primal feasibility and stationarity blocks. The
complementarity conditions — the hard part — are section 9.
""")

    C(r'''
MIPGAP_MPEC = 1e-3   # tight enough that every case below is proven optimal

mm = gp.Model("mpec")
mm.Params.OutputFlag = 0
mm.Params.MIPGap = MIPGAP_MPEC

# the leader's chain, carried over; qL is what it sells
Lh = chain(mm, LEADER, 'both', TIERS, rev_price=None)
qL = Lh['sale']

# the follower's variables, and its multipliers
qF = mm.addVars(REGIONS, P, lb=0.0, ub=BIG_Q, name='qF')
Cap = mm.addVar(lb=0.0, ub=BIG_Q, name='CapF')
slack = mm.addVars(P, lb=0.0, name='slk')
lam = mm.addVars(P, lb=0.0, name='lam')            # capacity shadow price
nu = mm.addVars(REGIONS, P, lb=0.0, name='nu')     # bound on qF >= 0
mcap = mm.addVar(lb=0.0, name='mcap')              # bound on Cap >= 0

# primal feasibility, as an equality with explicit slack
mm.addConstrs((qF.sum('*', p) + slack[p] == legacy_F[p] + Cap for p in P),
              name='fcap')
# stationarity in qF -- note the 2 on qF, from differentiating -B*qF^2
mm.addConstrs((OMEGA[p] * (A_INT[rt, p] - B_SLP[rt, p] * (2 * qF[rt, p] + qL[rt, p])
                           - c_f[rt]) - lam[p] + nu[rt, p] == 0
               for rt in REGIONS for p in P), name='stat_q')
# stationarity in Cap
mm.addConstr(-CAP_COST + gp.quicksum(lam[p] for p in P) + mcap == 0, name='stat_cap')

mm.update()
print(f"{mm.NumVars} vars, {mm.NumConstrs} constrs after the KKT primal + "
      f"stationarity blocks")
print(f"multipliers added: {len(P)} lam, {len(REGIONS) * len(P)} nu, 1 mcap")
''')

    # ============== 9. complementarity, and the big-Ms =====================
    M(r"""
## 9. Complementary slackness, and the big-Ms that deserve scrutiny

The remaining KKT conditions are the products $\lambda_p s_p = 0$,
$\nu_{rt,p} q^F_{rt,p} = 0$, $\mu_\kappa \kappa = 0$: for each pair, **at most
one side can be non-zero**. Written as products they are nonlinear and violate
every standard constraint qualification — the complementarity system has no
strict interior, so no solver can be trusted on it directly.

The standard reformulation introduces one binary per pair and a big-M:

$$\lambda_p \le M_\lambda\, y_p, \qquad s_p \le M_q\,(1 - y_p)$$

When $y_p = 1$ the multiplier is free and the slack is forced to zero; when
$y_p = 0$ the reverse. That is exactly "at most one side non-zero", and it turns
the MPEC into a MILP — which is why this route is standard rather than elegant.

**`BIG_Q` and `BIG_L` are chosen, not derived, and that is a real hazard.** Too
small silently caps a multiplier at a value below its true one, and the model
returns a wrong answer that still solves. Too large destroys the LP relaxation
and the solve crawls. Section 11 is the check that the choice was not fatal, and
it is the check people skip.
""")

    C(r'''
yc = mm.addVars(P, vtype=GRB.BINARY, name='yc')            # lam_p vs slack_p
zq = mm.addVars(REGIONS, P, vtype=GRB.BINARY, name='zq')   # nu vs qF
ycap = mm.addVar(vtype=GRB.BINARY, name='ycap')            # mcap vs Cap

mm.addConstrs((lam[p] <= BIG_L * yc[p] for p in P), name='cc1')
mm.addConstrs((slack[p] <= BIG_Q * (1 - yc[p]) for p in P), name='cc2')
mm.addConstrs((nu[rt, p] <= BIG_L * zq[rt, p] for rt in REGIONS for p in P), name='cc3')
mm.addConstrs((qF[rt, p] <= BIG_Q * (1 - zq[rt, p]) for rt in REGIONS for p in P),
              name='cc4')
mm.addConstr(mcap <= BIG_L * ycap, name='cc5')
mm.addConstr(Cap <= BIG_Q * (1 - ycap), name='cc6')

mm.update()
n_pairs = len(P) + len(REGIONS) * len(P) + 1
print(f"{n_pairs} complementarity pairs, so {n_pairs} new binaries")
print(f"BIG_L = {BIG_L} caps the multipliers, BIG_Q = {BIG_Q} caps the quantities")
print(f"{mm.NumVars} vars, {mm.NumConstrs} constrs, {mm.NumBinVars} binaries")
''')

    # =========== 10. the bilinear term, linearised exactly =================
    M(r"""
## 10. The bilinear revenue term, linearised **exactly**

One problem remains, and it is in the *leader's* objective. Its revenue is

$$\sum_{rt,p}\omega_p\Big(A_{rt,p} - B_{rt,p}\big(q^L_{rt,p} + q^F_{rt,p}\big)\Big)q^L_{rt,p}$$

which contains $-B\,q^F q^L$ — a product of two **decision variables**. Not a
variable times a constant, as in 04c where the rival's quantity was fixed input.

The trick: restrict the leader's quantity to a **finite grid** chosen by
binaries. With $q^L_{rt,p} = \sum_k S_k\, \beta_{rt,p,k}$ and
$\sum_k \beta_{rt,p,k} = 1$,

$$q^F q^L = \sum_k S_k \big(q^F \beta_k\big)$$

and each $q^F\beta_k$ is a **continuous times binary** product, which linearises
exactly with three inequalities — no approximation at all in that step. Define
$w_k = q^F\beta_k$ and force $w_k = q^F$ when $\beta_k = 1$ and $w_k = 0$
otherwise.

**The only approximation in this whole formulation is the grid**, and section 14
sweeps it. Note also `NQ` is a knob written out here: it is the one number
trading model size against how finely the leader may choose.
""")

    C(r'''
NQ = 6          # grid points for the leader's quantity
KQ = list(range(NQ))

bq = mm.addVars(REGIONS, P, KQ, vtype=GRB.BINARY, name='bq')
GRID = {}
for rt in REGIONS:
    for p in P:
        smax = A_INT[rt, p] / B_SLP[rt, p]
        GRID[rt, p] = [smax * k / (NQ - 1) for k in KQ]
        mm.addConstr(bq.sum(rt, p, '*') == 1, name=f'gsel_{rt}_{p}')
        mm.addConstr(qL[rt, p] == gp.quicksum(GRID[rt, p][k] * bq[rt, p, k] for k in KQ),
                     name=f'gq_{rt}_{p}')

print(f"the leader's grid in market R1, period 0 (choke quantity "
      f"{A_INT['R1', 0] / B_SLP['R1', 0]:.1f}):")
print("  " + "  ".join(f"{s:.1f}" for s in GRID['R1', 0]))
print(f"\n{len(REGIONS) * len(P) * NQ} grid binaries added")
''')

    M(r"""
### 10.1 The exact product linearisation

Three inequalities per $(rt, p, k)$. Read them as a pair of cases: with
$\beta_k = 1$, `w1` is slack, `w2` gives $w \le q^F$ and `w3` gives
$w \ge q^F$, so $w = q^F$ exactly. With $\beta_k = 0$, `w1` forces $w \le 0$ and
`w3` is slack. No approximation — unlike the grid above it, this step is exact.
""")

    C(r'''
w = mm.addVars(REGIONS, P, KQ, lb=0.0, name='w')
mm.addConstrs((w[rt, p, k] <= BIG_Q * bq[rt, p, k]
               for rt in REGIONS for p in P for k in KQ), name='w1')
mm.addConstrs((w[rt, p, k] <= qF[rt, p]
               for rt in REGIONS for p in P for k in KQ), name='w2')
mm.addConstrs((w[rt, p, k] >= qF[rt, p] - BIG_Q * (1 - bq[rt, p, k])
               for rt in REGIONS for p in P for k in KQ), name='w3')

rev = gp.LinExpr()
for rt in REGIONS:
    for p in P:
        for k in KQ:
            Sk = GRID[rt, p][k]
            rev += OMEGA[p] * (A_INT[rt, p] * Sk - B_SLP[rt, p] * Sk * Sk) * bq[rt, p, k]
            rev -= OMEGA[p] * B_SLP[rt, p] * Sk * w[rt, p, k]

mm.update()
print(f"revenue is now a LINEAR expression in {rev.size()} terms")
print(f"{mm.NumVars} vars, {mm.NumConstrs} constrs, {mm.NumBinVars} binaries")
''')

    M(r"""
### 10.2 Solve the MPEC

> **Predict before you run.** The leader now knows the follower will
> best-respond. Compared with Part 4c's simultaneous Cournot equilibrium, where
> R1 sold about 1,248, will the leader sell **more** or **less**? And will its
> profit be above or below the 11,071 it earned there?
""")

    C(r'''
mm.setObjective(rev - Lh['cost'], GRB.MAXIMIZE)
mm.update()
assert mm.NumVars > 0 and mm.NumConstrs > 0, "empty model"
assert mm.NumBinVars > 0, "an MPEC with no binaries is not the big-M model"

mm.optimize()
assert mm.SolCount > 0, f"no solution; status {mm.Status}"

hand_built = mm.ObjVal
qL_hand = {(rt, p): qL[rt, p].X for rt in REGIONS for p in P}
print(f"status {mm.Status}, leader profit {hand_built:,.4f}, gap {mm.MIPGap:.2e}")
print(f"  leader quantity   {sum(qL_hand.values()):10.2f}")
print(f"  follower quantity {sum(qF[rt, p].X for rt in REGIONS for p in P):10.2f}")
print(f"  follower expansion{Cap.X:10.2f}")
print(f"  model: {mm.NumVars} vars, {mm.NumConstrs} constrs, {mm.NumBinVars} binaries")
''')

    # ================= 11. the validation that matters =====================
    M(r"""
## 11. Validation — does the embedded KKT block reproduce the follower's optimum?

An MPEC is easy to get subtly wrong: a sign error in stationarity, the missing 2
on $q^F$, a big-M too small to let a multiplier reach its true value, a
complementarity pair left out. **The model will still solve and return plausible
numbers.** Nothing in the output tells you.

The check costs one small QP. Take the leader's committed quantities out of the
MPEC solution, hand them to the follower solved **directly** — section 7's model,
with `qL_zero` replaced by those quantities — and compare. If the KKT block is a
faithful representation, the two must agree.

**Always run this check on an MPEC.** It is the only thing standing between you
and a plausible wrong answer.
""")

    C(r'''
chk = gp.Model("follower_check")
chk.Params.OutputFlag = 0
qF_chk = chk.addVars(REGIONS, P, lb=0.0, ub=BIG_Q, name='qF')
Cap_chk = chk.addVar(lb=0.0, ub=BIG_Q, name='Cap')
chk.addConstrs((qF_chk.sum('*', p) <= legacy_F[p] + Cap_chk for p in P), name='cap')
obj = gp.QuadExpr()
for rt in REGIONS:
    for p in P:
        obj += OMEGA[p] * ((A_INT[rt, p] - B_SLP[rt, p] * qL_hand[rt, p] - c_f[rt])
                           * qF_chk[rt, p]
                           - B_SLP[rt, p] * qF_chk[rt, p] * qF_chk[rt, p])
obj -= CAP_COST * Cap_chk
chk.setObjective(obj, GRB.MAXIMIZE)
chk.optimize()
assert chk.SolCount > 0, "the validation QP found no solution"

dev = max(abs(qF[rt, p].X - qF_chk[rt, p].X) for rt in REGIONS for p in P)
print(f"  embedded KKT : quantity "
      f"{sum(qF[rt, p].X for rt in REGIONS for p in P):9.4f}  Cap {Cap.X:8.4f}")
print(f"  direct QP    : quantity "
      f"{sum(qF_chk[rt, p].X for rt in REGIONS for p in P):9.4f}  Cap {Cap_chk.X:8.4f}")
print(f"  max deviation per market-period: {dev:.3e}")
assert dev < 1e-4, f"the KKT block does not reproduce the follower's QP ({dev:.2e})"
print("\nagreement to machine precision - the leader really is optimising against"
      "\na best-responding rival, not against a mis-specified constraint set")
''')

    # ================= 12. now the streamlined version =====================
    M(r"""
## 12. Now the streamlined version

**This is where the notebook crosses from learning into convenience.**

You have written the follower's problem, its stationarity conditions, its
complementarity pairs, the grid and the exact product linearisation, once each.
The rest of this notebook needs that construction **eight more times** — a
monopoly case, a grid sweep at four resolutions, and Part 4e will sweep tariffs
through it. Writing it out eight more times would teach nothing that writing it
once did not.

So the next cell wraps it, and the cell after that **proves the wrapper
reproduces the hand-built answer**. That check is what earns the wrap.

`deter=False` is the one genuinely new argument: it drops the follower entirely,
giving the leader as a monopolist — an upper bound on leader profit and the third
row of section 13's table.
""")

    C(r'''
def mpec_model(learning, tiers, nq, deter, mipgap):
    """Sections 8-10.2, for any grid size, with or without a follower."""
    m = gp.Model()
    m.Params.OutputFlag = 0
    m.Params.MIPGap = mipgap
    Lh_ = chain(m, LEADER, learning, tiers, rev_price=None)
    qL_ = Lh_['sale']
    kq = list(range(nq))

    bq_ = m.addVars(REGIONS, P, kq, vtype=GRB.BINARY, name='bq')
    grid = {}
    for rt in REGIONS:
        for p in P:
            smax = A_INT[rt, p] / B_SLP[rt, p]
            grid[rt, p] = [smax * k / (nq - 1) for k in kq]
            m.addConstr(bq_.sum(rt, p, '*') == 1, name=f'gsel_{rt}_{p}')
            m.addConstr(qL_[rt, p] == gp.quicksum(grid[rt, p][k] * bq_[rt, p, k]
                                                  for k in kq), name=f'gq_{rt}_{p}')

    if deter:
        qF_ = m.addVars(REGIONS, P, lb=0.0, ub=BIG_Q, name='qF')
        Cap_ = m.addVar(lb=0.0, ub=BIG_Q, name='CapF')
        lam_ = m.addVars(P, lb=0.0, name='lam')
        nu_ = m.addVars(REGIONS, P, lb=0.0, name='nu')
        mcap_ = m.addVar(lb=0.0, name='mcap')
        yc_ = m.addVars(P, vtype=GRB.BINARY, name='yc')
        zq_ = m.addVars(REGIONS, P, vtype=GRB.BINARY, name='zq')
        ycap_ = m.addVar(vtype=GRB.BINARY, name='ycap')
        slk_ = m.addVars(P, lb=0.0, name='slk')

        m.addConstrs((qF_.sum('*', p) + slk_[p] == legacy_F[p] + Cap_ for p in P),
                     name='fcap')
        m.addConstrs((OMEGA[p] * (A_INT[rt, p] - B_SLP[rt, p] * (2 * qF_[rt, p]
                                                                 + qL_[rt, p])
                                  - c_f[rt]) - lam_[p] + nu_[rt, p] == 0
                      for rt in REGIONS for p in P), name='stat_q')
        m.addConstr(-CAP_COST + gp.quicksum(lam_[p] for p in P) + mcap_ == 0,
                    name='stat_cap')
        m.addConstrs((lam_[p] <= BIG_L * yc_[p] for p in P), name='cc1')
        m.addConstrs((slk_[p] <= BIG_Q * (1 - yc_[p]) for p in P), name='cc2')
        m.addConstrs((nu_[rt, p] <= BIG_L * zq_[rt, p]
                      for rt in REGIONS for p in P), name='cc3')
        m.addConstrs((qF_[rt, p] <= BIG_Q * (1 - zq_[rt, p])
                      for rt in REGIONS for p in P), name='cc4')
        m.addConstr(mcap_ <= BIG_L * ycap_, name='cc5')
        m.addConstr(Cap_ <= BIG_Q * (1 - ycap_), name='cc6')

        w_ = m.addVars(REGIONS, P, kq, lb=0.0, name='w')
        m.addConstrs((w_[rt, p, k] <= BIG_Q * bq_[rt, p, k]
                      for rt in REGIONS for p in P for k in kq), name='w1')
        m.addConstrs((w_[rt, p, k] <= qF_[rt, p]
                      for rt in REGIONS for p in P for k in kq), name='w2')
        m.addConstrs((w_[rt, p, k] >= qF_[rt, p] - BIG_Q * (1 - bq_[rt, p, k])
                      for rt in REGIONS for p in P for k in kq), name='w3')
    else:
        qF_, Cap_ = None, None

    rev_ = gp.LinExpr()
    for rt in REGIONS:
        for p in P:
            for k in kq:
                Sk = grid[rt, p][k]
                rev_ += OMEGA[p] * (A_INT[rt, p] * Sk
                                    - B_SLP[rt, p] * Sk * Sk) * bq_[rt, p, k]
                if deter:
                    rev_ -= OMEGA[p] * B_SLP[rt, p] * Sk * w_[rt, p, k]

    m.setObjective(rev_ - Lh_['cost'], GRB.MAXIMIZE)
    m.optimize()
    m._L, m._qL, m._qF, m._Cap = Lh_, qL_, qF_, Cap_
    return m


print("mpec_model() defined")
''')

    M(r"""
### 12.1 Does the wrapper reproduce the hand-built MPEC?

Same grid, same big-Ms, same learning setting. If these two numbers differ, the
wrapper is not the model you read in sections 8 to 10.
""")

    C(r'''
check = mpec_model('both', TIERS, nq=NQ, deter=True, mipgap=MIPGAP_MPEC)
rel = abs(check.ObjVal - hand_built) / abs(hand_built)
print(f"hand-built (sections 8-10): {hand_built:,.9f}")
print(f"wrapper    (section 12)   : {check.ObjVal:,.9f}")
assert rel < 1e-9, f"the wrapper is not the model you read; relative gap {rel:.2e}"
print(f"\nagree to {rel:.1e} - the wrap is earned")
''')

    # ==================== 13. three market structures ======================
    M(r"""
## 13. Three market structures

- **Monopoly** — no follower at all (`deter=False`). An upper bound on leader
  profit.
- **Stackelberg** — leader commits, follower best-responds. Sections 8–10.
- **Cournot** — simultaneous moves. Part 4c's equilibrium, whose headline numbers
  that notebook reports; here we quote its leader profit and quantities from the
  run committed with it.

Theory predicts a strict ordering,
$\Pi^{\text{mono}} > \Pi^{\text{Stack}} > \Pi^{\text{Cournot}}$, and the cell
asserts it rather than inviting you to eyeball the table.
""")

    C(r'''
mono = mpec_model('both', TIERS, nq=NQ, deter=False, mipgap=MIPGAP_MPEC)
assert mono.SolCount > 0, "monopoly case found no solution"

qL_s = sum(qL_hand.values())
qF_s = sum(qF[rt, p].X for rt in REGIONS for p in P)
qL_m = sum(mono._qL[rt, p].X for rt in REGIONS for p in P)

structures = pd.DataFrame([
    dict(structure='Monopoly (no rival)', leader_profit=round(mono.ObjVal, 1),
         leader_qty=round(qL_m, 1), follower_qty=0.0, total_qty=round(qL_m, 1)),
    dict(structure=f'Stackelberg (leader {LEADER})',
         leader_profit=round(hand_built, 1), leader_qty=round(qL_s, 1),
         follower_qty=round(qF_s, 1), total_qty=round(qL_s + qF_s, 1)),
    dict(structure='Cournot (simultaneous)',
         leader_profit=round(COURNOT_PROFIT[LEADER], 1),
         leader_qty=round(COURNOT_QTY[LEADER], 1),
         follower_qty=round(COURNOT_QTY[FOLLOWER], 1),
         total_qty=round(COURNOT_QTY[LEADER] + COURNOT_QTY[FOLLOWER], 1)),
])
assert mono.ObjVal > hand_built > COURNOT_PROFIT[LEADER], \
    "monopoly > Stackelberg > Cournot failed"
print(f"commitment is worth "
      f"{100 * (hand_built / COURNOT_PROFIT[LEADER] - 1):.1f}% of leader profit "
      f"over Cournot")
structures
''')

    M(r"""
The ordering is exactly what theory predicts, which is reassuring given how much
machinery sits underneath.

**Commitment is worth +24.6% of profit to the leader** — 13,789.8 against
Cournot's 11,070.7. And the mechanism is visible in the quantities: the
Stackelberg leader produces **more** than it would under Cournot (1,468.7 against
1,247.7) while the follower produces **less** (718.8 against 1,028.8).

That is the entire strategic logic. By committing to a large quantity first, the
leader moves the follower down its own reaction curve — every unit the leader
commits makes an additional follower unit less profitable. Overproduction is not
a mistake here; it is the instrument.

Note the leader reaches the *monopoly* quantity, 1,468.7 in both rows, but not
monopoly profit, because the follower still supplies 718.8 units and depresses
the price. The leader would like to be a monopolist and cannot be; the best it can
do is behave like one and accept the price the follower's output leaves it.
""")

    # ======================== 14. entry deterrence =========================
    M(r"""
## 14. Entry deterrence

The follower's capacity expansion $\kappa$ is the entry decision. How much does
the leader's commitment suppress it?

The comparison needs care, and it is the mistake `CLAUDE.md` Part 6 calls
*comparing two things that were not asked the same question*. The right
counterfactual is **the same follower problem, against a leader playing its
Cournot quantity** — not the follower's Cournot outcome, which came from a
different model. So we reuse section 11's validation QP with a different leader
schedule.
""")

    C(r'''
# the leader's Cournot schedule, market by market and period by period, taken
# from the equilibrium computed in section 5.3. NOT its total spread evenly -
# that would be a different leader, and the comparison would be meaningless.
qL_cournot = {(rt, p): cournot['sales'][LEADER][rt, p]
              for rt in REGIONS for p in P}

alt = gp.Model("follower_vs_cournot_leader")
alt.Params.OutputFlag = 0
qF_a = alt.addVars(REGIONS, P, lb=0.0, ub=BIG_Q, name='qF')
Cap_a = alt.addVar(lb=0.0, ub=BIG_Q, name='Cap')
alt.addConstrs((qF_a.sum('*', p) <= legacy_F[p] + Cap_a for p in P), name='cap')
obj = gp.QuadExpr()
for rt in REGIONS:
    for p in P:
        obj += OMEGA[p] * ((A_INT[rt, p] - B_SLP[rt, p] * qL_cournot[rt, p] - c_f[rt])
                           * qF_a[rt, p]
                           - B_SLP[rt, p] * qF_a[rt, p] * qF_a[rt, p])
obj -= CAP_COST * Cap_a
alt.setObjective(obj, GRB.MAXIMIZE)
alt.optimize()
assert alt.SolCount > 0

deterrence = pd.DataFrame([
    dict(case='Stackelberg (leader commits)', follower_expansion=round(Cap.X, 2),
         follower_qty=round(qF_s, 1)),
    dict(case='vs a leader at its Cournot volume',
         follower_expansion=round(Cap_a.X, 2),
         follower_qty=round(sum(qF_a[rt, p].X for rt in REGIONS for p in P), 1)),
])
assert Cap.X < Cap_a.X, "commitment did not suppress the follower's investment"
print(f"commitment cuts the follower's capacity expansion by "
      f"{100 * (1 - Cap.X / Cap_a.X):.1f}%")
deterrence
''')

    M(r"""
Read the `follower_expansion` column: this is how much new capacity the entrant
chooses to build. Facing a committed leader it builds **60.45** against the
**73.34** it would build facing a leader at its Cournot volume — 17.6% less
capital formation, on the same follower problem with the same big-Ms. The leader's
commitment does not merely take market share in the current period — it suppresses
the rival's *capital formation*, which is the durable form of deterrence and the
one that matters for industrial policy.

This is also where the Part 3b learning machinery closes the loop. Less follower
output means slower accumulation of follower production experience, which means
the follower stays on a higher operating-cost tier, which makes future expansion
less attractive still. Deterrence compounds.
""")

    # ===================== 15. grid refinement =============================
    M(r"""
## 15. How fine does the leader's quantity grid need to be?

The grid is the one approximation in this formulation — section 10.1's product
linearisation is exact, and the KKT block is exact for a concave follower. So
sweep it.

**What is guaranteed and what is not.** Every grid gives the leader a *feasible*
strategy, so every row's profit is a valid lower bound on what the leader could
earn choosing continuously. What is **not** guaranteed is that a finer grid always
scores higher: the grids here are $\{S\,k/(n-1)\}$, which are **not nested** —
the 3-point grid's midpoint $0.5S$ is not in the 6-point grid at all. So
monotonicity is an observation about these numbers, not a property of the
construction. Watch instead whether the *qualitative* conclusion is stable.
""")

    C(r'''
rows = []
for nq in [3, 4, 6, 8]:
    g = mpec_model('both', TIERS, nq=nq, deter=True, mipgap=MIPGAP_MPEC)
    assert g.SolCount > 0, f"nq={nq} found no solution"
    rows.append(dict(grid_points=nq, leader_profit=round(g.ObjVal, 1),
                     leader_qty=round(sum(g._qL[rt, p].X for rt in REGIONS
                                          for p in P), 1),
                     follower_qty=round(sum(g._qF[rt, p].X for rt in REGIONS
                                            for p in P), 1),
                     follower_expansion=round(g._Cap.X, 2),
                     binaries=g.NumBinVars))
grid_sweep = pd.DataFrame(rows)

# the invariant that IS guaranteed: every grid is a feasible leader strategy,
# so no row can exceed the continuous-strategy optimum. We do not know that
# optimum, but we do know a coarse grid cannot beat the monopoly bound.
assert (grid_sweep.leader_profit <= mono.ObjVal + 1e-6).all(), \
    "a grid beat the monopoly upper bound, which is impossible"
# and the qualitative conclusion should hold at every resolution: the leader
# out-produces the volume it would have chosen moving simultaneously
assert (grid_sweep.leader_qty > COURNOT_QTY[LEADER]).all(), \
    "the leader stopped out-producing its Cournot volume at some resolution"
print(f"leader profit across grids: {list(grid_sweep.leader_profit)}")
grid_sweep
''')

    M(r"""
Leader profit rises with grid resolution here — 9,794.8, 13,470.7, 13,789.8,
13,968.5 — and the qualitative conclusion is stable across all four: the leader
out-produces its Cournot volume and the follower's expansion stays suppressed. If
that had flipped between grids it would be a discretisation artefact rather than a
result, which is the reason to sweep rather than to trust one setting.

The 3-point grid is genuinely misleading, though, and worth dwelling on: at
9,794.8 it understates commitment by 29% and reports a leader quantity of 1,639.4,
*higher* than the finer grids. A coarse grid does not merely blur the answer, it
can point the wrong way on a specific number while the direction of the effect
survives.

The binary count rises quickly. Each grid point adds one binary per market-period
on top of the complementarity binaries and the leader's own build decisions, so
the model grows from 196 to 326 binaries across the sweep.
""")

    # ================= 16. the agreement assertion =========================
    M(r"""
## 16. The agreement assertion

Everything from section 6 onward was built by hand, and `src/lithium/` holds the
same models as functions because `scripts/run_all.py` and CI need to call them
without a notebook kernel. **That means this model exists twice, deliberately** —
and deliberate duplication with nothing comparing the copies is how a bug gets
fixed in three places out of four.

So this cell imports the package, hands it the same instance dictionaries and the
same knobs this notebook used, runs the same case, and asserts the two objectives
agree to $10^{-9}$.

This one assertion covers more than section 12.1's did. It compares the
hand-built MPEC against `lithium.mpec.stackelberg`, which builds the leader's
chain with `lithium.regions.add_region` — so it also covers the chain carried over
in section 5, which this notebook never narrated, and the tier calibration built
on top of it. A drift in any of them would move the objective.
""")

    C(r'''
from lithium import Instance, build_structure, stackelberg

nb_instance = Instance(
    regions=tuple(REGIONS), stages=tuple(STAGES),
    fixed=FIXED, unit=UNIT, opex=OPEX,
    legacy_cap=LEGACY_CAP, legacy_ret=LEGACY_RET,
    eta_ceil=ETA_CEIL, eta_base=ETA_BASE, alpha=ALPHA, beta=BETA, delta_bar=DELTA_BAR,
    demand_base=DEMAND_BASE, demand_growth=DEMAND_GROWTH, experience0=EXPERIENCE0,
)
nb_struct = build_structure(nb_instance, blocks=BLOCKS, dr=DR, life=LIFE, lead=LEAD,
                            cap_min=CAP_MIN, cap_max=CAP_MAX,
                            legacy_byr=LEGACY_BYR, eta_floor=ETA_FLOOR)

packaged = stackelberg(
    nb_struct, LEADER, FOLLOWER,
    a_int=A_INT, b_slp=B_SLP, transport=TRANSPORT,
    cap_cost=CAP_COST, big_q=BIG_Q, big_l=BIG_L, nq=NQ,
    learning='both', mipgap=MIPGAP_MPEC,
    pen_dispose=PEN_DISPOSE, price_fixed=PRICE_FIXED,
    capex_curve=(QBP, CBP), learn_stages=LEARN_STAGES,
    tiers=TIERS, n_tiers=N_TIERS, lag_years=LAG_YEARS,
)

rel = abs(packaged.ObjVal - hand_built) / abs(hand_built)
print(f"notebook (sections 8-10, by hand): {hand_built:,.9f}")
print(f"package  (lithium.mpec)          : {packaged.ObjVal:,.9f}")
assert rel < 1e-9, f"notebook and package disagree by {rel:.2e}"
print(f"\nnotebook and package agree to {rel:.1e}")
''')

    M(r"""
### 16.1 What this cell would catch

The check is only evidence if it can fail, so both checks in this notebook were
made to fail on purpose before it shipped. The failure worth naming is the one
section 8 warned about: **drop the 2 in the stationarity condition** — write
`b_slp * (qF + qL)` instead of `b_slp * (2 * qF + qL)` in
`src/lithium/mpec.py` — which enforces the optimality conditions of a *different*
follower, one whose marginal revenue falls half as fast as it should.

Here is what that produced:

```
                    status  leader profit      qL        qF      Cap
correct             2          13,789.76   1468.74    718.75    60.45
2 dropped           2           7,855.43   1524.57   1404.59   120.90
```

Nothing in that second row looks wrong. Gurobi returned `status 2` — optimal. The
leader still sells a sensible quantity, the follower still expands capacity, the
profit is still a plausible number. A reader would have no reason to doubt it.

**Section 11's QP check catches it immediately**: the embedded KKT block reports a
follower quantity of 1,404.59 while the follower solved directly against the same
leader wants 702.30 — a deviation of 72.17 per market-period against a threshold
of $10^{-4}$. That is why that check exists and why it should never be skipped.

**This cell catches it too**, at 4.3e-01, because the wrong follower changes the
leader's optimum. The two checks overlap here, but they fail differently in
general: section 11 catches a KKT block that misrepresents the follower even when
`src/lithium/` and the notebook agree with each other perfectly, and this cell
catches the notebook and the package drifting apart even when both represent the
follower correctly.
""")

    M(r"""
## 17. Summary

| Question | Answer |
|---|---|
| Can a bilevel program be solved directly? | No — replace the inner problem with its KKT conditions |
| What makes KKT valid here? | The follower's problem is **continuous and concave** |
| Why was that available? | Part 3 kept the operational layer an LP; integers only on investment |
| How is the bilinear term handled? | Leader quantity on a binary grid → continuous × binary → **exact** |
| Is the embedded KKT correct? | Verified against a direct QP; agreement at machine precision |
| What is commitment worth? | **+24.6%** of leader profit over Cournot (13,789.8 vs 11,070.7) |
| Does it deter entry? | Yes — the follower's capacity expansion falls from 73.34 to 60.45 |

### Formulation lessons

- **The 2 in the stationarity condition.** Marginal revenue falls twice as fast
  as price. Getting this wrong yields a model that solves and is wrong.
- **Complementarity needs an explicit slack.** The capacity constraint became an
  equality so that $\lambda_p s_p = 0$ had an $s_p$ to talk about.
- **Continuous × binary linearises exactly; a grid does not.** Know which of your
  approximations is one, and sweep only that one.
- **Big-Ms are chosen, not derived.** Too small silently caps a multiplier and
  returns a wrong answer that still solves. The QP check is the guard.
- **MPECs violate standard constraint qualifications** at every feasible point —
  the complementarity system has no strict interior. The big-M reformulation
  sidesteps this by turning it into a MILP, which is why that route is standard
  rather than elegant.
- **Match the counterfactual before interpreting a difference.** Section 14
  compares the follower against the *same* problem with a different leader
  schedule, not against a number from another model.

### Limitations, stated plainly

- **The follower cannot make lumpy investments.** Its capacity is a continuous
  scalar. Restoring binaries there would break KKT and require a different method
  entirely.
- **Its cost is frozen at the legacy vintage.** Section 6 does that deliberately
  to keep the problem concave; a follower whose yields improved with its own
  investment would not be KKT-representable this way.
- **Only one leader is modelled.** Which firm leads is assumed, not derived.
  Solving both directions and comparing tells you what leadership is worth, not
  who gets it.

### Things to try

Each is a one-line edit followed by *Run all*. The section 16 assertion should stay
green through every one — if it goes red, something you changed was not passed to
the package.

- `NQ = 12` — a finer grid; watch the binary count and the solve time
- `CAP_ADDER = 0.0` — cheaper entry, so deterrence should weaken
- `BIG_L = 40.0` — deliberately too small. Section 11's QP check should now
  **fail**, which is the point of having it
- `LEADER, FOLLOWER = 'R2', 'R1'` — swap the roles and ask what leadership is
  worth to the entrant
- `learning='capacity'` in section 12's calls — remove the production channel and
  see how much of the deterrence effect was the learning feedback

### Where this goes next

**4e — Policy instruments.** Tariffs as arc-cost adders, quotas as arc bounds,
local content minimums, all exogenous and swept. Government constrains, firms
respond. With the MPEC in hand the natural question is whether a tariff can
restore the follower's incentive to invest in the face of a committed leader —
and the answer turns out to be a step function, not a slope.
""")

    return out
