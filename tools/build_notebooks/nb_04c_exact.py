"""Build notebooks/04c_exact_miqp.ipynb.

**Subject:** what a piecewise-linear approximation costs, and where that cost
stops being predictable. Section 8 builds the exact MIQP by hand — it differs
from Part 4c's piecewise best response by about six lines — and sections 10 and
11 measure the error twice: once inside a single optimisation, where it is
signed, bounded and small, and once inside a *game*, where it is none of those.

**The licence.** Only section 12 needs one. `SMALL = True` shrinks the horizon to
3 periods, which puts the exact MIQP at 50 variables against the free `pip`
licence's ~150-variable quadratic cap, so the validation that is this notebook's
argument reproduces for everyone. Section 12's figures come from a recorded
full-scale run and its cells are guarded rather than left to fail.

A live WLS key used to sit in this notebook's cell 2 and went into the
repository's first commit. It reads the licence from the environment now; see
`tools/credscan.py` for the check that would have caught it.
"""
from . import common

NOTEBOOK = "04c_exact_miqp.ipynb"
TITLE = "Part 4c-exact - Cournot as a true MIQP"


def cells():
    out = []

    def M(text):
        out.append(("md", text.strip("\n")))

    def C(text):
        out.append(("code", text.strip("\n")))

    # ================================ front ================================
    M(r"""
# Part 4c-exact — Cournot as a true MIQP

### What the approximation cost, and where that cost stops being predictable

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/USERNAME/lithium-modelling/blob/main/notebooks/04c_exact_miqp.ipynb)

Part 4c piecewise-linearised the quadratic revenue to keep the model a MILP, and
argued the approximation was safe: revenue is concave, we maximise, so every
chord lies below the curve and the model can only **understate** profit.

That argument is correct and it is not the whole story. This notebook solves the
same game with revenue kept as a true quadratic and measures the difference —
first inside a single best response, then inside the equilibrium. **The two
answers have opposite signs**, and the second one is the reason this notebook
exists.

### How to read this notebook

Sections 5 to 7 are carried over from Parts 4a–4c and marked as such. Section 8
builds the exact MIQP **by hand**; it is short, because the difference from the
piecewise version is about six lines. Section 9 wraps it, section 10 validates
the approximation, section 11 is the finding, and section 14 asserts the notebook
and the `lithium` package agree to $10^{-9}$.
""")

    out += common.setup_section(notebook=NOTEBOOK)

    # ============================ 1. the licence ===========================
    M(r"""
## 1. Licence, and what fits without one

Only **section 12** needs a full licence. Everything above it, including the
validation in sections 10 and 11 that is this notebook's actual argument, runs on
the restricted `pip` licence.

That is not luck, it is what `SMALL` is for. The free licence caps **quadratic**
models at roughly **150 variables** — the linear cap of ~2,000 is far away and
never binds here. Measured:

| configuration | periods | variables | quadratic terms | fits free licence |
|---|---|---|---|---|
| `SMALL = True`, `learning='none'` | 3 | 50 | 6 | **yes** |
| `SMALL = True`, `learning='capacity'` | 3 | 83 | 6 | **yes** |
| `SMALL = False`, `learning='none'` | 13 | 398 | 26 | no |
| `SMALL = False`, `learning='capacity'` | 13 | 541 | 26 | no |

So `SMALL = True` is the shipped default.

**Never paste a licence key into a notebook.** A key committed to a repository is
exposed the moment the repository is shared, and deleting it in a later commit
does not remove it from history — the only fix is to rotate the key. This
notebook used to carry one, and it went into this repository's first commit. The
next cell reads one from the environment or, on Colab, from the secrets panel,
and falls back to the default licence when it finds nothing.
""")

    M(r"""
### 1.1 Getting a licence, if you want section 12

**Most readers need nothing here.** `pip install gurobipy` ships a restricted
licence, and everything through section 11 fits inside it. Skip to 1.2.

If you do want to run section 12, you need a **WLS** licence — and *which kind*
matters more than it looks.

| | what it is | works in Colab? |
|---|---|---|
| **Named-User Academic** | a `gurobi.lic` file | **No.** Node-locked to one machine, so it cannot travel |
| **WLS Academic** | three values checked over the network | **Yes.** This is the one you want |

Both are free for academics with a university email address, from the **Gurobi
User Portal** (`portal.gurobi.com`) — register, then request a licence from the
licences section. A WLS Academic licence gives you three values:

```
WLSACCESSID    a UUID
WLSSECRET      a UUID  <- this one is the secret; treat it like a password
LICENSEID      a number
```

**Putting them into Colab.** Click the **key icon** in the left sidebar to open
Secrets, add three secrets named exactly

```
GRB_WLSACCESSID     GRB_WLSSECRET     GRB_LICENSEID
```

and switch on notebook access for each. That is the whole setup.

Two things worth understanding rather than just following.

**A Colab secret binds to your Google account, not to the notebook.** So this
notebook can be shared, forked, or published and it still carries no key — every
reader supplies their own, and nobody can read anyone else's. That property is
the entire reason to do it this way rather than with a cell that asks you to
paste a value.

**`LICENSEID` is a number, and `userdata.get()` returns a string.** The next cell
casts it with `int()`. Without that cast Gurobi rejects the environment in a way
that does not obviously say why — a genuine time-waster, and the reason the cast
has a comment on it.

Running locally instead? Set the same three names as environment variables. The
next cell checks the environment first and Colab's secrets second, so the same
notebook works either way with no edit.
""")

    C(r'''
import os

# A licence from the environment, or from Colab secrets. Never a literal.
# Set GRB_WLSACCESSID / GRB_WLSSECRET / GRB_LICENSEID, or add those three names
# under Colab's key icon in the left sidebar.
KEYS = ('WLSACCESSID', 'WLSSECRET', 'LICENSEID')
found = {k: os.environ.get('GRB_' + k) for k in KEYS}
if not all(found.values()):
    try:
        from google.colab import userdata
        found = {k: userdata.get('GRB_' + k) for k in KEYS}
    except Exception:
        found = {}

if found and all(found.values()):
    ENV = gp.Env(params={'WLSACCESSID': found['WLSACCESSID'],
                         'WLSSECRET': found['WLSSECRET'],
                         # int(), not the raw value: Colab's userdata.get()
                         # returns strings, and a string LICENSEID fails quietly
                         'LICENSEID': int(found['LICENSEID'])})
else:
    ENV = None       # gp.Model(env=None) means "use the default licence"
HAVE_WLS = ENV is not None

print("WLS environment:", "ready" if HAVE_WLS else
      "not configured - using the default licence")
print("gp.Model(env=None) means 'use the default licence', so the same code path")
print("serves both. Nothing below section 12 needs a key.")
''')

    M(r"""
### 1.2 The size switch

`SMALL` shrinks the horizon from 13 periods to 3. Everything else is unchanged,
so the model is the same model — just small enough to solve as a quadratic on a
restricted licence.

**It has to be set before section 3**, because the horizon is what section 3
derives every set and coefficient from.
""")

    C(r'''
SMALL = True      # False -> the full 13-period horizon; needs a full licence

print(f"SMALL = {SMALL}  ->  "
      + ("3-period horizon; every model below fits the restricted licence"
         if SMALL else
         "13-period horizon; sections 8 and 12 need a full licence"))
if not SMALL and not HAVE_WLS:
    print("\n!! SMALL is False but no WLS licence was found. The quadratic models")
    print("!! below will fail on a restricted licence. Either set SMALL = True,")
    print("!! or set GRB_WLSACCESSID / GRB_WLSSECRET / GRB_LICENSEID and re-run.")
''')

    out += common.instance_section(agree=14)
    out += common.structure_section(
        agree=14, chain=5,
        blocks="[(2, 1), (1, 3)] if SMALL else [(6, 1), (4, 3), (2, 5), (1, 9)]",
        horizon_note=(
            "**`BLOCKS` follows `SMALL` here**, which is the one place this notebook "
            "differs\nstructurally from Part 4c. At `SMALL = True` the horizon is 3 "
            "periods over 5\nyears, small enough for the exact MIQP to fit a restricted "
            "licence; at `False` it\nis the full 13 periods over 37 years that every "
            "other Part 4 notebook uses. Nothing\nelse changes, so the model is the same "
            "model at either size."))
    out += common.capex_curve_section(chain=5, revenue=7)

    out += common.chain_section(tiers=6, tiered=8)
    out += common.tier_section()

    # ==================== 7. carried over: the piecewise mesh ==============
    M(r"""
## 7. Carried over from Part 4c: inverse demand and the piecewise mesh

Two things this notebook needs in order to have something to compare against.
Both are narrated in `04c_cournot.ipynb` sections 7.1 and 7.5; nothing here is
new, and section 8 is where this notebook starts.
""")

    C(r'''
# CARRIED OVER FROM 04c SECTIONS 7.1 AND 7.5 - narrated there, not re-taught here.

CHOKE, P_ANCHOR = 30.0, 13.0
NBP_REV = 7
TIERS = (TIER_Q, TIER_M)
MIPGAP_PLAN, MIPGAP_GAME, TOL = 0.005, 1e-3, 0.5

A_INT = {(rt, p): CHOKE for rt in REGIONS for p in P}
B_SLP = {(rt, p): (CHOKE - P_ANCHOR) / DEMAND[rt, p] for rt in REGIONS for p in P}


def chain(m, r, learning, tiers, rev_price):
    """Sections 5.1-5.6 of 04c, for any region, in any model."""
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
    if learning in ('capacity', 'both'):
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
    else:
        capex_ += gp.quicksum(MU[s, v] * UNIT[s, r] * c_[s, v]
                              for (s, v) in BUILD[r] if s in LEARN_STAGES)

    if learning in ('production', 'both') and tiers is not None:
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


def best_response_pwl(r, rival, learning, tiers, nbp_rev, mipgap, env=None):
    """04c's PIECEWISE best response - the thing being validated."""
    m = gp.Model(env=env) if env is not None else gp.Model()
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


print(f"carried over. horizon: {len(P)} periods, choke {CHOKE}, mesh {NBP_REV} points")
''')

    # ================= 8. the exact MIQP, by hand ==========================
    M(r"""
## 8. The exact MIQP, by hand

New material starts here, and there is not much of it — which is the first
point worth making. The difference from the piecewise version above is that
revenue is written **as what it is**:

$$\text{revenue}_{rt,p} \;=\; \big(A_{rt,p} - B_{rt,p}\bar{q}_{rt,p}\big)\,s_{rt,p}
\;-\; B_{rt,p}\,s_{rt,p}^2$$

No `mu` interpolation weights. No convexity constraint. No breakpoint mesh. A
`gp.QuadExpr` and the same cost expression.

**One constraint survives from the mesh**, and it is worth keeping: `choke` caps
sales at the quantity where price reaches zero. The model would never *want* a
negative price, but the bound tightens the relaxation and costs nothing.

**And `env=ENV` matters here.** This is the only quadratic model in the series. On
a restricted licence a plain `gp.Model()` refuses a quadratic objective above
about 150 variables, which is exactly why section 1's `SMALL` exists.

> **Predict before you run.** The piecewise mesh has 7 breakpoints on a curve.
> Will the exact solution's profit be **higher or lower** than the piecewise
> one — and can you say which before running it, from the shape of the curve
> alone?
""")

    C(r'''
FIRM = 'R1'
zero_rival = {(rt, p): 0.0 for rt in REGIONS for p in P}

mx = gp.Model(env=ENV) if ENV is not None else gp.Model()
mx.Params.OutputFlag = 0
mx.Params.MIPGap = MIPGAP_PLAN
h = chain(mx, FIRM, 'none', None, rev_price=None)
s = h['sale']

# the one constraint kept from the mesh: price cannot go negative
mx.addConstrs((s[rt, p] <= max(0.0, A_INT[rt, p] / B_SLP[rt, p]
                               - zero_rival.get((rt, p), 0.0))
               for rt in REGIONS for p in P), name='choke')

# revenue, written as what it is
revenue = gp.QuadExpr()
for rt in REGIONS:
    for p in P:
        q_bar = zero_rival.get((rt, p), 0.0)
        revenue += OMEGA[p] * ((A_INT[rt, p] - B_SLP[rt, p] * q_bar) * s[rt, p]
                               - B_SLP[rt, p] * s[rt, p] * s[rt, p])

mx.setObjective(revenue - h['cost'], GRB.MAXIMIZE)
mx.update()

assert mx.NumQNZs > 0, "a QP with no quadratic terms is not the model we meant"
print(f"{mx.NumVars} variables, {mx.NumConstrs} constraints, "
      f"{mx.NumQNZs} quadratic terms")
print(f"against the free licence's ~150-variable quadratic cap: "
      f"{'fits' if mx.NumVars <= 150 else 'DOES NOT FIT'}")

mx.optimize()
assert mx.SolCount > 0, f"no solution; status {mx.Status}"
hand_built = mx.ObjVal
print(f"\nexact MIQP profit {hand_built:12.4f}   "
      f"sales {sum(s[rt, p].X for rt in REGIONS for p in P):9.4f}")
''')

    # ===================== 9. now the streamlined version ==================
    M(r"""
## 9. Now the streamlined version

**This is where the notebook crosses from learning into convenience.**

You have written the exact revenue once. Section 10 needs it once more and
section 11 needs it inside a best-response loop — about twenty solves. Two cells:
the exact best response, and the iteration that calls it.

The iteration is 04c's, unchanged, including its **tolerance-based** convergence
test. That is still the right test here: the strategy is a continuous quantity
schedule, so exact matching would read MIP-gap wobble as a cycle.
""")

    C(r'''
def best_response_miqp(r, rival, learning, tiers, mipgap, env=None):
    """Section 8, for any firm against any rival schedule."""
    m = gp.Model(env=env) if env is not None else gp.Model()
    m.Params.OutputFlag = 0
    m.Params.MIPGap = mipgap
    h_ = chain(m, r, learning, tiers, rev_price=None)
    s_ = h_['sale']
    m.addConstrs((s_[rt, p] <= max(0.0, A_INT[rt, p] / B_SLP[rt, p]
                                   - rival.get((rt, p), 0.0))
                  for rt in REGIONS for p in P), name='choke')
    rev_ = gp.QuadExpr()
    for rt in REGIONS:
        for p in P:
            q_bar = rival.get((rt, p), 0.0)
            rev_ += OMEGA[p] * ((A_INT[rt, p] - B_SLP[rt, p] * q_bar) * s_[rt, p]
                                - B_SLP[rt, p] * s_[rt, p] * s_[rt, p])
    m.setObjective(rev_ - h_['cost'], GRB.MAXIMIZE)
    m.optimize()
    m._h, m._rev = h_, rev_
    return m


def iterate(kind, learning, tiers, nbp_rev, first, max_iter, tol, mipgap, env=None):
    """Iterated best response, with either formulation. Tolerance-based, as 04c."""
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
            b = (best_response_miqp(r, rival, learning, tiers, mipgap, env)
                 if kind == 'exact' else
                 best_response_pwl(r, rival, learning, tiers, nbp_rev, mipgap, env))
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


print("best_response_miqp() and iterate() defined")
''')

    M(r"""
### 9.1 Does the wrapper reproduce the hand-built MIQP?
""")

    C(r'''
check = best_response_miqp(FIRM, zero_rival, 'none', None, MIPGAP_PLAN, ENV)
rel = abs(check.ObjVal - hand_built) / abs(hand_built)
print(f"hand-built (section 8): {hand_built:,.9f}")
print(f"wrapper    (section 9): {check.ObjVal:,.9f}")
assert rel < 1e-9, f"the wrapper is not the model you read; relative gap {rel:.2e}"
print(f"\nagree to {rel:.1e} - the wrap is earned")
''')

    # ================ 10. validating the approximation =====================
    M(r"""
## 10. Validating the approximation

Run both formulations on the **same** instance and compare across mesh
densities.

Theory says the piecewise version should **understate** profit: revenue is
concave, chords lie below the curve, and we are maximising. So the approximation
is *conservative* — never optimistic. The cell asserts that rather than inviting
you to read the sign off a column.
""")

    C(r'''
MESHES = [3, 5, 7, 11, 21, 41]

rows = []
for n in MESHES:
    pw = best_response_pwl(FIRM, zero_rival, 'none', None, n, MIPGAP_PLAN, ENV)
    assert pw.SolCount > 0, f"mesh {n} found no solution"
    rows.append(dict(breakpoints=n, pwl_profit=round(pw.ObjVal, 3),
                     error=round(pw.ObjVal - hand_built, 3),
                     error_pct=round(100 * (pw.ObjVal - hand_built) / hand_built, 4),
                     sales=round(sum(pw._h['sale'][rt, p].X
                                     for rt in REGIONS for p in P), 3)))
mesh = pd.DataFrame(rows)

# the theory, as code: a chord below a concave curve can only understate a maximum
assert (mesh.error <= 1e-6).all(), \
    "a piecewise mesh OVERSTATED profit, which the concavity argument forbids"
print(f"every error is negative, as concavity requires: "
      f"{mesh.error_pct.min():.2f}% to {mesh.error_pct.max():.4f}%")
mesh
''')

    M(r"""
**Every error is negative**, confirming the theory: the piecewise revenue never
overstates. The approximation is a valid lower bound on achievable profit, and
the assertion above would fail if it ever were not.

The magnitude falls sharply with mesh density — about −42.9% at 3 breakpoints,
−0.25% at 7, and −0.08% at 21 and beyond. But **the convergence is not
monotone**: 7 breakpoints (−0.25%) beats 11 (−0.96%). What matters is not the
number of breakpoints but whether one happens to land near the optimal quantity.
That is the same lesson as the SOS2 re-meshing in Part 3 — **placement beats
density**.

Seven breakpoints, the Part 4c default, costs about a quarter of a percent on a
single best response. That is defensible for the qualitative conclusions drawn
there.
""")

    # ================ 11. the error inside a game ==========================
    M(r"""
## 11. But the error behaves differently inside a game

Everything above measured the error in **one** optimisation. Now measure it in an
**equilibrium**: run the whole best-response loop under each formulation and
compare where they land.

> **Predict before you run.** The single-solve error is negative and under a
> quarter of a percent at this mesh. What do you expect the equilibrium error to
> be — the same sign, the same magnitude, or something else?
""")

    C(r'''
MAX_ITER = 12

exact = iterate('exact', 'none', None, NBP_REV, first='R1', max_iter=MAX_ITER,
                tol=TOL, mipgap=MIPGAP_GAME, env=ENV)
pwl = iterate('pwl', 'none', None, NBP_REV, first='R1', max_iter=MAX_ITER,
              tol=TOL, mipgap=MIPGAP_GAME, env=ENV)
le = {g['firm']: g for g in exact['log'][-len(REGIONS):]}
lp = {g['firm']: g for g in pwl['log'][-len(REGIONS):]}

game = pd.DataFrame([
    dict(method='exact MIQP', status=exact['status'],
         **{f'profit_{r}': round(le[r]['profit'], 3) for r in REGIONS},
         **{f'sales_{r}': round(le[r]['sales'], 3) for r in REGIONS}),
    dict(method='piecewise linear', status=pwl['status'],
         **{f'profit_{r}': round(lp[r]['profit'], 3) for r in REGIONS},
         **{f'sales_{r}': round(lp[r]['sales'], 3) for r in REGIONS}),
])
for r in REGIONS:
    err = 100 * (lp[r]['profit'] / le[r]['profit'] - 1)
    print(f"{r}: piecewise reports {err:+6.2f}% against exact "
          f"({lp[r]['profit']:,.1f} vs {le[r]['profit']:,.1f})")

# the finding: in a game the sign FLIPS relative to the single-solve error
assert lp['R1']['profit'] > le['R1']['profit'], \
    "the in-game piecewise error did not come out positive; section 11's claim fails"
game
''')

    M(r"""
**This is the finding worth taking away.** In a single optimisation the piecewise
error is signed, bounded and small. In an **equilibrium** it is none of those.

Both methods converge, but to *different* equilibria, and the piecewise version
reports profits **above** the exact ones — the opposite sign to the single-solve
error, and by a much larger margin for R2 (+12.15%) than R1 (+1.96%).

The mechanism: each firm's approximated best response is slightly off, which
perturbs the *rival's* problem, which perturbs the response to that, and so on
around the loop. **The fixed point of a sequence of slightly-wrong maps is not
close to the fixed point of the correct maps** in any way the single-solve error
bound controls. Approximation error propagates through the equilibrium
computation rather than staying local.

The practical consequence is worth stating as a rule. A discretisation accuracy
that is perfectly adequate for one optimisation can be inadequate for a game
built out of the same optimisation. **If you must approximate inside a
best-response loop, validate at the equilibrium level, not the subproblem
level** — and if the qualitative conclusions flip between meshes, they are not
conclusions.
""")

    # ================ 12. the full-scale game ==============================
    M(r"""
## 12. The full-scale game, exactly

With `SMALL = False` and a licence configured, the same loop runs on the complete
13-period model with both learning channels and no revenue approximation at all —
541 variables with 26 quadratic terms, against the restricted licence's ~150 cap.

**On the default settings the next cell prints an explanation instead of
running.** The figures quoted below come from a run with `SMALL = False` on an
academic licence (2026-09-03, 26.9 s).
""")

    C(r'''
if SMALL:
    print("Section 12 needs the full 13-period model, which does not fit a "
          "restricted\nlicence as a MIQP: 541 variables against a ~150 cap.\n")
    print("To run it you need a full licence. Set SMALL = False, and supply one "
          "as\nthree secrets - in Colab, the key icon in the left sidebar:\n")
    print("    GRB_WLSACCESSID   GRB_WLSSECRET   GRB_LICENSEID\n")
    print("Each person supplies their own; the values bind to your account, not "
          "to\nthis notebook, so a shared notebook never carries a key. The "
          "figures in\nthe prose below come from exactly such a run.")
else:
    rows = []
    for first in REGIONS:
        r2 = iterate('exact', 'both', TIERS, NBP_REV, first=first, max_iter=16,
                     tol=TOL, mipgap=MIPGAP_GAME, env=ENV)
        last = {g['firm']: g for g in r2['log'][-len(REGIONS):]}
        rows.append(dict(first_mover=first, status=r2['status'],
                         iterations=r2['iters'],
                         **{f'profit_{r}': round(last[r]['profit'], 1)
                            for r in REGIONS},
                         **{f'sales_{r}': round(last[r]['sales'], 1)
                            for r in REGIONS}))
    display(pd.DataFrame(rows))
''')

    M(r"""
### What the full-scale exact run said

| | piecewise (Part 4c) | exact MIQP | |
|---|---|---|---|
| total quantity | 2,276.5 | 2,264.5 | −0.5% |
| average price | 15.81 | 15.84 | +0.03 |
| joint profit | 17,791.5 | 18,461.1 | +3.8% |
| output uplift from production learning | +15.2% | **+13.4%** | both positive |
| disposal | 0 | **0** | unchanged |
| convergence | CONVERGED | **CYCLE** | ← see below |

**Every qualitative conclusion survives.** Output rises with the production
channel, price falls, the incumbent gains more than the entrant (R1 1,082.0 →
1,262.6 against R2's 914.9 → 1,001.9), and disposal stays at exactly zero. A
conclusion that survives both formulations is a conclusion about the economics.
One that does not was an artefact of the mesh.

**But the exact game does not settle.** Both move orders end in `CYCLE` — at 5
iterations from R1 and 6 from R2 — where the piecewise version converged cleanly.
The cycling profiles are close (R1 earns 11,419.6 and 11,419.9 across the two
orders, within 0.003%), so this is not a large oscillation; it is the quantity
profile refusing to sit still to within the `tol = 0.5` test.

That points the same way as section 11. The piecewise mesh **discretises the
strategy space**: quantities can only land on convex combinations of seven
breakpoints, which damps the best-response map and helps it reach a fixed point.
Remove the mesh and the map is free to keep moving. **The smoothness that made
Part 4c converge was partly an artefact of the approximation**, not a property of
the game.

So the honest reading of Part 4c's "pure-strategy equilibrium, from both move
orders" is narrower than it looks: an equilibrium *of the approximated game*. The
economics is robust; the convergence is not.
""")

    # ================= 13. the agreement assertion =========================
    M(r"""
## 13. The agreement assertion

Section 8 was built by hand, and `src/lithium/` holds the same model as a
function. **The same model exists twice, deliberately** — and deliberate
duplication with nothing comparing the copies is how a bug gets fixed in three
places out of four.
""")

    C(r'''
from lithium import Instance, best_response_miqp as pkg_miqp, build_structure

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

packaged = pkg_miqp(
    FIRM, zero_rival, nb_struct,
    a_int=A_INT, b_slp=B_SLP, learning='none', mipgap=MIPGAP_PLAN, env=ENV,
    transport=TRANSPORT, pen_dispose=PEN_DISPOSE, price_fixed=PRICE_FIXED,
    capex_curve=(QBP, CBP), learn_stages=LEARN_STAGES,
    n_tiers=N_TIERS, lag_years=LAG_YEARS,
)

rel = abs(packaged.ObjVal - hand_built) / abs(hand_built)
print(f"notebook (section 8, by hand): {hand_built:,.9f}")
print(f"package  (lithium.games)     : {packaged.ObjVal:,.9f}")
assert rel < 1e-9, f"notebook and package disagree by {rel:.2e}"
print(f"\nnotebook and package agree to {rel:.1e}")
print(f"(both at {len(P)} periods, because BLOCKS follows SMALL - so this check")
print(" runs at whatever scale you set, and needs no licence at the default.)")
''')

    M(r"""
## 14. Summary

| Question | Answer |
|---|---|
| Does the piecewise mesh understate profit? | **Yes, always** — concave revenue, maximised, so chords lie below |
| How much, at 7 breakpoints? | About **−0.25%** on a single best response |
| Does the error shrink monotonically with density? | **No** — 7 beats 11. Placement beats density |
| Does the same bound hold in a game? | **No.** The sign flips: piecewise reports **+1.96%** for R1 and **+12.15%** for R2 |
| Do Part 4c's conclusions survive exact solution? | The **economics** does. The **convergence** does not — the exact game cycles |
| Does any of this need a licence? | Only section 12. At `SMALL = True` the MIQP is 50 variables |

### Formulation lessons

- **An error bound proved for one optimisation says nothing about a fixed point
  built from it.** Validate at the equilibrium level.
- **Placement beats density.** A mesh point near the optimum is worth more than
  ten spread evenly.
- **Approximation can manufacture convergence.** Discretising the strategy space
  damps the best-response map; the exact game cycles where the approximated one
  settles.
- **Check the model is the kind you meant.** `assert mx.NumQNZs > 0` in section 8
  catches a "QP" that is secretly linear — which would validate nothing.

### Things to try

- `MESHES = [6, 7, 8, 9, 10]` — zoom in on the non-monotonicity and see how much
  of it is luck
- `SMALL = False` with a licence — reproduce section 12 rather than reading it
- `NBP_REV = 3` in section 11 — a coarse mesh inside the loop; does the *sign* of
  the in-game error survive, or does the equilibrium move somewhere else entirely?
- `learning='both'` in section 10 — validate the approximation with the tier
  binaries present, which is what Part 4c actually runs
""")

    return out
