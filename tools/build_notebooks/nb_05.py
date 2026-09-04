"""Build notebooks/05_integrated_core.ipynb.

**Subject:** the integrated deterministic core -- five stages plus recycling,
which makes it the only model in the series with a **closed loop**. Packs sold
`pack_life` years ago come back as feedstock, so a decision in period 3 changes
what is available in period 8.

**The migration's main structural change.** The original kept every parameter in
one `BASE = dict(...)` at the top and had `build(cfg)` read from it. That is
correct for a package and wrong for a teaching notebook -- `CLAUDE.md` Part 3 is
explicit that a config dict at the top makes every subsequent cell a lookup
rather than a decision. So the numbers are split the way Part 4 asks: the
per-stage costs and lifetimes, per-region demand and the legacy fleet become
tables in `data/raw/`, and the loop's own parameters -- `pack_life`, `recovery`,
the period plan, the size bounds -- stay written out inline where the prose
explains them.

**What the original already got right and this keeps.** Its regression harness
asserts the invariant on the LP relaxation, where it is exact (1.6e-15), and
reports the MILP difference as a diagnostic rather than asserting it. It also
guards against a silently empty relaxation. That is the discipline the rest of
the series had to be taught; Part 5 had it already.
"""
from . import common

NOTEBOOK = "05_integrated_core.ipynb"
TITLE = "Part 5 - The integrated deterministic core"


def cells():
    out = []

    def M(text):
        out.append(("md", text.strip("\n")))

    def C(text):
        out.append(("code", text.strip("\n")))

    # ================================ front ================================
    M(r"""
# Part 5 — The integrated core, and a chain that feeds itself

### The only model here with a loop in it

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/sear-labs/advopt-lithiumsc/blob/main/notebooks/05_integrated_core.ipynb)

Every other model in this series moves material one way: dig it up, refine it,
build something, sell it. This one adds the return leg. Packs sold ten years ago
become scrap, a fraction of that is recovered as PROC-grade material, and the
cathode stage can consume it **instead of** freshly processed ore.

That single arc changes the character of the problem. A decision made in period 3
changes what is *available* in period 8, so the model has to reason about its own
output as a future input — and the capacity you build for recycling only pays off
if you sold enough, long enough ago, to feed it.

| | |
|---|---|
| **chain** | MINE → PROC → CATH → CELL → PACK |
| **the loop** | PACK sold at `p - pack_life` → REC → back into CATH |
| **horizon** | 33 years on a 13-period variable mesh |
| **the switch** | `allow_dual_feedstock`, and section 8 measures what it is worth |

### Two modelling decisions worth flagging before the code

**The recycling constraint is an inequality.** Scrap *bounds* what recycling can
process; it is not a quota that must be met. Written as an equality the model
would be forced to recycle everything it ever sold, in every period, whether or
not that made any sense.

**Turning the loop off requires an extra constraint, not a deletion.** With
`allow_dual_feedstock = False`, recycled material has nowhere to go — and unless
you say so explicitly, REC capacity is free to be built and its output silently
vanishes, reporting a cheaper answer than the truth. Section 7 has the line.

### The check this notebook is built around

Section 10 is a structural invariant, and it is the cleanest in the series: **two
identical regions with free trade must cost exactly what one region carrying the
doubled demand costs.** If geography is free and the regions are the same, the
arc and balance logic has to collapse. It holds to 1.6e-15 on the LP relaxation.
""")

    out += common.setup_section(notebook=NOTEBOOK)

    # ==================== 2. the instance ==================================
    M(r"""
## 2. The instance

Three tables. The stage table carries an `in_chain` flag — five stages are the
one-way chain, and `REC` is the sixth, which is not part of it but feeds into it.

**That flag is the loop, expressed as data.** Everything else about recycling
follows from where `REC` sits relative to the chain.
""")

    C(r'''
DATA = Path("data/raw")

if not (DATA / "integrated_stages.csv").exists():
    print("!" * 78)
    print("! data/raw/ was not found, so this notebook is FALLING BACK to generated")
    print("! numbers. Everything below will run, but the results are NOT the shipped")
    print("! instance and are NOT an acceptable submission.")
    print("! Fix: clone the repo (see section 0) or run from the repo root.")
    print("!" * 78)
    DATA = Path("_generated_fallback")
    DATA.mkdir(exist_ok=True)
    (DATA / "integrated_stages.csv").write_text(
        "stage,in_chain,lead,life,yield,fixed_cost,unit_cost,op_cost\n"
        "MINE,1,3,20,0.95,300.0,2.4,0.9\nPROC,1,2,20,0.90,260.0,3.1,1.4\n"
        "CATH,1,1,15,0.92,180.0,2.2,1.1\nCELL,1,1,12,0.94,220.0,3.6,1.7\n"
        "PACK,1,1,12,0.98,90.0,1.1,0.5\nREC,0,1,15,0.85,140.0,1.9,0.8\n")
    (DATA / "integrated_regions.csv").write_text(
        "region,demand0\nR1,30.0\nR2,18.0\n")
    (DATA / "integrated_legacy.csv").write_text(
        "stage,region,legacy_cap\nMINE,R1,12.0\nPROC,R1,10.0\nCATH,R1,8.0\n"
        "CELL,R1,8.0\nPACK,R1,8.0\nMINE,R2,6.0\nPROC,R2,5.0\n")

stages_df = pd.read_csv(DATA / "integrated_stages.csv")
regions_df = pd.read_csv(DATA / "integrated_regions.csv")
legacy_df = pd.read_csv(DATA / "integrated_legacy.csv")
for nm, df in (("integrated_stages", stages_df), ("integrated_regions", regions_df),
               ("integrated_legacy", legacy_df)):
    print(f"{nm + '.csv':22s} {len(df)} rows x {len(df.columns)} columns")
stages_df
''')

    M(r"""
The dictionary form, so the key is explicit. `CHAIN` is the ordered one-way path;
`STAGES` adds the recycling stage. The order of `CHAIN` matters — section 6's
flow-balance constraints walk it pairwise.
""")

    C(r'''
REGIONS = tuple(regions_df["region"])
CHAIN = tuple(stages_df.loc[stages_df["in_chain"] == 1, "stage"])
REC = stages_df.loc[stages_df["in_chain"] == 0, "stage"].iloc[0]
STAGES = CHAIN + (REC,)

LEAD = {s: int(v) for s, v in zip(stages_df["stage"], stages_df["lead"])}
LIFE = {s: int(v) for s, v in zip(stages_df["stage"], stages_df["life"])}
YIELD = {s: float(v) for s, v in zip(stages_df["stage"], stages_df["yield"])}
FIXED = {s: float(v) for s, v in zip(stages_df["stage"], stages_df["fixed_cost"])}
UNIT = {s: float(v) for s, v in zip(stages_df["stage"], stages_df["unit_cost"])}
OPCOST = {s: float(v) for s, v in zip(stages_df["stage"], stages_df["op_cost"])}
DEMAND0 = {r: float(d) for r, d in zip(regions_df["region"], regions_df["demand0"])}
LEGACY = {(s, r): float(c) for s, r, c
          in zip(legacy_df["stage"], legacy_df["region"], legacy_df["legacy_cap"])}

print(f"CHAIN  {CHAIN}")
print(f"REC    {REC!r}  <- not in the chain; it feeds INTO it")
print(f"STAGES {STAGES}")
print(f"\n{'LEAD':8s} {LEAD}")
print(f"{'LIFE':8s} {LIFE}")
print(f"{'YIELD':8s} {YIELD}")
print(f"\nlegacy fleet: {len(LEGACY)} of {len(STAGES) * len(REGIONS)} "
      f"(stage, region) nodes start with capacity")
print(f"  {LEGACY}")
print(f"\ncompounded chain yield: "
      f"{__import__('math').prod(YIELD[s] for s in CHAIN):.4f} of a unit mined "
      f"reaches a customer")
''')

    # ==================== 3. time ==========================================
    M(r"""
## 3. Time, and the knobs

Thirteen periods over 33 years: six single years, then four three-year blocks,
then three five-year blocks. Fine where the decisions are, coarse where the
model just needs somewhere for consequences to land.

**`PACK_LIFE` and `RECOVERY` are the loop's two knobs**, and they are the two
numbers a reader should reach for first. Ten years from sale to scrap; 55% of
that recovered as usable feedstock.
""")

    C(r'''
PERIOD_PLAN = [(6, 1), (4, 3), (3, 5)]    # (how many periods, years each)
RHO = 0.05             # discount rate
CAP_MIN, CAP_MAX = 8.0, 60.0      # a facility built is between these
TAU_INTRA, TAU_INTER = 0.3, 1.6   # transport within / across regions
PENALTY = 40.0         # per unit of unmet demand
DEMAND_GROWTH = 0.045
PACK_LIFE = 10         # years from sale to scrap
RECOVERY = 0.55        # PROC-grade material recovered per retired pack unit
ALLOW_DUAL_FEEDSTOCK = True
MIPGAP = 1e-4
# 1e-4, not the 0.005 the original used: section 8 differences two objectives to
# claim a 2.2% effect, and a half-percent tolerance is too close to that to be
# comfortable. Verified during migration that the objective is unchanged from
# 5e-3 down to 1e-5 on this instance - but that is luck, not a guarantee.

LENS = [L for n, L in PERIOD_PLAN for _ in range(n)]
STARTS, _t = [], 0
for L in LENS:
    STARTS.append(_t)
    _t += L
HORIZON = _t
P = list(range(len(LENS)))

# a period's weight is the SUM of the annual discount factors inside it, so a
# five-year period carries five years of cost. It is not an average.
OMEGA = {p: sum((1 + RHO) ** -(STARTS[p] + k) for k in range(LENS[p])) for p in P}

print(f"{len(P)} periods over {HORIZON} years: {LENS}")
print(f"period starts: {STARTS}")
print(f"\nthe loop: a pack sold in year t becomes scrap in year t + {PACK_LIFE}, "
      f"and {RECOVERY:.0%} of it returns as feedstock")
print(f"so recycling cannot begin before year {PACK_LIFE}, which is period "
      f"{next(p for p in P if STARTS[p] >= PACK_LIFE)}")
''')

    M(r"""
### 3.1 The period weights must tile the horizon

A period weight that does not sum to the horizon's own discount factors means
some years are being counted twice or not at all — and the objective would still
look perfectly reasonable. Worth one assertion.
""")

    C(r'''
tiled = sum(OMEGA.values())
independent = sum((1 + RHO) ** -t for t in range(HORIZON))
print(f"sum of period weights : {tiled:.6f}")
print(f"independent annual sum: {independent:.6f}")
assert abs(tiled - independent) < 1e-9, (
    f"the period weights do not tile the horizon ({tiled:.6f} vs "
    f"{independent:.6f}) - some years are double-counted or missing")
print("\nOK - the weights tile the horizon exactly")
''')

    # ==================== 4. vintages ======================================
    M(r"""
## 4. Vintages, and when a facility is running

A facility decided in period `v` comes online `LEAD` years later and runs for
`LIFE` years. Vintage `-1` is the inherited fleet, which is running from the
start and never retires — a simplification, and one worth naming: the legacy
fleet here is a floor on capacity, not an asset with a remaining life.
""")

    C(r'''
VIN = [-1] + P


# THE FUNCTION IS THE LESSON: lead time and retirement are one predicate, and
# writing it once is what stops them drifting apart. It is called from the
# ACTIVE set below and nowhere else - but ACTIVE is what every constraint in
# section 6 iterates over, so an error here is an error everywhere.
def online(s, v, p):
    """Is vintage v of stage s operating in period p? Encodes lead AND retirement."""
    if v == -1:
        return True
    ready = STARTS[v] + LEAD[s]
    return ready <= STARTS[p] < ready + LIFE[s]


BUILD = [(s, r, v) for s in STAGES for r in REGIONS for v in P]
ACTIVE = [(s, r, v, p) for s in STAGES for r in REGIONS for v in VIN for p in P
          if online(s, v, p) and (v != -1 or (s, r) in LEGACY)]
ARCS = [(s, r1, r2) for s in STAGES for r1 in REGIONS for r2 in REGIONS]

assert len(ACTIVE) > 0 and len(BUILD) > 0, "an empty index set reports success too"
print(f"{len(BUILD)} build decisions, {len(ACTIVE)} active tuples, {len(ARCS)} arcs")
print(f"\na CELL decided in period 0 (year {STARTS[0]}) is online years "
      f"{STARTS[0] + LEAD['CELL']} to "
      f"{STARTS[0] + LEAD['CELL'] + LIFE['CELL'] - 1}")
print(f"a CELL decided in period {P[-1]} (year {STARTS[-1]}) comes online in year "
      f"{STARTS[-1] + LEAD['CELL']}, which is "
      f"{'inside' if STARTS[-1] + LEAD['CELL'] < HORIZON else 'OUTSIDE'} the horizon")
''')

    # ==================== 5. capex PV ======================================
    M(r"""
## 5. Charging capital by the year

The same annuitisation Part 3 uses: convert the lump sum into an equivalent
annual payment with the capital recovery factor, then discount only the operating
years that fall **inside** the horizon.

A build late in the horizon therefore carries less of its own cost, because the
model stops before the asset does. That is the truncation every finite-horizon
capacity model has, and annuitising is what keeps it from dominating the answer.
""")

    C(r'''
# THE FUNCTION IS THE LESSON: annuitisation is the modelling decision this
# section is about, and it is called once per build decision from the objective
# in section 7 and again from the wrapper in section 8.
def mu(s, v):
    """PV of one unit of capital at stage s decided in period v."""
    life = LIFE[s]
    crf = RHO * (1 + RHO) ** life / ((1 + RHO) ** life - 1)
    t0 = STARTS[v] + LEAD[s]
    yrs = list(range(t0, min(t0 + life, HORIZON)))
    return crf * sum((1 + RHO) ** -t for t in yrs) if yrs else 0.0


DEMAND = {(r, p): DEMAND0[r] * (1 + DEMAND_GROWTH) ** STARTS[p]
          for r in REGIONS for p in P}

print("MU for CELL by decision period:")
for v in (0, 4, 8, P[-1]):
    print(f"  period {v:2d} (year {STARTS[v]:2d})  mu = {mu('CELL', v):.4f}")
print("\nit falls at the end because a late build's operating years fall outside")
print("the horizon - the truncation annuitisation is there to soften\n")
print(f"demand, year 0 : { {r: round(DEMAND[r, 0], 1) for r in REGIONS} }")
print(f"demand, year {STARTS[-1]}: "
      f"{ {r: round(DEMAND[r, P[-1]], 1) for r in REGIONS} }")
''')

    # ==================== 6. the model =====================================
    M(r"""
## 6. The model

The skeleton is familiar from Part 3 — semi-continuous sizing, capacity limiting
throughput, yield-converted output leaving on arcs — with **two new blocks**:

- the **CATH inflow** accepts recycled material as well as processed ore, which
  is the arc that closes the loop;
- the **recycling availability** constraint, which bounds what REC can process by
  what was sold `PACK_LIFE` years ago.

Everything else you have written before.
""")

    C(r'''
import gurobipy as gp
from gurobipy import GRB
import time

m = gp.Model("integrated_core")
m.Params.OutputFlag = 0
m.Params.MIPGap = MIPGAP

y = m.addVars(BUILD, vtype=GRB.BINARY, name="y")
c = m.addVars(BUILD, lb=0.0, ub=CAP_MAX, name="c")
x = m.addVars(ACTIVE, lb=0.0, name="x")
f = m.addVars(ARCS, P, lb=0.0, name="f")
u = m.addVars(REGIONS, P, lb=0.0, name="u")

m.addConstrs((c[s, r, v] <= CAP_MAX * y[s, r, v] for (s, r, v) in BUILD), name="size_hi")
m.addConstrs((c[s, r, v] >= CAP_MIN * y[s, r, v] for (s, r, v) in BUILD), name="size_lo")
m.addConstrs((x[s, r, v, p] <= (LEGACY[s, r] if v == -1 else c[s, r, v])
              for (s, r, v, p) in ACTIVE), name="cap")


# THE FUNCTION IS THE LESSON: throughput is stored per VINTAGE but every
# constraint below needs it per NODE. Writing the sum out at each of the six
# places it appears is how the vintage set and the constraint drift apart.
def thr(s, r, p):
    """Total throughput at node (s, r) in period p, across every live vintage."""
    return gp.quicksum(x[s, r, v, p] for v in VIN if (s, r, v, p) in x)


# yield-converted output leaves on the outbound arcs
m.addConstrs((YIELD[s] * thr(s, r, p) == f.sum(s, r, "*", p)
              for s in STAGES for r in REGIONS for p in P), name="out")
m.update()
print(f"{m.NumVars} variables ({m.NumBinVars} binary), {m.NumConstrs} constraints "
      f"so far - the loop is not in yet")
''')

    M(r"""
Now the inflow constraints, and **the line that closes the loop**. Read the
`if s == "CATH"` branch carefully: cathode may be fed by processed ore *or* by
recycled material, and the model chooses. Every other stage takes only what the
stage before it produced.
""")

    C(r'''
for i, s in enumerate(CHAIN):
    if i == 0:
        continue                      # MINE draws on reserves, not on an arc
    prev = CHAIN[i - 1]
    for r in REGIONS:
        for p in P:
            inflow = f.sum(prev, "*", r, p)
            if s == "CATH" and ALLOW_DUAL_FEEDSTOCK:
                inflow = inflow + f.sum(REC, "*", r, p)      # <-- the loop closes
            m.addConstr(inflow == thr(s, r, p), name=f"in_{s}_{r}_{p}")

if not ALLOW_DUAL_FEEDSTOCK:
    # Without this, recycled material has no consumer and simply disappears -
    # so REC capacity looks free and the objective comes out below the truth.
    m.addConstrs((f.sum(REC, "*", r, p) == 0 for r in REGIONS for p in P),
                 name="rec_sink")

m.update()
print(f"inflow constraints added; dual feedstock is "
      f"{'ON - CATH may consume recycled material' if ALLOW_DUAL_FEEDSTOCK else 'OFF'}")
''')

    M(r"""
### 6.1 Recycling availability — the return leg

What REC can process in period `p` is bounded by what PACK *sold* in the period
containing year `start[p] - PACK_LIFE`. Before that year exists, recycling is
forced to zero.

**It is `<=`, not `==`.** Scrap is an upper bound on the feedstock available, not
an obligation to process it. As an equality the model would have to recycle
everything it ever sold, in every period, which is not a supply chain — it is a
mandate.
""")

    C(r'''
# THE FUNCTION IS THE LESSON: this is the loop's core mechanic - a lag defined
# in YEARS, mapped onto whichever period contains that year. Counting back a
# fixed number of PERIODS instead would silently stretch from 10 years to 30 as
# the mesh coarsens, and would still produce a plausible answer.
def pack_period(p):
    """The period containing year (start[p] - PACK_LIFE), or None if pre-horizon."""
    t = STARTS[p] - PACK_LIFE
    if t < 0:
        return None
    for q in P:
        if STARTS[q] <= t < STARTS[q] + LENS[q]:
            return q
    return None


n_zero = 0
for r in REGIONS:
    for p in P:
        q = pack_period(p)
        if q is None:
            m.addConstr(thr(REC, r, p) == 0, name=f"rec0_{r}_{p}")
            n_zero += 1
        else:
            m.addConstr(thr(REC, r, p) <= RECOVERY * f.sum(CHAIN[-1], "*", r, q),
                        name=f"rec_{r}_{p}")

m.addConstrs((f.sum(CHAIN[-1], "*", r, p) + u[r, p] >= DEMAND[r, p]
              for r in REGIONS for p in P), name="dem")
m.update()
print(f"recycling is forced to zero in {n_zero // len(REGIONS)} of {len(P)} periods "
      f"(no sales {PACK_LIFE} years earlier)")
print(f"the lag map: { {p: pack_period(p) for p in P} }")
''')

    # ==================== 7. objective and solve ===========================
    M(r"""
## 7. The objective, and the solve

Four terms: annuitised capital, operating cost, transport, and the shortfall
penalty. Nothing surprising — the interest is entirely in what the loop does to
the answer.

> **Predict before you run.** Recycling capacity can only be used from year 10
> onwards. Will the model build any of it, and if so, when?
""")

    C(r'''
capex = gp.quicksum(mu(s, v) * (FIXED[s] * y[s, r, v] + UNIT[s] * c[s, r, v])
                    for (s, r, v) in BUILD)
opex = gp.quicksum(OMEGA[p] * OPCOST[s] * x[s, r, v, p] for (s, r, v, p) in ACTIVE)
trans = gp.quicksum(OMEGA[p] * (TAU_INTRA if r1 == r2 else TAU_INTER) * f[s, r1, r2, p]
                    for (s, r1, r2) in ARCS for p in P)
short = gp.quicksum(OMEGA[p] * PENALTY * u[r, p] for r in REGIONS for p in P)
m.setObjective(capex + opex + trans + short, GRB.MINIMIZE)
m.update()

t0 = time.time()
m.optimize()
BASE_OBJ = m.ObjVal
assert m.SolCount > 0, f"no solution (status {m.Status})"
assert m.NumConstrs > 0, "an empty model reports success too"
print(f"objective {BASE_OBJ:,.4f}   gap {100 * m.MIPGap:.4f}%   ({time.time() - t0:.1f}s)")
print(f"{m.NumVars} variables, {m.NumConstrs} constraints, {m.NumBinVars} binaries\n")
for nm, e in (("capital", capex), ("operating", opex), ("transport", trans),
              ("shortfall", short)):
    print(f"  {nm:12s} {e.getValue():10.1f}")
''')

    M(r"""
The cost split first, then the plan. Operating cost dominates, which is worth
knowing before tuning any capex knob — and the shortfall term is zero, so the
penalty is doing its job without distorting anything.
""")

    C(r'''
plan = pd.DataFrame(
    [dict(stage=s, region=r, vintage=v, year=STARTS[v], size=round(c[s, r, v].X, 2))
     for (s, r, v) in BUILD if y[s, r, v].X > 0.5]).sort_values(
        ["year", "stage", "region"]).reset_index(drop=True)
rec_builds = plan[plan.stage == REC]
print(f"{len(plan)} facilities built, {plan['size'].sum():.1f} units of capacity")
print(f"of which {len(rec_builds)} are recycling, first in year "
      f"{rec_builds.year.min() if len(rec_builds) else 'never'}")
assert len(rec_builds) > 0, (
    "no recycling capacity was built at all, so the loop is inert and the rest "
    "of this notebook has nothing to measure")
plan
''')

    M(r"""
**Recycling appears in year 9 in R1 and year 15 in R2** — the earliest it usefully
can, since the constraint permits processing from year 10 and the R1 build in the
period starting year 9 is online in time to use the first available scrap. A
*second* R1 recycler follows in year 23, once the scrap stream has grown enough
to feed it: the loop is not a single decision but a capacity that gets added to
as the installed base ages.

Note also that no facility sits at `CAP_MIN`. The semi-continuous lower bound is
not binding anywhere, which means it is doing no work on this instance; a reader
tuning it would see nothing move.
""")

    C(r'''
built = plan["size"]
print(f"facilities built : {len(built)}")
print(f"  at CAP_MAX ({CAP_MAX:.0f}) : {(built >= CAP_MAX - 1e-6).sum()}")
print(f"  at CAP_MIN ({CAP_MIN:.0f})  : {(built <= CAP_MIN + 1e-6).sum()}")
print(f"  strictly interior : {((built > CAP_MIN + 1e-6) & (built < CAP_MAX - 1e-6)).sum()}")
assert (built >= CAP_MIN - 1e-6).all(), "a facility was built below CAP_MIN"
assert (built <= CAP_MAX + 1e-6).all(), "a facility was built above CAP_MAX"
built.describe().round(2).to_frame("size")
''')

    # ==================== 8. the loop measured =============================
    M(r"""
## 8. What the loop is worth

Recycling's share of cathode feed, period by period — and then the number that
matters: what the whole loop is worth, measured by turning it off.
""")

    C(r'''
rows = []
for p in P:
    recycled = sum(f[REC, r1, r2, p].X for r1 in REGIONS for r2 in REGIONS)
    fresh = sum(f["PROC", r1, r2, p].X for r1 in REGIONS for r2 in REGIONS)
    tot = recycled + fresh
    rows.append(dict(period=p, year=STARTS[p], recycled=round(recycled, 2),
                     fresh=round(fresh, 2),
                     share_pct=round(100 * recycled / tot, 1) if tot > 1e-9 else 0.0,
                     unmet=round(sum(u[r, p].X for r in REGIONS), 2)))
loop = pd.DataFrame(rows)
early = loop[loop.year < PACK_LIFE]
assert (early.recycled < 1e-6).all(), (
    f"recycled material appeared before year {PACK_LIFE}, which is before any "
    f"pack could have been scrapped")
print(f"recycled share rises to {loop.share_pct.max():.1f}% by year "
      f"{loop.loc[loop.share_pct.idxmax(), 'year']}")
loop
''')

    M(r"""
Zero before year 10, as the constraint requires and the assertion checks, then
rising to **25.5%** of cathode feed by the final period. The loop takes a decade
to start and then becomes a quarter of the supply.

### 8.1 Now the streamlined version

The counterfactual needs this model twice more, and section 9 needs it twice
again on a different region set. You have written every block of it by hand in
sections 4 to 7, so wrapping it now is the right trade — and the assertion
straight after the definition is what earns the wrap.

> **Predict before you run.** Recycling supplies a quarter of the feed by the
> end. Is the loop therefore worth roughly a quarter of the cost?
""")

    C(r'''
# THE FUNCTION IS THE LESSON: sections 8 and 9 need this model at four settings
# - the loop on, the loop off, and twice more on a different REGION set. Every
# block below appears in sections 4 to 7; the only additions are the arguments.
# The check immediately after is what earns the wrap.
def build_variant(regions=REGIONS, demand0=DEMAND0, legacy=LEGACY,
                  allow_dual=ALLOW_DUAL_FEEDSTOCK, tau_inter=TAU_INTER,
                  gap=MIPGAP):
    """Sections 4-7, with the region set and the loop switch made arguments."""
    R = tuple(regions)
    bld = [(s_, r, v) for s_ in STAGES for r in R for v in P]
    act = [(s_, r, v, p) for s_ in STAGES for r in R for v in VIN for p in P
           if online(s_, v, p) and (v != -1 or (s_, r) in legacy)]
    arc = [(s_, r1, r2) for s_ in STAGES for r1 in R for r2 in R]
    dem = {(r, p): demand0[r] * (1 + DEMAND_GROWTH) ** STARTS[p]
           for r in R for p in P}

    mm = gp.Model()
    mm.Params.OutputFlag = 0
    mm.Params.MIPGap = gap
    yy = mm.addVars(bld, vtype=GRB.BINARY)
    cc = mm.addVars(bld, lb=0.0, ub=CAP_MAX)
    xx = mm.addVars(act, lb=0.0)
    ff = mm.addVars(arc, P, lb=0.0)
    uu = mm.addVars(R, P, lb=0.0)

    mm.addConstrs(cc[k] <= CAP_MAX * yy[k] for k in bld)
    mm.addConstrs(cc[k] >= CAP_MIN * yy[k] for k in bld)
    mm.addConstrs(xx[s_, r, v, p] <= (legacy[s_, r] if v == -1 else cc[s_, r, v])
                  for (s_, r, v, p) in act)

    def th(s_, r, p):
        return gp.quicksum(xx[s_, r, v, p] for v in VIN if (s_, r, v, p) in xx)

    mm.addConstrs(YIELD[s_] * th(s_, r, p) == ff.sum(s_, r, "*", p)
                  for s_ in STAGES for r in R for p in P)
    for i, s_ in enumerate(CHAIN):
        if i == 0:
            continue
        for r in R:
            for p in P:
                inflow = ff.sum(CHAIN[i - 1], "*", r, p)
                if s_ == "CATH" and allow_dual:
                    inflow = inflow + ff.sum(REC, "*", r, p)
                mm.addConstr(inflow == th(s_, r, p))
    if not allow_dual:
        mm.addConstrs(ff.sum(REC, "*", r, p) == 0 for r in R for p in P)
    for r in R:
        for p in P:
            q = pack_period(p)
            if q is None:
                mm.addConstr(th(REC, r, p) == 0)
            else:
                mm.addConstr(th(REC, r, p) <= RECOVERY * ff.sum(CHAIN[-1], "*", r, q))
    mm.addConstrs(ff.sum(CHAIN[-1], "*", r, p) + uu[r, p] >= dem[r, p]
                  for r in R for p in P)

    mm.setObjective(
        gp.quicksum(mu(s_, v) * (FIXED[s_] * yy[s_, r, v] + UNIT[s_] * cc[s_, r, v])
                    for (s_, r, v) in bld)
        + gp.quicksum(OMEGA[p] * OPCOST[s_] * xx[s_, r, v, p] for (s_, r, v, p) in act)
        + gp.quicksum(OMEGA[p] * (TAU_INTRA if r1 == r2 else tau_inter)
                      * ff[s_, r1, r2, p] for (s_, r1, r2) in arc for p in P)
        + gp.quicksum(OMEGA[p] * PENALTY * uu[r, p] for r in R for p in P),
        GRB.MINIMIZE)
    mm.update()          # required before .relax(); see section 9
    return mm


_chk = build_variant()
_chk.optimize()
assert abs(_chk.ObjVal - BASE_OBJ) / abs(BASE_OBJ) < 1e-9, \
    "the wrapper does not reproduce the hand-built model"
print(f"the wrapper reproduces section 7 exactly: {_chk.ObjVal:,.4f} "
      f"vs {BASE_OBJ:,.4f}")

_offm = build_variant(allow_dual=False)
_offm.optimize()
off = _offm.ObjVal
print(f"\ndual feedstock ON  : {BASE_OBJ:,.4f}")
print(f"dual feedstock OFF : {off:,.4f}")
print(f"\nvalue of the loop  : {off - BASE_OBJ:,.2f}  "
      f"({100 * (off - BASE_OBJ) / off:.2f}% of the no-loop cost)")
assert off > BASE_OBJ, "turning the loop off made the problem cheaper, which is impossible"
''')

    M(r"""
**A quarter of the feed, and 2.20% of the cost.** Those are not in tension, and
the gap between them is the point.

Recycled material replaces *processed ore*, and processing is only one of five
stages. The mine still has to be smaller, the cathode plant is the same size
either way, and the recycling capacity itself has to be built and run. What the
loop saves is the marginal cost of the ore it displaces, not the cost of the
chain that carries it.

**Turning the loop off can only make things worse, and the assertion says so** —
it removes an option without removing an obligation. If that assertion ever
failed it would mean the `rec_sink` constraint had gone missing and recycled
material was quietly vanishing.
""")

    # ==================== 9. the collapse test =============================
    M(r"""
## 9. The regression harness

The structural invariant this model is checked against, and the cleanest in the
series:

> **Two identical regions with free trade must cost exactly what one region
> carrying the doubled demand costs.**

If geography costs nothing and the regions are the same, the arc and balance
logic has to collapse. It is a strong test because almost any error in the flow
constraints breaks it, and almost no error in the *costs* does — so when it
fails, you know where to look.

**It is asserted on the LP relaxation**, where the invariant is exact. The MILP
versions differ, because integrality is lumpy and two regions of 12 cannot always
split what one region of 24 can. That difference is real and is reported as a
diagnostic — asserting on it would be asserting on an artefact.

Both models solve at `mipgap = 0` so the reported lumpiness is a property of the
integrality and not of the tolerance.
""")

    C(r'''
# THE FUNCTION IS THE LESSON: the harness is the deliverable here, not a
# convenience - section 10 hands the same invariant to the package and compares.
def collapse_test(tol=1e-4):
    """Two identical free-trading regions must equal one region, doubled."""
    common_kw = dict(gap=0.0, tau_inter=TAU_INTRA)
    multi = build_variant(regions=("A", "B"), demand0={"A": 12.0, "B": 12.0},
                          legacy={(s_, r): 6.0 for s_ in CHAIN for r in ("A", "B")},
                          **common_kw)
    single = build_variant(regions=("A",), demand0={"A": 24.0},
                           legacy={(s_, "A"): 12.0 for s_ in CHAIN}, **common_kw)

    ra, rb = multi.relax(), single.relax()
    for rr in (ra, rb):
        rr.Params.OutputFlag = 0
        rr.optimize()
    # a silently empty relaxation solves to 0 and would pass any status check
    assert ra.NumConstrs > 0 and rb.NumConstrs > 0, \
        "the relaxation is empty - a missing m.update() before .relax()"
    assert ra.ObjVal > 1.0, "the relaxed objective is ~0; the model was not copied"
    rel_lp = abs(ra.ObjVal - rb.ObjVal) / max(1.0, abs(rb.ObjVal))

    multi.optimize()
    single.optimize()
    rel_ip = abs(multi.ObjVal - single.ObjVal) / max(1.0, abs(single.ObjVal))
    print(f"LP relaxation  multi {ra.ObjVal:.6f} | single {rb.ObjVal:.6f} | "
          f"rel {rel_lp:.3e}   <-- the test")
    print(f"MILP           multi {multi.ObjVal:.4f} | single {single.ObjVal:.4f} | "
          f"rel {rel_ip:.3e}   (lumpiness, diagnostic only)")
    assert rel_lp < tol, (
        f"the collapse invariant failed at {rel_lp:.2e} - the arc or balance "
        f"logic does not reduce correctly when geography is free")
    return rel_lp, rel_ip


rel_lp, rel_ip = collapse_test()
print(f"\nPASS - the arc and balance logic collapses exactly under relaxation")
print(f"integer lumpiness contributes {100 * rel_ip:.2f}% on this instance")
''')

    # ==================== 10. agreement ====================================
    M(r"""
## 10. The agreement assertion

`src/lithium/integrated.py` holds the same model. This compares the instance
tables, the base objective, the loop's value, the **build plan**, and the
collapse test — the last because it is the invariant, and an implementation that
agreed on the objective but broke the collapse would be broken in exactly the way
this notebook is designed to detect.
""")

    C(r'''
from lithium import IntegratedInstance
from lithium import integrated as IC

nb_inst = IntegratedInstance(
    regions=REGIONS, chain=CHAIN, stages=STAGES, recycle_stage=REC,
    lead=LEAD, life=LIFE, yield_=YIELD, fixed_cost=FIXED, unit_cost=UNIT,
    op_cost=OPCOST, demand0=DEMAND0, legacy_cap=LEGACY)

KW = dict(period_plan=PERIOD_PLAN, rho=RHO, cap_min=CAP_MIN, cap_max=CAP_MAX,
          tau_intra=TAU_INTRA, tau_inter=TAU_INTER, penalty=PENALTY,
          pack_life=PACK_LIFE, recovery=RECOVERY,
          demand_growth=DEMAND_GROWTH, mipgap=MIPGAP)

pkg_lens, pkg_starts, pkg_H = IC.periods_from_plan(PERIOD_PLAN)
assert pkg_lens == LENS and pkg_starts == STARTS and pkg_H == HORIZON, \
    "the period meshes differ"
print(f"{'period mesh':32s} identical ({len(LENS)} periods, {HORIZON} years)")

for dual, tag in ((True, "dual ON "), (False, "dual OFF")):
    pm = IC.build(nb_inst, allow_dual_feedstock=dual, **KW)
    pm.optimize()
    nb_val = BASE_OBJ if dual else off
    rel = abs(nb_val - pm.ObjVal) / abs(pm.ObjVal)
    print(f"{tag + ' objective':32s} notebook {nb_val:12.4f}  "
          f"package {pm.ObjVal:12.4f}  rel {rel:.1e}")
    assert rel < 1e-9, f"{tag}: objectives disagree by {rel:.2e}"
    if dual:
        pkg_plan = IC.build_plan(pm)
        nb_plan = sorted((s, r, v, STARTS[v], round(c[s, r, v].X, 2))
                         for (s, r, v) in BUILD if y[s, r, v].X > 0.5)
        assert pkg_plan == nb_plan, "same objective, different build plan"
        print(f"{'build plan':32s} identical ({len(nb_plan)} facilities)")
''')

    M(r"""
And the invariant itself, which is the part that would catch an implementation
agreeing on the objective while getting the flow logic wrong.
""")

    C(r'''
pk = IC.collapse_test(nb_inst, **{k: v for k, v in KW.items() if k != "mipgap"})
print(f"{'collapse test, LP relative':32s} notebook {rel_lp:.3e}  "
      f"package {pk['rel_lp']:.3e}")
assert abs(rel_lp - pk["rel_lp"]) < 1e-12, "the collapse tests disagree"
assert pk["passed"], "the package fails its own collapse invariant"
print(f"{'  its LP objectives':32s} {pk['lp_multi']:.6f} / {pk['lp_single']:.6f}")
print(f"{'collapse test, IP relative':32s} notebook {rel_ip:.3e}  "
      f"package {pk['rel_ip']:.3e}")
assert abs(rel_ip - pk["rel_ip"]) < 1e-12, "the lumpiness diagnostics disagree"

print("\nnotebook and package agree on the mesh, both objectives, the build plan,")
print("and the collapse invariant including its diagnostic")
''')

    M(r"""
## 11. Summary

| Question | Answer |
|---|---|
| When does recycling start? | Year 9 in R1, year 15 in R2 — the earliest the 10-year lag allows |
| How much feed does it supply? | Rising to **25.5%** of cathode input by the final period |
| What is the loop worth? | **459.88**, or 2.20% — a quarter of the feed, a fortieth of the cost |
| Why the gap? | It displaces processed ore, not the four other stages that carry it |
| Does the collapse invariant hold? | Yes, to **1.6e-15** on the LP relaxation |
| Is the semi-continuous floor doing anything? | **No** — nothing is built at `CAP_MIN` on this instance |

### Formulation lessons

- **A closed loop makes output an input.** The model must reason about what it
  sold a decade ago, which is why `pack_period` maps a *year* offset onto
  periods rather than counting period indices.
- **Bound the return leg, do not require it.** `<=` means scrap is available;
  `==` would make recycling a mandate.
- **Removing an option needs a constraint, not a deletion.** Switching off dual
  feedstock without `rec_sink` lets recycled material vanish and reports a
  cheaper answer than the truth.
- **Assert the invariant where it is exact.** The collapse holds on the LP
  relaxation; the MILP difference is real lumpiness and is a diagnostic, not a
  test.
- **Guard against a silently empty relaxation.** `.relax()` on a model that was
  never `update()`d copies nothing, solves to zero, and passes any status check.
- **A share is not a value.** A quarter of the feedstock is a fortieth of the
  cost, and only one of those two numbers is a reason to build something.

### Things to try

- `RECOVERY = 0.9` — a much better recycling process, and see whether the loop's
  value moves proportionally
- `PACK_LIFE = 4` — scrap returning inside the fine-mesh periods, so the loop
  starts before the model coarsens
- `TAU_INTER = 0.3` — free trade between regions, and watch the collapse test's
  premise become the base case
- `CAP_MIN = 30` — a binding lower bound, which section 7 shows is currently idle
- `ALLOW_DUAL_FEEDSTOCK = False` at the top, then *Run all* — every recycling
  build should vanish

### Where this goes next

This is the last of the migrated series. The models it leaves behind — a closed
loop, a three-level game, two learning channels, four ways to be wrong about
uncertainty — are the pieces a research model assembles. **Part 0** is the place
to go back to for any concept that went past too quickly.
""")

    return out
