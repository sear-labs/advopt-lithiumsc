"""Build notebooks/03b_production_learning.ipynb.

**Subject:** a second learning channel. Part 3's capex falls with cumulative
*capacity*; here opex also falls with lagged cumulative *production*, which makes
learning depend on how hard you run the fleet rather than only on how much of it
you built.

**Two findings the notebook is built on.**

The channels are *separable*: capacity learning moves capex and leaves opex
alone (29,610.8 vs 29,544.5), production learning moves opex and leaves capex
untouched to the last decimal (9,098.3 in both), and `both` gets each effect
whole. That is a strong structural check and it is asserted rather than admired.

And -- as in Part 3 -- the channels move the bill far more than the decision.
Production learning cuts opex 18.4% and returns the *identical* build plan;
only capacity learning shifts anything, pulling one build from year 24 to 19.
Four variants, two distinct plans.

The pump-and-dump section is the one worth reading twice: a planner who can
overproduce to climb the learning curve faster never does, even when disposal is
free and the learning rate is 55%.
"""
from . import common

NOTEBOOK = "03b_production_learning.ipynb"
TITLE = "Part 3b - Learning by doing: production-based learning"


def cells():
    out = []

    def M(text):
        out.append(("md", text.strip("\n")))

    def C(text):
        out.append(("code", text.strip("\n")))

    # ================================ front ================================
    M(r"""
# Part 3b — Learning by doing

### Two channels, and neither of them changes the plan much

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/sear-labs/advopt-lithiumsc/blob/main/notebooks/03b_production_learning.ipynb)

Part 3 had one learning channel: build more capacity, and capacity gets cheaper.
That is learning-by-*building*. It is also only half of what the literature means
by a learning curve — the other half is learning-by-*doing*, where cost falls
because you have made a lot of the stuff, not because you have built a lot of
factories.

| | driver | what gets cheaper | how it is modelled |
|---|---|---|---|
| **Channel A** | cumulative **capacity** | capex | SOS2 on a continuous curve (Part 3 §9) |
| **Channel B** | lagged cumulative **production** | opex | discrete tiers with binaries (§6) |

### Why Channel B is discrete when Channel A is continuous

Not for realism — for **linearity**. Channel A multiplies a curve by nothing: the
model reads a cumulative cost off it and pays the difference. Channel B has to
multiply an opex *multiplier* by a *throughput*, and both are variables. That
product is bilinear and a MILP cannot have it.

Tiers solve it: a binary picks which multiplier applies, throughput is split
across tiers, and multiplier × throughput becomes a sum of constants × variables.
§6 builds that, and it costs 234 extra binaries.

### The three questions this notebook answers

1. **Do the two channels interfere?** No — they are separable to the last
   decimal, and §8 asserts it.
2. **Would a planner overproduce just to learn faster?** No, and §11 fails to
   make it happen even with free disposal and a 55% learning rate.
3. **Does any of it change the build plan?** Barely. §13.

### A note on the lag

Know-how does not arrive the instant a unit is made. `LAG_YEARS = 3` delays it —
and the lag is defined in **years**, then mapped to whichever period contains
that year. Defining it in periods instead would silently stretch from 3 years to
9 as the mesh coarsens, which is the kind of bug that produces a plausible answer.
""")

    out += common.setup_section(notebook=NOTEBOOK)
    out += common.netcore_instance_section(agree=14)
    out += common.netcore_structure_section(
        agree=14, blocks="[(6, 1), (4, 3), (2, 5), (1, 9)]",
        horizon=37, nperiods=13, report_until=28)

    # ==================== 4. carried over ==================================
    M(r"""
## 4. Carried over from Part 3: Channel A

The capex learning curve is Part 3 §4 unchanged apart from two knobs — a gentler
learning rate and a higher floor. It arrives under a `CARRIED OVER` marker rather
than being re-narrated; if you have not read Part 3 §4 and §9, read them before
this cell.

The two knobs that differ, and they are knobs rather than corrections: Part 3
used `LR_CAPEX = 0.20` with a floor at 0.55, this notebook uses **0.15** and
**0.60**. A gentler capex channel makes the contrast with Channel B legible
rather than swamped.
""")

    C(r'''
# CARRIED OVER FROM 03_network_core SECTIONS 4 AND 9 - narrated there.
import math
import time

LEARN_STAGES = ["PROC", "MFG"]
LR_CAPEX = 0.15          # gentler than Part 3's 0.20
Q_START, Q_ADD = 400.0, 1000.0
CAPEX_FLOOR = 0.60       # higher floor than Part 3's 0.55
NBP = 9
PANELS = 600

_bc = -math.log2(1 - LR_CAPEX)
U0 = sum(UNIT[s] for s in LEARN_STAGES) / len(LEARN_STAGES)


def capex_unit(q):
    return max(CAPEX_FLOOR * U0, U0 * (q / Q_START) ** (-_bc))


def capex_cum(q, panels=PANELS):
    if q <= Q_START:
        return 0.0
    h = (q - Q_START) / panels
    return sum(0.5 * (capex_unit(Q_START + i * h) + capex_unit(Q_START + (i + 1) * h)) * h
               for i in range(panels))


K = list(range(NBP))
QBP = [Q_START + Q_ADD * k / (NBP - 1) for k in K]
CBP = [capex_cum(q) for q in QBP]
MU_TECH = {p: MU[LEARN_STAGES[0], p] for p in P}

print(f"Channel A: LR {LR_CAPEX:.0%}, floor {CAPEX_FLOOR:.0%}, {NBP} breakpoints")
print(f"unit cost across the mesh {[round(capex_unit(q), 2) for q in QBP]}")
''')

    # ==================== 5. channel B parameters ==========================
    M(r"""
## 5. Channel B: the parameters, and what has to be calibrated

Opex falls with **cumulative production**, in `N_TIERS` discrete steps. Two
things need deciding before any of it can be built.

**Where do the thresholds go?** They cannot be guessed, and they cannot come from
a solve that already has production learning — that would be circular. So §7
solves the model *without* Channel B, observes how much each stage actually
produces, and places the thresholds at **doublings** of that. Doublings, because
Wright's law is stated per doubling: the multiplier at tier $j$ is then exactly
$(1 - \text{LR})^{j}$.

**What is the lag for?** Cumulative production at the *lagged* period drives the
current tier, because know-how takes time to embody in practice. Set
`LAG_YEARS = 0` and the model gets its discount the instant it produces, which is
both wrong and makes the tier constraints easier — a bad combination.
""")

    C(r'''
LR_OPEX = 0.18        # opex falls this much per doubling of cumulative production
OPEX_FLOOR = 0.65     # floor, as a fraction of base opex
LAG_YEARS = 3         # know-how embodies with a delay, defined in YEARS
N_TIERS = 3           # tier 0 is the no-discount tier
LEARN_SCOPE = "regional"   # 'regional' | 'global'

PEN_DISPOSE = 12.0    # cost of throwing product away
PEN_DEVIATE = 35.0    # one-sided penalty for undershooting a local-content floor
TIER_MIN_PHASE_IN = 6      # no local-content minimum binds before this year

MIPGAP = 1e-6
# 1e-6, not the 0.005 the original used. At 0.005 the capacity variant stopped
# at 45,547.7 here and 45,546.0 in an equivalent formulation - a difference of
# 3.6e-05, invisible against the gap but larger than several effects this
# notebook measures.

# the lag, in years, mapped to whichever period holds that year
LAGP = {p: YEAR_TO_P[max(1, START[p] - LAG_YEARS)] for p in P}
print(f"Channel B: LR {LR_OPEX:.0%}, floor {OPEX_FLOOR:.0%}, {N_TIERS} tiers, "
      f"{LAG_YEARS}-year lag, scope '{LEARN_SCOPE}'")
print(f"\nthe lag maps period -> lagged period: "
      f"{ {p: LAGP[p] for p in P[:6]} } ...")
print("defined in YEARS: period 8 starts in year "
      f"{START[8]} and looks back to year {max(1, START[8] - LAG_YEARS)}, "
      f"which is period {LAGP[8]}")
print("had the lag been '3 periods' it would mean "
      f"{START[8] - START[max(0, 8 - 3)]} years here and more later - "
      "a bug that produces plausible output")
''')

    # ==================== 6. the model =====================================
    M(r"""
## 6. The model, with both channels

The skeleton is Part 3's: semi-continuous sizing, vintage-indexed throughput,
cross-region arcs, demand service. Three things are added.

**Cumulative production**, `cumprod[s, scope, p]` — undiscounted, because
know-how accrues in physical units. It uses `LEN[q]`, the number of years in
period `q`, and never `OMEGA`. Discounting a knowledge stock would be a category
error and a very easy one to make when every other sum in the model is
discounted.

**The tier selection**, `z[s, scope, p, j]` — exactly one tier per node-period,
with big-M constraints saying the chosen tier is consistent with lagged
cumulative production.

**The throughput split**, `tsplit[s, r, p, j]` — the linearisation. Throughput is
divided across tiers, each piece is charged at its tier's multiplier, and a
binary forces all of it into the selected tier. Note it splits **node-level**
throughput, not per-vintage: the opex rate does not depend on vintage, so the two
are exactly equivalent and this one is far smaller.

Disposal and the local-content floor are also here, unused until §11 and §12.
""")

    C(r'''
# THE FUNCTION IS THE LESSON: the four variants in section 8 must differ ONLY in
# which channels are switched on. Writing the model out per variant would make a
# difference between two rows uninterpretable - a change in the objective, or a
# typo in a constraint, with no way to tell. Every block is narrated above.
def build_model(learning="production", tiers=None, tier_min=None,
                allow_dispose=True, pen_dispose=PEN_DISPOSE,
                pen_deviate=PEN_DEVIATE, mipgap=MIPGAP):
    """learning: 'none' | 'capacity' | 'production' | 'both'"""
    tier_min = dict(tier_min or {})
    m = gp.Model()
    m.Params.OutputFlag = 0
    m.Params.MIPGap = mipgap

    build = m.addVars(BUILD, vtype=GRB.BINARY, name="build")
    size = m.addVars(BUILD, lb=0.0, ub=CAP_MAX, name="size")
    thr = m.addVars(ACTIVE, lb=0.0, name="thr")
    flow = m.addVars(ARCS, P, lb=0.0, name="flow")
    short = m.addVars(REGIONS, P, lb=0.0, name="short")
    dev = m.addVars(NODES, P, lb=0.0, name="dev")
    disp = m.addVars(REGIONS, P, lb=0.0, name="disp")

    m.addConstrs(size[s, r, v] <= CAP_MAX * build[s, r, v] for (s, r, v) in BUILD)
    m.addConstrs(size[s, r, v] >= CAP_MIN * build[s, r, v] for (s, r, v) in BUILD)
    m.addConstrs(thr[s, r, v, p] <= (LEGACY_CAP[s, r] if v == -1 else size[s, r, v])
                 for (s, r, v, p) in ACTIVE)
    m.addConstrs(gp.quicksum(ETA[s, v, p] * thr[s, r, v, p] for v in VIN[s, r, p])
                 == flow.sum(s, r, "*", p) for (s, r) in NODES for p in P)
    for i, s in enumerate(STAGES):
        if i == 0:
            continue
        m.addConstrs(flow.sum(STAGES[i - 1], "*", r, p)
                     == gp.quicksum(thr[s, r, v, p] for v in VIN[s, r, p])
                     for r in REGIONS for p in P)
    # equality with a disposal slack: surplus has to go somewhere and be paid for
    m.addConstrs(flow.sum(STAGES[-1], "*", r, p) + short[r, p] - disp[r, p]
                 == DEMAND[r, p] for r in REGIONS for p in P)
    if not allow_dispose:
        m.addConstrs(disp[r, p] == 0 for r in REGIONS for p in P)
    if tier_min:
        m.addConstrs(gp.quicksum(thr[s, r, v, p] for v in VIN[s, r, p]) + dev[s, r, p]
                     >= tier_min.get((s, r, p), 0.0)
                     for (s, r) in NODES for p in P)

    # cumulative production: UNDISCOUNTED, in physical units, so LEN not OMEGA
    scope = ([(s, r) for (s, r) in NODES] if LEARN_SCOPE == "regional"
             else [(s, "ALL") for s in STAGES])
    cum_ub = 3.0 * CAP_MAX * HORIZON * (len(REGIONS) if LEARN_SCOPE == "global" else 1)
    cumprod = m.addVars(scope, P, lb=0.0, ub=cum_ub, name="cumprod")
    m.addConstrs(cumprod[s, rk, p]
                 == gp.quicksum(LEN[q] * thr[s, r, v, q]
                                for r in (REGIONS if rk == "ALL" else [rk])
                                for q in P if q <= p for v in VIN[s, r, q])
                 for (s, rk) in scope for p in P)

    capex = (gp.quicksum(MU[s, v] * FIXED[s] * build[s, r, v] for (s, r, v) in BUILD)
             + gp.quicksum(MU[s, v] * UNIT[s] * size[s, r, v]
                           for (s, r, v) in BUILD if s not in LEARN_STAGES))
    if learning in ("capacity", "both"):
        Q = m.addVars(P, lb=Q_START, ub=Q_START + Q_ADD)
        Cc = m.addVars(P, lb=0.0)
        lam = m.addVars(P, K, lb=0.0, ub=1.0)
        m.addConstrs(lam.sum(p, "*") == 1 for p in P)
        m.addConstrs(Q[p] == gp.quicksum(QBP[k] * lam[p, k] for k in K) for p in P)
        m.addConstrs(Cc[p] == gp.quicksum(CBP[k] * lam[p, k] for k in K) for p in P)
        m.addConstrs(Q[p] == Q_START + gp.quicksum(size[s, r, v] for (s, r, v) in BUILD
                                                   if s in LEARN_STAGES and v <= p)
                     for p in P)
        for p in P:
            m.addSOS(GRB.SOS_TYPE2, [lam[p, k] for k in K])
        capex += gp.quicksum(MU_TECH[p] * (Cc[p] - (Cc[p - 1] if p > 0 else 0.0))
                             for p in P)
    else:
        capex += gp.quicksum(MU[s, v] * UNIT[s] * size[s, r, v]
                             for (s, r, v) in BUILD if s in LEARN_STAGES)

    if learning in ("production", "both") and tiers:
        tq, tm = tiers
        J = list(range(N_TIERS))
        z = m.addVars(scope, P, J, vtype=GRB.BINARY, name="tier")
        m.addConstrs(z.sum(s, rk, p, "*") == 1 for (s, rk) in scope for p in P)
        bigq = cum_ub
        m.addConstrs(cumprod[s, rk, LAGP[p]] >= tq[s][j - 1] - bigq * (1 - z[s, rk, p, j])
                     for (s, rk) in scope for p in P for j in J if j > 0)
        m.addConstrs(cumprod[s, rk, LAGP[p]] <= tq[s][j] + bigq * (1 - z[s, rk, p, j])
                     for (s, rk) in scope for p in P for j in J if j < N_TIERS - 1)
        tsplit = m.addVars(NODES, P, J, lb=0.0, name="tsplit")
        m.addConstrs(tsplit.sum(s, r, p, "*")
                     == gp.quicksum(thr[s, r, v, p] for v in VIN[s, r, p])
                     for (s, r) in NODES for p in P)
        m.addConstrs(tsplit[s, r, p, j]
                     <= 3 * CAP_MAX * z[s, (r if LEARN_SCOPE == "regional" else "ALL"), p, j]
                     for (s, r) in NODES for p in P for j in J)
        operate = gp.quicksum(OMEGA[p] * OPERATE[s] * tm[s][j] * tsplit[s, r, p, j]
                              for (s, r) in NODES for p in P for j in J)
        m._z = z
    else:
        operate = gp.quicksum(OMEGA[p] * OPERATE[s] * thr[s, r, v, p]
                              for (s, r, v, p) in ACTIVE)
        m._z = None

    transport = gp.quicksum(OMEGA[p] * TRANSPORT[a, b] * flow[s, a, b, p]
                            for (s, a, b) in ARCS for p in P)
    penalty = (gp.quicksum(OMEGA[p] * PEN_SHORT * short[r, p] for r in REGIONS for p in P)
               + gp.quicksum(OMEGA[p] * pen_deviate * dev[s, r, p]
                             for (s, r) in NODES for p in P)
               + gp.quicksum(OMEGA[p] * pen_dispose * disp[r, p]
                             for r in REGIONS for p in P))

    m.setObjective(capex + operate + transport + penalty, GRB.MINIMIZE)
    m._e = dict(capex=capex, operate=operate, transport=transport, penalty=penalty)
    m._v = dict(build=build, size=size, thr=thr, flow=flow, short=short,
                dev=dev, disp=disp, cumprod=cumprod)
    m._scope = scope
    return m


_probe = build_model(learning="none")
_probe.update()
print(f"learning='none':       {_probe.NumVars:5d} vars, {_probe.NumBinVars:4d} binaries")
''')

    # ==================== 7. calibration ===================================
    M(r"""
## 7. Calibrating the tiers

Solve without Channel B, look at how much each stage actually makes over the
horizon, and put the thresholds at $q/8$ and $q/4$ of that. The multipliers are
then exactly Wright's law per doubling.

**This is a modelling decision, not a measurement**, and it is worth being
explicit that it is arbitrary: thresholds at $q/8$ mean the fleet reaches tier 2
about two-thirds of the way through. Put them at $q/2$ and nothing ever leaves
tier 0, and the whole channel silently does nothing.
""")

    C(r'''
base = build_model(learning="none")
base.optimize()
assert base.SolCount > 0, "the calibration solve found no solution"
BASE_OBJ = base.ObjVal

prod = {}
for s in STAGES:
    prod[s] = max(base._v["cumprod"][s, rk, P[-1]].X
                  for (ss, rk) in base._scope if ss == s)

TIER_Q, TIER_M = {}, {}
for s in STAGES:
    top = max(prod[s], 1.0)
    q1 = top / 8.0
    TIER_Q[s] = [q1 * 2 ** j for j in range(N_TIERS - 1)]
    TIER_M[s] = [max(OPEX_FLOOR, (1 - LR_OPEX) ** j) for j in range(N_TIERS)]

print(f"no-learning objective : {BASE_OBJ:,.4f}")
print(f"cumulative production by stage: { {k: round(v, 1) for k, v in prod.items()} }")
print(f"tier thresholds : { {k: [round(x, 1) for x in v] for k, v in TIER_Q.items()} }")
print(f"tier multipliers: { {k: [round(x, 4) for x in v] for k, v in TIER_M.items()} }")

assert all(len(TIER_Q[s]) == N_TIERS - 1 for s in STAGES), \
    "k tiers need k-1 boundaries between them"
assert all(TIER_M[s] == sorted(TIER_M[s], reverse=True) for s in STAGES), \
    "a later tier must not be dearer than an earlier one"
print(f"\nmultipliers are exactly (1 - {LR_OPEX:.0%})^j, floored at {OPEX_FLOOR}")
''')

    # ==================== 8. four variants =================================
    M(r"""
## 8. Four learning variants, and whether the channels interfere

> **Predict before you run.** Channel A makes capacity cheaper; Channel B makes
> running it cheaper. Does turning both on save more, less, or exactly the sum of
> turning on each alone?

Read the **cost columns**, not the total. The total tells you which variant is
cheapest, which is not interesting; the split tells you whether each channel hit
the thing it was supposed to hit.
""")

    C(r'''
rows, res, plans = [], {}, {}
for lm in ("none", "capacity", "production", "both"):
    t0 = time.time()
    mm = build_model(learning=lm, tiers=(TIER_Q, TIER_M))
    mm.optimize()
    assert mm.SolCount > 0, f"learning={lm} found no solution"
    res[lm] = mm
    pl = {k: round(mm._v["size"][k].X, 6)
          for k in BUILD if mm._v["build"][k].X > 0.5}
    plans[lm] = tuple(sorted(pl.items()))
    rows.append(dict(learning=lm, objective=round(mm.ObjVal, 1),
                     capex=round(mm._e["capex"].getValue(), 1),
                     opex=round(mm._e["operate"].getValue(), 1),
                     builds=len(pl), capacity=round(sum(pl.values()), 1),
                     disposal=round(sum(mm._v["disp"][r, p].X
                                        for r in REGIONS for p in P), 2),
                     binaries=mm.NumBinVars, seconds=round(time.time() - t0, 1)))
variants = pd.DataFrame(rows)
variants
''')

    M(r"""
### 8.1 The separation, asserted

If the two channels were interfering — sharing a constraint they should not, or
double-counting a cost — the cleanest symptom would be Channel B moving capex, or
Channel A moving opex. Neither should happen, and the cell below requires it.
""")

    C(r'''
cap = {lm: res[lm]._e["capex"].getValue() for lm in res}
opx = {lm: res[lm]._e["operate"].getValue() for lm in res}

print(f"{'variant':11s} {'capex':>11s} {'opex':>11s}")
for lm in ("none", "capacity", "production", "both"):
    print(f"{lm:11s} {cap[lm]:11.4f} {opx[lm]:11.4f}")

assert abs(cap["production"] - cap["none"]) < 1e-6, (
    "production learning changed capex; Channel B is supposed to touch opex only")
assert abs(opx["both"] - opx["production"]) < 1e-6, (
    "adding Channel A changed Channel B's opex; the channels are interfering")
print(f"\nChannel B leaves capex untouched : {cap['none']:.4f} = {cap['production']:.4f}")
print(f"Channel A leaves Channel B's opex : {opx['production']:.4f} = {opx['both']:.4f}")
print(f"\nChannel A moves capex {cap['none']:.1f} -> {cap['capacity']:.1f} "
      f"({100 * (cap['capacity'] / cap['none'] - 1):+.2f}%)")
print(f"Channel B moves opex  {opx['none']:.1f} -> {opx['production']:.1f} "
      f"({100 * (opx['production'] / opx['none'] - 1):+.2f}%)")
''')

    M(r"""
**Separable, exactly.** Channel B leaves capex at 9,098.3347 in both `none` and
`production`; Channel A leaves Channel B's opex at 24,153.3621 in both
`production` and `both`. Those are equalities to six decimal places, not
approximations, and they are the strongest single check in this notebook that the
two channels are wired to the right cost.

The sizes are very different, though. **Channel A takes 2.25% off capex; Channel
B takes 18.43% off opex** — and since opex is more than three times capex here,
production learning is worth roughly fifteen times what capacity learning is
worth. A modelling effort that implemented only Channel A, which is the more
commonly modelled one, would have found the smaller of the two effects.
""")

    # ==================== 9. utilization ===================================
    M(r"""
## 9. Utilization — the check you should have predicted

Channel B rewards *producing*. So a plant that would otherwise idle now has a
reason to run: every unit made moves the fleet toward the next tier.

> **Predict before you run.** Does production learning push utilization up at
> every node?
""")

    C(r'''
# THE FUNCTION IS THE LESSON: utilization is computed for two models and the
# comparison is only meaningful if both are measured the same way - the same
# discipline Part 2c needed, one level down.
def utilization(mm):
    """Throughput as a share of installed capacity, per node, over the horizon."""
    thr, size = mm._v["thr"], mm._v["size"]
    out = {}
    for (s, r) in NODES:
        used = cap_ = 0.0
        for p in P:
            for v in VIN[s, r, p]:
                used += LEN[p] * thr[s, r, v, p].X
                cap_ += LEN[p] * (LEGACY_CAP[s, r] if v == -1 else size[s, r, v].X)
        out[s, r] = 100.0 * used / cap_ if cap_ > 0 else 0.0
    return out


un, up = utilization(res["none"]), utilization(res["production"])
util = pd.DataFrame([dict(node=f"{s}/{r}", none=round(un[s, r], 1),
                          production=round(up[s, r], 1),
                          change=round(up[s, r] - un[s, r], 1))
                     for (s, r) in NODES])
assert all(v > 50 for v in un.values()), "a node is idling badly even without learning"
util
''')

    M(r"""
**Not uniformly, and that is the interesting part.** Utilization rises at three
nodes and falls at three. Production learning does not simply say "run
everything harder" — it says "run the nodes whose next tier is within reach", and
for a node that cannot get there in time the optimal answer is to let a
better-placed node do the producing.

MFG/R1 is the low one at 76% in both cases. That is not a defect: R1's
manufacturing sits next to the larger legacy fleet, so it has capacity it does
not need early on, and the model would rather leave it idle than build less of it
and fail demand later.
""")

    # ==================== 10. tier activation ==============================
    M(r"""
## 10. Which tiers actually activate?

A tier structure that never leaves tier 0 is decoration. A tier structure that
jumps straight to the last tier is a threshold set too low. Neither raises an
error, so look.
""")

    C(r'''
mz = res["production"]
tiers_path = []
for (s, rk) in mz._scope:
    path = [next(j for j in range(N_TIERS) if mz._z[s, rk, p, j].X > 0.5) for p in P]
    tiers_path.append(dict(stage=s, scope=rk, tier_by_period=path,
                           cumprod_end=round(mz._v["cumprod"][s, rk, P[-1]].X, 1)))
    assert path == sorted(path), (
        f"{s}/{rk} went BACKWARDS through the tiers; a cumulative driver cannot "
        f"decrease, so this is a constraint error")
    assert path[0] == 0, f"{s}/{rk} started above tier 0"
tier_table = pd.DataFrame(tiers_path)
assert max(max(r["tier_by_period"]) for r in tiers_path) == N_TIERS - 1, \
    "no node ever reached the top tier; the thresholds are too high to bind"
print("every node progresses 0 -> 1 -> 2 monotonically, and every node gets there")
tier_table
''')

    M(r"""
Monotone everywhere, which a cumulative driver requires and the assertion checks.
Every node reaches the top tier, and MFG/R2 gets there one period later than the
rest — it is the smallest node, so it takes longest to accumulate.

The transition happens around period 7–8, roughly year 13. With a three-year lag
that means the production justifying it happened around year 10, which is when
the first wave of new capacity has been running for a while. The timing is a
consequence of the calibration in §7, not an independent finding.
""")

    # ==================== 11. pump and dump ================================
    M(r"""
## 11. Would a planner overproduce just to learn faster?

This is the question a production-learning model exists to be asked. Making more
than you need is wasteful — but it moves you down the learning curve, and the
discount applies to everything you make afterwards. A model that gets this wrong
in the permissive direction will happily manufacture and bin product forever.

The lever is `PEN_DISPOSE`. Lower it to zero and disposal is free.

> **Predict before you run.** With free disposal, does the planner overproduce?
""")

    C(r'''
rows = []
for pen in (12.0, 6.0, 3.0, 1.0, 0.0):
    mm = build_model(learning="production", tiers=(TIER_Q, TIER_M), pen_dispose=pen)
    mm.optimize()
    rows.append(dict(disposal_penalty=pen, objective=round(mm.ObjVal, 1),
                     disposal_units=round(sum(mm._v["disp"][r, p].X
                                              for r in REGIONS for p in P), 2)))
dump = pd.DataFrame(rows)
assert (dump.disposal_units < 1e-6).all(), \
    "the planner disposed of product; section 11's conclusion needs rewriting"
print("zero disposal at every penalty, INCLUDING free disposal")
dump
''')

    M(r"""
Zero, everywhere, including at a penalty of exactly zero. Worth pushing harder
before believing it — the learning rate might simply be too weak to be worth
gaming. So: crank it, and drop the floor so the higher rate can actually bite.
""")

    C(r'''
rows = []
for lr, floor in ((0.18, 0.65), (0.35, 0.25), (0.55, 0.25)):
    tq = {s: list(TIER_Q[s]) for s in STAGES}      # thresholds unchanged
    tm = {s: [max(floor, (1 - lr) ** j) for j in range(N_TIERS)] for s in STAGES}
    mm = build_model(learning="production", tiers=(tq, tm), pen_dispose=0.0)
    mm.optimize()
    rows.append(dict(LR_opex=lr, floor=floor,
                     multipliers=[round(x, 3) for x in tm["PROC"]],
                     objective=round(mm.ObjVal, 1),
                     disposal_units=round(sum(mm._v["disp"][r, p].X
                                              for r in REGIONS for p in P), 2)))
hard = pd.DataFrame(rows)
assert (hard.disposal_units < 1e-6).all(), \
    "disposal appeared under an aggressive learning rate; the section is wrong"
print("still zero, at a 55% learning rate with free disposal")
hard
''')

    M(r"""
**Still zero.** The objective falls a long way — 40,535.3 down to 33,030.0 as the
rate goes from 18% to 55% — so the channel is certainly doing something. It is
just never worth *manufacturing waste* to get there.

The reason is structural and worth naming: the tiers are driven by cumulative
production, and the model is already producing near capacity to serve demand.
Buying an earlier tier transition would mean building **more capacity** and
running it to make product nobody wants. The capex of that extra capacity
outweighs the opex discount it unlocks, at every rate tested.

**That is a result about this instance, not a theorem.** A model with cheaper
capacity, a steeper curve, or a longer horizon over which to amortise the
discount could easily flip it. What the section demonstrates is the *test*, not
the answer — and note that the negative result required removing the penalty
entirely to be convincing. A conclusion drawn at `PEN_DISPOSE = 12` would have
proved only that disposal is expensive.
""")

    # ==================== 12. local content ================================
    M(r"""
## 12. The government lever: local content minimums

A minimum throughput at every node, phased in from year 6. This is the one place
in the notebook where a *non-market* constraint drives behaviour, and it is where
the disposal mechanism finally earns its place in the model.
""")

    C(r'''
rows = []
for level in (0.0, 60.0, 110.0, 160.0):
    tmin = ({} if level <= 0 else
            {(s, r, p): (0.0 if START[p] < TIER_MIN_PHASE_IN else level)
             for (s, r) in NODES for p in P})
    mm = build_model(learning="production", tiers=(TIER_Q, TIER_M), tier_min=tmin)
    mm.optimize()
    pl = {k for k in BUILD if mm._v["build"][k].X > 0.5}
    rows.append(dict(min_throughput=level, objective=round(mm.ObjVal, 1),
                     undersupply=round(sum(mm._v["dev"][s, r, p].X
                                           for (s, r) in NODES for p in P), 2),
                     disposal=round(sum(mm._v["disp"][r, p].X
                                        for r in REGIONS for p in P), 2),
                     builds=len(pl)))
lcr = pd.DataFrame(rows)
assert lcr.disposal.iloc[-1] > 1, (
    "the strictest local-content level produced no disposal, so this section's "
    "point about forced overproduction has gone")
lcr
''')

    M(r"""
**Here is where disposal activates, and it validates the mechanism.** At a floor
of 160 the planner builds two extra facilities, produces 260.46 units it cannot
sell, and pays to dispose of them — pushing the objective from 40,535.3 to
52,255.8, a 29% increase.

That is the difference between the two sections. §11 asked whether a planner
would *choose* to overproduce for a commercial reason and the answer was no, at
every rate. §12 shows what it looks like when a planner is *made* to overproduce
by a constraint that ignores demand. The disposal variable was never dead code —
it was waiting for a policy that would make it bind.

Note the step: 60 and 110 cost almost nothing (40,535.3 and 40,558.6), then 160
costs 29%. Local-content rules are cheap while they sit below what the chain was
going to do anyway, and expensive the moment they exceed it. A policy set at 110
here would look free and be one unit of demand growth away from being ruinous.
""")

    # ==================== 13. does it change the plan ======================
    M(r"""
## 13. Does any of this change the *plan*?

Part 3 found that four accounting and learning variants gave one identical build
plan. The same question here, with two genuine learning channels rather than
one.
""")

    C(r'''
n_distinct = len(set(plans.values()))
comp = pd.DataFrame([
    dict(learning=lm, builds=len(plans[lm]),
         total_capacity=round(sum(v for _k, v in plans[lm]), 1),
         mean_size=round(sum(v for _k, v in plans[lm]) / len(plans[lm]), 1),
         build_years=sorted(START[v] for ((_s, _r, v), _x) in plans[lm]))
    for lm in ("none", "capacity", "production", "both")])

print(f"DISTINCT BUILD PLANS among the four variants: {n_distinct}")
# Sizes compared with a tolerance, not for equality. Two solves inside the same
# MIP gap can land on equally optimal vertices differing in the last digits;
# Part 3 hit exactly that on a Linux runner - 226.9412 against 226.941, same
# sites, same periods. Keys still compare exactly, so a genuinely different plan
# still trips these.
PLAN_RTOL = 1e-5
_d = {lm: dict(plans[lm]) for lm in plans}
_close = {(x, y): set(_d[x]) == set(_d[y])
          and all(abs(_d[x][k] - _d[y][k]) <= PLAN_RTOL * max(1.0, abs(_d[y][k]))
                  for k in _d[y])
          for x in _d for y in _d}

assert _close[("none", "production")] and _close[("none", "both")], (
    "production learning changed the build plan; section 13's claim is that it "
    "does not, so the prose needs rewriting rather than the assertion relaxing")
assert not _close[("capacity", "none")], \
    "capacity learning changed nothing at all, which section 13 says it does"
print("`none`, `production` and `both` share a plan; only `capacity` differs")
comp
''')

    M(r"""
**Two plans out of four variants**, and the split is instructive.

`none`, `production` and `both` build the same six facilities in the same years
— [7, 7, 10, 13, 19, 24]. Production learning cuts opex by 18% and does not move
a single build decision, because it makes *running* the fleet cheaper and the
fleet you want is determined by demand.

Only Channel A moves anything, and barely: it pulls the last build from year 24
to **year 19** and trims total capacity from 1,231.9 to 1,215.4. That is exactly
what capacity learning should do — building earlier is now worth slightly more,
because it makes the next build cheaper.

**So the honest summary is that both channels are worth a lot of money and
almost no decisions.** That is a legitimate and common finding, and the only way
to know it is to compare plans. It also means a modeller who needs the *plan*
and not the *cost* could skip Channel B entirely here — and one who needs the
cost cannot.
""")

    # ==================== 14. agreement ====================================
    M(r"""
## 14. The agreement assertion

`src/lithium/netcore.py` holds the same model, and the same one covers Part 3:
`build_netcore` with `learning='capacity'` and no tiers *is* Part 3, and adding
tiers gives this notebook. One implementation, two notebooks — the same
arrangement `add_region` uses for Parts 4c and 4e.

This compares the tier calibration, all four variants' objectives, their **cost
components separately** (which is what would catch a channel wired to the wrong
term), and their build plans.
""")

    C(r'''
from lithium import NetCoreInstance, build_netcore_structure
from lithium import curves as pkg_curves
from lithium import netcore as NC

nb_inst = NetCoreInstance(
    stages=STAGES, regions=REGIONS, fixed=FIXED, unit=UNIT, operate=OPERATE,
    lead=LEAD, legacy_cap=LEGACY_CAP, legacy_ret=LEGACY_RET,
    demand_base=DEMAND_BASE, demand_growth=DEMAND_GROWTH,
    eta_ceil=ETA_CEIL, eta_base=ETA_BASE, alpha=ALPHA, beta=BETA,
    delta_bar=DELTA_BAR)
nb_st = build_netcore_structure(
    nb_inst, blocks=BLOCKS, dr=DR, life=LIFE, cap_min=CAP_MIN, cap_max=CAP_MAX,
    legacy_byr=LEGACY_BYR, eta_floor=ETA_FLOOR,
    transport_own=TRANSPORT_OWN, transport_cross=TRANSPORT_CROSS)

pkg_QBP, pkg_CBPm = pkg_curves.capex_breakpoints(
    Q_START, Q_ADD, NBP, LR_CAPEX, CAPEX_FLOOR, panels=PANELS)
pkg_CBP = [U0 * c for c in pkg_CBPm]
assert max(abs(a - b) for a, b in zip(CBP, pkg_CBP)) / max(CBP) < 1e-12, \
    "the hand-built capex curve and lithium.curves differ"

(ptq, ptm), pkg_base, pkg_prod = NC.calibrate_tiers(
    nb_st, n_tiers=N_TIERS, lr_opex=LR_OPEX, opex_floor=OPEX_FLOOR,
    capex_curve=(pkg_QBP, pkg_CBP), learn_stages=tuple(LEARN_STAGES),
    pen_short=PEN_SHORT, pen_dispose=PEN_DISPOSE, pen_deviate=PEN_DEVIATE,
    allow_dispose=True, mipgap=MIPGAP)
rel = abs(pkg_base - BASE_OBJ) / abs(BASE_OBJ)
print(f"{'calibration objective':28s} notebook {BASE_OBJ:12.4f}  "
      f"package {pkg_base:12.4f}  rel {rel:.1e}")
assert rel < 1e-9, f"the calibration solves disagree by {rel:.2e}"
for s in STAGES:
    assert max(abs(a - b) for a, b in zip(TIER_Q[s], ptq[s])) < 1e-6
    assert max(abs(a - b) for a, b in zip(TIER_M[s], ptm[s])) < 1e-12
print(f"{'tier thresholds and multipliers':28s} identical for all "
      f"{len(STAGES)} stages")
''')

    M(r"""
The calibration agreeing is the precondition; the models themselves are what
matter. This compares each variant's objective, **every cost component
separately** — which is what would catch a channel wired to the wrong term —
and the build plan.
""")

    C(r'''
print(f"{'variant':11s} {'notebook':>12s} {'package':>12s} {'rel':>9s}  "
      f"components  plan")
for lm in ("none", "capacity", "production", "both"):
    a = res[lm]
    b = NC.solve_netcore(nb_st, learning=lm, capex_curve=(pkg_QBP, pkg_CBP),
                         tiers=(ptq, ptm), learn_stages=tuple(LEARN_STAGES),
                         learn_scope=LEARN_SCOPE, n_tiers=N_TIERS,
                         lag_years=LAG_YEARS, pen_short=PEN_SHORT,
                         pen_dispose=PEN_DISPOSE, pen_deviate=PEN_DEVIATE,
                         allow_dispose=True, mipgap=MIPGAP)
    rel = abs(a.ObjVal - b["obj"]) / abs(b["obj"])
    worst_c = max(abs(a._e[k].getValue() - b["components"][k])
                  / max(abs(b["components"][k]), 1.0)
                  for k in ("capex", "operate", "transport", "penalty"))
    nb_plan = {k: round(a._v["size"][k].X, 6)
               for k in BUILD if a._v["build"][k].X > 0.5}
    same = nb_plan == b["plan"]
    print(f"{lm:11s} {a.ObjVal:12.4f} {b['obj']:12.4f} {rel:9.1e}  "
          f"{worst_c:10.1e}  {'same' if same else '** DIFFERS **'}")
    assert rel < 1e-9, f"{lm}: objectives disagree by {rel:.2e}"
    assert worst_c < 1e-9, f"{lm}: a cost component disagrees by {worst_c:.2e}"
    assert same, f"{lm}: same objective, different build plan"

print("\nnotebook and package agree on the calibration, the tiers, all four")
print("objectives, every cost component separately, and all four build plans")
''')

    M(r"""
## 15. Summary

| Question | Answer |
|---|---|
| Do the two channels interfere? | **No** — capex identical under `none`/`production`, opex identical under `production`/`both` |
| Which is worth more? | Channel B, by roughly 15× — opex −18.43% against capex −2.25% |
| Does production learning change the plan? | **No.** Same six builds, same years |
| Does capacity learning? | Barely — one build moves from year 24 to 19 |
| Would a planner overproduce to learn faster? | **No**, at any disposal penalty down to zero and any rate up to 55% |
| When does disposal ever happen? | Only when a local-content floor forces it: 260.46 units at a floor of 160 |
| What does a 160 local-content floor cost? | **+29%**, against ~0% at 110 |

### Formulation lessons

- **A learning channel that multiplies a variable multiplier by a variable
  quantity is bilinear.** Tiers plus a throughput split make it linear again, for
  234 binaries.
- **Define a lag in the unit it means.** Three *years* mapped onto periods stays
  three years; three *periods* silently becomes nine years once the mesh coarsens.
- **A knowledge stock is not discounted.** `cumprod` uses `LEN`, never `OMEGA` —
  it counts units made, not their present value.
- **Split throughput at the coarsest index the rate depends on.** The opex rate
  is vintage-independent, so splitting node-level throughput is exactly
  equivalent to splitting per-vintage and much smaller.
- **Test a negative result by removing the obstacle entirely.** "No disposal at a
  penalty of 12" proves nothing; "no disposal at a penalty of 0, at a 55%
  learning rate" is a finding.
- **Compare plans, not just objectives** — the same lesson Part 3 ends on, and
  here it separates a channel worth 18% of opex from one that changes what you
  build.

### Things to try

- `LAG_YEARS = 0` — instant know-how, and watch the tier transitions jump earlier
- `q1 = top / 2.0` in section 7 — thresholds so high nothing leaves tier 0, and
  section 10's assertion catching it
- `LEARN_SCOPE = 'global'` — one industry-wide production pool instead of
  per-region, so R2 free-rides on R1's experience
- `N_TIERS = 6` — a finer approximation to a smooth curve, and the binary count
  it costs
- `TIER_MIN_PHASE_IN = 1` — a local-content floor from day one, which the legacy
  fleet cannot satisfy

### Where this goes next

**Part 4** takes this chain and hands it to two firms who do not cooperate. The
planner's question — what should be built — becomes an equilibrium question, and
the learning pool that is industry-wide here becomes firm-specific, which turns
out to change the answer far more than either channel here did.
""")

    return out
