"""Build notebooks/01_deterministic.ipynb.

**Subject:** the deterministic multi-period network MILP, and four things that
look like economics but are really modelling choices — how capex is charged, how
finely investment is discretised, what "learning" means, and how much foresight
the model is given.

Section 6 builds the model by hand in its **simplest** form: full horizon, no
rolling-horizon machinery, no learning. That is the model worth reading block by
block. Section 7 wraps it as the full `build()` with every option, and sections 8
to 11 turn those options on one at a time, each with the narration for that
option where it is used rather than all at once in section 6.

Five figures in the original prose were checked against a run and four were
wrong; the corrections and what they were are in the commit message.
"""
from . import common

NOTEBOOK = "01_deterministic.ipynb"
TITLE = "Part 1 - Deterministic multi-period supply chain MILP"


def cells():
    out = []

    def M(text):
        out.append(("md", text.strip("\n")))

    def C(text):
        out.append(("code", text.strip("\n")))

    # ================================ front ================================
    M(r"""
# Part 1 — Deterministic multi-period supply chain MILP

### Four things that look like economics and are really modelling choices

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/USERNAME/lithium-modelling/blob/main/notebooks/01_deterministic.ipynb)

A six-site network — two mines, two processors, two fabricators — serving two
regions over twenty years. One decision maker, perfect information, and lumpy
capacity that must be built in whole units. It is the simplest model in the
series and every later one is built on it.

The interesting content is not the model. It is that **four separate decisions
you have to make while building it will move the answer more than the data
does**:

| section | the choice | what it costs to get wrong |
|---|---|---|
| 8 | charge capex as a lump sum or an annuity | **+26%** on the objective, and 14× more unmet demand |
| 9 | how finely to discretise investment years | up to **+8%**, and not monotone in the number of years |
| 10 | learning: none, exogenous, or endogenous | exogenous is a **free lunch** the model will happily take |
| 11 | foresight window, and whether to ban tail investment | foresight is nearly free; the tail ban costs **+10.9%** |

Each of those is measured below, and each is a number a reader can check against
the output in the cell above it.

### The formulation

**Sets.** Sites $s$ (mines $\cup$ processors $\cup$ fabricators), regions $g$,
years $t$, decision years $v$, unit index $k$.

**Decisions.** $y_{s,v,k}\in\{0,1\}$ — build the $k$-th unit at site $s$, decided
in year $v$. Throughput $x_{s,v,t}\ge 0$, arc flows, and unmet demand $u_{g,t}$.

**Objective.**

$$\min \;\; \underbrace{\sum_{s,v,k}\pi_{s,v}\,c_{s}\,y_{s,v,k}}_{\text{capex}}
\;+\; \sum_t \delta_t\Big[\underbrace{\sum_s o_s x_{s,t}}_{\text{operating}}
+ \underbrace{\sum_{a,b}\tau_{ab}f_{ab,t}}_{\text{transport}}
+ \underbrace{\pi^{u}\sum_g u_{g,t}}_{\text{unmet}}\Big]$$

**The interesting coefficient is $\pi_{s,v}$**, the present value of \$1 of capex
for a facility decided in year $v$. Section 4 derives it, and section 8 shows
that the two defensible ways of computing it disagree by 26%.

### How to read this notebook

Sections 4 to 6 build the model by hand, one idea per cell. Section 7 wraps it
and checks the wrapper reproduces what you built. Section 12 asserts the notebook
and the `lithium` package agree to $10^{-9}$.
""")

    out += common.setup_section(notebook=NOTEBOOK)

    out += common.network_instance_section(agree=12)
    out += common.network_structure_section(agree=12, model=6)

    # ==================== 4. capex timing ==================================
    M(r"""
## 4. Charging capex: the coefficient that decides everything

A facility decided in year $v$ comes online in year $v + \text{lead}_s$ and runs
for `LIFE` years. How much of its cost belongs inside a twenty-year horizon?

Two defensible answers, and they are not close.

**Lump sum.** Pay the whole cost at the decision year, discounted:
$\pi_{s,v} = \delta_v$. Simple, and it charges the model for an asset most of
whose life falls *outside* the horizon.

**Annualised.** Spread the cost over the asset's life with the capital recovery
factor, and charge only the years that fall inside the horizon:
$\pi_{s,v} = \text{CRF}\sum_{t=v+\text{lead}}^{\min(v+\text{lead}+L-1,\,T)}\delta_t$.

The difference is not cosmetic and it is not small — section 8 measures it. Write
the multiplier out for both modes and look at what happens late in the horizon.
""")

    C(r'''
CAPEX_MODES = ("annualized", "lumpsum")

PI = {}
for mode in CAPEX_MODES:
    for s in SITES:
        for v in YEARS:
            online = v + LEAD[s]
            if mode == "lumpsum":
                PI[mode, s, v] = DF.get(v, 0.0)
            else:
                last = min(online + LIFE - 1, T)
                PI[mode, s, v] = (0.0 if last < online else
                                  CRF * sum(DF[t] for t in range(online, last + 1)
                                            if t in DF))

print(f"PV of $1 of capex at site P1 (lead {LEAD['P1']} yrs), by decision year:")
print(f"{'year':>5s} {'annualized':>12s} {'lumpsum':>10s} {'ratio':>8s}")
for v in (1, 5, 10, 15, 18, 20):
    a, l = PI["annualized", "P1", v], PI["lumpsum", "P1", v]
    print(f"{v:5d} {a:12.4f} {l:10.4f} {a / l if l else float('nan'):8.2f}")
''')

    M(r"""
Read the last two rows. By year 18 the annualised multiplier has collapsed —
a processor decided then comes online in year 21, which is **outside the
horizon**, so it is charged nothing and delivers nothing. The lump-sum
multiplier has not collapsed at all: it still charges 41% of the cost, for an
asset the model will never operate.

That asymmetry is the whole of section 8. Lump-sum does not merely cost more —
it **systematically refuses to build late**, and calls that economics.

> **Predict before you run.** Given that, which mode do you expect to leave more
> demand unmet? And by roughly how much — a few per cent, or more?
""")

    # ==================== 5. the learning curve ============================
    M(r"""
## 5. The learning curve, and why SOS2 is mandatory

Capex splits in two: a **site adder** that never gets cheaper, and a
**technology** component that may. Under Wright's law the unit cost of the
technology falls by `LR` per doubling of cumulative capacity $Q$:

$$c(Q) \;=\; \max\Big(c_{\text{floor}},\; (Q/Q_0)^{-b}\Big),
\qquad b = -\log_2(1 - \text{LR})$$

**The model needs the area under that curve, not the curve itself.** Going from
$Q_0$ to $Q$ costs the integral of $c$, because the 401st unit costs what the
curve says at 401 — not what it said at $Q_0$. So integrate numerically and let
the model interpolate between breakpoints.

**And here is the trap.** Cumulative cost $C(Q)$ is **concave**, and it enters a
cost we are **minimising**. A chord between two breakpoints therefore lies
*below* the true curve, so a free convex combination would happily mix
breakpoint 0 with breakpoint 6 and claim a discount that does not exist.
**SOS2** restricts the weights to at most two *adjacent* breakpoints, which is
the interpolation we actually meant.

Without it the model does not fail — it returns a cheaper, wrong answer. That is
the worst kind of bug, and section 10 is where it would have shown up.
""")

    C(r'''
import math

INVEST_YEARS = list(range(1, T + 1, 3))   # section 9 sweeps this; section 6 uses it
NBP = 7          # breakpoints on the cumulative-cost curve
PANELS = 400     # trapezoid panels per breakpoint

# The mesh has to reach as far as cumulative capacity can plausibly go, and that
# depends on how many INVESTMENT years there are - not how many years there are.
QMAX = Q0 + sum(CAP_UNIT[s] * MAX_BUILDS for s in LEARN_SITES) * max(
    1, len(INVEST_YEARS) // 3)
_b = -math.log2(1 - LR)

QBP = [Q0 + (QMAX - Q0) * (i / (NBP - 1)) for i in range(NBP)]
CBP = []
for q in QBP:
    if q <= Q0:
        CBP.append(0.0)
        continue
    h = (q - Q0) / PANELS
    grid = [Q0 + i * h for i in range(PANELS + 1)]
    unit = [max(C_FLOOR_FRAC, (g / Q0) ** (-_b)) for g in grid]
    CBP.append(sum(0.5 * (unit[i] + unit[i + 1]) * h for i in range(PANELS)))

print(f"learning exponent b = {_b:.4f}   (unit cost x2^-b per doubling)")
print(f"{'k':>2s} {'Q (cum capacity)':>18s} {'unit cost':>11s} {'C (cum spend)':>15s}")
for k in range(NBP):
    print(f"{k:2d} {QBP[k]:18.1f} "
          f"{max(C_FLOOR_FRAC, (QBP[k] / Q0) ** (-_b)):11.4f} {CBP[k]:15.2f}")

# the property that makes SOS2 necessary: the chord lies BELOW the curve
mid_chord = 0.5 * (CBP[0] + CBP[-1])
mid_true = CBP[NBP // 2]
assert mid_chord < mid_true, "C(Q) is not concave; the SOS2 argument does not apply"
print(f"\nchord midpoint {mid_chord:.2f} < true midpoint {mid_true:.2f}")
print("-> a free convex combination would understate cost. Hence SOS2.")
''')

    # ==================== 6. the model, by hand ============================
    M(r"""
## 6. The model, built by hand

The next seven cells build the whole thing, one block at a time, in its simplest
form: the full horizon, no learning, and no rolling-horizon machinery. Sections 8
to 11 turn those options on one at a time, with the narration for each where it
is used.

### 6.1 The build decisions, and a symmetry that costs nothing to break

$y_{s,v,k}$ is the $k$-th unit at site $s$ decided in year $v$. The units at one
site in one year are **interchangeable**, so a solver exploring
$(1,0,0)$ and $(0,1,0)$ and $(0,0,1)$ is exploring the same plan three times.
Insisting they are taken in order — $y_{s,v,0}\ge y_{s,v,1}\ge y_{s,v,2}$ —
removes that without removing a single distinct solution.

`INVEST_YEARS` is a knob and section 9 is about it. A decision is only kept if
the asset comes online inside the horizon: deciding in year 19 to build a
processor with a 3-year lead is a decision to build nothing.
""")

    C(r'''
# 1e-3, not the 0.005 this model was written with. At 0.005 the
# lumpsum/endogenous case stops 0.07% above its true optimum, which is
# enough to break section 12's agreement assertion. See 12.1.
MIPGAP = 1e-3

m = gp.Model("deterministic")
m.Params.OutputFlag = 0
m.Params.MIPGap = MIPGAP

# a decision only matters if the asset comes online inside the horizon
SITE_IY = {s: [v for v in INVEST_YEARS if v + LEAD[s] <= T] for s in SITES}

y = {}
for s in SITES:
    for v in SITE_IY[s]:
        for k in range(MAX_BUILDS):
            y[s, v, k] = m.addVar(vtype=GRB.BINARY, ub=1.0, name=f"y_{s}_{v}_{k}")
# symmetry breaking: units at a site-year are interchangeable
for s in SITES:
    for v in SITE_IY[s]:
        for k in range(MAX_BUILDS - 1):
            m.addConstr(y[s, v, k] >= y[s, v, k + 1])

m.update()
print(f"investment years: {INVEST_YEARS}")
for s in SITES:
    dropped = set(INVEST_YEARS) - set(SITE_IY[s])
    print(f"  {s}: lead {LEAD[s]}, usable decision years {SITE_IY[s]}"
          + (f"   (dropped {sorted(dropped)})" if dropped else ""))
print(f"\n{m.NumVars} binaries, {m.NumConstrs} symmetry-breaking constraints")
''')

    M(r"""
### 6.2 What is running in year *t*

A site's capacity in year $t$ comes from three places: the **legacy** units it
started with, which retire on a fixed schedule, and any units **decided** in an
earlier year whose lead time has elapsed and whose life has not.

Building this as a dictionary rather than a function keeps it readable and keeps
the vintage attached: the model needs to know not just *how much* capacity is
running but *which vintage*, because yield depends on it.
""")

    C(r'''
ONLINE = {}
for s in SITES:
    for t in YEARS:
        terms = []
        ln, lv, lret = LEGACY[s]
        if t <= lret:                       # legacy units, until they retire
            terms.append((lv, float(ln)))
        for v in SITE_IY[s]:                # units decided earlier, if online and alive
            on = v + LEAD[s]
            if on <= t <= on + LIFE - 1:
                terms.append((v, gp.quicksum(y[s, v, k] for k in range(MAX_BUILDS))))
        ONLINE[s, t] = terms

print(f"vintages available at P1, year by year:")
for t in (1, 5, 10, 13, 16, 20):
    vs = [v for (v, _) in ONLINE["P1", t]]
    print(f"  year {t:2d}: {vs}"
          + ("   <- legacy retired" if LEGACY['P1'][2] < t else ""))
''')

    M(r"""
### 6.3 Throughput and the arcs between sites

Throughput at a processor or fabricator is indexed **by vintage**, because a
vintage-2 asset and a vintage-13 asset in the same year have different yields and
the model must be able to tell them apart. Mines are not: their yield is a
constant.

Then the arcs: mine → processor, processor → fabricator, fabricator → region, and
a slack variable for demand nobody serves.
""")

    C(r'''
thr = {}
for s in PROCS + FABS:
    for t in YEARS:
        for (v, _) in ONLINE[s, t]:
            if (s, v, t) not in thr:
                thr[s, v, t] = m.addVar(name=f"thr_{s}_{v}_{t}")
ext = {(s, t): m.addVar(name=f"ext_{s}_{t}") for s in MINES for t in YEARS}

fmp = {(a, b, t): m.addVar() for a in MINES for b in PROCS for t in YEARS}
fpf = {(a, b, t): m.addVar() for a in PROCS for b in FABS for t in YEARS}
ffr = {(a, g, t): m.addVar() for a in FABS for g in REGIONS for t in YEARS}
slk = {(g, t): m.addVar() for g in REGIONS for t in YEARS}

m.update()
print(f"{len(thr):5d} vintage-indexed throughput variables")
print(f"{len(ext):5d} mine extraction variables")
print(f"{len(fmp) + len(fpf) + len(ffr):5d} arc flows"
      f"   ({len(fmp)} mine->proc, {len(fpf)} proc->fab, {len(ffr)} fab->region)")
print(f"{len(slk):5d} unmet-demand variables")
print(f"{m.NumVars:5d} variables in total")
''')

    M(r"""
### 6.4 Capacity: you cannot run what you did not build

Two shapes, and the difference matters. A mine's extraction is capped by its
**total** online capacity — one number. A processor's or fabricator's throughput
is capped **per vintage**, because throughput is tracked per vintage.
""")

    C(r'''
for t in YEARS:
    for s in MINES:
        cap = gp.quicksum(n * CAP_UNIT[s] for (_, n) in ONLINE[s, t])
        m.addConstr(ext[s, t] <= cap)
    for s in PROCS + FABS:
        for (v, n) in ONLINE[s, t]:
            m.addConstr(thr[s, v, t] <= n * CAP_UNIT[s])

m.update()
print(f"{m.NumConstrs} constraints after the capacity block")
''')

    M(r"""
### 6.5 Flow balance: what comes out of one tier goes into the next

Four equalities per year, and they are the physical heart of the model.

Ore extracted, times the mining yield, equals what flows to processing. What
flows in equals what processing takes in. What processing *puts out* — its
throughput times a **vintage-dependent** yield — equals what flows to
fabrication. And so on to the regions, where deliveries plus unmet demand must
cover what is demanded.

Note where `ETA` enters: on the **output** side of a tier, never the input. A
tonne fed into an old processor comes out smaller than a tonne fed into a new one.
""")

    C(r'''
for t in YEARS:
    for s in MINES:
        m.addConstr(ETA_MINE * ext[s, t] == gp.quicksum(fmp[s, b, t] for b in PROCS))
    for s in PROCS:
        vints = [v for (v, _) in ONLINE[s, t]]
        m.addConstr(gp.quicksum(fmp[a, s, t] for a in MINES)
                    == gp.quicksum(thr[s, v, t] for v in vints))
        m.addConstr(gp.quicksum(ETA["P", v, t] * thr[s, v, t] for v in vints)
                    == gp.quicksum(fpf[s, b, t] for b in FABS))
    for s in FABS:
        vints = [v for (v, _) in ONLINE[s, t]]
        m.addConstr(gp.quicksum(fpf[a, s, t] for a in PROCS)
                    == gp.quicksum(thr[s, v, t] for v in vints))
        m.addConstr(gp.quicksum(ETA["F", v, t] * thr[s, v, t] for v in vints)
                    == gp.quicksum(ffr[s, g, t] for g in REGIONS))
    for g in REGIONS:
        m.addConstr(gp.quicksum(ffr[f, g, t] for f in FABS) + slk[g, t] >= D[g, t])

m.update()
print(f"{m.NumConstrs} constraints after the flow balance")
print(f"({len(YEARS)} years x ({len(MINES)} mines + 2x{len(PROCS)} procs"
      f" + 2x{len(FABS)} fabs + {len(REGIONS)} regions) added)")
''')

    M(r"""
### 6.6 The capex term

The site adder is charged in every mode. The technology component is charged at a
flat rate here, because this first build uses `learning='none'` — section 10 is
where the other two modes arrive, and where the SOS2 block from section 5 gets
built.

`TECH_RATE` is the average technology cost per unit of capacity across the
learning sites, which is what makes a single learning curve meaningful for
several sites at once.
""")

    C(r'''
LS = set(LEARN_SITES)
ADDER = {s: CAPEX0[s] * (1 - LEARN_FRAC) if s in LS else CAPEX0[s] for s in SITES}
TECH_RATE = sum(CAPEX0[s] * LEARN_FRAC / CAP_UNIT[s] for s in LS) / len(LS)

CAPEX_MODE = "annualized"     # section 8 is about this choice

capex = gp.LinExpr()
for s in SITES:                                    # site adders, every mode
    for v in SITE_IY[s]:
        for k in range(MAX_BUILDS):
            capex += PI[CAPEX_MODE, s, v] * ADDER[s] * y[s, v, k]
for s in LEARN_SITES:                              # technology, flat for 'none'
    for v in SITE_IY[s]:
        for k in range(MAX_BUILDS):
            capex += PI[CAPEX_MODE, s, v] * TECH_RATE * CAP_UNIT[s] * y[s, v, k]

print(f"technology rate {TECH_RATE:.3f} per unit of capacity")
print(f"{'site':6s} {'capex0':>8s} {'site adder':>11s} {'technology':>11s}")
for s in SITES:
    tech = TECH_RATE * CAP_UNIT[s] if s in LS else 0.0
    print(f"{s:6s} {CAPEX0[s]:8.0f} {ADDER[s]:11.1f} {tech:11.1f}"
          + ("" if s in LS else "   <- mining does not learn"))
print(f"\ncapex expression: {capex.size()} linear terms")
''')

    M(r"""
### 6.7 Operating cost, transport, the penalty — and solve

Everything here is an annual flow, so every term carries the discount factor
`DF[t]`. The capex terms above carried `PI` instead, because they are annuities
on a lump rather than flows.

> **Predict before you run.** Demand over the twenty years totals about 5,774
> units, and the penalty for leaving a unit unserved is 45 against an operating
> cost near 6. Will the model serve everything?
""")

    C(r'''
op = gp.LinExpr()
for t in YEARS:
    w = DF[t]
    for s in MINES:
        op += w * OPEX[s] * ext[s, t]
    for s in PROCS + FABS:
        for (v, _) in ONLINE[s, t]:
            op += w * OPEX[s] * thr[s, v, t]
    for a in MINES:
        for b in PROCS:
            op += w * TC[a, b] * fmp[a, b, t]
    for a in PROCS:
        for b in FABS:
            op += w * TC[a, b] * fpf[a, b, t]
    for f in FABS:
        for g in REGIONS:
            op += w * TC_DEM[f, g] * ffr[f, g, t]
    for g in REGIONS:
        op += w * SLACK_PEN * slk[g, t]

m.setObjective(capex + op, GRB.MINIMIZE)
m.update()
assert m.NumVars > 0 and m.NumConstrs > 0, "empty model"
assert m.NumSOS == 0, "learning='none' should add no SOS2 sets"

m.optimize()
assert m.SolCount > 0, f"no solution; status {m.Status}"

hand_built = m.ObjVal
plan = {}
for (s, v, k), var in y.items():
    if var.X > 0.5:
        plan[s, v] = plan.get((s, v), 0) + 1
print(f"status {m.Status}, objective {hand_built:,.1f}, gap {m.MIPGap:.2e}")
print(f"  capex          {capex.getValue():12,.1f}")
print(f"  operating etc  {op.getValue():12,.1f}")
print(f"  units built    {sum(plan.values()):12d}")
print(f"  unmet demand   {sum(v.X for v in slk.values()):12,.2f}"
      f"   of {sum(D.values()):,.0f} demanded")
print(f"\nplan: {dict(sorted(plan.items()))}")
''')

    # ==================== 7. the streamlined version =======================
    M(r"""
## 7. Now the streamlined version

**This is where the notebook crosses from learning into convenience.**

You have written the model once. Sections 8 to 11 need it **about thirty times** —
two capex modes, four investment meshes, three learning modes, five foresight
windows, and a rolling horizon that rebuilds it on every roll.

So the next cell wraps it, with the options those sections need: the capex mode,
the learning mode, an operating window, and the rolling-horizon machinery. Each
option is narrated in the section that uses it, not here.

Then cell 7.1 **proves the wrapper reproduces what you built**.
""")

    C(r'''
def build(invest_years, capex_mode="annualized", learning="none",
          y_start=1, y_end=None, fixed_builds=None, forced_zero_after=None,
          relax_int_after=None, mipgap=MIPGAP):
    """Sections 6.1-6.7, plus the options sections 8-11 turn on."""
    y_end = y_end or T
    yrs = [t for t in YEARS if y_start <= t <= y_end]
    IY = [v for v in invest_years if y_start <= v <= y_end]
    if forced_zero_after is not None:
        IY = [v for v in IY if v <= forced_zero_after]
    site_iy = {s: [v for v in IY if v + LEAD[s] <= y_end] for s in SITES}
    prebuilt = fixed_builds or {}

    mm = gp.Model()
    mm.Params.OutputFlag = 0
    mm.Params.MIPGap = mipgap

    yy = {}
    for s in SITES:
        for v in site_iy[s]:
            for k in range(MAX_BUILDS):
                cont = relax_int_after is not None and v > relax_int_after
                yy[s, v, k] = mm.addVar(
                    vtype=GRB.CONTINUOUS if cont else GRB.BINARY, ub=1.0)
    for s in SITES:
        for v in site_iy[s]:
            for k in range(MAX_BUILDS - 1):
                mm.addConstr(yy[s, v, k] >= yy[s, v, k + 1])

    online = {}
    for s in SITES:
        for t in yrs:
            terms = []
            ln, lv, lret = LEGACY[s]
            if t <= lret:
                terms.append((lv, float(ln)))
            for v in site_iy[s]:
                on = v + LEAD[s]
                if on <= t <= on + LIFE - 1:
                    terms.append((v, gp.quicksum(yy[s, v, k]
                                                 for k in range(MAX_BUILDS))))
            for (ps, pv), n in prebuilt.items():
                if ps == s and pv + LEAD[s] <= t <= pv + LEAD[s] + LIFE - 1:
                    terms.append((pv, n))
            online[s, t] = terms

    th, ex = {}, {}
    for s in PROCS + FABS:
        for t in yrs:
            for (v, _) in online[s, t]:
                if (s, v, t) not in th:
                    th[s, v, t] = mm.addVar()
    for s in MINES:
        for t in yrs:
            ex[s, t] = mm.addVar()
    a_mp = {(a, b, t): mm.addVar() for a in MINES for b in PROCS for t in yrs}
    a_pf = {(a, b, t): mm.addVar() for a in PROCS for b in FABS for t in yrs}
    a_fr = {(a, g, t): mm.addVar() for a in FABS for g in REGIONS for t in yrs}
    sl = {(g, t): mm.addVar() for g in REGIONS for t in yrs}

    # capacity first, then flow balance - the SAME order as section 6, so the
    # two models are not merely equivalent but identically presented. At a 0.5%
    # gap a different presentation can land on a different incumbent, and the
    # 7.1 check would then fail for no reason worth chasing.
    for t in yrs:
        for s in MINES:
            mm.addConstr(ex[s, t] <= gp.quicksum(n * CAP_UNIT[s]
                                                 for (_, n) in online[s, t]))
        for s in PROCS + FABS:
            for (v, n) in online[s, t]:
                mm.addConstr(th[s, v, t] <= n * CAP_UNIT[s])
    for t in yrs:
        for s in MINES:
            mm.addConstr(ETA_MINE * ex[s, t]
                         == gp.quicksum(a_mp[s, b, t] for b in PROCS))
        for s in PROCS:
            vi = [v for (v, _) in online[s, t]]
            mm.addConstr(gp.quicksum(a_mp[a, s, t] for a in MINES)
                         == gp.quicksum(th[s, v, t] for v in vi))
            mm.addConstr(gp.quicksum(ETA["P", v, t] * th[s, v, t] for v in vi)
                         == gp.quicksum(a_pf[s, b, t] for b in FABS))
        for s in FABS:
            vi = [v for (v, _) in online[s, t]]
            mm.addConstr(gp.quicksum(a_pf[a, s, t] for a in PROCS)
                         == gp.quicksum(th[s, v, t] for v in vi))
            mm.addConstr(gp.quicksum(ETA["F", v, t] * th[s, v, t] for v in vi)
                         == gp.quicksum(a_fr[s, g, t] for g in REGIONS))
        for g in REGIONS:
            mm.addConstr(gp.quicksum(a_fr[f, g, t] for f in FABS) + sl[g, t]
                         >= D[g, t])

    cx = gp.LinExpr()
    for s in SITES:
        for v in site_iy[s]:
            pi = (DF.get(v, 0.0) if capex_mode == "lumpsum" else
                  (0.0 if min(v + LEAD[s] + LIFE - 1, y_end) < v + LEAD[s] else
                   CRF * sum(DF[t] for t in range(v + LEAD[s],
                                                  min(v + LEAD[s] + LIFE - 1,
                                                      y_end) + 1) if t in DF)))
            for k in range(MAX_BUILDS):
                cx += pi * ADDER[s] * yy[s, v, k]
            if s in LS and learning in ("none", "exogenous"):
                decay = (1 - G_EXOG) ** (v - 1) if learning == "exogenous" else 1.0
                rate = TECH_RATE * max(decay, C_FLOOR_FRAC)
                for k in range(MAX_BUILDS):
                    cx += pi * rate * CAP_UNIT[s] * yy[s, v, k]

    if learning == "endogenous":
        prevC = None
        for v in sorted({v for s in LS for v in site_iy[s]}):
            Qv = mm.addVar(lb=Q0, ub=QMAX)
            Cv = mm.addVar(lb=0)
            lam = [mm.addVar(lb=0, ub=1) for _ in QBP]
            mm.addConstr(gp.quicksum(lam) == 1)
            mm.addConstr(Qv == gp.quicksum(l * q for l, q in zip(lam, QBP)))
            mm.addConstr(Cv == gp.quicksum(l * c for l, c in zip(lam, CBP)))
            mm.addSOS(GRB.SOS_TYPE2, lam)              # <-- section 5's restriction
            pre = sum(CAP_UNIT[ps] * n for (ps, pv), n in prebuilt.items()
                      if ps in LS and pv <= v)
            mm.addConstr(Qv == Q0 + pre + gp.quicksum(
                CAP_UNIT[s] * yy[s, vv, k] for s in LS for vv in site_iy[s]
                if vv <= v for k in range(MAX_BUILDS)))
            cand = [(DF.get(v, 0.0) if capex_mode == "lumpsum" else
                     CRF * sum(DF[t] for t in range(v + LEAD[s],
                                                    min(v + LEAD[s] + LIFE - 1,
                                                        y_end) + 1) if t in DF))
                    for s in LS if v in site_iy[s]]
            pi = sum(cand) / len(cand) if cand else 0.0
            cx += pi * TECH_RATE * (Cv - (prevC if prevC is not None else 0))
            prevC = Cv

    ope = gp.LinExpr()
    for t in yrs:
        w = DF[t]
        for s in MINES:
            ope += w * OPEX[s] * ex[s, t]
        for s in PROCS + FABS:
            for (v, _) in online[s, t]:
                ope += w * OPEX[s] * th[s, v, t]
        for a in MINES:
            for b in PROCS:
                ope += w * TC[a, b] * a_mp[a, b, t]
        for a in PROCS:
            for b in FABS:
                ope += w * TC[a, b] * a_pf[a, b, t]
        for f in FABS:
            for g in REGIONS:
                ope += w * TC_DEM[f, g] * a_fr[f, g, t]
        for g in REGIONS:
            ope += w * SLACK_PEN * sl[g, t]

    mm.setObjective(cx + ope, GRB.MINIMIZE)
    mm._y, mm._slk = yy, sl
    return mm


def plan_of(mm):
    """{(site, decision year): units} from a solved model."""
    out = {}
    for (s, v, k), var in mm._y.items():
        if var.X > 0.5:
            out[s, v] = out.get((s, v), 0) + 1
    return out


print("build() and plan_of() defined")
''')

    M(r"""
### 7.1 Does the wrapper reproduce the hand-built model?
""")

    C(r'''
check = build(INVEST_YEARS, capex_mode="annualized", learning="none")
check.optimize()
rel = abs(check.ObjVal - hand_built) / abs(hand_built)
print(f"hand-built (section 6.7): {hand_built:,.9f}")
print(f"wrapper    (section 7)  : {check.ObjVal:,.9f}")
assert rel < 1e-9, f"the wrapper is not the model you read; relative gap {rel:.2e}"
assert plan_of(check) == plan, "same objective, different plan - check the symmetry break"
print(f"\nagree to {rel:.1e}, and the build plans match - the wrap is earned")
''')

    # ==================== 8. lump-sum vs annualised ========================
    M(r"""
## 8. Lump-sum versus annualised capex
""")

    C(r'''
rows = []
for mode in CAPEX_MODES:
    mm = build(INVEST_YEARS, capex_mode=mode, learning="none")
    mm.optimize()
    assert mm.SolCount > 0, f"{mode} found no solution"
    pl = plan_of(mm)
    rows.append(dict(capex_mode=mode, objective=round(mm.ObjVal, 1),
                     units_built=sum(pl.values()),
                     last_decision_year=max(v for (_, v) in pl),
                     unmet_demand=round(sum(v.X for v in mm._slk.values()), 2)))
capex_table = pd.DataFrame(rows)

a, l = capex_table.iloc[0], capex_table.iloc[1]
assert l.objective > a.objective, "lump-sum should charge more inside the horizon"
assert l.unmet_demand > a.unmet_demand, "and should therefore serve less"
print(f"lump-sum costs {100 * (l.objective / a.objective - 1):+.1f}% and leaves "
      f"{l.unmet_demand / a.unmet_demand:.1f}x more demand unmet")
print(f"latest build decision: annualised year {a.last_decision_year}, "
      f"lump-sum year {l.last_decision_year} "
      f"(investment years are {INVEST_YEARS})")
capex_table
''')

    M(r"""
**Lump-sum abandons the end of the horizon.** Its last build decision is year 13,
against annualised's year 16 — it walks away from two of the seven investment
opportunities. And it leaves **342.4 units of demand unmet against 23.7**, 14.4
times more, while costing 26.4% more overall.

That is not economics. It is an accounting artefact of **truncating the horizon
while charging the full asset cost**: a facility decided in year 13 runs for
twenty years, of which the model sees seven, but lump-sum bills it for all twenty.
Annualised bills it for the seven it sees.

Two caveats for a real model. Use the **same $r$** in the CRF as in the objective,
or you reintroduce a wedge by the back door. And **lock the capital charge at the
vintage's cost** — do not let it float down as later learning occurs, or an asset
gets cheaper after it is built.

One honest counter-caveat: annualising removes the anti-late-build bias so
completely that you will see builds right at the horizon edge. That is correct if
capacity can effectively be rented, but if it is lumpy and irreversible you want
an explicit salvage term, or a **cool-down buffer** — model to year 30, report to
year 20.
""")

    # ==================== 9. investment granularity ========================
    M(r"""
## 9. How finely should investment be discretised?

Every investment year multiplies the binary count by the number of sites times
`MAX_BUILDS`. Fewer years means a smaller, faster model — and a coarser answer.

> **Predict before you run.** Four meshes: every year, a staggered mesh (annual
> early, coarse late), every third year, every fifth. Rank them by objective
> before you look. Does more investment years always mean a better answer?
""")

    C(r'''
import time

MESHES = [("annual", list(range(1, T + 1))),
          ("staggered", [1, 2, 3, 4, 5, 6, 7, 9, 11, 16]),
          ("every 3rd", list(range(1, T + 1, 3))),
          ("every 5th", list(range(1, T + 1, 5)))]

rows = []
for name, iy in MESHES:
    t0 = time.time()
    mm = build(iy, capex_mode="annualized", learning="none")
    mm.optimize()
    assert mm.SolCount > 0, f"{name} found no solution"
    rows.append(dict(mesh=name, invest_years=len(iy), objective=round(mm.ObjVal, 1),
                     binaries=mm.NumBinVars, variables=mm.NumVars,
                     seconds=round(time.time() - t0, 1)))
mesh_table = pd.DataFrame(rows)

best = mesh_table.loc[mesh_table.objective.idxmin()]
print(f"best objective: {best.mesh} at {best.objective:,.1f} "
      f"with {best.invest_years} investment years and {best.binaries} binaries")
stag = mesh_table[mesh_table.mesh == "staggered"].iloc[0]
e3 = mesh_table[mesh_table.mesh == "every 3rd"].iloc[0]
print(f"but 'staggered' has {stag.invest_years} years and {stag.binaries} binaries "
      f"and scores {stag.objective:,.1f},")
print(f"while 'every 3rd' has {e3.invest_years} years and {e3.binaries} binaries "
      f"and scores {e3.objective:,.1f} - BETTER with fewer of both.")
mesh_table
''')

    M(r"""
**More investment years is not better.** The staggered mesh has 10 investment
years and 180 binaries; every-third has 7 and 108, and scores **1.3% lower**
(47,885.9 against 48,539.7). Fewer decisions, fewer binaries, and a better
answer.

The reason is that the meshes are **not nested**. Staggered runs annually through
year 7 and then jumps to 9, 11, 16; every-third reaches 19. Staggered spends its
resolution early, where the legacy fleet has not yet retired and there is little
to decide, and has none left for the late-horizon replacement wave. Placement
beats count — which is the same lesson as the revenue mesh in Part 4c-exact, one
model family over.

That is a correction to what this notebook used to say. It claimed the staggered
mesh "buys most of the speedup of uniform 5-year periods at a fraction of the
accuracy cost, because it puts binaries where decisions actually bind". The first
half is true — staggered does beat every-fifth, 48,539.7 against 50,180.8. The
explanation is not: on this instance the binaries are *not* where decisions bind,
and a uniform every-third mesh with fewer binaries beats it.

**The practical rule is therefore weaker and more honest than "stagger it":**
sweep the mesh, and do not assume a cleverly-shaped one dominates a uniform one.
The annual mesh is the reference at 46,311.3, and every coarser mesh pays
something against it — 3.4% for every-third, 4.8% for staggered, 8.4% for
every-fifth. Note that ordering: the *uniform* coarse mesh with 7 years beats the
shaped one with 10.
""")

    # ==================== 10. learning modes ===============================
    M(r"""
## 10. Learning: none, exogenous, endogenous

Three ways to model technology getting cheaper, and they encode three different
beliefs.

- **none** — it does not.
- **exogenous** — it gets cheaper with *time*, at `G_EXOG` a year, whatever you
  build.
- **endogenous** — it gets cheaper with *cumulative capacity*, which you only get
  by building. This is the one that needs section 5's SOS2.

> **Predict before you run.** Rank the three by objective. Which should be
> cheapest, and is "cheapest" the same as "most realistic"?
""")

    C(r'''
rows = []
for mode in ("none", "exogenous", "endogenous"):
    mm = build(INVEST_YEARS, capex_mode="annualized", learning=mode)
    mm.optimize()
    assert mm.SolCount > 0, f"learning={mode} found no solution"
    mm.update()
    pl = plan_of(mm)
    rows.append(dict(learning=mode, objective=round(mm.ObjVal, 1),
                     sos2_sets=mm.NumSOS, units_built=sum(pl.values()),
                     last_decision_year=max(v for (_, v) in pl)))
learn_table = pd.DataFrame(rows)

none_, exo, endo = (learn_table.iloc[i].objective for i in range(3))
assert learn_table.iloc[0].sos2_sets == 0 and learn_table.iloc[2].sos2_sets > 0, \
    "only endogenous learning should add SOS2 sets"
assert exo < none_ and endo < none_, "learning should never raise cost"
assert exo < endo, "exogenous is the free lunch; it should undercut endogenous"
print(f"none       {none_:10,.1f}")
print(f"exogenous  {exo:10,.1f}  ({100 * (exo / none_ - 1):+.2f}%)")
print(f"endogenous {endo:10,.1f}  ({100 * (endo / none_ - 1):+.2f}%)"
      f"   <- more expensive than exogenous, and that is the point")
learn_table
''')

    M(r"""
**Exogenous is the cheapest of the three, and that is the free lunch.** At
46,266.2 it undercuts endogenous learning's 46,903.1 by 1.4%, because it hands
the model a cost reduction requiring **no deployment at all**. A model that
believes costs fall by themselves is a model that systematically prefers to
*wait*.

Endogenous sits between "none" and "exogenous": the reduction is real, but it has
to be earned by building. Note the `sos2_sets` column — 6 sets, one per
investment year in which a learning site can be built, and zero in the other two
modes. Those are what stop the convex combination claiming a discount off the
chord, and section 5 is why.

In this instance build *timing* barely shifts: all three modes build 18 units and
stop deciding in year 16. **Legacy retirements dominate the learning signal at
this learning rate.** Raise `LR` toward 0.35 and re-run to see timing move — that
sensitivity is itself the finding. Your model is usually more sensitive to the
learning rate than to the discount rate, and the learning rate has much the
weaker empirical grounding.
""")

    # ==================== 11. foresight ====================================
    M(r"""
## 11. Perfect foresight versus a rolling horizon

Everything so far assumed the planner sees all twenty years. A rolling horizon
sees `W` years, commits `delta` of them, and rolls forward — which is both more
realistic and a way to make a large model tractable.

Two questions, and the second turns out to matter far more than the first.
""")

    C(r'''
def rolling(W, delta, invest_step=3, decision_zone=None, tail_continuous=True):
    """Re-solve on a moving window, committing `delta` years at a time."""
    committed, log, start = {}, [], 1
    while start <= T:
        y_end = min(start + W - 1, T)
        dz = y_end if decision_zone is None else min(start + decision_zone - 1, y_end)
        iy = [v for v in range(start, y_end + 1) if (v - 1) % invest_step == 0]
        kw = dict(capex_mode="annualized", y_start=start, y_end=y_end,
                  fixed_builds=dict(committed))
        kw["relax_int_after" if tail_continuous else "forced_zero_after"] = dz
        mm = build(iy, **kw)
        mm.optimize()
        if mm.SolCount == 0:
            log.append((start, y_end, "INFEASIBLE"))
            break
        for (s, v, k), var in mm._y.items():
            if v <= start + delta - 1 and var.X > 0.5:
                committed[s, v] = committed.get((s, v), 0) + 1
        start += delta
        log.append((start, y_end, dz))
    return committed, log


def cost_of(plan_dict):
    """Cost of a FIXED plan under the full-horizon model, operations re-optimised.

    build() charges nothing for prebuilt capacity, so the plan's own capex has to
    be added back. Forgetting that would make every plan look free.
    """
    mm = build([], capex_mode="annualized", learning="none", fixed_builds=plan_dict)
    mm.optimize()
    if mm.SolCount == 0:
        return None
    extra = 0.0
    for (s, v), n in plan_dict.items():
        pi = PI["annualized", s, v]
        unit = (ADDER[s] + TECH_RATE * CAP_UNIT[s]) if s in LS else CAPEX0[s]
        extra += n * unit * pi
    return mm.ObjVal + extra


print("rolling() and cost_of() defined")
''')

    M(r"""
### 11.1 How much foresight is enough?

> **Predict before you run.** Lead times here are 2 and 3 years and assets live
> 20. How short can the window get before the answer degrades?
""")

    C(r'''
pf = build(INVEST_YEARS, capex_mode="annualized", learning="none")
pf.optimize()
pf_cost = pf.ObjVal

rows = []
for W in (3, 4, 5, 6, 8, 10, 20):
    plan_w, _ = rolling(W=W, delta=3, invest_step=3)
    c = cost_of(plan_w)
    rows.append(dict(window=W, cost=round(c, 1),
                     vs_PF_pct=round(100 * (c / pf_cost - 1), 2),
                     units_built=sum(plan_w.values())))
fore_table = pd.DataFrame(rows)

assert fore_table.iloc[0].vs_PF_pct > 10, \
    "W=3 was expected to be far off; the hard floor claim needs re-checking"
assert fore_table.iloc[-1].vs_PF_pct < 0.1, "W=20 should reproduce perfect foresight"
print(f"perfect foresight: {pf_cost:,.1f}")
print(f"W=3 is {fore_table.iloc[0].vs_PF_pct:+.1f}% and builds only "
      f"{fore_table.iloc[0].units_built} units; W>=5 is within "
      f"{fore_table[fore_table.window >= 5].vs_PF_pct.max():.2f}%")
fore_table
''')

    M(r"""
**There is a hard floor, and above it foresight is nearly free.**

At `W = 3` the model is **74.6% worse** and builds **4 units instead of 18**.
The window is shorter than a processor's lead time plus enough operating years
for the annuity to register, so long-lead assets never look worth building and
the model simply does not build them. That is not a foresight *cost*, it is an
artefact — and misreading it as a result is the trap.

At `W = 4` it is +13.5%. **From `W = 5` onward every window reproduces perfect
foresight exactly** — 47,885.9 and 18 units at 5, 6, 8, 10 and 20.

So the honest summary is the opposite of a "foresight cliff" story: once the
window clears the lead time, **seeing five years ahead is as good as seeing
twenty** on this instance, to the last decimal place.

One caution worth internalising anyway. A single perfect-foresight solve at a
0.1% gap gives a genuine 0.1% bound on the whole answer, whereas a *sequence* of
0.1%-gap solves compounds error across rolls and gives **no bound at all**. The
exact agreement above is a property of this instance, not a guarantee — which is
why the cell asserts the floor and the plateau rather than the individual
numbers.
""")

    M(r"""
### 11.2 The artefact that actually costs something

A decision zone shorter than the window confines binaries to the near term while
the tail runs as pure LP. That is where a rolling horizon's speedup really lives.

But **do not hard-prohibit investment in the tail.** Forcing many years of
capacity growth into a few years of building causes systematic over-investment,
and it is a *belief inconsistency*: the first solve assumes it can never build
after the zone ends, while the second and third demonstrably will.

> **Predict before you run.** Same 3-year decision zone either way. One relaxes
> the tail to continuous capacity; the other bans it. How much can that be worth?
""")

    C(r'''
rows = []
for tail in (True, False):
    plan_t, _ = rolling(W=8, delta=3, invest_step=3, decision_zone=3,
                        tail_continuous=tail)
    c = cost_of(plan_t)
    early = sum(n for (s, v), n in plan_t.items() if v <= 6)
    rows.append(dict(tail="continuous" if tail else "banned",
                     cost=round(c, 1), vs_PF_pct=round(100 * (c / pf_cost - 1), 2),
                     units_built=sum(plan_t.values()), built_in_years_1_6=early))
tail_table = pd.DataFrame(rows)

cont, ban = tail_table.iloc[0], tail_table.iloc[1]
assert ban.vs_PF_pct > cont.vs_PF_pct, "banning the tail should cost something"
assert ban.built_in_years_1_6 > cont.built_in_years_1_6, \
    "and should pull building forward"
print(f"banning tail investment costs {ban.vs_PF_pct - cont.vs_PF_pct:+.2f} "
      f"percentage points against PF,")
print(f"and pulls building forward: {cont.built_in_years_1_6} units in years 1-6 "
      f"becomes {ban.built_in_years_1_6}")
tail_table
''')

    M(r"""
**Banning tail investment costs +10.9% against perfect foresight**, where
relaxing the tail to continuous costs **exactly nothing** — 47,885.9, the
perfect-foresight answer to the decimal. All of the gap comes from one modelling
choice that looks like a harmless tractability trick.

And the mechanism is visible in the last column: **building in years 1–6 triples,
2 units becoming 6.** The model, believing it can never build after year 3, front-
loads capacity it does not need yet — then the next roll builds more anyway,
because the ban was never true.

Relaxing the tail to *continuous* capacity — no binaries, no siting lumpiness,
but the model knows it can build later — eliminates the artefact while keeping
the entire binary reduction. Longer decision zones mask the problem, which is
exactly why it ships undetected.

Two corrections to what this notebook used to claim here. It said the ban costs
"**~+22%**" — it costs +10.9%. And it said the ban "roughly doubles early builds"
— it triples them, 2 to 6. The direction was right in both cases and the
magnitudes were not.
""")

    # ==================== 12. agreement ====================================
    M(r"""
## 12. The agreement assertion

Everything above was built by hand, and `src/lithium/core.py` holds the same
model as functions. **The same model exists twice, deliberately** — and
deliberate duplication with nothing comparing the copies is how a bug gets fixed
in three places out of four.

This cell imports the package, hands it the same instance dictionaries and the
same knobs, runs the same case as section 6.7, and asserts the two objectives
agree to $10^{-9}$.
""")

    C(r'''
from lithium import NetworkInstance, build_core_structure
from lithium import build as pkg_build

nb_instance = NetworkInstance(
    regions=tuple(REGIONS), mines=tuple(MINES), procs=tuple(PROCS),
    fabs=tuple(FABS), tier=TIER, home=HOME, cap_unit=CAP_UNIT, lead=LEAD,
    capex0=CAPEX0, opex=OPEX, legacy=LEGACY,
    eta_bar=ETA_BAR, eta_0=ETA_0, alpha=ALPHA, beta=BETA, dbar=DBAR,
    demand_base=DEMAND_BASE, demand_growth=DEMAND_GROWTH,
)
nb_struct = build_core_structure(
    nb_instance, T=T, r=r, life=LIFE, max_builds=MAX_BUILDS,
    eta_mine=ETA_MINE, eta_min=ETA_MIN,
    transport_own=TRANSPORT_OWN, transport_cross=TRANSPORT_CROSS,
    slack_pen=SLACK_PEN, learn_tiers=LEARN_TIERS, learn_frac=LEARN_FRAC,
    lr=LR, q0=Q0, c_floor_frac=C_FLOOR_FRAC, g_exog=G_EXOG,
)

packaged = pkg_build(nb_struct, invest_years=INVEST_YEARS,
                     capex_mode="annualized", learning="none", mipgap=MIPGAP)
packaged.optimize()

rel = abs(packaged.ObjVal - hand_built) / abs(hand_built)
print(f"notebook (section 6.7, by hand): {hand_built:,.9f}")
print(f"package  (lithium.core)        : {packaged.ObjVal:,.9f}")
assert rel < 1e-9, f"notebook and package disagree by {rel:.2e}"
print(f"notebook and package agree to {rel:.1e}\n")

# ...and every OTHER mode too. Checking one case is not checking the model:
# section 6.7 uses learning='none', which never touches the learning mesh, so a
# wrong QMAX sails straight past a single-case assertion. It did, once - see 12.2.
print(f"{'capex mode':12s} {'learning':12s} {'notebook':>14s} {'package':>14s} {'rel':>9s}")
for cm in CAPEX_MODES:
    for lm in ("none", "exogenous", "endogenous"):
        a = build(INVEST_YEARS, capex_mode=cm, learning=lm)
        a.optimize()
        b = pkg_build(nb_struct, invest_years=INVEST_YEARS, capex_mode=cm,
                      learning=lm, mipgap=MIPGAP)
        b.optimize()
        rel = abs(a.ObjVal - b.ObjVal) / abs(b.ObjVal)
        print(f"{cm:12s} {lm:12s} {a.ObjVal:14,.4f} {b.ObjVal:14,.4f} {rel:9.1e}")
        assert rel < 1e-9, f"{cm}/{lm} disagrees by {rel:.2e}"
print("\nall six capex-mode x learning-mode combinations agree")
''')

    M(r"""
### 12.1 What the wider check caught

That table is wider than it needs to look, and it caught **two** things the
single-case assertion above sailed straight past. Section 6.7 uses
`learning='none'` and `capex_mode='annualized'`, so one green check says nothing
about the other five combinations.

**One.** The notebook was sizing `QMAX` off `len(YEARS)` where the package sizes
it off `len(INVEST_YEARS)` — a different mesh, a different interpolation, and a
different answer for both endogenous cases. A one-line fix that nothing would
have found.

**Two.** With that fixed, `lumpsum/endogenous` still disagreed, by 7.4e-04. Not a
specification difference this time: the 0.005 MIP gap this model was written with
stops that one case 0.07% above its true optimum, while every other combination
lands exactly. Tightening to 1e-3 makes all six agree and costs about eight
seconds. It also moved the annual-mesh figure in section 9 from 46,353.6 to
46,311.3, and sharpened section 11 — at 0.005 the foresight plateau wobbled in
the fourth decimal, and at 1e-3 every window from 5 up is *exactly* the
perfect-foresight answer.

**A number that moves when you change a tolerance is not a result yet**, and a
check that only ever exercises one configuration will not tell you which of your
numbers those are.

### 12.2 And the derived structure, not just the objective

The objective agreeing is strong evidence but not complete: two different `ETA`
tables could in principle produce the same optimum. Compare the derivations
directly.
""")

    C(r'''
worst_eta = max(abs(ETA[k] - nb_struct.ETA[k]) for k in ETA)
worst_d = max(abs(D[k] - nb_struct.D[k]) for k in D)
worst_pi = max(abs(PI["annualized", s, v]
                   - __import__("lithium").capex_pv_multiplier(
                       nb_struct, s, v, "annualized"))
               for s in SITES for v in YEARS)
print(f"{'ETA (%d entries)' % len(ETA):28s} max abs diff {worst_eta:.2e}")
print(f"{'demand (%d entries)' % len(D):28s} max abs diff {worst_d:.2e}")
print(f"{'capex PV multiplier':28s} max abs diff {worst_pi:.2e}")
print(f"{'CRF':28s} max abs diff {abs(CRF - nb_struct.crf):.2e}")
for name, w in (("ETA", worst_eta), ("D", worst_d), ("PI", worst_pi)):
    assert w < 1e-12, f"{name} derivations disagree by {w:.2e}"
print("\nevery derivation agrees, not just the optimum")
''')

    M(r"""
### 12.4 And the rolling horizon, which a cost comparison would not have caught

Everything above compares a **cost**. Section 8's rolling horizon returns a
**committed plan**, assembled one window at a time, and that is a different kind
of thing to check: each window commits discrete builds, so a disagreement does
not shift the answer slightly — it commits a different plan, and the difference
compounds across every window that follows.

It is also the one part of this notebook the cell above could not see, and it
drifted. `lithium.core.rolling_horizon` had no `mipgap` argument, so it solved
every window at the package default of 0.005 while `rolling()` here uses
`MIPGAP` = 0.001. At W=3 that commits **5 units instead of 4** and reports
+73.5% against perfect foresight instead of +74.6% — a number that appears in
this notebook's prose.

**The lesson is about what an assertion covers, not about a MIP gap.** A check on
one number is a check on one code path. The paths it does not touch are exactly
where a second copy is free to drift, and the drift is invisible precisely
because everything that *is* checked still passes.
""")

    C(r'''
from lithium import rolling_horizon as pkg_rolling
from lithium import evaluate_plan as pkg_evaluate_plan

print(f"{'W':>3s} {'notebook':>12s} {'package':>12s} {'units':>7s}  plans match?")
for W in (3, 4, 5, 8, 20):
    nb_plan, _ = rolling(W=W, delta=3, invest_step=3)
    pk_plan, _ = pkg_rolling(nb_struct, W=W, delta=3, invest_step=3,
                             mipgap=MIPGAP)
    nb_c = cost_of(nb_plan)
    pk_c = pkg_evaluate_plan(nb_struct, pk_plan, mipgap=MIPGAP)
    same = nb_plan == pk_plan
    print(f"{W:3d} {nb_c:12,.1f} {pk_c:12,.1f} {sum(nb_plan.values()):7d}  {same}")
    assert same, f"W={W}: the committed plans differ, not merely their cost"
    assert abs(nb_c - pk_c) / abs(nb_c) < 1e-9, f"W={W}: costs differ"
print("\nthe rolling horizon agrees on the PLAN, not merely on the cost")
''')

    M(r"""
## 13. Summary

| Question | Answer |
|---|---|
| Lump-sum or annualised capex? | **Annualised.** Lump-sum costs +26.4%, leaves 14.4× more demand unmet, and abandons the last two investment years |
| Does a cleverer investment mesh beat a uniform one? | **Not here.** Staggered has 10 years and 180 binaries and loses to every-third's 7 and 108 |
| Which learning mode is cheapest? | **Exogenous** — because it is a free lunch, not because it is right |
| How much foresight is needed? | Above a hard floor at W=5, none at all — W≥5 reproduces PF exactly. W=3 is +74.6% and an artefact |
| What actually costs money? | **Banning tail investment: +10.9%**, and it triples early building |

### Formulation lessons

- **The capex coefficient is a modelling choice with a 26% price tag.** Charging
  an asset's whole cost inside a horizon it outlives makes the model refuse to
  build late, and that looks like economics.
- **Concave cost, minimised, needs SOS2.** Without it the model returns a
  cheaper, wrong answer and reports success. Compare Part 4c, where the same
  shape in a *maximisation* needs nothing.
- **More decision variables is not a better model.** Placement beats count, and
  the only way to know is to sweep.
- **Exogenous learning is a free lunch and models will take it.** Prefer
  endogenous, and be more careful with the learning rate than with the discount
  rate.
- **A sequence of gap-tolerant solves has no bound.** One solve at 0.1% bounds
  the answer at 0.1%; seven rolls at 0.1% bound nothing.
- **Check every configuration, not one.** Section 12's six-way loop found a wrong
  learning mesh and a too-loose MIP gap that the single-case check had passed.
- **Do not hard-prohibit what a later solve will do anyway.** The tail ban is a
  belief inconsistency, and it is the most expensive mistake in this notebook.

### Things to try

- `LR = 0.35` — a stronger learning rate; section 10 says build *timing* should
  start to move, and this is where you check that
- `SLACK_PEN = 200` — make unmet demand nearly unthinkable and watch lump-sum's
  refusal to build late become very expensive
- `MESHES` with `[1, 4, 7, 10, 13, 16, 19]` replaced by a mesh of your own — can
  you beat every-third with ten years rather than seven?
- `decision_zone=6` in section 11.2 — longer zones mask the tail-ban artefact,
  which is exactly why it ships undetected

### Where this goes next

**Part 2 — stochastic.** The same network, with demand growth uncertain. The
build plan must be chosen before the uncertainty resolves, which is what
nonanticipativity means, and progressive hedging is how a problem too big for one
solve gets decomposed.
""")

    return out
