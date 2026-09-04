"""Build notebooks/02_stochastic.ipynb.

**Subject:** two-stage stochastic programming on Part 1's network — the extensive
form and its nonanticipativity constraints, then progressive hedging for when
that stops fitting.

**The narrative is rebuilt around what the model actually does.** The original
told a vivid story: the mean-value plan under-builds and is "catastrophic" in the
high-growth scenario, with a shortfall "an order of magnitude worse" than the
stochastic plan's. On the shipped configuration that is not true — EV and SP leave
*identical* shortfalls and VSS is 4.48 out of 34,138, or 0.013%.

The reason turns out to be the more interesting lesson, and section 10 is built
on it: only year 1 is stage-1, so the plan can adapt at years 4, 7 and 10, and
there is almost nothing locked in to hedge. Lock more in and VSS rises — 0.013%,
0.342%, 1.121% as stage 1 grows — and at [1, 4, 7] the under-building story
appears exactly as described. **VSS measures how much of the uncertainty you have
committed to before it resolves, which is a modelling choice as much as a
property of the data.**
"""
from . import common

NOTEBOOK = "02_stochastic.ipynb"
TITLE = "Part 2 - Two-stage stochastic programming and progressive hedging"


def cells():
    out = []

    def M(text):
        out.append(("md", text.strip("\n")))

    def C(text):
        out.append(("code", text.strip("\n")))

    # ================================ front ================================
    M(r"""
# Part 2 — Two-stage stochastic programming, and progressive hedging

### What it is worth knowing the future, and what it is worth admitting you don't

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/sear-labs/advopt-lithiumsc/blob/main/notebooks/02_stochastic.ipynb)

Part 1's network, with one thing changed: **Region 2's demand growth is
uncertain**. Three scenarios, known probabilities, and a build plan for year 1
that must be chosen **before** anyone finds out which world they are in.

That last clause is the entire subject. Without it this is Part 1 solved three
times.

### Four quantities, and keeping them straight is most of the work

| | what it is | achievable? |
|---|---|---|
| **WS** | each scenario solved knowing which one it is, then averaged | **No** — it needs information nobody has |
| **RP** | one stage-1 plan, stage 2 re-optimised per scenario | Yes. This is what stochastic programming buys |
| **EEV** | the *mean-demand* plan, evaluated the same way | Yes. This is planning for the average and hoping |

$$\text{EVPI} = \text{RP} - \text{WS} \qquad\qquad \text{VSS} = \text{EEV} - \text{RP}$$

EVPI is the value of a crystal ball. VSS is the value of *modelling the
uncertainty at all* — and unlike EVPI, it is entirely under your control.

**Theory says $\text{WS} \le \text{RP} \le \text{EEV}$.** Section 8 computes all
three through identical machinery and asserts the chain, because the easiest way
to get this wrong produces a *negative* VSS, which is impossible.

### What this notebook found, which is not what it used to say

VSS on the shipped configuration is **0.013%** — essentially nothing. Section 9
reports that honestly and section 10 explains it: with only year 1 committed and
years 4, 7 and 10 free to react, there is almost nothing locked in to hedge. Lock
more in and VSS climbs to 1.1%. That is the finding.

### How to read this notebook

Section 4 carries Part 1's model over, marked. Sections 5, 7 and 12 build the new
material by hand — the scenario tree, the extensive form's nonanticipativity
constraints, and progressive hedging. Section 15 asserts the notebook and the
`lithium` package agree to $10^{-9}$.
""")

    out += common.setup_section(notebook=NOTEBOOK)

    # ============================ 1. the switch ============================
    M(r"""
## 1. A runtime switch, on by default

This notebook solves a lot of MILPs: a scenario tree, three strategy
evaluations, a stage-1 sweep, a $\rho$ sweep, and a block-asynchrony comparison.
At full settings that is several minutes, which is more than a lecture has.

`QUICK = True` drops a single redundant $\rho$ from section 12's sweep. It
changes **no** headline number — every figure quoted in the prose comes from a
cell that runs either way — and the cell below prints exactly what it dropped.

It is deliberately a small saving, because the first version of this switch was
wrong in an instructive way. It also trimmed the $\rho$ range to
`[100, 300, 3000]`, which looks harmless and is not: dropping $\rho = 30$ removes
the only evidence that the good setting is *interior*, and section 12's assertion
failed on exactly that. **A quick switch may trim cost. It may not trim the
lesson**, and the difference is not always obvious from the parameter list.
""")

    C(r'''
QUICK = True     # False for the full sweeps

# QUICK drops only rho = 1000, which duplicates a conclusion rho = 30 already
# carries. It does NOT touch the stage-1 sweep: that sweep is section 9's
# finding, and trimming it would be trimming the lesson rather than the cost.
RHO_SWEEP = [30, 100, 300, 3000] if QUICK else [30, 100, 300, 1000, 3000]
STAGE1_SWEEP = [[1], [1, 4], [1, 4, 7], [1, 4, 7, 10]]
PH_ITERS = 40    # unchanged by QUICK: the rho sweep's conclusions depend on it

print(f"QUICK = {QUICK}")
print(f"  rho sweep      : {RHO_SWEEP}"
      + ("   (full adds 1000)" if QUICK else ""))
print(f"  stage-1 sweep  : {[str(s) for s in STAGE1_SWEEP]}   (never trimmed)")
print(f"  PH iterations  : {PH_ITERS}   (never trimmed)")
if QUICK:
    print("\nEvery number quoted in the prose still comes from a cell that runs.")
    print("Set QUICK = False to add rho = 1000, which lands where rho = 30 does.")
''')

    out += common.network_instance_section(agree=15)
    out += common.network_structure_section(agree=15, model=4, horizon=12)

    # ==================== 4. carried over from Part 1 ======================
    M(r"""
## 4. Carried over from Part 1: the network model

The model itself is unchanged and is narrated cell by cell in
`01_deterministic.ipynb` sections 4 to 6. Re-narrating it here would bury what
this notebook is about, so it arrives as a wrapper under a `CARRIED OVER` marker.

**Three arguments are new**, and they are the ones this notebook needs:

- `demand` — solve the same network against a *scenario's* demand rather than the
  deterministic path.
- `into` and `prefix` — build this network **into an existing model** under a name
  prefix, instead of into a fresh one. That is what lets section 7 put three
  copies of the whole network into one model, which is what an extensive form is.

If you have not read 01's sections 4 to 6, read them before this cell.
""")

    C(r'''
# CARRIED OVER FROM 01_deterministic SECTIONS 4-6 - narrated there, not re-taught
# here. `demand`, `into` and `prefix` are the additions this notebook needs.
import math
import time

INVEST_YEARS = list(range(1, T + 1, 3))     # [1, 4, 7, 10] on a 12-year horizon
STAGE1_YEARS = [1]                          # what must be decided before we know
MIPGAP = 1e-6                               # tight: section 8 compares expectations

NBP, PANELS = 7, 400
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

LS = set(LEARN_SITES)
ADDER = {s: CAPEX0[s] * (1 - LEARN_FRAC) if s in LS else CAPEX0[s] for s in SITES}
TECH_RATE = sum(CAPEX0[s] * LEARN_FRAC / CAP_UNIT[s] for s in LS) / len(LS)


def build(invest_years, demand=None, into=None, prefix="", mipgap=MIPGAP,
          capex_mode="annualized", learning="none"):
    """01_deterministic sections 4-6, plus demand / into / prefix."""
    yrs, IY = YEARS, list(invest_years)
    site_iy = {s: [v for v in IY if v + LEAD[s] <= T] for s in SITES}
    Dd = demand if demand is not None else D
    m = into if into is not None else gp.Model()
    if into is None:
        m.Params.OutputFlag = 0
        m.Params.MIPGap = mipgap

    yy = {}
    for s in SITES:
        for v in site_iy[s]:
            for k in range(MAX_BUILDS):
                yy[s, v, k] = m.addVar(vtype=GRB.BINARY, ub=1.0,
                                       name=f"{prefix}y_{s}_{v}_{k}")
    for s in SITES:
        for v in site_iy[s]:
            for k in range(MAX_BUILDS - 1):
                m.addConstr(yy[s, v, k] >= yy[s, v, k + 1])

    online = {}
    for s in SITES:
        for t in yrs:
            terms = []
            ln, lv, lret = LEGACY[s]
            if t <= lret:
                terms.append((lv, float(ln)))
            for v in site_iy[s]:
                if v + LEAD[s] <= t <= v + LEAD[s] + LIFE - 1:
                    terms.append((v, gp.quicksum(yy[s, v, k]
                                                 for k in range(MAX_BUILDS))))
            online[s, t] = terms

    th, ex = {}, {}
    for s in PROCS + FABS:
        for t in yrs:
            for (v, _) in online[s, t]:
                if (s, v, t) not in th:
                    th[s, v, t] = m.addVar(name=f"{prefix}thr_{s}_{v}_{t}")
    for s in MINES:
        for t in yrs:
            ex[s, t] = m.addVar(name=f"{prefix}ext_{s}_{t}")
    a_mp = {(a, b, t): m.addVar() for a in MINES for b in PROCS for t in yrs}
    a_pf = {(a, b, t): m.addVar() for a in PROCS for b in FABS for t in yrs}
    a_fr = {(a, g, t): m.addVar() for a in FABS for g in REGIONS for t in yrs}
    sl = {(g, t): m.addVar() for g in REGIONS for t in yrs}

    for t in yrs:
        for s in MINES:
            m.addConstr(ex[s, t] <= gp.quicksum(n * CAP_UNIT[s]
                                                for (_, n) in online[s, t]))
        for s in PROCS + FABS:
            for (v, n) in online[s, t]:
                m.addConstr(th[s, v, t] <= n * CAP_UNIT[s])
    for t in yrs:
        for s in MINES:
            m.addConstr(ETA_MINE * ex[s, t]
                        == gp.quicksum(a_mp[s, b, t] for b in PROCS))
        for s in PROCS:
            vi = [v for (v, _) in online[s, t]]
            m.addConstr(gp.quicksum(a_mp[a, s, t] for a in MINES)
                        == gp.quicksum(th[s, v, t] for v in vi))
            m.addConstr(gp.quicksum(ETA["P", v, t] * th[s, v, t] for v in vi)
                        == gp.quicksum(a_pf[s, b, t] for b in FABS))
        for s in FABS:
            vi = [v for (v, _) in online[s, t]]
            m.addConstr(gp.quicksum(a_pf[a, s, t] for a in PROCS)
                        == gp.quicksum(th[s, v, t] for v in vi))
            m.addConstr(gp.quicksum(ETA["F", v, t] * th[s, v, t] for v in vi)
                        == gp.quicksum(a_fr[s, g, t] for g in REGIONS))
        for g in REGIONS:
            m.addConstr(gp.quicksum(a_fr[f, g, t] for f in FABS) + sl[g, t]
                        >= Dd[g, t])

    cx = gp.LinExpr()
    for s in SITES:
        for v in site_iy[s]:
            last = min(v + LEAD[s] + LIFE - 1, T)
            pi = (0.0 if last < v + LEAD[s] else
                  CRF * sum(DF[t] for t in range(v + LEAD[s], last + 1) if t in DF))
            for k in range(MAX_BUILDS):
                cx += pi * ADDER[s] * yy[s, v, k]
            if s in LS:
                for k in range(MAX_BUILDS):
                    cx += pi * TECH_RATE * CAP_UNIT[s] * yy[s, v, k]

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

    if into is None:
        m.setObjective(cx + ope, GRB.MINIMIZE)
    m._y, m._slk, m._capex_expr, m._op_expr = yy, sl, cx, ope
    if into is not None:
        return m, yy, cx + ope, sl
    return m


def plan_of(mm):
    out = {}
    for (s, v, k), var in mm._y.items():
        if var.X > 0.5:
            out[s, v] = out.get((s, v), 0) + 1
    return out


print(f"carried over. horizon {T} years, investment years {INVEST_YEARS},")
print(f"stage-1 years {STAGE1_YEARS} - only those are decided before we know.")
''')

    # ==================== 5. the scenario tree =============================
    M(r"""
## 5. The scenario tree

New material starts here, and it is deliberately small.

**These are not random draws and this is not Monte Carlo.** Three hand-specified
demand paths with assigned probabilities — a coarse *discretisation* of a
growth-rate distribution.

Three things to be clear about.

**Only Region 2 is uncertain.** Region 1's demand is known exactly, which keeps
the uncertainty one-dimensional and legible. The cell asserts it, because a tree
in which everything varies is a different model.

**The uncertain quantity is a single parameter** — the growth *rate*, not
per-year noise. Within a scenario the future is perfectly known, so each path is a
smooth exponential. Year-on-year shocks, correlated regional demand or price
uncertainty would all need a genuine multistage tree.

**Three scenarios is tiny.** Real practice runs dozens to hundreds, usually Monte
Carlo draws followed by scenario reduction. EVPI and VSS from three points are
coarse estimates, not converged ones — section 11 shows why three is what fits.
""")

    C(r'''
GROWTHS = [(0.010, 0.30), (0.070, 0.40), (0.140, 0.30)]
R2_BASE = 105.0     # the scenario set is a what-if, not the base case relabelled

SCENS = []
for j, (g, p) in enumerate(GROWTHS):
    Ds = {}
    for t in YEARS:
        Ds["R1", t] = D["R1", t]                     # R1 known
        Ds["R2", t] = R2_BASE * ((1 + g) ** (t - 1))  # R2 uncertain
    SCENS.append((f"s{j}_g{g:.3f}", p, Ds))

assert abs(sum(p for _, p, _ in SCENS) - 1.0) < 1e-12, "probabilities must sum to 1"
r1_paths = {tuple(v for (k, v) in sorted(Ds.items()) if k[0] == "R1")
            for _, _, Ds in SCENS}
assert len(r1_paths) == 1, "R1 differs across scenarios; it is meant to be known"

print(f"{'scenario':12s} {'prob':>5s} {'R2 growth':>10s} "
      f"{'R2 yr 1':>9s} {'R2 yr ' + str(T):>9s}")
for (nm, p, Ds), (g, _) in zip(SCENS, GROWTHS):
    print(f"{nm:12s} {p:5.2f} {g:10.3f} {Ds['R2', 1]:9.1f} {Ds['R2', T]:9.1f}")
print(f"\nR1 is identical in all three: {D['R1', 1]:.1f} rising to {D['R1', T]:.1f}")
''')

    M(r"""
### 5.1 Is there anything to hedge?

If every scenario wanted the same year-1 decision there would be no problem to
solve. Solve each one on its own and look at what it wants.

> **Predict before you run.** Low growth is 1% a year and high growth is 14%.
> Will they disagree about what to build in **year 1**, or only about later years?
""")

    C(r'''
rows = []
for nm, p, Ds in SCENS:
    m = build(INVEST_YEARS, demand=Ds)
    m.optimize()
    assert m.SolCount > 0, f"{nm} found no solution"
    pl = plan_of(m)
    rows.append(dict(scenario=nm, prob=p, cost=round(m.ObjVal, 1),
                     total_builds=sum(pl.values()),
                     year1_builds=sum(n for (s, v), n in pl.items() if v == 1),
                     unmet=round(sum(v.X for v in m._slk.values()), 2)))
hedge_table = pd.DataFrame(rows)

y1 = set(hedge_table.year1_builds)
assert len(y1) > 1, "every scenario wants the same year-1 plan; nothing to hedge"
print(f"year-1 builds wanted: {list(hedge_table.year1_builds)} - they disagree,")
print("so there is a genuine decision to make before the uncertainty resolves.")
hedge_table
''')

    M(r"""
**Genuine disagreement.** Low growth builds nothing in year 1 and 4 units in
total; high growth builds 2 in year 1 and 20 in total. The year-1 decision has to
be made before knowing which world you are in, and the assertion above would fail
if that were not so — in which case this notebook would have nothing to say.

Notice also the cost spread: 23,985 to 45,608. Nearly a factor of two, from one
uncertain growth rate.
""")

    # ==================== 7. the extensive form ============================
    M(r"""
## 6. The extensive form, built by hand

One monolithic MILP containing **all three scenarios at once**. Each gets its own
complete copy of the network — that is what `into` and `prefix` are for — and the
copies are tied together by one block of constraints.

$$y^{(1)}_{s,v,k} \;=\; y^{(j)}_{s,v,k}
\qquad \forall\, v \in \text{stage 1},\; \forall\, j \ne 1$$

**Those equalities are the model.** They say: whatever you build in year 1, you
build the same thing in every world, because in year 1 you do not know which
world you are in. That is **nonanticipativity**, and without it this is three
independent problems wearing one objective — which is the wait-and-see bound, not
a stochastic program.

Everything *not* in stage 1 is free to differ between scenarios. That is
**recourse**: the ability to react once you know. Section 10 is about how much of
it you have.
""")

    C(r'''
ef = gp.Model("extensive_form")
ef.Params.OutputFlag = 0
ef.Params.MIPGap = MIPGAP

ys, objs = [], gp.LinExpr()
for (nm, p, Ds) in SCENS:
    _, y_s, obj_s, _ = build(INVEST_YEARS, demand=Ds, into=ef, prefix=nm + "_")
    ys.append(y_s)
    objs += p * obj_s          # probability-weighted, so the objective is E[cost]
ef.update()
before = ef.NumConstrs

# nonanticipativity: stage-1 builds identical across scenarios
for key in ys[0]:
    if key[1] in STAGE1_YEARS:
        for j in range(1, len(ys)):
            ef.addConstr(ys[0][key] == ys[j][key], name=f"NA_{key}_{j}")
ef.update()

n_s1 = len([k for k in ys[0] if k[1] in STAGE1_YEARS])
n_na = ef.NumConstrs - before
print(f"{len(SCENS)} scenario copies: {ef.NumVars} variables, {before} constraints")
print(f"nonanticipativity added {n_na} constraints"
      f"  = {n_s1} stage-1 keys x {len(SCENS) - 1} scenario pairs")
assert n_na == n_s1 * (len(SCENS) - 1), "the NA block is not the right size"

ef.setObjective(objs, GRB.MINIMIZE)
ef.optimize()
assert ef.SolCount > 0, f"no solution; status {ef.Status}"
print(f"\nextensive form objective E[cost] = {ef.ObjVal:,.4f}")
''')

    # ==================== 8. the three strategies ==========================
    M(r"""
## 7. The three strategies — and a trap worth naming

All three numbers must be **evaluated expectations produced by identical
machinery**:

| Case | How it is computed |
|---|---|
| **PI** (WS) | solve each scenario deterministically, probability-weight |
| **SP** (RP) | take stage 1 from the extensive form, **fix it**, re-optimise stage 2 per scenario, weight |
| **EV** (EEV) | take stage 1 from the **mean-demand** problem, **fix it**, re-optimise stage 2 per scenario, weight |

**The trap:** reading RP straight off `ef.ObjVal` while EEV comes from the
evaluation path. Those are not the same measurement. A MILP terminated at a gap
reports an objective *above* the true optimum, while the evaluation path
re-solves stage 2 to optimality for a fixed stage 1 — systematically tighter.
Mix the two and you can produce a **negative VSS**, which is impossible, since the
EV stage-1 decision is feasible for the stochastic problem and therefore cannot
beat it.

So everything below goes through one path, and the check is that
**`RP` evaluated equals `ef.ObjVal`**. That equality is the assertion that the
plumbing is right, and the cell makes it.

> **Predict before you run.** Before looking: how much do you expect the hedge to
> be worth here — a few per cent of total cost, or less?
""")

    C(r'''
# THE FUNCTION IS THE LESSON: this section's whole point is that the three
# strategies are measured by IDENTICAL machinery. Writing the evaluation out
# three times by hand would let the three paths drift, which is exactly the
# bug described above and the one that produces an impossible negative VSS.
def evaluate(s1_fix, scens):
    """Fix a stage-1 strategy; re-optimise stage 2 in EVERY scenario separately."""
    rows = []
    for (nm, p, Ds) in scens:
        m = build(INVEST_YEARS, demand=Ds)
        for k, val in s1_fix.items():
            if k in m._y:
                m._y[k].LB = m._y[k].UB = (1 if val > 0.5 else 0)
        m.optimize()
        rows.append(dict(scenario=nm, prob=p, cost=m.ObjVal,
                         unmet=sum(v.X for v in m._slk.values())))
    return rows


def perfect_info(scens):
    rows = []
    for (nm, p, Ds) in scens:
        m = build(INVEST_YEARS, demand=Ds)
        m.optimize()
        rows.append(dict(scenario=nm, prob=p, cost=m.ObjVal,
                         unmet=sum(v.X for v in m._slk.values())))
    return rows


def mean_value_plan(scens, stage1_years):
    """The stage-1 decision you get by planning for average demand."""
    Dm = {key: sum(p * Ds[key] for (_, p, Ds) in scens) for key in scens[0][2]}
    m = build(INVEST_YEARS, demand=Dm)
    m.optimize()
    return {k: m._y[k].X for k in m._y if k[1] in stage1_years}


sp_fix = {k: ys[0][k].X for k in ys[0] if k[1] in STAGE1_YEARS}
ev_fix = mean_value_plan(SCENS, STAGE1_YEARS)
per = {"PI": perfect_info(SCENS), "SP": evaluate(sp_fix, SCENS),
       "EV": evaluate(ev_fix, SCENS)}
exp = {k: sum(r["prob"] * r["cost"] for r in v) for k, v in per.items()}
WS, RP, EEV = exp["PI"], exp["SP"], exp["EV"]

# the plumbing assertion: RP evaluated must be the extensive form's own objective
assert abs(RP - ef.ObjVal) / abs(ef.ObjVal) < 1e-6, (
    f"RP evaluated ({RP:,.4f}) != ef.ObjVal ({ef.ObjVal:,.4f}); the two paths "
    f"are not measuring the same thing")
# and the theory
assert WS <= RP + 1e-6, "wait-and-see is not a lower bound; something is wrong"
assert RP <= EEV + 1e-6, "the mean-value plan beat the stochastic plan; impossible"

print(f"WS  {WS:12,.2f}   (a bound nobody can achieve)")
print(f"RP  {RP:12,.2f}   = ef.ObjVal {ef.ObjVal:,.2f}  <- the plumbing check")
print(f"EEV {EEV:12,.2f}\n")
print(f"EVPI = RP - WS  = {RP - WS:9,.2f}  ({100 * (RP - WS) / RP:.3f}% of RP)")
print(f"VSS  = EEV - RP = {EEV - RP:9,.2f}  ({100 * (EEV - RP) / RP:.3f}% of RP)")
''')

    M(r"""
### 7.1 The three strategies, scenario by scenario

The expectations hide what the strategies actually do. This is the detail, and it
carries a check the aggregate cannot: **in every individual scenario, perfect
information must be at least as cheap as either strategy.** PI is that scenario's
own optimum, so nothing can beat it there. If a strategy ever did, the strategy
would be solving a different problem from the one PI solved.
""")

    C(r'''
detail = pd.DataFrame([
    dict(scenario=pi["scenario"], prob=pi["prob"],
         PI_cost=round(pi["cost"], 1), SP_cost=round(sp["cost"], 1),
         EV_cost=round(ev["cost"], 1), PI_unmet=round(pi["unmet"], 2),
         SP_unmet=round(sp["unmet"], 2), EV_unmet=round(ev["unmet"], 2))
    for pi, sp, ev in zip(per["PI"], per["SP"], per["EV"])])

# per scenario, perfect information cannot be beaten
for pi, sp, ev in zip(per["PI"], per["SP"], per["EV"]):
    assert pi["cost"] <= sp["cost"] + 1e-6 and pi["cost"] <= ev["cost"] + 1e-6, \
        f"{pi['scenario']}: perfect information lost to a strategy"
print("per scenario, PI <= SP and PI <= EV in every case")
detail
''')

    # ==================== 9. what the numbers say ==========================
    M(r"""
## 8. What the numbers actually say

**EVPI is 528.25, or 1.55% of RP.** That is the value of a crystal ball, and it
is real: knowing which world you are in ahead of time would save about a
percent and a half.

**VSS is 4.48, or 0.013% of RP.** That is the value of doing stochastic
programming at all rather than planning for the average — and here it is
essentially nothing.

Look at the detail table before accepting that. The two strategies leave
**identical** shortfalls in every scenario, and their costs differ only in the
low-growth world, by 31 units on a cost of 25,682.5. The mean-value plan and the
stochastic plan are, for practical purposes, the same plan.

**This notebook used to claim otherwise**, in some detail: that the EV strategy
"under-builds", is "catastrophic" in the high-growth scenario, and leaves a
shortfall "an order of magnitude worse" than SP's. On this configuration none of
that is true — the high-scenario shortfalls are 69.40 and 69.40, a ratio of
exactly 1.0.

A near-zero VSS is a legitimate result and it has to be reported, not narrated
around. But it is worth asking *why*, because the answer is the more useful
lesson and it is not about the data.
""")

    # ==================== 10. the finding ==================================
    M(r"""
## 9. Why VSS is nearly zero: how much is actually locked in

`STAGE1_YEARS = [1]`. Only year 1 is committed before the uncertainty resolves.
Years 4, 7 and 10 are **recourse** — the plan can react to whichever world
appeared, three years in, long before high growth compounds into a real shortage.

With that much freedom to adapt, there is very little to hedge, and a plan built
for average demand is nearly as good as one built for the distribution.

So make the commitment longer and watch. This is a **modelling** choice, not a
data one: nothing about the scenarios changes.

> **Predict before you run.** As more years move into stage 1, what happens to
> WS? And to VSS?
""")

    C(r'''
rows = []
for s1 in STAGE1_SWEEP:
    ef_s = gp.Model()
    ef_s.Params.OutputFlag = 0
    ef_s.Params.MIPGap = MIPGAP
    ys_s, obj_s = [], gp.LinExpr()
    for (nm, p, Ds) in SCENS:
        _, y_s, o_s, _ = build(INVEST_YEARS, demand=Ds, into=ef_s, prefix=nm + "_")
        ys_s.append(y_s)
        obj_s += p * o_s
    for key in ys_s[0]:
        if key[1] in s1:
            for j in range(1, len(ys_s)):
                ef_s.addConstr(ys_s[0][key] == ys_s[j][key])
    ef_s.setObjective(obj_s, GRB.MINIMIZE)
    ef_s.optimize()
    sp_f = {k: ys_s[0][k].X for k in ys_s[0] if k[1] in s1}
    ev_f = mean_value_plan(SCENS, s1)
    p_sp, p_ev = evaluate(sp_f, SCENS), evaluate(ev_f, SCENS)
    ws = sum(r["prob"] * r["cost"] for r in per["PI"])       # unchanged by s1
    rp = sum(r["prob"] * r["cost"] for r in p_sp)
    eev = sum(r["prob"] * r["cost"] for r in p_ev)
    rows.append(dict(stage1_years=str(s1), WS=round(ws, 1), RP=round(rp, 1),
                     EEV=round(eev, 1), VSS=round(eev - rp, 2),
                     VSS_pct=round(100 * (eev - rp) / rp, 3),
                     hi_unmet_SP=round(p_sp[-1]["unmet"], 1),
                     hi_unmet_EV=round(p_ev[-1]["unmet"], 1)))
lock_table = pd.DataFrame(rows)

# WS cannot depend on the stage-1 set: wait-and-see ignores nonanticipativity
assert lock_table.WS.nunique() == 1, \
    "WS moved when stage 1 changed; it must not - that would be a plumbing bug"
assert lock_table.VSS_pct.iloc[-1] > lock_table.VSS_pct.iloc[0], \
    "locking more in did not raise VSS; the section's explanation is wrong"
print(f"WS is {lock_table.WS.iloc[0]:,.1f} in every row, as it must be:")
print("wait-and-see never sees a nonanticipativity constraint.\n")
print(f"VSS rises {lock_table.VSS_pct.iloc[0]:.3f}% -> "
      f"{lock_table.VSS_pct.iloc[-1]:.3f}% as the commitment lengthens")
lock_table
''')

    M(r"""
**There it is.** VSS climbs from 0.013% with only year 1 committed, to 0.342%
with years 1 and 4, to **1.121%** with years 1, 4 and 7 — a factor of nearly 90.
Same scenarios, same probabilities, same network; only the amount you must commit
before knowing.

The last row falls back to 0.751%, and that is not noise. `INVEST_YEARS` is
`[1, 4, 7, 10]`, so at that setting **every** build decision is stage 1 and there
is no recourse left at all. EEV cannot move — it is the same fully-committed
mean-value plan as the row above, 37,804.6 in both — while RP rises from 37,385.4
to 37,522.9 as the stochastic plan loses its last freedom too. The gap between
them narrows. VSS is largest in the middle, where the stochastic plan still has
flexibility that the mean-value plan wastes.

And at `[1, 4, 7]` the story the notebook used to tell **does** appear. The
high-growth shortfall is **731.5 under the mean-value plan against 510.3 under
the stochastic plan** — EV under-builds and eats the penalty, exactly as
described. It just needs the commitment to be long enough for that to matter.

Two things worth taking from this.

**WS is identical in every row**, and the cell asserts it. Wait-and-see solves
each scenario in full knowledge and never sees a nonanticipativity constraint, so
it cannot depend on which years are stage 1. If it ever moved, the plumbing would
be wrong — it is a free and very sharp check.

**VSS is not a property of your data.** It is a property of your data *and* how
much of the decision you have to commit before the uncertainty resolves. A model
with generous recourse will report that stochastic programming is not worth much,
and it will be telling the truth about that model. Whether that model is the right
one is a separate question, and a more important one.
""")

    # ==================== 11. why decomposition ============================
    M(r"""
## 10. Why decomposition is needed

The extensive form replicates the entire network once per scenario, so it grows
linearly in the scenario count. Three scenarios is not a modelling choice here —
it is what fits.
""")

    C(r'''
one = build(INVEST_YEARS)
one.update()
print(f"one deterministic scenario: {one.NumVars} variables, "
      f"{one.NumBinVars} binaries")
print(f"the extensive form above  : {ef.NumVars} variables "
      f"({len(SCENS)} x {one.NumVars})\n")
print(f"{'scenarios':>10s} {'~variables':>12s}   vs the restricted licence's ~2,000")
for n in (3, 5, 6, 10, 20, 50):
    v = one.NumVars * n
    print(f"{n:10d} {v:12d}   {'over' if v > 2000 else 'fits'}")
first_over = next(n for n in range(1, 100) if one.NumVars * n > 2000)
print(f"\nthe monolithic model stops fitting at n = {first_over}.")
print("Progressive hedging never builds it, so it has no such ceiling.")
''')

    # ==================== 12. progressive hedging ==========================
    M(r"""
## 11. Progressive hedging, built by hand

Instead of one model containing every scenario, solve each scenario **separately**
and make them negotiate their way to agreement.

Each iteration: solve every scenario against a penalty for disagreeing with the
current consensus $z$; average the answers into a new $z$; update the multipliers
$w$. Repeat until the disagreement is small.

$$\min_{x_i} \; f_i(x_i) \;+\; w_i^\top x_i \;+\; \tfrac{\rho}{2}\lVert x_i - z\rVert^2
\qquad\qquad z \leftarrow \sum_i p_i x_i$$

**And here is the trick that makes it work at all.** That quadratic penalty would
make every subproblem a **MIQP** — which, per this repo's `README.md`, does not
fit a restricted licence at anything but toy size. But stage-1 $x$ is **binary**,
and for binary $x$, $x^2 = x$. So

$$\tfrac{\rho}{2}\lVert x - z\rVert^2 \;=\; \tfrac{\rho}{2}\big[x(1 - 2z) + z^2\big]$$

which is **linear**. The subproblems stay MILPs. The cell asserts it: a
subproblem with quadratic terms would mean the linearisation was lost.
""")

    C(r'''
# THE FUNCTION IS THE LESSON: progressive hedging is an iterative algorithm.
# Its structure -- solve, average, update multipliers, repeat -- cannot be
# written out inline, and sections 12 and 13 need to call it at eight settings.
# Every line inside is narrated above; nothing here is hidden convenience.
def progressive_hedging(scens, stage1_years, rho, iters, tol=1e-4, block_frac=1.0):
    """Solve the scenarios separately; agree by negotiation. Never builds the
    monolithic model, so it has no size ceiling."""
    subs = []
    for (nm, p, Ds) in scens:
        m = build(INVEST_YEARS, demand=Ds)
        m._base_obj = m._capex_expr + m._op_expr
        subs.append((nm, p, m))
    n = len(subs)
    keys = [k for k in subs[0][2]._y if k[1] in stage1_years]
    w = [{k: 0.0 for k in keys} for _ in range(n)]
    xv = [{k: 0.0 for k in keys} for _ in range(n)]
    z = {k: 0.0 for k in keys}
    hist, solved, cursor = [], 0, 0
    nblock = max(1, int(round(block_frac * n)))

    for it in range(iters):
        if it == 0 or nblock >= n:
            I = list(range(n))                  # everyone, to seed every x_i
        else:
            # deterministic round-robin, NOT a random sample: fairness requires
            # every scenario to be revisited within a bounded number of
            # iterations, and random sampling does not guarantee that
            I = [(cursor + j) % n for j in range(nblock)]
            cursor = (cursor + nblock) % n
        for i in I:
            nm, p, m = subs[i]
            obj = gp.LinExpr(m._base_obj)
            for k in keys:
                obj += w[i][k] * m._y[k]                       # Lagrange term
                obj += 0.5 * rho * (m._y[k] * (1 - 2 * z[k])   # LINEARISED penalty
                                    + z[k] ** 2)
            m.setObjective(obj, GRB.MINIMIZE)
            m.optimize()
            solved += 1
            for k in keys:
                xv[i][k] = m._y[k].X
        z = {k: sum(subs[i][1] * xv[i][k] for i in range(n)) for k in keys}
        for i in range(n):
            for k in keys:
                w[i][k] += rho * (xv[i][k] - z[k])
        resid = math.sqrt(sum(subs[i][1] * (xv[i][k] - z[k]) ** 2
                              for i in range(n) for k in keys))
        hist.append(resid)
        if resid < tol and it > 0:
            break
    return dict(z=z, resid=hist, iters=len(hist), subsolves=solved, rho=rho)


# the linearisation, asserted: a subproblem must have NO quadratic terms
probe = build(INVEST_YEARS, demand=SCENS[0][2])
probe.update()
assert probe.NumQNZs == 0, "a subproblem picked up quadratic terms"
print(f"a PH subproblem: {probe.NumVars} vars, {probe.NumQNZs} quadratic terms")
print("zero quadratic terms - the x^2 = x linearisation is holding, so these")
print("stay MILPs and stay inside a restricted licence.")
''')

    # ==================== 13. the rho sweep ================================
    M(r"""
## 12. The $\rho$ sweep, and why you cannot skip it

$\rho$ is the penalty weight. Too small and the scenarios never agree; too large
and they snap to whatever they agreed on first.

> **Predict before you run.** Is there a monotone relationship between $\rho$ and
> solution quality — bigger is more agreement, so better? Write down yes or no.
""")

    C(r'''
rows = []
for rho in RHO_SWEEP:
    t0 = time.time()
    ph = progressive_hedging(SCENS, STAGE1_YEARS, rho=rho, iters=PH_ITERS)
    z_round = {k: (1.0 if v > 0.5 else 0.0) for k, v in ph["z"].items()}
    cost = sum(x["prob"] * x["cost"] for x in evaluate(z_round, SCENS))
    rows.append(dict(rho=rho, iterations=ph["iters"],
                     final_residual=round(ph["resid"][-1], 5),
                     evaluated_cost=round(cost, 1),
                     vs_RP_pct=round(100 * (cost / RP - 1), 3),
                     seconds=round(time.time() - t0, 1)))
rho_table = pd.DataFrame(rows)

ibest = rho_table.vs_RP_pct.idxmin()
best, worst = rho_table.loc[ibest], rho_table.loc[rho_table.vs_RP_pct.idxmax()]
# The claim is not "big rho is bad" - it is that the good setting is INTERIOR,
# so neither end of the range finds it and you have no choice but to sweep.
assert 0 < ibest < len(rho_table) - 1, (
    f"the best rho was at an end of the range ({best.rho}); this section's "
    f"point is that it is interior, which is why a sweep is unavoidable")
print(f"best  rho={best.rho:>5}  {best.vs_RP_pct:+.3f}% off RP"
      f"   <- interior: neither the smallest nor the largest rho found it")
print(f"worst rho={worst.rho:>5}  {worst.vs_RP_pct:+.3f}% off RP"
      f"   (terminated after {worst.iterations} iterations)")
rho_table
''')

    M(r"""
**The good setting is interior, and the assertion above requires that.** Neither
the smallest $\rho$ nor the largest finds it — $\rho = 30$ lands at +0.146% and
$\rho = 3000$ at +0.677%, while $\rho = 100$ and $\rho = 300$ sit at +0.013%.
Quality is not monotone in $\rho$, so there is no direction to push in and no
way to avoid sweeping.

The best setting recovers the extensive-form answer to **+0.013%**, which is
close enough to be useful. The largest $\rho$ is the instructive failure: it
terminates after **2 iterations** with a residual of exactly zero — perfect
agreement — and lands **+0.677%** off. It did not converge to a good answer; it
forced the scenarios to agree on the first thing they happened to agree on, and
then reported success.

**A zero residual is not a quality guarantee.** It says the scenarios agree, not
that they agree on anything good. That is the single most useful thing on this
page.

This is the practical cost of PH on **mixed-integer** problems. PH's convergence
proof covers **convex** problems with a compact feasible set; on MILPs it is a
*heuristic*, though with adjustments it yields valid Lagrangian lower bounds
(Gade et al. 2016; Boland et al. 2018). Never deploy PH on a MILP without a $\rho$
sweep and a termination rule that does not assume convergence.
""")

    # ==================== 14. block asynchrony =============================
    M(r"""
## 13. Block-asynchronous operation

The expensive part of each iteration is solving every subproblem. The
APH-style variant re-solves only a **subset** each round.

The subset is a **deterministic round-robin**, not a random sample. Fairness —
every scenario revisited within a bounded number of iterations — is what the
convergence argument needs, and random sampling does not guarantee it. It also
makes the result reproducible, which is why there is no seed anywhere in this
notebook: **nothing here is random.**

> **Predict before you run.** Solving two thirds of the subproblems each round,
> then one third: does the answer degrade a little, a lot, or not at all?
""")

    C(r'''
rows = []
for bf in (1.0, 0.67, 0.34):
    ph = progressive_hedging(SCENS, STAGE1_YEARS, rho=300, iters=20, block_frac=bf)
    z_round = {k: (1.0 if v > 0.5 else 0.0) for k, v in ph["z"].items()}
    cost = sum(x["prob"] * x["cost"] for x in evaluate(z_round, SCENS))
    rows.append(dict(block_frac=bf, subproblem_solves=ph["subsolves"],
                     iterations=ph["iters"],
                     final_residual=round(ph["resid"][-1], 5),
                     evaluated_cost=round(cost, 1),
                     vs_RP_pct=round(100 * (cost / RP - 1), 4)))
block_table = pd.DataFrame(rows)

full, part = block_table.iloc[0], block_table.iloc[-1]
assert part.subproblem_solves < full.subproblem_solves, \
    "the block variant solved no fewer subproblems, so it saved nothing"
# The honest finding: skipping subproblems is an APPROXIMATION, not a free
# saving. An earlier version of this cell asserted the answer was unchanged.
# It appeared to hold only because the subproblems were being solved at a
# 0.005 MIP gap - larger than the differences being measured.
assert block_table.vs_RP_pct.nunique() > 1, (
    "every block fraction returned exactly the same cost. That is what a MIP "
    "gap looser than the quantity being measured looks like; check it before "
    "believing the saving is free")
print(f"solves: {full.subproblem_solves} -> {part.subproblem_solves} "
      f"({100 * (1 - part.subproblem_solves / full.subproblem_solves):.0f}% fewer)")
print(f"quality: {full.vs_RP_pct:+.4f}% -> {part.vs_RP_pct:+.4f}%   NOT free")
block_table
''')

    M(r"""
**Skipping subproblems is not free, and the numbers are worth staring at.**

At `block_frac = 0.67` the run costs **41 solves instead of 60** and lands at
**+0.0000%** — it recovers the extensive-form optimum *exactly*, doing less work
than the full version, which itself sits at +0.0131%. At `block_frac = 0.34` the
saving is bigger, **22 solves**, and the answer degrades to **+1.3896%** — twice
as bad as the worst $\rho$ in section 12.

So less work produced a better answer once and a much worse one once. There is no
monotone relationship here either, and no defensible way to pick `block_frac`
without measuring it on your own problem.

**This section previously claimed the opposite** — 63% fewer solves for an
identical answer — and the cell asserted it. That assertion passed because the
subproblems were being solved at a **0.005** MIP gap, which is far larger than
the 0.01% differences being compared: every configuration returned the same
number because the solver was not being asked for a precise one. Tightening the
gap to $10^{-6}$ made all three separate. The assertion above is now the reverse:
it *fails* if every block fraction agrees exactly, because on this problem that
is the signature of a gap too loose to measure what is being claimed.

With three scenarios on one core this is still a toy demonstration of the
mechanism. The margin widens as the ratio of scenarios to cores grows; the source
work tests it at 20,000 to 1,000,000 scenarios on 48 to 6,000 cores.

Note what block-asynchrony does **not** fix. It changes the cost of the
coordination loop. It is no remedy at all for the $\rho$ sensitivity in section
12 — a badly chosen $\rho$ converges to the same poor answer, just faster.
""")

    # ==================== 15. agreement ====================================
    M(r"""
## 14. The agreement assertion

Everything above was built by hand, and `src/lithium/stochastic.py` holds the
same models as functions. **The same model exists twice, deliberately** — and
deliberate duplication with nothing comparing the copies is how a bug gets fixed
in three places out of four.

This checks more than one number, because Part 1 taught that lesson the hard way:
a single-case assertion there passed while the notebook and the package disagreed
on two other configurations. So this compares the scenario tree, the extensive
form, all three expectations, and progressive hedging's consensus vector.
""")

    C(r'''
from lithium import NetworkInstance, build_core_structure
from lithium import stochastic as S

nb_instance = NetworkInstance(
    regions=tuple(REGIONS), mines=tuple(MINES), procs=tuple(PROCS),
    fabs=tuple(FABS), tier=TIER, home=HOME, cap_unit=CAP_UNIT, lead=LEAD,
    capex0=CAPEX0, opex=OPEX, legacy=LEGACY,
    eta_bar=ETA_BAR, eta_0=ETA_0, alpha=ALPHA, beta=BETA, dbar=DBAR,
    demand_base=DEMAND_BASE, demand_growth=DEMAND_GROWTH,
)
nb_struct = build_core_structure(
    nb_instance, T=T, r=r, life=LIFE, max_builds=MAX_BUILDS,
    eta_mine=ETA_MINE, eta_min=ETA_MIN, transport_own=TRANSPORT_OWN,
    transport_cross=TRANSPORT_CROSS, slack_pen=SLACK_PEN,
    learn_tiers=LEARN_TIERS, learn_frac=LEARN_FRAC, lr=LR, q0=Q0,
    c_floor_frac=C_FLOOR_FRAC, g_exog=G_EXOG,
)

pkg_scens = S.scenarios(nb_struct, growths=tuple(GROWTHS), r2_base=R2_BASE)
worst = max(abs(pkg_scens[j][2][k] - SCENS[j][2][k])
            for j in range(len(SCENS)) for k in SCENS[j][2])
print(f"{'scenario tree':28s} max abs diff {worst:.2e}")
assert worst < 1e-12, "the notebook and the package disagree on the scenario tree"
print("the instance, the structure and the tree reconstruct exactly")
''')

    M(r"""
With the same instance rebuilt from the notebook's own variables, the package can
now be asked the same questions. Anything below that differs is a real
disagreement, not a difference in inputs.
""")

    C(r'''
pkg = S.three_case_comparison(nb_struct, pkg_scens, INVEST_YEARS, STAGE1_YEARS,
                              mipgap=MIPGAP)
print(f"{'quantity':12s} {'notebook':>14s} {'package':>14s} {'rel':>10s}")
for name, mine in (("WS", WS), ("RP", RP), ("EEV", EEV), ("ef_obj", ef.ObjVal)):
    theirs = pkg[name]
    rel = abs(mine - theirs) / abs(theirs)
    print(f"{name:12s} {mine:14,.4f} {theirs:14,.4f} {rel:10.1e}")
    assert rel < 1e-9, f"notebook and package disagree on {name} by {rel:.2e}"

nb_ph = progressive_hedging(SCENS, STAGE1_YEARS, rho=300, iters=20)
pk_ph = S.progressive_hedging(nb_struct, pkg_scens, INVEST_YEARS, STAGE1_YEARS,
                              rho=300, iters=20)
wz = max(abs(nb_ph["z"][k] - pk_ph["z"][k]) for k in nb_ph["z"])
wr = max(abs(a - b) for a, b in zip(nb_ph["resid"], pk_ph["resid"]))
print(f"\n{'PH consensus z':28s} max abs diff {wz:.2e}")
print(f"{'PH residual history':28s} max abs diff {wr:.2e}")
assert wz < 1e-9 and wr < 1e-9, "progressive hedging disagrees"
assert nb_ph["subsolves"] == pk_ph["subsolves"]
print("\nnotebook and package agree on the tree, all three expectations, and PH")
''')

    M(r"""
## 15. Summary

| Question | Answer |
|---|---|
| Is there anything to hedge? | **Yes** — year-1 builds wanted differ 0 / 2 / 2 across scenarios |
| What is perfect information worth? | **EVPI 528.25**, 1.55% of RP |
| What is stochastic programming worth? | **VSS 4.48**, 0.013% — essentially nothing, *as configured* |
| Why so little? | Only year 1 is committed. Lock in years 1, 4 and 7 and VSS reaches **1.121%** |
| Does a zero PH residual mean a good answer? | **No.** ρ=3000 agrees perfectly in 2 iterations and lands 0.677% off |
| Does block-asynchrony cost accuracy? | **Sometimes.** 0.67 is free and exact; 0.34 is 1.39% off |
| When does the extensive form stop fitting? | At **n = 6** scenarios, on the restricted licence |

### Formulation lessons

- **Nonanticipativity is the model.** Remove those equalities and you have three
  independent problems and the wait-and-see bound.
- **Evaluate every strategy through identical machinery.** Reading RP off
  `ef.ObjVal` while EEV comes from the evaluation path can produce a negative
  VSS, which is impossible. `RP == ef.ObjVal` is the check.
- **VSS measures how much you must commit, not just how uncertain you are.**
  Generous recourse makes stochastic programming look worthless — truthfully, for
  that model.
- **A converged residual is not a good answer.** PH on a MILP is a heuristic;
  sweep ρ and never assume convergence means quality.
- **Set the MIP gap smaller than the effect you are measuring.** VSS here is
  0.013% of RP. At the solver's 0.005 default, three genuinely different block
  fractions all reported the same cost and an assertion certified it. The gap
  did not add noise to the answer — it *manufactured* the agreement.
- **WS cannot depend on the stage-1 set.** A free, very sharp plumbing check.
- **Nothing here is random**, so there is no seed. A parameter that cannot change
  the answer is worse than no parameter.

### Things to try

- `STAGE1_YEARS = [1, 4, 7]` at the top, then *Run all* — the whole notebook
  becomes the story section 8 said was missing, with a real hedge
- `SLACK_PEN = 200` in section 3.3 — make shortfall expensive and watch VSS climb
  without touching the scenario tree
- `GROWTHS` with a wider spread, say 0.5% and 20% — more uncertainty, and see
  whether VSS moves as much as widening the commitment did
- `QUICK = False` — adds ρ = 1000, which lands where ρ = 30 does
- `RHO_SWEEP = [200, 250, 300, 350, 400]` — how sharp is the good region really?
- `MIPGAP = 0.005` in section 4 — the solver's usual default. Watch section 13's
  three block fractions collapse onto one number, and its assertion catch it

### Where this goes next

**Parts 2b and 2c.** Benders decomposition attacks the same scaling problem from
the other side — cuts instead of penalties — and CVaR replaces the expectation
with a risk measure, which changes what "the best plan" even means when the tail
is what you care about.
""")

    return out
