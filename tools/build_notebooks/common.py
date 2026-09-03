"""Cell sources shared by every migrated notebook in this series.

Each notebook builds the same instance, the same derived structure and the same
learning curve, **by hand**, because deriving them is the lesson (`CLAUDE.md`
Part 3). That means the same twenty-odd narrated cells appear in every notebook —
which is exactly the duplication that goes stale when a fix lands in three
notebooks out of four.

So they are emitted from here. `CLAUDE.md` Part 4's corollary applies: this
module is the source of truth and the notebook is a build output, and
`tests/test_notebook_sources.py` asserts that regenerating reproduces the sources
that shipped. Without that test this file and the notebooks would drift exactly
as fast as two pasted copies.

**Note what is NOT here.** Nothing in this module is a model. Every function
below emits *narrated cells that build things by hand*; the models live in
`src/lithium/`. A notebook's own subject matter is written out in its own
`nb_*.py`, never shared, because sharing it would be sharing the lesson.
"""


DEFAULT_HORIZON_NOTE = """\
A 37-year horizon at annual resolution would be 37 copies of every decision. Instead the horizon is
chopped into **13 periods of increasing length** — six 1-year periods while the interesting things
happen, then 3-, 5- and finally 9-year blocks."""


def _cells():
    out = []

    def M(text):
        out.append(("md", text.strip("\n")))

    def C(text):
        out.append(("code", text.strip("\n")))

    return out, M, C


def _sub(text, **numbers):
    """Fill the @NAME@ section-number placeholders.

    Not `str.format`: these cells are full of Python braces (f-strings, dict and
    set literals), and `format` would try to interpret every one of them.
    """
    for name, value in numbers.items():
        text = text.replace(f"@{name.upper()}@", str(value))
    left = [m for m in ("@AGREE@", "@CHAIN@", "@REVENUE@", "@TIERS@", "@TIERED@",
                       "@BLOCKS@", "@HORIZON_NOTE@")
            if m in text]
    if left:
        raise ValueError(f"unfilled section placeholders {left} in a shared cell")
    return text


def setup_section(repo="lithium-modelling", notebook="04c_cournot.ipynb"):
    """Section 0: the Colab bootstrap. The only place the package appears
    before the agreement assertion."""
    out, M, C = _cells()
    M(r"""
## 0. Setup

One cell, and it is the only place the `lithium` package appears before the final check. On Colab it
clones the repo and installs it; locally it assumes you have already run `pip install -e .` and just
moves up out of `notebooks/` so the relative data paths work.
""")

    C(r"""
import os
import subprocess
import sys
from pathlib import Path

REPO_URL = "https://github.com/USERNAME/lithium-modelling.git"   # <-- edit me
REPO_NAME = REPO_URL.rstrip("/").split("/")[-1].replace(".git", "")

if "google.colab" in sys.modules:
    if not Path(REPO_NAME).exists():
        subprocess.run(["git", "clone", "--depth", "1", REPO_URL], check=True)
    os.chdir(REPO_NAME)
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-e", "."], check=True)
elif Path.cwd().name == "notebooks":
    os.chdir("..")

import gurobipy as gp
from gurobipy import GRB
import matplotlib.pyplot as plt
import pandas as pd

plt.rcParams.update({"font.size": 12, "axes.grid": True, "grid.alpha": 0.3})
print(f"working directory : {Path.cwd().name}")
print(f"gurobipy          : {gp.gurobi.version()}")
print(f"pandas            : {pd.__version__}")
""")
    return out


def instance_section(agree=12):
    """Section 2: load the three tables, render them, show the key structure,
    and give a commented worked example of overriding one entry."""
    out, M, C = _cells()
    M(r"""
## 2. The instance tables

Two kinds of number go into this model and they are treated differently.

A **knob** is a scalar carrying a concept — the discount rate, the number of revenue breakpoints,
the choke price. Knobs stay written out in the cell where they are explained, because seeing
`NBP_REV = 7` next to the sentence describing what a breakpoint mesh does *is* the lesson. This
notebook hands every knob to the package explicitly in section @AGREE@, so the agreement assertion covers
them.

A **table** is instance data — many entries, indexed by the model's own sets, named nowhere in the
prose. Tables live in `data/raw/`, and both this notebook and `src/lithium/` read the same file. If
each typed its own copy, a failed assertion could not tell a typo in the data from a bug in a
constraint. Three tables, three key structures:

| file | keyed by | rows |
|---|---|---|
| `instance_base.csv` | `(stage, region)` | 6 |
| `efficiency.csv` | `stage` | 3 |
| `market.csv` | `region` | 2 |
""")

    M(r"""
Read the base table first and look at it as a **frame** — rows and columns — before turning it into
anything the model can index.
""")

    C(r"""
DATA = Path("data/raw")

if not (DATA / "instance_base.csv").exists():
    print("!" * 78)
    print("! data/raw/ was not found, so this notebook is FALLING BACK to generated")
    print("! numbers. Everything below will run and every figure will render, but the")
    print("! results are NOT the shipped instance and are NOT an acceptable submission.")
    print("! Fix: clone the repo (see section 0) or run this notebook from the repo root.")
    print("!" * 78)
    DATA = Path("_generated_fallback")
    DATA.mkdir(exist_ok=True)
    (DATA / "instance_base.csv").write_text(
        "stage,region,fixed,unit,opex,legacy_cap,legacy_ret\n"
        + "\n".join(f"{s},{r},1000.0,8.0,2.0,150,15"
                    for r in ("R1", "R2") for s in ("MINE", "PROC", "MFG")) + "\n")
    (DATA / "efficiency.csv").write_text(
        "stage,eta_ceil,eta_base,alpha,beta,delta_bar\n"
        "MINE,0.92,0.86,0.0,0.0,0.02\nPROC,0.95,0.80,0.03,0.01,0.05\n"
        "MFG,0.93,0.78,0.025,0.008,0.05\n")
    (DATA / "market.csv").write_text(
        "region,demand_base,demand_growth,experience0\n"
        "R1,100.0,0.008,1000.0\nR2,75.0,0.026,1000.0\n")

base = pd.read_csv(DATA / "instance_base.csv")
print(f"instance_base.csv: {len(base)} rows x {len(base.columns)} columns")
base
""")

    M(r"""
The other two tables. `efficiency.csv` is keyed by stage alone — a mine's yield behaviour does not
depend on which region owns it — and `market.csv` is keyed by region alone.
""")

    C(r"""
eff = pd.read_csv(DATA / "efficiency.csv")
mkt = pd.read_csv(DATA / "market.csv")
print(f"efficiency.csv: {len(eff)} rows    market.csv: {len(mkt)} rows")
display(eff)
mkt
""")

    M(r"""
### 2.1 From table to lookup — see the key

A frame shows rows and columns. **The model does not index by row number.** Every constraint below
looks a value up by a *key*: `FIXED['PROC', 'R1']`, `ETA_CEIL['MFG']`, `EXPERIENCE0['R2']`. That key
is what connects the data to the algebra, so build the dictionaries and print them in the form the
constraints will actually use, rather than leaving the index set implied by punctuation.

The two index sets come out of the tables themselves, in file order — so the order the model
iterates in is a property of the data, not of a sorted() call somewhere.
""")

    C(r"""
STAGES = list(dict.fromkeys(eff["stage"]))
REGIONS = list(dict.fromkeys(mkt["region"]))

FIXED = {(r.stage, r.region): r.fixed for r in base.itertuples()}
UNIT = {(r.stage, r.region): r.unit for r in base.itertuples()}
OPEX = {(r.stage, r.region): r.opex for r in base.itertuples()}
LEGACY_CAP = {(r.stage, r.region): float(r.legacy_cap) for r in base.itertuples()}
LEGACY_RET = {(r.stage, r.region): int(r.legacy_ret) for r in base.itertuples()}

print(f"index sets:  STAGES  = {STAGES}")
print(f"             REGIONS = {REGIONS}")
print(f"{len(FIXED)} keys, each a (stage, region) tuple\n")
print(f"{'key':18s} {'FIXED':>8s} {'UNIT':>7s} {'OPEX':>6s} {'LEG_CAP':>8s} {'LEG_RET':>8s}")
for s in STAGES:
    for r in REGIONS:
        print(f"{str((s, r)):18s} {FIXED[s, r]:8.1f} {UNIT[s, r]:7.2f} {OPEX[s, r]:6.2f}"
              f" {LEGACY_CAP[s, r]:8.0f} {LEGACY_RET[s, r]:8d}")
""")

    M(r"""
The same move for the two single-key tables. Note `EXPERIENCE0`: R1 starts with 2,600 units of
accumulated production experience against R2's 500. Nothing in this instance is labelled
"incumbent" — that word is a *reading* of three numbers pulling the same way: R1 starts with more
experience, larger inherited plants, and the bigger home market. R2's compensating advantage is in
`instance_base.csv`, and it is capital, not operating cost: R2 is cheaper to **build** at every stage
and more expensive to **run** at every stage. Check that against the table above before going on,
because most of the results below turn on it.
""")

    C(r"""
ETA_CEIL = {r.stage: r.eta_ceil for r in eff.itertuples()}
ETA_BASE = {r.stage: r.eta_base for r in eff.itertuples()}
ALPHA = {r.stage: r.alpha for r in eff.itertuples()}
BETA = {r.stage: r.beta for r in eff.itertuples()}
DELTA_BAR = {r.stage: r.delta_bar for r in eff.itertuples()}

DEMAND_BASE = {r.region: r.demand_base for r in mkt.itertuples()}
DEMAND_GROWTH = {r.region: r.demand_growth for r in mkt.itertuples()}
EXPERIENCE0 = {r.region: r.experience0 for r in mkt.itertuples()}

print("keyed by stage :")
for s in STAGES:
    print(f"  {s!r:8s} ceil {ETA_CEIL[s]:.2f}  base {ETA_BASE[s]:.2f}  alpha {ALPHA[s]:.3f}"
          f"  beta {BETA[s]:.3f}  delta_bar {DELTA_BAR[s]:.2f}")
print("\nkeyed by region:")
for r in REGIONS:
    print(f"  {r!r:6s} demand_base {DEMAND_BASE[r]:6.1f}  growth {DEMAND_GROWTH[r]:.3f}"
          f"  experience0 {EXPERIENCE0[r]:7.1f}")
""")

    M(r"""
### 2.2 Want to experiment? Change a number here, not in the CSV

Each table is now a dictionary keyed the way the model indexes. Assign to a key to override one
entry. The change flows into every model built below **and** into the section @AGREE@ agreement check,
because the package takes the data as an argument instead of re-reading the file — so the assertion
stays green and you can see exactly what your edit did.
""")

    C(r"""
# ---------------------------------------------------------------------------
# Example - give R2 the same processing opex as R1 (2.0 instead of its 2.2):
#
#     OPEX['PROC', 'R2'] = 2.00
#
# Uncomment, then re-run this cell and everything below it. This erases R1's
# operating-cost edge at the processing stage, so R2 gets cheaper to run, its
# equilibrium share rises, and the section @AGREE@ assertion stays green because the
# notebook passes OPEX to the package rather than letting it re-read the file.
# Re-run with it commented out to get the shipped instance back.
# ---------------------------------------------------------------------------
print(f"OPEX['PROC', 'R2'] is currently {OPEX['PROC', 'R2']}")
""")
    return [(k, _sub(t, agree=agree)) for k, t in out]


def structure_section(agree=12, chain=5,
                      blocks="[(6, 1), (4, 3), (2, 5), (1, 9)]",
                      horizon_note=DEFAULT_HORIZON_NOTE):
    """Section 3: everything derived from the tables plus the horizon knobs."""
    out, M, C = _cells()
    M(r"""
## 3. The knobs, and the structure derived from them

Everything from here to section @CHAIN@ is **derived**: sets, windows, discount weights, yields. None of
it is data and none of it is a knob — it is arithmetic on the two, and doing that arithmetic is the
point of this section. `src/lithium/structure.py` computes exactly the same things, and section @AGREE@
is what proves the two derivations agree.

### 3.1 Time: variable-length periods

@HORIZON_NOTE@ `OMEGA[p]` is the sum of discount factors for the
years inside period `p`, so a long late period is correctly worth less per year *and* covers more
years. The cell prints the block structure it actually built, so you can check it against whatever
`BLOCKS` says rather than against this paragraph.
""")

    C(r"""
BLOCKS = @BLOCKS@   # (how many periods, how many years each)
DR = 0.05                                    # discount rate

LEN, START = [], []
_y = 1
for _count, _length in BLOCKS:
    for _ in range(_count):
        LEN.append(_length)
        START.append(_y)
        _y += _length

P = list(range(len(LEN)))
HORIZON = _y - 1
YEARS = {p: list(range(START[p], START[p] + LEN[p])) for p in P}
OMEGA = {p: sum(1 / (1 + DR) ** t for t in YEARS[p]) for p in P}
YEAR_TO_P = {t: p for p in P for t in YEARS[p]}

print(f"{len(P)} periods covering {HORIZON} years")
print(f"{'p':>3s} {'start':>6s} {'len':>4s} {'OMEGA':>8s}")
for p in P:
    print(f"{p:3d} {START[p]:6d} {LEN[p]:4d} {OMEGA[p]:8.4f}")
""")

    M(r"""
### 3.2 Technology: turning a lump of capex into an annual charge

A plant built in period `v` is paid for once and used for `LIFE` years. `CRF` is the capital
recovery factor that spreads that lump into equal annual payments, and `MU[s, v]` discounts those
payments back to today — truncated at the horizon, so a plant built late gets credit only for the
years that actually fall inside the model.

`LEAD` is the construction lag: decide in period `v`, produce from `START[v] + LEAD[s]`.
""")

    C(r"""
LIFE = 25
LEAD = {'MINE': 1, 'PROC': 2, 'MFG': 2}
CAP_MIN, CAP_MAX = 60.0, 260.0

CRF = DR * (1 + DR) ** LIFE / ((1 + DR) ** LIFE - 1)
ONLINE = {(s, p): START[p] + LEAD[s] for s in STAGES for p in P}
MU = {(s, v): CRF * sum(1 / (1 + DR) ** t
                        for t in range(ONLINE[s, v], ONLINE[s, v] + LIFE)
                        if t <= HORIZON)
      for s in STAGES for v in P}

print(f"CRF = {CRF:.6f}   (a 1.0 lump becomes {CRF:.4f} per year for {LIFE} years)")
print(f"\nMU['PROC', v] by build period - note the collapse as v approaches the horizon:")
print("  " + "  ".join(f"v{v}:{MU['PROC', v]:5.2f}" for v in P))
""")

    M(r"""
### 3.3 Efficiency: yield depends on when a plant was built and how old it is

Two effects, and they pull in opposite directions. A plant built later starts closer to the
technological ceiling (`ALPHA` — the frontier improves). A plant that has been running for a while
also drifts up towards the ceiling through operating experience (`BETA`), but only by at most
`DELTA_BAR` above where it started. `ETA_FLOOR` stops the arithmetic producing a nonsense yield.

`LEGACY_BYR = -8` says the inherited plants were built eight years before year 1 — which is why they
sit well below the frontier.
""")

    C(r"""
ETA_FLOOR = 0.60
LEGACY_BYR = -8

VINTAGES = [-1] + P                      # -1 is the inherited fleet
BYEAR = {v: (LEGACY_BYR if v == -1 else START[v]) for v in VINTAGES}

ETA = {}
for s in STAGES:
    for v in VINTAGES:
        fr = ETA_CEIL[s] - (ETA_CEIL[s] - ETA_BASE[s]) * (1 - ALPHA[s]) ** (BYEAR[v] - 1)
        fr = max(ETA_FLOOR, min(fr, ETA_CEIL[s]))
        for p in P:
            age = max(0, START[p] - BYEAR[v])
            aged = ETA_CEIL[s] - (ETA_CEIL[s] - fr) * (1 - BETA[s]) ** age
            ETA[s, v, p] = max(ETA_FLOOR, min(fr + DELTA_BAR[s], aged))

print(f"{len(ETA)} yields, keyed (stage, vintage, period)\n")
print("PROC yield in period 0, by vintage - the frontier effect:")
print("  legacy (v=-1): %.4f" % ETA['PROC', -1, 0])
print("  " + "  ".join(f"v{v}:{ETA['PROC', v, 0]:.4f}" for v in P[:5]))
print("\nlegacy PROC plant ageing through the horizon:")
print("  " + "  ".join(f"p{p}:{ETA['PROC', -1, p]:.4f}" for p in P[:6]))
""")

    M(r"""
### 3.4 Demand

Each region's demand grows from its own base at its own rate. R2 is the smaller market but grows
more than three times as fast, which is why the entrant's home turf is worth fighting for later even
though it is worth less now. The value stored is the **average annual** demand across the period, so
it is comparable across periods of different length.
""")

    C(r"""
DEMAND = {(r, p): sum(DEMAND_BASE[r] * (1 + DEMAND_GROWTH[r]) ** (t - 1) for t in YEARS[p]) / LEN[p]
          for r in REGIONS for p in P}

print(f"average annual demand ({len(DEMAND)} keys, (region, period)):")
print(f"{'p':>3s} {'year':>5s} " + " ".join(f"{r:>8s}" for r in REGIONS))
for p in P:
    print(f"{p:3d} {START[p]:5d} " + " ".join(f"{DEMAND[r, p]:8.2f}" for r in REGIONS))
""")

    M(r"""
### 3.5 Who can produce, when

Three sets that every constraint below indexes over, and they are worth printing rather than
trusting:

- `ACTIVE[r]` — the `(stage, vintage, period)` triples that exist at all: an inherited plant until
  its retirement year, a new plant from the period it comes online until it has run for `LIFE` years.
- `VIN[r, s, p]` — the vintages available at one stage in one period. This is the set the chain
  balance sums over.
- `BUILD[r]` — the `(stage, vintage)` pairs that could be built, i.e. those that come online before
  the horizon ends.
""")

    C(r"""
ACTIVE = {r: [(s, v, p) for s in STAGES for v in VINTAGES for p in P
              if (v == -1 and START[p] <= LEGACY_RET[s, r])
              or (v >= 0 and ONLINE[s, v] <= START[p] <= ONLINE[s, v] + LIFE - 1)]
          for r in REGIONS}
VIN = {(r, s, p): [v for (ss, v, pp) in ACTIVE[r] if (ss, pp) == (s, p)]
       for r in REGIONS for s in STAGES for p in P}
BUILD = {r: [(s, v) for s in STAGES for v in P if ONLINE[s, v] <= HORIZON]
         for r in REGIONS}

for r in REGIONS:
    print(f"{r}: {len(ACTIVE[r]):4d} active (stage, vintage, period) triples, "
          f"{len(BUILD[r]):3d} buildable (stage, vintage) pairs")
print(f"\nVIN['R1', 'MFG', p] - vintages that can manufacture, period by period:")
for p in P:
    print(f"  p{p:<2d} {VIN['R1', 'MFG', p]}")
""")

    M(r"""
### 3.6 The remaining knobs: moving goods and the two penalties

`TRANSPORT` is nearly five times more expensive across regions than within one. That single number
is what makes geography matter — without it the two markets would collapse into one.
""")

    C(r"""
TRANSPORT_OWN, TRANSPORT_CROSS = 0.5, 2.4
TRANSPORT = {(rf, rt): (TRANSPORT_OWN if rf == rt else TRANSPORT_CROSS)
             for rf in REGIONS for rt in REGIONS}

PRICE_FIXED = 12.0     # the Part 4b price; kept so 4b's revenue term stays available
PEN_SHORT = 90.0       # planner-only: cost of leaving demand unserved
PEN_DISPOSE = 12.0     # cost of destroying output rather than selling it

print("TRANSPORT, keyed (from, to):")
for k, v in TRANSPORT.items():
    print(f"  {str(k):14s} {v:4.1f}")
print(f"\nPEN_DISPOSE = {PEN_DISPOSE}  <- watch this one: section 10 shows it never binds")
""")
    return [(k, _sub(t, agree=agree, chain=chain, blocks=blocks,
                     horizon_note=horizon_note)) for k, t in out]


def capex_curve_section(chain=5, revenue=7):
    """Section 4: the capacity-learning curve, and why THIS one needs SOS2."""
    out, M, C = _cells()
    M(r"""
## 4. The capacity-learning curve

Building capacity gets cheaper the more of it you have built. A learning rate `LR_CAPEX = 0.15`
means unit cost falls 15% per doubling of cumulative capacity, which is the exponent
$-\log_2(1 - 0.15)$.

**The model needs the area under that curve, not the curve itself.** Total spend to go from
`Q_START` to `Q` is the integral of the unit cost over that range — building the 401st unit costs
what the curve says at 401, not what it said at 300. So we integrate numerically (trapezoid rule,
`PANELS` panels) at each of `NBP` breakpoints, and the model interpolates between them.

**This curve is concave and it enters a cost we are *minimising*** — so a chord between two
breakpoints lies *below* the true cumulative cost, and a free convex combination would happily mix
distant breakpoints to claim a discount that does not exist. That is why the model in section @CHAIN@ adds
**SOS2** here. Compare section @REVENUE@, where the same concave shape in a *maximisation* needs nothing.
""")

    C(r"""
import math

LEARN_STAGES = ['PROC', 'MFG']
LR_CAPEX = 0.15        # cost falls 15% per doubling
Q_START = 300.0        # cumulative capacity at which learning starts
Q_ADD = 700.0          # how much further the mesh reaches
CAPEX_FLOOR = 0.60     # the multiplier cannot fall below this
NBP = 9                # breakpoints on the capex mesh
PANELS = 400           # trapezoid panels per breakpoint

_bc = -math.log2(1 - LR_CAPEX)
K = list(range(NBP))                     # the breakpoint index the model sums over
QBP = [Q_START + Q_ADD * k / (NBP - 1) for k in K]

CBP = []
for q in QBP:
    if q <= Q_START:
        CBP.append(0.0)
        continue
    h = (q - Q_START) / PANELS
    grid = [Q_START + i * h for i in range(PANELS + 1)]
    unit = [max(CAPEX_FLOOR, (g / Q_START) ** (-_bc)) for g in grid]
    CBP.append(sum(0.5 * (unit[i] + unit[i + 1]) * h for i in range(PANELS)))

print(f"learning exponent b = {_bc:.4f}\n")
print(f"{'k':>2s} {'QBP (cum capacity)':>19s} {'unit mult':>10s} {'CBP (cum spend mult)':>21s}")
for k in range(NBP):
    print(f"{k:2d} {QBP[k]:19.1f} {max(CAPEX_FLOOR, (QBP[k] / Q_START) ** (-_bc)):10.4f}"
          f" {CBP[k]:21.2f}")
""")
    return [(k, _sub(t, chain=chain, revenue=revenue)) for k, t in out]


def chain_section(tiers=6, tiered=7):
    """Sections 5.1-5.7: one region's chain, built by hand, one block per cell,
    solved as the cooperative planner.

    This is Part 4a's model. Every later Part 4 notebook either emits this
    section (04ab, 04c) or carries the resulting wrapper over with a marker
    (04d, 04e) - and either way it is narrated exactly once, here.
    """
    out, M, C = _cells()
    M(r"""
## 5. The chain, built by hand

A **region** here is a whole vertically-integrated business: it mines ore, processes it, manufactures
the finished good, and sells into either market. The next seven cells build that chain for both
regions, one block of constraints at a time.

We build it first as a **cooperative planner** — one decision maker minimising the weighted sum of
both regions' costs subject to meeting demand. That is Part 4a's model, and we need it here for a
specific reason given in section @TIERS@: it tells us the *scale* at which this chain operates, and the
operating-cost learning tiers have to be calibrated against a scale.

### 5.1 The decision variables

Seven families per region. `b` is the only binary block — build or don't — and everything else is
continuous, which is a deliberate choice from Part 3 that pays off in Part 4d.
""")

    C(r"""
m = gp.Model("planner")
m.Params.OutputFlag = 0
m.Params.MIPGap = 0.005

b, c, x, f_mp, f_pf, sale, disp = {}, {}, {}, {}, {}, {}, {}
for r in REGIONS:
    b[r] = m.addVars(BUILD[r], vtype=GRB.BINARY, name=f'b_{r}')      # build it?
    c[r] = m.addVars(BUILD[r], lb=0.0, ub=CAP_MAX, name=f'c_{r}')    # how big?
    x[r] = m.addVars(ACTIVE[r], lb=0.0, name=f'x_{r}')               # throughput
    f_mp[r] = m.addVars(P, lb=0.0, name=f'fmp_{r}')                  # mine -> proc flow
    f_pf[r] = m.addVars(P, lb=0.0, name=f'fpf_{r}')                  # proc -> mfg flow
    sale[r] = m.addVars(REGIONS, P, lb=0.0, name=f'sale_{r}')        # sales into each market
    disp[r] = m.addVars(P, lb=0.0, name=f'disp_{r}')                 # destroyed output

m.update()
print(f"{m.NumVars} variables, of which {m.NumBinVars} binary")
print(f"per region: {len(BUILD['R1'])} build pairs, {len(ACTIVE['R1'])} throughput triples")
""")

    M(r"""
### 5.2 Capacity: a plant you did not build cannot run

Three constraints, and the first two are the classic big-M pair that ties a continuous size to a
binary decision. `c <= CAP_MAX * b` forces size to zero when you don't build; `c >= CAP_MIN * b`
forces a *minimum viable scale* when you do — you cannot build a token 3-unit plant. Together they
make capacity a semi-continuous variable.

The third says throughput never exceeds the capacity available: inherited plants are capped by their
legacy size, new ones by whatever `c` was chosen.
""")

    C(r"""
for r in REGIONS:
    m.addConstrs((c[r][s, v] <= CAP_MAX * b[r][s, v] for (s, v) in BUILD[r]), name=f'su_{r}')
    m.addConstrs((c[r][s, v] >= CAP_MIN * b[r][s, v] for (s, v) in BUILD[r]), name=f'sl_{r}')
    m.addConstrs((x[r][s, v, p] <= (LEGACY_CAP[s, r] if v == -1 else c[r][s, v])
                  for (s, v, p) in ACTIVE[r]), name=f'cap_{r}')

m.update()
print(f"{m.NumConstrs} constraints after the capacity block")
""")

    M(r"""
### 5.3 The chain balance: what comes out of one stage goes into the next

Five constraints per region per period, and they are the physical heart of the model. Ore mined,
multiplied by the mine's **yield**, has to equal the flow into processing; that flow has to equal
what processing takes in; and so on down to manufactured output, which must equal what is sold plus
what is thrown away.

The yield `ETA[s, v, p]` is where section 3.3's work shows up: an old inherited plant loses more of
the material at every step, so it needs more ore to deliver the same finished tonne.
""")

    C(r"""
for r in REGIONS:
    m.addConstrs((gp.quicksum(ETA['MINE', v, p] * x[r]['MINE', v, p]
                              for v in VIN[r, 'MINE', p]) == f_mp[r][p] for p in P),
                 name=f'mine_{r}')
    m.addConstrs((f_mp[r][p] == gp.quicksum(x[r]['PROC', v, p] for v in VIN[r, 'PROC', p])
                  for p in P), name=f'pin_{r}')
    m.addConstrs((gp.quicksum(ETA['PROC', v, p] * x[r]['PROC', v, p]
                              for v in VIN[r, 'PROC', p]) == f_pf[r][p] for p in P),
                 name=f'pout_{r}')
    m.addConstrs((f_pf[r][p] == gp.quicksum(x[r]['MFG', v, p] for v in VIN[r, 'MFG', p])
                  for p in P), name=f'min_{r}')
    m.addConstrs((gp.quicksum(ETA['MFG', v, p] * x[r]['MFG', v, p]
                              for v in VIN[r, 'MFG', p])
                  == sale[r].sum('*', p) + disp[r][p] for p in P), name=f'mout_{r}')

m.update()
print(f"{m.NumConstrs} constraints after the chain balance")
""")

    M(r"""
### 5.4 Cumulative production, and the head start

`cum[p]` is everything the region has ever manufactured up to and including period `p`, undiscounted
— learning does not care about the time value of money — **plus `EXPERIENCE0[r]`**, the experience it
walked in with. Note `LEN[q] * x[...]`: a period of length 5 produces five years' worth.

This single variable is the one that turns quantity into a strategic weapon later. Selling more today
moves you up this curve, and section 10 is where that stops being a footnote.
""")

    C(r"""
cum = {}
for r in REGIONS:
    cum[r] = m.addVars(P, lb=0.0, ub=3 * CAP_MAX * HORIZON + EXPERIENCE0[r], name=f'cum_{r}')
    m.addConstrs((cum[r][p] == EXPERIENCE0[r] +
                  gp.quicksum(LEN[q] * x[r]['MFG', v, q] for q in P if q <= p
                              for v in VIN[r, 'MFG', q]) for p in P), name=f'cp_{r}')

m.update()
print("starting experience:", {r: EXPERIENCE0[r] for r in REGIONS})
print(f"upper bound on cum: ", {r: round(3 * CAP_MAX * HORIZON + EXPERIENCE0[r], 0) for r in REGIONS})
""")

    M(r"""
### 5.5 Capital cost, and the SOS2 that section 4 warned about

Capex splits in two. Stages that do **not** learn are charged the ordinary way: an annuitised fixed
cost for deciding to build, plus an annuitised per-unit cost for the size.

Stages that **do** learn get the piecewise curve. `Q[p]` is cumulative learning-stage capacity by
period `p`, `Cc[p]` the cumulative spend multiplier read off the curve at that point, and `lam` the
convex-combination weights. The capex charged in period `p` is the *increment* `Cc[p] - Cc[p-1]` —
what this period's building added, not the whole area again.

**`m.addSOS(GRB.SOS_TYPE2, ...)` is the line that matters.** Without it the weights are free to
combine breakpoint 0 with breakpoint 8 and report a cost below the true curve, because the curve is
concave and this term is being minimised. SOS2 restricts the weights to at most two *adjacent*
breakpoints, which is exactly the interpolation we meant.
""")

    C(r"""
capex = {}
for r in REGIONS:
    capex[r] = (gp.quicksum(MU[s, v] * FIXED[s, r] * b[r][s, v] for (s, v) in BUILD[r])
                + gp.quicksum(MU[s, v] * UNIT[s, r] * c[r][s, v]
                              for (s, v) in BUILD[r] if s not in LEARN_STAGES))

    Q = m.addVars(P, lb=Q_START, ub=Q_START + Q_ADD, name=f'Q_{r}')
    Cc = m.addVars(P, lb=0.0, name=f'C_{r}')
    lam = m.addVars(P, K, lb=0.0, ub=1.0, name=f'lam_{r}')
    m.addConstrs((lam.sum(p, '*') == 1 for p in P), name=f'sc_{r}')
    m.addConstrs((Q[p] == gp.quicksum(QBP[k] * lam[p, k] for k in K) for p in P), name=f'sQ_{r}')
    m.addConstrs((Cc[p] == gp.quicksum(CBP[k] * lam[p, k] for k in K) for p in P), name=f'sC_{r}')
    m.addConstrs((Q[p] == Q_START + gp.quicksum(c[r][s, v] for (s, v) in BUILD[r]
                                                if s in LEARN_STAGES and v <= p)
                  for p in P), name=f'cc_{r}')
    for p in P:
        m.addSOS(GRB.SOS_TYPE2, [lam[p, k] for k in K])          # <-- the important line

    rate = sum(UNIT[s, r] for s in LEARN_STAGES) / len(LEARN_STAGES)
    capex[r] += gp.quicksum(MU['PROC', p] * rate * (Cc[p] - (Cc[p - 1] if p > 0 else 0.0))
                            for p in P)

m.update()
print(f"{m.NumVars} variables, {m.NumConstrs} constraints, {m.NumSOS} SOS2 sets")
print(f"({len(P)} periods x {len(REGIONS)} regions = {len(P) * len(REGIONS)} SOS2 sets, as expected)")
""")

    M(r"""
### 5.6 Operating cost, transport and disposal

Here the operating cost is **flat** — `OPEX[s, r]` per unit, no tiers. That is deliberate and
temporary: the tiered version needs a calibration this model has not produced yet. Section @TIERS@ does the
calibration and section @TIERED@ builds the tiered version.

`OMEGA[p]` appears on every operating term because these are annual flows inside a multi-year period,
where the capex terms above used `MU` because they are annuities on a lump.
""")

    C(r"""
cost = {}
for r in REGIONS:
    opex = gp.quicksum(OMEGA[p] * OPEX[s, r] * x[r][s, v, p] for (s, v, p) in ACTIVE[r])
    trans = gp.quicksum(OMEGA[p] * TRANSPORT[r, rt] * sale[r][rt, p]
                        for rt in REGIONS for p in P)
    dcost = gp.quicksum(OMEGA[p] * PEN_DISPOSE * disp[r][p] for p in P)
    cost[r] = capex[r] + opex + trans + dcost

print("cost expression built for", list(cost))
print(f"each has {cost['R1'].size()} linear terms")
""")

    M(r"""
### 5.7 Meet demand, then solve

The planner has to serve both markets or pay `PEN_SHORT` per unit short. `w1 = 0.5` weights the two
regions equally.

> **Predict before you run.** R1 has the bigger market and far more accumulated experience; R2 is
> cheaper to build and cheaper to run at every stage. Write down which region you expect the planner
> to lean on for the *marginal* tonne, and whether you expect any demand to go unserved at a penalty
> of 90 against a transport cost of 2.4.

The `assert` before `optimize()` is a shape check, not a status check: an empty model also "succeeds".
""")

    C(r"""
W1 = 0.5
short = m.addVars(REGIONS, P, lb=0.0, name='short')
m.addConstrs((gp.quicksum(sale[r][rt, p] for r in REGIONS) + short[rt, p] >= DEMAND[rt, p]
              for rt in REGIONS for p in P), name='demand')
pen = gp.quicksum(OMEGA[p] * PEN_SHORT * short[rt, p] for rt in REGIONS for p in P)
m.setObjective(W1 * cost['R1'] + (1 - W1) * cost['R2'] + pen, GRB.MINIMIZE)

m.update()
assert m.NumVars > 0 and m.NumConstrs > 0, "empty model"
assert m.NumSOS == len(P) * len(REGIONS), "SOS2 sets went missing"

m.optimize()
assert m.SolCount > 0, f"no solution; status {m.Status}"
print(f"status {m.Status}, objective {m.ObjVal:,.1f}, MIP gap {m.MIPGap:.2e}")
print(f"unserved demand total: {sum(short[rt, p].X for rt in REGIONS for p in P):.3f}")
print("builds:", {r: sum(1 for k in BUILD[r] if b[r][k].X > 0.5) for r in REGIONS})
""")

    return [(k, _sub(t, tiers=tiers, tiered=tiered)) for k, t in out]


def tier_section():
    """Section 6: calibrating the operating-cost tiers off the planner's scale."""
    out, M, C = _cells()
    M(r"""
## 6. Calibrating the operating-cost tiers

Operating cost falls with cumulative production too, but through a different mechanism: a **step
function**, not a smooth curve. Below a threshold you pay full price; past it you drop to a cheaper
tier. `LR_OPEX = 0.18` sets the size of each step (18% cheaper per tier), `N_TIERS = 3` how many
there are.

The thresholds cannot be knobs, because a threshold is only meaningful relative to how much this
chain actually produces. So they are calibrated: take the cumulative production the planner just
reached, and place the first threshold at one eighth of it, the second at a quarter. Any region that
runs its chain hard passes both; one that idles passes neither.

**`LAG_YEARS = 3`** is the other idea here. Learning takes time to show up in the cost base, so the
tier applying in period `p` is decided by cumulative production three years *earlier*. That lag is
what stops a firm buying itself an instant discount in the period it produces.
""")

    C(r"""
LR_OPEX = 0.18        # each tier is 18% cheaper than the one before
OPEX_FLOOR = 0.65     # the multiplier cannot fall below this
N_TIERS = 3
LAG_YEARS = 3

top = {r: cum[r][P[-1]].X for r in REGIONS}

TIER_Q, TIER_M = {}, {}
for r in REGIONS:
    _t = max(top[r], 1.0)
    _q1 = _t / 8.0
    TIER_Q[r] = [_q1 * 2 ** j for j in range(N_TIERS - 1)]
    TIER_M[r] = [max(OPEX_FLOOR, (1 - LR_OPEX) ** j) for j in range(N_TIERS)]

print("cumulative production the planner reached, by the last period:")
for r in REGIONS:
    print(f"  {r}: {top[r]:10.2f}")
print(f"\n{N_TIERS} tiers means {N_TIERS - 1} thresholds (they are the boundaries between tiers):")
for r in REGIONS:
    print(f"  {r}: thresholds {[round(q, 1) for q in TIER_Q[r]]}"
          f"   multipliers {[round(v, 3) for v in TIER_M[r]]}")
""")

    return out
