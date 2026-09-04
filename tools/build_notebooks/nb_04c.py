"""Build notebooks/04c_cournot.ipynb.

Section 5 builds the chain by hand and section 7 the Cournot best response;
section 8 wraps them once the reader has written every component, and section 12
asserts the wrapper and the package agree. The shared setup sections come from
`common.py` — see that module for why.
"""
from . import common

NOTEBOOK = "04c_cournot.ipynb"
TITLE = "Part 4c - Cournot competition with endogenous price"


def cells():
    out = []

    def M(text):
        out.append(("md", text.strip("\n")))

    def C(text):
        out.append(("code", text.strip("\n")))

    # ---- front matter ----------------------------------------------------
    M(r"""
# Part 4c — Cournot competition with endogenous price

### Where flooding the market becomes rational

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/sear-labs/advopt-lithiumsc/blob/main/notebooks/04c_cournot.ipynb)

Part 4b had a **fixed** price, so rivalry was a pure race for a capped market and the only channel
between firms was residual demand. That produced two artefacts: a large first-mover advantage, and
an equilibrium that served less demand than a planner would.

Here price responds to quantity:

$$p_{rt,p} \;=\; A_{rt,p} - B_{rt,p} \sum_{r} \text{sale}_{r,rt,p}$$

That single change alters the economics qualitatively. Extra output now **depresses the rival's
margin as well as your own** — and because operating-cost learning is driven by cumulative
production, extra output also **advances your own learning tier**. Those two effects together are
the documented predatory dynamic: flood the market, starve the entrant, and come out cheaper.

### What is new

| | 4b (fixed price) | **4c (Cournot)** |
|---|---|---|
| Price | exogenous constant | $A - BQ$, endogenous |
| Firm objective | $\bar{p}\cdot\text{sales} - \text{cost}$ | quadratic revenue − cost |
| Rivalry channel | residual demand cap | **the price itself** |
| Quantity cap | rival's leftovers | choke price only |
| Benchmark | cooperative planner | **collusion** (joint profit max) |

### How to read this notebook

Sections 1–7 build the model **by hand**, one idea per cell, so you see every constraint before you
see any abstraction. Section 8 wraps what you built into three functions, because the analysis needs
them a dozen times — and checks the wrapper reproduces the hand-built answer before using it.
Section 12 imports the `lithium` package, runs the same case, and asserts the two agree to $10^{-9}$.
That last cell is what makes it safe for the same model to exist twice.
""")

    out += common.setup_section(notebook=NOTEBOOK)

    M(r"""
## 1. The formulation problem, and a neat way around it

Firm $r$'s revenue in market $rt$, taking the rival's quantity $\bar{q}$ as given:

$$\big(A - B(s + \bar{q})\big)\, s \;=\; \underbrace{(A - B\bar{q})}_{a_{\text{eff}}}\, s \;-\; B s^2$$

This is **quadratic**, so each best response is naturally a MIQP. Two reasons not to do that:
Gurobi's size-limited `pip` licence does not accept quadratic objectives at this model size, and a
MIQP is heavier than it needs to be.

**Piecewise-linearise the revenue instead.** And here the curvature works in our favour:

| | Minimising | Maximising |
|---|---|---|
| **Convex** | safe | chord exploited |
| **Concave** | **chord exploited** (Part 3's learning curve) | **safe** ← we are here |

Revenue is **concave** and we **maximise**, so every chord lies *below* the true curve. A free
convex combination of breakpoints has no incentive to mix non-adjacent points — mixing would report
*less* revenue. So this needs **no SOS2 and adds no binaries**, unlike Part 3's cumulative cost
curve. It is the exact mirror image, and worth pausing on: whether you need SOS2 depends on
curvature *and* optimisation direction together, never on one alone.

You will see both cases in this notebook — the capacity-learning curve in section 5 needs SOS2, and
the revenue curve in section 7 does not.
""")

    out += common.instance_section(agree=12)
    out += common.structure_section(agree=12, chain=5)
    out += common.capex_curve_section(chain=5, revenue=7)


    out += common.chain_section(tiers=6, tiered=7)
    out += common.tier_section()

    # ---- 7. the best response, built by hand ----
    M(r"""
## 7. The Cournot best response, built by hand

Now the model this notebook is actually about. One firm, R1, choosing its whole investment and sales
plan to maximise **its own profit**, taking the rival's sales schedule as fixed.

Two things are new relative to section 5, and everything else is the same chain you already built:

1. **Tiered operating cost** — the block calibrated in section 6, which needs binaries.
2. **Endogenous price** — revenue is no longer `PRICE_FIXED * sales` but a piecewise-linearised
   quadratic.

### 7.1 Inverse demand

`CHOKE` is the price at zero quantity. `B` is calibrated so that when quantity equals the Part 4b
demand reference, price equals `P_ANCHOR` — the level at which the fixed-price game was interesting.
That makes 4b and 4c comparable at a reference point rather than at an arbitrary one.
""")

    C(r"""
CHOKE = 30.0       # price at zero quantity
P_ANCHOR = 13.0    # price when quantity equals the Part 4b demand reference

A_INT = {(rt, p): CHOKE for rt in REGIONS for p in P}
B_SLP = {(rt, p): (CHOKE - P_ANCHOR) / DEMAND[rt, p] for rt in REGIONS for p in P}

print(f"{'market':>7s} {'p':>3s} {'A (choke)':>10s} {'B (slope)':>10s} {'p at D':>8s}"
      f" {'max qty':>9s}")
for rt in REGIONS:
    for p in [0, 6, len(P) - 1]:
        q = DEMAND[rt, p]
        print(f"{rt:>7s} {p:3d} {A_INT[rt, p]:10.1f} {B_SLP[rt, p]:10.5f}"
              f" {A_INT[rt, p] - B_SLP[rt, p] * q:8.2f} {A_INT[rt, p] / B_SLP[rt, p]:9.1f}")
""")

    M(r"""
### 7.2 The rival's schedule, and a fresh model

The best response is defined *against something*. We start where the iteration in section 9 starts:
a rival selling nothing. That makes this first solve a monopoly problem, and its answer is the
natural upper bound on what R1 can earn.

The next four cells rebuild the chain from section 5 — same variables, same constraints, now for R1
alone. Read them as a recap; the genuinely new blocks start at 7.4.
""")

    C(r"""
FIRM = 'R1'
rival_sales = {(rt, p): 0.0 for rt in REGIONS for p in P}

mb = gp.Model("best_response")
mb.Params.OutputFlag = 0
mb.Params.MIPGap = 1e-3

bb = mb.addVars(BUILD[FIRM], vtype=GRB.BINARY, name=f'b_{FIRM}')
cc_ = mb.addVars(BUILD[FIRM], lb=0.0, ub=CAP_MAX, name=f'c_{FIRM}')
xx = mb.addVars(ACTIVE[FIRM], lb=0.0, name=f'x_{FIRM}')
ff_mp = mb.addVars(P, lb=0.0, name=f'fmp_{FIRM}')
ff_pf = mb.addVars(P, lb=0.0, name=f'fpf_{FIRM}')
ss = mb.addVars(REGIONS, P, lb=0.0, name=f'sale_{FIRM}')
dd = mb.addVars(P, lb=0.0, name=f'disp_{FIRM}')

mb.update()
print(f"{mb.NumVars} variables for one firm ({mb.NumBinVars} binary)")
print(f"rival sells {sum(rival_sales.values()):.1f} in every market and period")
""")

    M(r"""
### 7.3 The same capacity, chain-balance, cumulative-production and capex blocks
""")

    C(r"""
mb.addConstrs((cc_[s, v] <= CAP_MAX * bb[s, v] for (s, v) in BUILD[FIRM]), name='su')
mb.addConstrs((cc_[s, v] >= CAP_MIN * bb[s, v] for (s, v) in BUILD[FIRM]), name='sl')
mb.addConstrs((xx[s, v, p] <= (LEGACY_CAP[s, FIRM] if v == -1 else cc_[s, v])
               for (s, v, p) in ACTIVE[FIRM]), name='cap')

mb.addConstrs((gp.quicksum(ETA['MINE', v, p] * xx['MINE', v, p]
                           for v in VIN[FIRM, 'MINE', p]) == ff_mp[p] for p in P), name='mine')
mb.addConstrs((ff_mp[p] == gp.quicksum(xx['PROC', v, p] for v in VIN[FIRM, 'PROC', p])
               for p in P), name='pin')
mb.addConstrs((gp.quicksum(ETA['PROC', v, p] * xx['PROC', v, p]
                           for v in VIN[FIRM, 'PROC', p]) == ff_pf[p] for p in P), name='pout')
mb.addConstrs((ff_pf[p] == gp.quicksum(xx['MFG', v, p] for v in VIN[FIRM, 'MFG', p])
               for p in P), name='min')
mb.addConstrs((gp.quicksum(ETA['MFG', v, p] * xx['MFG', v, p] for v in VIN[FIRM, 'MFG', p])
               == ss.sum('*', p) + dd[p] for p in P), name='mout')

mb.update()
print(f"{mb.NumConstrs} constraints after capacity + chain balance")
""")

    M(r"""
The cumulative-production and capex blocks, likewise unchanged from 5.4 and 5.5. The SOS2 sets come
along with them, because the capacity-learning curve is still concave and still being subtracted from
a profit we are maximising — which makes it a *cost* term facing the same chord-exploitation risk as
in section 5.
""")

    C(r"""
ccum = mb.addVars(P, lb=0.0, ub=3 * CAP_MAX * HORIZON + EXPERIENCE0[FIRM], name='cum')
mb.addConstrs((ccum[p] == EXPERIENCE0[FIRM] +
               gp.quicksum(LEN[q] * xx['MFG', v, q] for q in P if q <= p
                           for v in VIN[FIRM, 'MFG', q]) for p in P), name='cp')

bcapex = (gp.quicksum(MU[s, v] * FIXED[s, FIRM] * bb[s, v] for (s, v) in BUILD[FIRM])
          + gp.quicksum(MU[s, v] * UNIT[s, FIRM] * cc_[s, v]
                        for (s, v) in BUILD[FIRM] if s not in LEARN_STAGES))

bQ = mb.addVars(P, lb=Q_START, ub=Q_START + Q_ADD, name='Q')
bC = mb.addVars(P, lb=0.0, name='C')
blam = mb.addVars(P, K, lb=0.0, ub=1.0, name='lam')
mb.addConstrs((blam.sum(p, '*') == 1 for p in P), name='sc')
mb.addConstrs((bQ[p] == gp.quicksum(QBP[k] * blam[p, k] for k in K) for p in P), name='sQ')
mb.addConstrs((bC[p] == gp.quicksum(CBP[k] * blam[p, k] for k in K) for p in P), name='sC')
mb.addConstrs((bQ[p] == Q_START + gp.quicksum(cc_[s, v] for (s, v) in BUILD[FIRM]
                                              if s in LEARN_STAGES and v <= p)
               for p in P), name='cc')
for p in P:
    mb.addSOS(GRB.SOS_TYPE2, [blam[p, k] for k in K])

_rate = sum(UNIT[s, FIRM] for s in LEARN_STAGES) / len(LEARN_STAGES)
bcapex += gp.quicksum(MU['PROC', p] * _rate * (bC[p] - (bC[p - 1] if p > 0 else 0.0)) for p in P)

mb.update()
print(f"{mb.NumVars} variables, {mb.NumConstrs} constraints, {mb.NumSOS} SOS2 sets")
""")

    M(r"""
### 7.4 New: the operating-cost tier block

This is where the calibration from section 6 enters the model, and it is the block that costs the
most binaries.

`z[p, j]` says period `p` is on tier `j` — exactly one tier per period. The two big-M constraints
force `z` to agree with the lagged cumulative production: if you are on tier `j` then lagged
production must be at least threshold `j-1` and at most threshold `j`. When `z[p, j] = 0` the big-M
`BIGQ` makes both constraints vacuous, which is the whole point of the construction.

`ts[s, p, j]` then splits each stage's throughput across tiers, with `ts` forced to zero on the tiers
that are switched off — so the operating cost picks up the multiplier belonging to the *selected*
tier. The product `TIER_M[r][j] * ts[s, p, j]` is linear because `TIER_M` is a number, not a
variable; that is the trick that keeps a step-function cost inside a MILP.
""")

    C(r"""
J = list(range(N_TIERS))
BIGQ = 3 * CAP_MAX * HORIZON + EXPERIENCE0[FIRM]
LAGP = {p: YEAR_TO_P[max(1, START[p] - LAG_YEARS)] for p in P}

zz = mb.addVars(P, J, vtype=GRB.BINARY, name='z')
mb.addConstrs((zz.sum(p, '*') == 1 for p in P), name='ot')
mb.addConstrs((ccum[LAGP[p]] >= TIER_Q[FIRM][j - 1] - BIGQ * (1 - zz[p, j])
               for p in P for j in J if j > 0), name='tf')
mb.addConstrs((ccum[LAGP[p]] <= TIER_Q[FIRM][j] + BIGQ * (1 - zz[p, j])
               for p in P for j in J if j < N_TIERS - 1), name='tc')

mb.update()
print(f"lag map (period -> period whose cum production decides its tier):")
print("  " + "  ".join(f"{p}->{LAGP[p]}" for p in P))
print(f"\nBIGQ = {BIGQ:,.0f}   {mb.NumBinVars} binaries now ({len(P) * N_TIERS} of them tier flags)")
""")

    M(r"""
With the tier chosen, split each stage's throughput across tiers and price it. `tl` is the constraint
that does the work: throughput can only land on a tier whose flag is on, so the cost picks up that
tier's multiplier and no other. The remaining three cost terms — transport, disposal, and the capex
built above — are unchanged from section 5.6.
""")

    C(r"""
tts = mb.addVars(STAGES, P, J, lb=0.0, name='ts')
mb.addConstrs((tts.sum(s, p, '*') == gp.quicksum(xx[s, v, p] for v in VIN[FIRM, s, p])
               for s in STAGES for p in P), name='tss')
mb.addConstrs((tts[s, p, j] <= 3 * CAP_MAX * zz[p, j]
               for s in STAGES for p in P for j in J), name='tl')

bopex = gp.quicksum(OMEGA[p] * OPEX[s, FIRM] * TIER_M[FIRM][j] * tts[s, p, j]
                    for s in STAGES for p in P for j in J)
btrans = gp.quicksum(OMEGA[p] * TRANSPORT[FIRM, rt] * ss[rt, p] for rt in REGIONS for p in P)
bdcost = gp.quicksum(OMEGA[p] * PEN_DISPOSE * dd[p] for p in P)
bcost = bcapex + bopex + btrans + bdcost

mb.update()
print(f"{mb.NumVars} variables, {mb.NumConstrs} constraints after the tier block")
print(f"cost expression: {bcost.size()} linear terms")
""")

    M(r"""
### 7.5 New: piecewise-linear revenue, and the SOS2 we do *not* need

For one market and period, with the rival selling $\bar{q}$, revenue in own quantity $s$ is

$$\big(A - B(s + \bar{q})\big)\,s \;=\; \underbrace{(A - B\bar{q})}_{a_{\text{eff}}}\,s \;-\; B s^2$$

so we tabulate that on `NBP_REV` points between 0 and the quantity at which price hits zero, and let
`mu` interpolate. `rev_t[rt, p]` is the revenue the model is allowed to claim.

**Compare this with section 5.5.** Same concave shape, same convex-combination machinery — and here
there is no `addSOS` call, because we are *maximising*. A chord between two non-adjacent breakpoints
lies below the true curve, so claiming it would *reduce* the objective. The solver will not do it,
and the constraint would be dead weight. Curvature alone does not tell you whether you need SOS2;
curvature and direction together do.

`NBP_REV` is a knob worth changing: set it to 3 and re-run, and the quantities go visibly blocky
because the mesh is too coarse to represent the curve.
""")

    C(r"""
NBP_REV = 7                        # breakpoints on the revenue curve
KR = list(range(NBP_REV))

mmu = mb.addVars(REGIONS, P, KR, lb=0.0, ub=1.0, name='mu')
rev_t = mb.addVars(REGIONS, P, lb=-GRB.INFINITY, name='revt')

for rt in REGIONS:
    for p in P:
        q_bar = rival_sales.get((rt, p), 0.0)
        a_eff = A_INT[rt, p] - B_SLP[rt, p] * q_bar
        smax = max(1e-6, A_INT[rt, p] / B_SLP[rt, p] - q_bar)
        S = [smax * k / (NBP_REV - 1) for k in KR]
        R = [a_eff * v - B_SLP[rt, p] * v * v for v in S]
        mb.addConstr(mmu.sum(rt, p, '*') == 1, name=f'rcvx_{rt}_{p}')
        mb.addConstr(ss[rt, p] == gp.quicksum(S[k] * mmu[rt, p, k] for k in KR),
                     name=f'rS_{rt}_{p}')
        mb.addConstr(rev_t[rt, p] == gp.quicksum(R[k] * mmu[rt, p, k] for k in KR),
                     name=f'rR_{rt}_{p}')

brevenue = gp.quicksum(OMEGA[p] * rev_t[rt, p] for rt in REGIONS for p in P)

mb.update()
print(f"revenue mesh for market R1, period 0 (rival at {rival_sales['R1', 0]:.0f}):")
_S = [A_INT['R1', 0] / B_SLP['R1', 0] * k / (NBP_REV - 1) for k in KR]
for k in KR:
    print(f"  k={k}  qty {_S[k]:8.2f}   revenue {A_INT['R1', 0] * _S[k] - B_SLP['R1', 0] * _S[k] ** 2:10.2f}")
print(f"\n{mb.NumSOS} SOS2 sets in total - still only the {len(P)} from the capex curve")
""")

    M(r"""
### 7.6 Solve it

> **Predict before you run.** R1 faces no rival at all here, so it is a monopolist in both markets.
> Will it sell *more* or *less* than the planner's quantity from section 5? And do you expect any
> disposal — is there ever a reason to manufacture something and destroy it?
""")

    C(r"""
mb.setObjective(brevenue - bcost, GRB.MAXIMIZE)
mb.update()
assert mb.NumVars > 0 and mb.NumConstrs > 0, "empty model"

mb.optimize()
assert mb.SolCount > 0, f"no solution; status {mb.Status}"

hand_built = mb.ObjVal
print(f"status {mb.Status}, profit {hand_built:,.4f}, MIP gap {mb.MIPGap:.2e}")
print(f"  revenue  {brevenue.getValue():12,.2f}")
print(f"  cost     {bcost.getValue():12,.2f}")
print(f"  sales    {sum(ss[rt, p].X for rt in REGIONS for p in P):12,.2f}")
print(f"  disposal {sum(dd[p].X for p in P):12,.2f}")
print(f"  tier per period: {[max(J, key=lambda j: zz[p, j].X) for p in P]}")
""")

    # ---- 8. the streamlined version ----
    M(r"""
## 8. Now the streamlined version

**This is where the notebook crosses from learning into convenience.**

Everything above was written out once so you could read it. From here the notebook needs that same
construction **about forty times** — two firms, up to sixteen rounds of best response, two move
orders, two learning settings, plus a collusive benchmark. Writing it out forty times would teach
nothing that writing it out once did not.

So cells 8.1 and 8.2 wrap what you just built. You have written every component by hand, so
nothing in them should be a surprise; the only additions are the two branches that let the same code
serve the flat-opex planner of section 5 and the tiered best response of section 7.

**And then 8.3 proves the wrapper reproduces the hand-built answer.** That check is what earns
the wrap. Without it, the wrapper is just a second copy of the model with nothing comparing them.

One trap worth naming, because this notebook series shipped it once: every argument below is
**explicit**, and none of them has a module-level global as its default. `def f(..., n=NBP_REV)`
would freeze `NBP_REV` at the moment the cell ran, so a later `NBP_REV = 3` would silently change
nothing. Pass the value, don't default it.
""")

    C(r'''
def chain(m, r, learning, tiers, rev_price):
    """Attach region r's chain to model m. Exactly sections 5.1-5.6 and 7.3-7.4.

    learning : 'capacity' (flat opex) or 'both' (tiered opex, needs `tiers`)
    tiers    : (TIER_Q, TIER_M) or None
    rev_price: fixed price for the 4b-style revenue term, or None to omit it
    """
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


print("8.1  chain() defined -", chain.__doc__.splitlines()[0])
''')

    M(r"""
### 8.2 The best response, wrapped

`chain()` above plus the revenue mesh of section 7.5, for any firm against any rival schedule. Note
`nbp_rev` and `mipgap` are parameters, not globals read from the enclosing scope.
""")

    C(r'''
def best_response(r, rival, learning, tiers, nbp_rev, mipgap):
    """Sections 7.2-7.6, for any firm against any rival schedule."""
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
            m.addConstr(mu_.sum(rt, p, '*') == 1, name=f'rcvx_{rt}_{p}')
            m.addConstr(s_[rt, p] == gp.quicksum(Sg[k] * mu_[rt, p, k] for k in kr),
                        name=f'rS_{rt}_{p}')
            m.addConstr(revt_[rt, p] == gp.quicksum(Rg[k] * mu_[rt, p, k] for k in kr),
                        name=f'rR_{rt}_{p}')
    rev_ = gp.quicksum(OMEGA[p] * revt_[rt, p] for rt in REGIONS for p in P)
    m.setObjective(rev_ - h['cost'], GRB.MAXIMIZE)
    m.optimize()
    m._h, m._rev = h, rev_
    return m


print("8.2  best_response() defined")
''')

    M(r"""
### 8.3 Does the wrapper reproduce the hand-built answer?

Same firm, same rival schedule, same knobs. If these two numbers differ, the wrapper is not what you
read in section 7 — and everything below section 8 would be measuring the wrong model.
""")

    C(r"""
check = best_response(FIRM, rival_sales, learning='both', tiers=(TIER_Q, TIER_M),
                      nbp_rev=NBP_REV, mipgap=1e-3)
rel = abs(check.ObjVal - hand_built) / abs(hand_built)
print(f"hand-built (section 7): {hand_built:,.9f}")
print(f"wrapper    (section 8): {check.ObjVal:,.9f}")
assert rel < 1e-9, f"the wrapper is not the model you read; relative gap {rel:.2e}"
print(f"\nagree to {rel:.1e} - the wrap is earned")
""")

    # ---- 9. iterated best response ----
    M(r"""
## 9. Convergence testing with continuous strategies

Part 4b tested convergence on the **build plan** alone. That is wrong here, and the failure mode is
instructive.

In Cournot the strategy *is* the quantity schedule. Testing plans alone declared convergence while
quantities were still moving by thousands of cost units. Fixing that by hashing the exact quantity
vector then produced a spurious **5-cycle** — profits oscillating in the fourth significant figure
with identical build plans. That was **MIP-gap noise**: each best response is a MILP solved to a
finite tolerance, so the returned quantities wobble slightly even at a genuine fixed point.

The correct test is **tolerance-based**, on the full strategy:

- **Converged** — the quantity profile moved less than `TOL` since the previous round
- **Cycle** — the profile matches one from $k \ge 2$ rounds back, within `TOL`
- **Cap** — report non-convergence

Two lessons that generalise: never hash floating-point strategies for equilibrium detection, and a
loose MIP gap inside a best-response loop can masquerade as strategic cycling.
""")

    C(r'''
TOL = 0.5            # quantity units; a profile moving less than this has settled
MAX_ITER = 16
MIPGAP_GAME = 1e-3   # tighter than the planner's, because the loop amplifies gap noise


def iterate(learning, tiers, nbp_rev, first, max_iter, tol, mipgap):
    """Iterated best response. Convergence is tested with a TOLERANCE, never by
    exact state matching - see the markdown above for why."""
    def dist(a, bb):
        return max(abs(a[r][k] - bb[r][k]) for r in REGIONS for k in a[r])

    sales = {r: {(rt, p): 0.0 for rt in REGIONS for p in P} for r in REGIONS}
    plans, hist, log = {}, [], []
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
            mm = best_response(r, rival, learning, tiers, nbp_rev, mipgap)
            if mm.SolCount == 0:
                return dict(status='INFEASIBLE', iters=it, log=log)
            sales[r] = {(rt, p): mm._h['sale'][rt, p].X for rt in REGIONS for p in P}
            plans[r] = tuple(sorted((s_, v) for (s_, v) in mm._h['b']
                                    if mm._h['b'][s_, v].X > 0.5))
            log.append(dict(iter=it, firm=r, profit=mm.ObjVal,
                            revenue=mm._rev.getValue(), cost=mm._h['cost'].getValue(),
                            builds=len(plans[r]), sales=sum(sales[r].values()),
                            disposal=sum(mm._h['disp'][p].X for p in P)))
        cur = {r: dict(sales[r]) for r in REGIONS}
        if it > 0 and dist(cur, prev) < tol:
            return dict(status='CONVERGED', cycle_len=1, iters=it + 1, log=log,
                        plans=plans, sales=sales, drift=dist(cur, prev))
        for k, past in enumerate(hist):                  # genuine k-cycle, k >= 2
            if dist(cur, past) < tol:
                return dict(status='CYCLE', cycle_len=len(hist) - k, iters=it + 1,
                            log=log, plans=plans, sales=sales)
        hist.append(cur)
    return dict(status='MAX_ITER', iters=max_iter, log=log, plans=plans, sales=sales)


print(f"iterate() defined; TOL = {TOL}, MAX_ITER = {MAX_ITER}, MIPGAP_GAME = {MIPGAP_GAME}")
''')

    M(r"""
### 9.1 Does moving first still pay?

> **Predict before you run.** In Part 4b, going first was worth about 29% of profit to R1 (7,612.7
> against 5,895.7 — that notebook's own numbers, re-executed). Under a fixed price the leader could
> commit capacity and seize a capped market. Now the price moves. Write down whether you expect the
> first-mover advantage to grow, shrink, or stay roughly the same.
""")

    C(r"""
rows = []
runs = {}
for first in REGIONS:
    res_ = iterate(learning='both', tiers=(TIER_Q, TIER_M), nbp_rev=NBP_REV,
                   first=first, max_iter=MAX_ITER, tol=TOL, mipgap=MIPGAP_GAME)
    runs[first] = res_
    last = {g['firm']: g for g in res_['log'][-len(REGIONS):]}
    rows.append(dict(first_mover=first, status=res_['status'], iterations=res_['iters'],
                     **{f'profit_{r}': round(last[r]['profit'], 1) for r in REGIONS},
                     **{f'sales_{r}': round(last[r]['sales'], 1) for r in REGIONS}))

order_table = pd.DataFrame(rows)
assert (order_table.status == 'CONVERGED').all(), "a move order failed to converge"
adv_R1 = 100 * (order_table.profit_R1[0] / order_table.profit_R1[1] - 1)
adv_R2 = 100 * (order_table.profit_R2[1] / order_table.profit_R2[0] - 1)
print(f"first-mover advantage: R1 {adv_R1:.1f}%   R2 {adv_R2:.1f}%")
order_table
""")

    M(r"""
**Endogenous price largely dissolves the first-mover advantage.** Moving first is worth 4.4% to R1
and 1.9% to R2, against roughly 29% for R1 under the fixed price of Part 4b.

The mechanism: under a fixed price the leader could commit capacity and *seize* a capped market,
leaving only leftovers. With a responsive price there is no cap to seize — if the leader floods, the
price falls and its own margin falls with it. Price adjustment substitutes for the quantity
rationing that gave commitment its bite.

This is worth taking seriously as a modelling lesson rather than a curiosity: **the large first-mover
advantage in 4b was substantially an artefact of the fixed price**, not a robust finding. Whenever a
result depends on a rationing rule, check what happens when a price does the rationing instead.

(Commitment is not worthless — Part 4d gives the leader a genuine *first-mover technology* rather
than merely a turn order, and there it is worth +24.6%. What dies here is the advantage that came
from move order alone.)
""")

    # ---- 10. results ----
    M(r"""
## 10. Cournot against collusion

The natural benchmark now is not a cost-minimising planner but **joint profit maximisation** — the
two firms colluding as a single monopolist. Textbook prediction: collusion restricts quantity, raises
price, and earns higher joint profit.

Two more small wrappers, both assembled from parts you have already built: the collusive model is
just both chains in one model with a *shared* revenue curve on total quantity, and `market_table`
does no optimisation at all — it reads prices off the inverse demand curve.
""")

    C(r'''
def joint_max(learning, tiers, nbp_rev, mipgap):
    """Collusive benchmark: one decision maker maximising the SUM of both profits."""
    m = gp.Model()
    m.Params.OutputFlag = 0
    m.Params.MIPGap = mipgap
    H = {r: chain(m, r, learning, tiers, rev_price=None) for r in REGIONS}
    kr = list(range(nbp_rev))
    mu_ = m.addVars(REGIONS, P, kr, lb=0.0, ub=1.0, name='mu')
    revt_ = m.addVars(REGIONS, P, lb=-GRB.INFINITY, name='revt')
    for rt in REGIONS:
        for p in P:
            smax = A_INT[rt, p] / B_SLP[rt, p]
            Sg = [smax * k / (nbp_rev - 1) for k in kr]
            Rg = [A_INT[rt, p] * v - B_SLP[rt, p] * v * v for v in Sg]
            m.addConstr(mu_.sum(rt, p, '*') == 1)
            m.addConstr(gp.quicksum(H[r]['sale'][rt, p] for r in REGIONS)
                        == gp.quicksum(Sg[k] * mu_[rt, p, k] for k in kr))
            m.addConstr(revt_[rt, p] == gp.quicksum(Rg[k] * mu_[rt, p, k] for k in kr))
    rev_ = gp.quicksum(OMEGA[p] * revt_[rt, p] for rt in REGIONS for p in P)
    m.setObjective(rev_ - gp.quicksum(H[r]['cost'] for r in REGIONS), GRB.MAXIMIZE)
    m.optimize()
    m._H, m._rev = H, rev_
    return m


def market_table(sales):
    """Price, quantity, consumer surplus and R1's share, market by market and period."""
    out = []
    for rt in REGIONS:
        for p in P:
            q = sum(sales[r][rt, p] for r in REGIONS)
            out.append(dict(market=rt, period=p, year=START[p], quantity=q,
                            price=A_INT[rt, p] - B_SLP[rt, p] * q,
                            consumer_surplus=0.5 * B_SLP[rt, p] * q * q,
                            share_R1=(sales['R1'][rt, p] / q if q > 1e-6 else None)))
    return out


print("joint_max() and market_table() defined")
''')

    M(r"""
> **Predict before you run.** Collusion should restrict output and raise price. By how much? And
> which side of the ledger moves further — the firms' profit, or consumers' surplus?
""")

    C(r"""
res = runs['R1']
jm = joint_max(learning='both', tiers=(TIER_Q, TIER_M), nbp_rev=NBP_REV, mipgap=0.005)
assert jm.SolCount > 0, "collusive benchmark found no solution"

mo = pd.DataFrame(market_table(res['sales']))
jsales = {r: {(rt, p): jm._H[r]['sale'][rt, p].X for rt in REGIONS for p in P} for r in REGIONS}
mj = pd.DataFrame(market_table(jsales))
cournot_joint = sum(g['profit'] for g in res['log'][-len(REGIONS):])

regimes = pd.DataFrame([
    dict(regime='Cournot duopoly', total_quantity=round(mo.quantity.sum(), 1),
         avg_price=round(mo.price.mean(), 2), joint_profit=round(cournot_joint, 1),
         consumer_surplus=round(mo.consumer_surplus.sum(), 1)),
    dict(regime='Collusion (joint max)', total_quantity=round(mj.quantity.sum(), 1),
         avg_price=round(mj.price.mean(), 2), joint_profit=round(jm.ObjVal, 1),
         consumer_surplus=round(mj.consumer_surplus.sum(), 1)),
])

# the theory, asserted rather than described
assert mj.quantity.sum() < mo.quantity.sum(), "collusion did not restrict output"
assert mj.price.mean() > mo.price.mean(), "collusion did not raise price"
assert jm.ObjVal > cournot_joint, "collusion did not raise joint profit"
assert mj.consumer_surplus.sum() < mo.consumer_surplus.sum(), "consumers did not lose"
assert (mo.quantity >= -1e-6).all(), "negative quantity"
print(f"output restriction {100 * (1 - mj.quantity.sum() / mo.quantity.sum()):.1f}%   "
      f"joint profit +{100 * (jm.ObjVal / cournot_joint - 1):.1f}%")
print("who produces under collusion:")
for r in REGIONS:
    print(f"  {r}: sales {sum(jsales[r][rt, p] for rt in REGIONS for p in P):9.3f}"
          f"   plants built {sum(1 for k in BUILD[r] if jm._H[r]['b'][k].X > 0.5)}")
regimes
""")

    M(r"""
Exactly the expected pattern, which is a useful validation that the price layer is wired correctly:

- **Collusion restricts output** — 1,571.7 against 2,276.5, about 31% less
- **Price rises** — 20.21 against 15.81
- **Joint profit rises** — 22,870.0 against 17,791.5, so competition costs the firms 22% of the
  profit they could have had
- **Consumers lose** heavily under collusion — surplus falls from 16,124.7 to 7,685.8

The Cournot equilibrium sits between monopoly and the competitive ideal, as it should. Note that the
four assertions above are the theory itself, written as code: if a later edit broke the price layer,
they would fail rather than quietly producing a plausible table.

**And look at who produces.** Under collusion R2 sells nothing at all and builds no plants; R1 serves
both markets alone. That is why the collusive profit here, 22,869.98, is *exactly* the number section
7.6 printed for R1 facing no rival — the cartel's optimum is R1 as a monopolist, with R2 paid to stay
out. It falls out of the instance rather than being assumed: R1's accumulated experience puts it on a
cheaper operating tier, and once the cartel is choosing a single total quantity there is no reason to
serve any of it from the higher-cost chain. The 2.4 cross-region transport premium is not enough to
overturn that, though it is what keeps R2 alive in the *competitive* equilibrium, where R2 is not
choosing to maximise the pair's profit.
""")

    C(r"""
fig, ax = plt.subplots(1, 2, figsize=(12, 4.3))
for mk, col in zip(REGIONS, ['#2471a3', '#d68910']):
    d = mo[mo.market == mk]
    ax[0].plot(d.year, d.price, 'o-', lw=2.4, color=col, label=f'{mk} Cournot')
    dj = mj[mj.market == mk]
    ax[0].plot(dj.year, dj.price, 's--', lw=2.0, color=col, alpha=0.6, label=f'{mk} collusion')
ax[0].set_xlabel('year'); ax[0].set_ylabel('price'); ax[0].legend(fontsize=9)
ax[0].set_title('Collusion holds price above Cournot')
for mk, col in zip(REGIONS, ['#2471a3', '#d68910']):
    d = mo[mo.market == mk]
    ax[1].plot(d.year, d.share_R1, 'o-', lw=2.4, color=col, label=f'market {mk}')
ax[1].axhline(0.5, ls=':', color='k')
ax[1].set_xlabel('year'); ax[1].set_ylabel("R1's share of the market")
ax[1].set_ylim(0, 1); ax[1].legend(fontsize=10)
ax[1].set_title("Incumbent's share: home market vs entrant's market")
plt.tight_layout(); plt.show()

print("mean share held by R1:")
print(mo.groupby('market').share_R1.mean().round(3).to_string())
""")

    M(r"""
The share panel shows the asymmetry doing its work. R1 holds about 61% of its **home** market, where
it has both the transport advantage and its accumulated experience, but only about 49% of R2's
market, where the 2.4 cross-region transport premium offsets its lower operating cost. Geography and
experience push in different directions, and the equilibrium splits the difference market by market.
""")

    M(r"""
## 11. Does learning drive output? The flooding channel

This is the question Part 3b could not answer. There, cumulative production was pinned by demand, so
production learning was a windfall that changed cost but not a single decision. Here quantity is a
genuine decision, so the channel finally has a lever.

The comparison is `learning='capacity'` (capex learning only) against `learning='both'` (capex plus
the tiered operating cost). Everything else is held fixed.

> **Predict before you run.** Adding a channel that rewards cumulative production — does total
> output go up or down? And if firms want to accumulate production, is *disposal* a cheaper way to do
> it than selling?
""")

    C(r"""
rows = []
for lm in ['capacity', 'both']:
    r2 = iterate(learning=lm, tiers=(TIER_Q, TIER_M), nbp_rev=NBP_REV, first='R1',
                 max_iter=MAX_ITER, tol=TOL, mipgap=MIPGAP_GAME)
    last = {g['firm']: g for g in r2['log'][-len(REGIONS):]}
    m2 = pd.DataFrame(market_table(r2['sales']))
    rows.append(dict(learning=lm, status=r2['status'],
                     total_quantity=round(m2.quantity.sum(), 1),
                     avg_price=round(m2.price.mean(), 2),
                     **{f'sales_{r}': round(last[r]['sales'], 1) for r in REGIONS},
                     **{f'profit_{r}': round(last[r]['profit'], 1) for r in REGIONS},
                     disposal=round(sum(last[r]['disposal'] for r in REGIONS), 2)))

learning_table = pd.DataFrame(rows)
assert (learning_table.status == 'CONVERGED').all(), "a learning setting failed to converge"
q_up = 100 * (learning_table.total_quantity[1] / learning_table.total_quantity[0] - 1)
print(f"production learning raises total quantity by {q_up:.1f}% and cuts average price by "
      f"{learning_table.avg_price[0] - learning_table.avg_price[1]:.2f}")
learning_table
""")

    M(r"""
**Adding the production-learning channel raises total output by 15.2%** (1,976.4 → 2,276.5) and
pushes average price down from 17.65 to 15.81. That is the flooding mechanism, and it is the first
time in this whole series that a learning channel has changed *quantities* rather than only costs.

The logic: a unit sold today is worth more than its immediate margin, because it advances cumulative
production toward a cheaper operating-cost tier. Firms therefore rationally sell **past** the static
profit-maximising quantity — which depresses price for both of them. Learning makes the market more
competitive.

Note also that R1 gains more output than R2 (1,060.7 → 1,247.7, up 17.6%, against 915.8 → 1,028.8,
up 12.3%). The incumbent starts closer to the next tier, so its marginal unit buys more learning.
**Learning-by-doing amplifies incumbency** rather than helping the entrant catch up — a result that
matters for industrial policy and that only appears once quantity is endogenous.

**Disposal stays at exactly zero** in both rows. Firms flood by *selling* at a depressed price, not
by dumping: disposal destroys the revenue while still paying the production cost, so it is dominated.
This confirms the Part 3b calibration — `PEN_DISPOSE = 12` is comfortably above any threshold where
dumping would appear, and the mechanism remains correctly wired and idle.
""")

    # ---- 12. the agreement assertion ----
    M(r"""
## 12. The agreement assertion

Everything above was built by hand. `src/lithium/` holds the same model as functions, because
`scripts/run_all.py` and CI need to call it without a notebook kernel. **That means this model exists
twice, deliberately** — and deliberate duplication with nothing comparing the copies is how a bug
gets fixed in three places out of four.

So this cell imports the package, hands it the *same instance dictionaries* and the *same knobs* this
notebook used, runs the same case, and asserts the two objectives agree to $10^{-9}$.

Read the argument list: every knob written out above crosses the boundary here explicitly. That is
why knobs do not need to live in a shared file the way the instance tables do — the assertion already
proves both sides used the same value. And because the package takes the instance as an argument and
never re-reads the CSV, the override you may have uncommented in section 2.2 flows into *both* sides
and this check stays green.
""")

    C(r"""
from lithium import Instance, best_response_cournot, build_structure

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

packaged = best_response_cournot(
    FIRM, rival_sales, nb_struct,
    a_int=A_INT, b_slp=B_SLP, nbp_rev=NBP_REV,
    learning='both', mipgap=1e-3,
    transport=TRANSPORT, pen_dispose=PEN_DISPOSE, price_fixed=PRICE_FIXED,
    capex_curve=(QBP, CBP), learn_stages=LEARN_STAGES,
    tiers=(TIER_Q, TIER_M), n_tiers=N_TIERS, lag_years=LAG_YEARS,
)

rel = abs(packaged.ObjVal - hand_built) / abs(hand_built)
print(f"notebook (section 7, by hand): {hand_built:,.9f}")
print(f"package  (lithium.games)     : {packaged.ObjVal:,.9f}")
assert rel < 1e-9, f"notebook and package disagree by {rel:.2e}"
print(f"\nnotebook and package agree to {rel:.1e}")
""")

    M(r"""
### 12.1 What this cell would catch

The check is only evidence if it can fail, so it was made to fail on purpose before this notebook
shipped. Flipping the minimum-scale constraint in `src/lithium/regions.py` from
`c >= CAP_MIN * b` to `c >= CAP_MIN * (1 - b)` — a plausible typo, since both forms *look* like a
big-M pairing — produced this:

```
notebook (section 7, by hand): 22,869.984021205
package  (lithium.games)     : -3,257.565407376
AssertionError: notebook and package disagree by 1.14e+00
```

Everything else about that run was unremarkable. The package still built a model, Gurobi still
returned `status 2` (optimal), and every other cell in the notebook was unaffected because the
notebook builds its own copy. Nothing except this comparison noticed.

It also proves the two derivations of the structure agree, not just the final objective: `ETA`,
`MU`, `OMEGA`, `ACTIVE` and `VIN` are all computed twice, once in section 3 and once in
`lithium.structure`, and a discrepancy in any of them would move the objective.
""")

    M(r"""
## 13. Summary

| Question | Answer |
|---|---|
| Does endogenous price change the 4b conclusions? | **Yes** — first-mover advantage falls from ~29% to 4.4% |
| Cournot vs collusion? | Collusion cuts output 31%, raises price 15.81 → 20.21, joint profit +28.5% |
| Does production learning drive output now? | **Yes** — +15.2% quantity, price down 1.84 |
| Who benefits from learning? | **The incumbent** — R1 +17.6% output against R2's +12.3% |
| Does pump-and-dump appear? | No. Flooding happens through **sales**, not disposal |
| Pure-strategy equilibrium? | Yes, from both move orders |

### Formulation lessons

- **Curvature and direction together decide whether you need SOS2.** Concave-and-maximised revenue
  (section 7.5) is safe with free $\lambda$; concave-and-minimised cost (section 5.5) is not. Same
  shape, opposite requirement — and both appear in this one notebook.
- **Piecewise-linearising revenue avoided a MIQP entirely** — and kept the model inside the
  size-limited licence.
- **Test convergence on the actual strategy, with a tolerance.** Plans alone declared premature
  convergence; exact quantity hashing invented a 5-cycle out of MIP-gap noise.
- **Results that depend on a rationing rule deserve suspicion.** 4b's first-mover advantage was
  mostly an artefact of the fixed price.
- **Never default an argument to a global.** `def f(..., n=NBP_REV)` freezes the value when the cell
  runs; a later `NBP_REV = 3` then changes nothing at all, silently.

### Things to try

Each of these is a one-line edit to a knob, followed by *Run all*. The section 12 assertion should
stay green through every one of them — if it goes red, something you changed was not passed to the
package.

- `CHOKE = 24` — a flatter market; competition bites harder and margins compress
- `P_ANCHOR = 10` — barely profitable, and capacity investment should collapse
- `NBP_REV = 3` — a coarse revenue mesh; quantities should get visibly blocky
- `TRANSPORT_CROSS = 1.0` — one integrated market instead of two linked ones
- In section 2.2, `EXPERIENCE0['R1'] = 500.0` — remove incumbency and watch the learning
  amplification in section 11 disappear

### Where this goes next

- **4d — Stackelberg.** Leader commits, follower responds. Because the follower's *operational*
  problem is an LP, its KKT conditions can be written explicitly and the bilevel model collapsed to a
  single-level MPEC with big-M complementarity. This is the payoff for keeping flows continuous all
  the way back in Part 3.
- **4e — Policy instruments.** Tariffs as arc-cost adders, quotas as arc bounds, local content
  minimums. Government constrains, firms respond. `lithium.regions.add_region` already carries all
  three as optional arguments that collapse to nothing when empty — which is why the model you
  checked against in section 12 is literally the same function 4e will use.
""")


    return out
