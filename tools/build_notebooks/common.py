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
                       "@BLOCKS@", "@HORIZON_NOTE@", "@MODEL@",
                       "@HORIZON@", "@YEAR_GRID@", "@BLOCKS@",
                       "@REPORT_UNTIL@", "@NPERIODS@")
            if m in text]
    if left:
        raise ValueError(f"unfilled section placeholders {left} in a shared cell")
    return text


def setup_section(repo="advopt-lithiumsc", notebook="04c_cournot.ipynb"):
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

REPO_URL = "https://github.com/sear-labs/advopt-lithiumsc.git"
# Forked or renamed? Change BOTH halves of that path. Only the owner ever
# looked like a placeholder, and the repo name beside it broke 64 URLs once.
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


def twostage_instance_section(agree=9):
    """Section 2 for Parts 2b and 2c: the two-stage network's two tables."""
    out, M, C = _cells()

    M(r"""
## 2. The instance

**This is a third instance, and confusing it with the other two will waste an
hour.** Part 1 and Part 2 use a six-site, twenty-year network with vintages,
lead times and learning. Part 4 uses a two-region chain owned by competing
firms. This one is single-period: three stages, two regions, six capacity
nodes, twelve arcs, and no time at all.

It is smaller on purpose. Part 2b needs the **duals** of the capacity rows, and
for those to exist the second stage has to be a linear program. In Part 1's
model capacity is entangled with binaries, vintages and lead times, and there is
no clean dual to build a cut from.

| file | keyed by | rows |
|---|---|---|
| `twostage_stages.csv` | `stage` | 3 |
| `twostage_regions.csv` | `region` | 2 |

`region_cost` is read by both notebooks and used only by Part 2c; Part 2b has no
regional cost asymmetry. They are different models, not one model with a flag.
""")

    M(r"""
Read the two tables and look at them as frames before turning them into anything
the model indexes.
""")

    C(r'''
DATA = Path("data/raw")

if not (DATA / "twostage_stages.csv").exists():
    print("!" * 78)
    print("! data/raw/ was not found, so this notebook is FALLING BACK to generated")
    print("! numbers. Everything below will run and every figure will render, but the")
    print("! results are NOT the shipped instance and are NOT an acceptable submission.")
    print("! Fix: clone the repo (see section 0) or run this notebook from the repo root.")
    print("!" * 78)
    DATA = Path("_generated_fallback")
    DATA.mkdir(exist_ok=True)
    (DATA / "twostage_stages.csv").write_text(
        "stage,fix,unit,opc,eta\nMINE,240.0,2.2,0.8,0.95\n"
        "PROC,200.0,2.9,1.3,0.90\nMFG,160.0,3.3,1.6,0.93\n")
    (DATA / "twostage_regions.csv").write_text(
        "region,demand_base,region_cost\nR1,34.0,0.72\nR2,22.0,1.00\n")

stages_df = pd.read_csv(DATA / "twostage_stages.csv")
regions_df = pd.read_csv(DATA / "twostage_regions.csv")
print(f"twostage_stages.csv : {len(stages_df)} rows x {len(stages_df.columns)} columns")
print(f"twostage_regions.csv: {len(regions_df)} rows x {len(regions_df.columns)} columns")
stages_df
''')

    M(r"""
A frame shows rows and columns. The model does not index by row number — it
indexes by `stage` and by `region`. Print the dictionary form so the **key** is
explicit rather than implied by the layout.
""")

    C(r'''
STAGES = tuple(stages_df["stage"])
REGIONS = tuple(regions_df["region"])

FIX = dict(zip(stages_df["stage"], stages_df["fix"].astype(float)))
UNIT = dict(zip(stages_df["stage"], stages_df["unit"].astype(float)))
OPC = dict(zip(stages_df["stage"], stages_df["opc"].astype(float)))
ETA = dict(zip(stages_df["stage"], stages_df["eta"].astype(float)))
DEMAND_BASE = dict(zip(regions_df["region"], regions_df["demand_base"].astype(float)))
REGION_COST = dict(zip(regions_df["region"], regions_df["region_cost"].astype(float)))

print(f"STAGES  {STAGES}")
print(f"REGIONS {REGIONS}")
for name, d in (("FIX", FIX), ("UNIT", UNIT), ("OPC", OPC), ("ETA", ETA)):
    print(f"{name:12s} {d}")
print(f"{'DEMAND_BASE':12s} {DEMAND_BASE}")
print(f"{'REGION_COST':12s} {REGION_COST}   (Part 2c only)")

# Try it: give R2 the cheaper operating costs instead and watch section @AGREE@
# stay green, because the package is handed this table rather than re-reading it.
# REGION_COST["R1"], REGION_COST["R2"] = 1.00, 0.72
''')
    return [(k, _sub(t, agree=agree)) for k, t in out]


def twostage_structure_section(agree=9):
    """Section 3 for Parts 2b and 2c: the knobs, and the sets derived from them."""
    out, M, C = _cells()

    M(r"""
## 3. The knobs, and the sets derived from them

Everything in this section is either a **knob** — a scalar carrying a concept,
written out here where the sentence explaining it is — or **arithmetic** on the
tables above. Nothing here is data.

The four knobs:

- `CMIN`, `CMAX` — a node that opens at all must be at least `CMIN` and at most
  `CMAX`. Together with the binary `y` this is what makes stage 1 a *discrete*
  decision rather than a continuous one, and therefore what makes the master
  problem in Part 2b a MILP.
- `PEN` — the penalty per unit of unmet demand. It has to exceed the cost of
  serving that demand the expensive way, or the model will simply decline to
  serve it.
- `TAU_OWN`, `TAU_CROSS` — transport within a region and across regions.
""")

    C(r'''
CMIN, CMAX = 5.0, 70.0        # a node that opens is between these
PEN = 30.0                    # per unit of unmet demand
TAU_OWN, TAU_CROSS = 0.3, 1.5   # transport within / across regions

NODES = [(s, r) for s in STAGES for r in REGIONS]
ARCS = [(s, a, b) for s in STAGES for a in REGIONS for b in REGIONS]
TAU = {(a, b): (TAU_OWN if a == b else TAU_CROSS)
       for a in REGIONS for b in REGIONS}

print(f"{len(NODES)} capacity nodes, {len(ARCS)} arcs")
print(f"nodes: {NODES}")
print(f"TAU  : {TAU}")
print(f"\ncrossing a region costs {TAU_CROSS / TAU_OWN:.0f}x what staying home does,")
print(f"and PEN = {PEN} is {PEN / max(OPC.values()):.0f}x the dearest stage's opex,")
print("so unmet demand is a last resort rather than a cheap way out.")
''')

    M(r"""
### 3.1 What a plan can physically deliver

Yields compound down the chain, so a MINE node of capacity $c$ can support at
most $\eta_{\text{MINE}} c$ of processing and $\eta_{\text{MINE}}
\eta_{\text{PROC}} c$ of manufacturing. That product is worth computing now,
because it turns up as the answer later: the optimal plans in both notebooks sit
exactly on this chain rather than anywhere in between.
""")

    C(r'''
chain = 1.0
for s in STAGES:
    chain *= ETA[s]
    print(f"a unit of MINE capacity supports {chain:.4f} through {s}")

MAX_DELIVERABLE = CMAX * ETA[STAGES[0]] * ETA[STAGES[1]]
print(f"\none full-size chain ({CMAX:.0f} at each stage, sized down the yields):")
print(f"  {CMAX:.2f} -> {CMAX * ETA[STAGES[0]]:.2f} -> {MAX_DELIVERABLE:.4f}")
print(f"total peak demand across regions can reach "
      f"{sum(DEMAND_BASE.values()) * 1.55:.1f}, so one chain is not obviously enough")
''')
    return [(k, _sub(t, agree=agree)) for k, t in out]


def netcore_instance_section(agree=15):
    """Section 2 for Parts 3 and 3b: the network-core instance's four tables."""
    out, M, C = _cells()

    M(r"""
## 2. The instance

**This is the fourth instance in the series, and it is the one most easily
confused with Part 4's**, because it has the same three stages and the same two
regions. The differences are the whole reason both exist:

| | here (Parts 3, 3b) | Part 4's chain |
|---|---|---|
| who decides | one planner, minimising cost | two firms, maximising profit |
| what crosses regions | anything, at any stage | finished goods only |
| learning | one industry-wide pool | per firm |
| price | none; demand must be served | endogenous, or fixed |
| costs by region | **symmetric** | asymmetric |

The symmetric costs matter. With both regions identical on cost, whatever
asymmetry appears in the answer came from demand, legacy fleets and geography —
not from one region simply being cheaper. That makes this the right place to
study the machinery before Part 4 adds a thumb to the scale.

| file | keyed by | rows |
|---|---|---|
| `netcore_stages.csv` | `stage` | 3 |
| `netcore_nodes.csv` | `(stage, region)` | 6 |
| `netcore_regions.csv` | `region` | 2 |
| `efficiency.csv` | `stage` | 3 |

`efficiency.csv` is **the same file Part 4 reads**, not a copy of it. The yield
model is genuinely shared; the cost tables are not.
""")

    C(r'''
DATA = Path("data/raw")

if not (DATA / "netcore_stages.csv").exists():
    print("!" * 78)
    print("! data/raw/ was not found, so this notebook is FALLING BACK to generated")
    print("! numbers. Everything below will run and every figure will render, but the")
    print("! results are NOT the shipped instance and are NOT an acceptable submission.")
    print("! Fix: clone the repo (see section 0) or run this notebook from the repo root.")
    print("!" * 78)
    DATA = Path("_generated_fallback")
    DATA.mkdir(exist_ok=True)
    (DATA / "netcore_stages.csv").write_text(
        "stage,fixed,unit,operate,lead\nMINE,900.0,7.0,1.2,1\n"
        "PROC,1500.0,11.0,2.0,2\nMFG,1300.0,9.5,2.4,2\n")
    (DATA / "netcore_nodes.csv").write_text(
        "stage,region,legacy_cap,legacy_ret\nMINE,R1,200,9\nMINE,R2,180,14\n"
        "PROC,R1,170,12\nPROC,R2,150,19\nMFG,R1,130,16\nMFG,R2,120,24\n")
    (DATA / "netcore_regions.csv").write_text(
        "region,demand_base,demand_growth\nR1,100.0,0.008\nR2,70.0,0.026\n")
    (DATA / "efficiency.csv").write_text(
        "stage,eta_ceil,eta_base,alpha,beta,delta_bar\nMINE,0.92,0.86,0.0,0.0,0.02\n"
        "PROC,0.95,0.80,0.030,0.010,0.05\nMFG,0.93,0.78,0.025,0.008,0.05\n")

stages_df = pd.read_csv(DATA / "netcore_stages.csv")
nodes_df = pd.read_csv(DATA / "netcore_nodes.csv")
regions_df = pd.read_csv(DATA / "netcore_regions.csv")
eff_df = pd.read_csv(DATA / "efficiency.csv")
for nm, df in (("netcore_stages", stages_df), ("netcore_nodes", nodes_df),
               ("netcore_regions", regions_df), ("efficiency", eff_df)):
    print(f"{nm + '.csv':22s} {len(df)} rows x {len(df.columns)} columns")
stages_df
''')

    M(r"""
A frame shows rows and columns; the model indexes by `stage` and by
`(stage, region)`. Print the dictionary form so the **key** is explicit rather
than implied by the layout — every constraint below looks values up by one of
those two keys, and getting them confused is the most common way to build a
model that solves and means nothing.
""")

    C(r'''
STAGES = tuple(stages_df["stage"])
REGIONS = tuple(regions_df["region"])
NODES = [(s, r) for s in STAGES for r in REGIONS]
ARCS = [(s, a, b) for s in STAGES for a in REGIONS for b in REGIONS]

FIXED = dict(zip(stages_df["stage"], stages_df["fixed"].astype(float)))
UNIT = dict(zip(stages_df["stage"], stages_df["unit"].astype(float)))
OPERATE = dict(zip(stages_df["stage"], stages_df["operate"].astype(float)))
LEAD = dict(zip(stages_df["stage"], stages_df["lead"].astype(int)))

_k = list(zip(nodes_df["stage"], nodes_df["region"]))
LEGACY_CAP = dict(zip(_k, nodes_df["legacy_cap"].astype(float)))
LEGACY_RET = dict(zip(_k, nodes_df["legacy_ret"].astype(int)))

DEMAND_BASE = dict(zip(regions_df["region"], regions_df["demand_base"].astype(float)))
DEMAND_GROWTH = dict(zip(regions_df["region"], regions_df["demand_growth"].astype(float)))

ETA_CEIL = dict(zip(eff_df["stage"], eff_df["eta_ceil"].astype(float)))
ETA_BASE = dict(zip(eff_df["stage"], eff_df["eta_base"].astype(float)))
ALPHA = dict(zip(eff_df["stage"], eff_df["alpha"].astype(float)))
BETA = dict(zip(eff_df["stage"], eff_df["beta"].astype(float)))
DELTA_BAR = dict(zip(eff_df["stage"], eff_df["delta_bar"].astype(float)))

print(f"{len(NODES)} nodes: {NODES}")
print(f"{len(ARCS)} arcs, e.g. {ARCS[:3]} ...")
print(f"\n{'FIXED':12s} {FIXED}")
print(f"{'UNIT':12s} {UNIT}")
print(f"{'OPERATE':12s} {OPERATE}")
print(f"{'LEAD':12s} {LEAD}")
print(f"{'LEGACY_CAP':12s} {LEGACY_CAP}")
print(f"{'LEGACY_RET':12s} {LEGACY_RET}")

# Try it: make R2 the cheap region and re-run. Section @AGREE@ stays green,
# because the package is handed this table rather than re-reading the file.
# FIXED, UNIT, OPERATE are keyed by STAGE here, so that edit needs the model to
# index them by (stage, region) first - which is exactly what Part 4 does.
''')

    M(r"""
**Every arc exists.** A mine in R1 can feed a processor in R2 and vice versa, at
every stage. That is the structural difference from Part 4, where each region's
chain is internally closed and only the finished product is traded, and it is
why this model has a `flow` variable indexed by `(stage, from, to, period)`
rather than a single sales variable.
""")
    return [(k, _sub(t, agree=agree)) for k, t in out]


def netcore_structure_section(agree=15, blocks="[(8, 1), (4, 3), (2, 5), (1, 9)]",
                              horizon=39, nperiods=15, report_until=30):
    """Section 3 for Parts 3 and 3b: the knobs and everything derived from them."""
    out, M, C = _cells()

    M(r"""
## 3. Time, and the knobs everything hangs off

### Variable-length periods, and why

A 39-year horizon at annual resolution would be 39 periods and a model several
times the size. But the near years are where the decisions are, and the far
years are there to stop the model treating the end of the horizon as the end of
the world. So the mesh is **fine early and coarse late**.

`BLOCKS` is a list of `(how many periods, years in each)`. Everything downstream
— period starts, discount weights, which vintages are operating when — is
arithmetic on it, which is why it is a knob and not a table.

**`REPORT_UNTIL` is the other half of the same idea.** The horizon runs past the
last year anyone reads, so that a facility built in the reporting window still
captures most of its 25-year life *inside* the model. Without that buffer the
model refuses to build late, not because building late is bad but because the
model stops before the asset has paid for itself. Section 16 measures what that
buffer is worth.
""")

    C(r'''
BLOCKS = @BLOCKS@   # (how many periods, years in each)
DR = 0.05           # discount rate
LIFE = 25           # asset life, years
CAP_MIN, CAP_MAX = 60.0, 260.0    # a facility that is built is between these
LEGACY_BYR = -8     # inherited assets are already 8 years old
ETA_FLOOR = 0.60    # no vintage is ever worse than this
REPORT_UNTIL = @REPORT_UNTIL@   # years past this are the cool-down buffer

LEN, START, _y = [], [], 1
for _count, _length in BLOCKS:
    for _ in range(_count):
        LEN.append(_length)
        START.append(_y)
        _y += _length
P = list(range(len(LEN)))
HORIZON = _y - 1
YEARS = {p: list(range(START[p], START[p] + LEN[p])) for p in P}
YEAR_TO_P = {t: p for p in P for t in YEARS[p]}

# OMEGA[p] is the SUM of annual discount factors inside period p, so a
# per-year cost multiplied by it becomes that period's present value. It is NOT
# an average: a 9-year period must carry nine years of cost.
OMEGA = {p: sum(1 / (1 + DR) ** t for t in YEARS[p]) for p in P}

print(f"{len(P)} periods spanning {HORIZON} years; "
      f"sum of weights = {sum(OMEGA.values()):.3f}")
print(f"reporting window ends at year {REPORT_UNTIL}; "
      f"years {REPORT_UNTIL + 1}-{HORIZON} are the cool-down buffer")
pd.DataFrame([dict(period=p, years=f"{START[p]}-{START[p] + LEN[p] - 1}",
                   length=LEN[p], omega=round(OMEGA[p], 3)) for p in P])
''')

    M(r"""
### 3.1 The capital recovery factor, and charging capex by the year

A facility bought in year $v$ is paid for once but used for `LIFE` years. Charging
the whole cheque in year $v$ makes late builds look ruinous; charging nothing
makes them free. The standard fix is to **annuitise**: convert the lump sum into
an equivalent annual payment with the capital recovery factor, then discount only
the years that fall inside the horizon.

$$\text{CRF} = \frac{r(1+r)^{L}}{(1+r)^{L}-1}
\qquad\qquad
\mu_{s,v} = \text{CRF}\sum_{t=\text{online}}^{\text{online}+L-1}\!\!\!\!
\frac{\mathbb{1}[t \le T]}{(1+r)^{t}}$$

**`MU` is the coefficient that makes late builds behave sensibly**, and section
16 compares it against the lump-sum alternative.
""")

    C(r'''
CRF = DR * (1 + DR) ** LIFE / ((1 + DR) ** LIFE - 1)
ONLINE = {(s, p): START[p] + LEAD[s] for s in STAGES for p in P}

MU = {(s, v): CRF * sum(1 / (1 + DR) ** t
                        for t in range(ONLINE[s, v], ONLINE[s, v] + LIFE)
                        if t <= HORIZON)
      for s in STAGES for v in P}

print(f"CRF ({LIFE} yr at {DR:.0%}) = {CRF:.5f}")
print("MU for PROC by decision period:",
      {v: round(MU['PROC', v], 3) for v in [0, len(P) // 3, len(P) - 4, len(P) - 1]})
print("\nMU falls at the end of the horizon because a late build's later years")
print("fall outside it. That is the truncation the buffer is there to absorb.")
''')

    M(r"""
### 3.2 Demand

Each region's demand grows at its own rate. R2 starts smaller and grows faster,
which is what makes the siting question interesting rather than obvious.
""")

    C(r'''
DEMAND = {}
for r in REGIONS:
    base, g = DEMAND_BASE[r], DEMAND_GROWTH[r]
    for p in P:
        DEMAND[r, p] = sum(base * (1 + g) ** (t - 1) for t in YEARS[p]) / LEN[p]

TRANSPORT_OWN, TRANSPORT_CROSS = 0.5, 2.0
TRANSPORT = {(a, b): (TRANSPORT_OWN if a == b else TRANSPORT_CROSS)
             for a in REGIONS for b in REGIONS}
PEN_SHORT = 90.0     # per unit of unmet final demand

print(f"demand rate, year 1 : { {r: round(DEMAND[r, 0], 1) for r in REGIONS} }")
print(f"demand rate, year {START[P[-1]]}: "
      f"{ {r: round(DEMAND[r, P[-1]], 1) for r in REGIONS} }")
cross = [r for r in REGIONS if DEMAND[r, P[-1]] > DEMAND[REGIONS[0], P[-1]]]
print(f"\ncrossing regions costs {TRANSPORT_CROSS / TRANSPORT_OWN:.0f}x staying home")
print(f"unmet demand costs {PEN_SHORT}, which is "
      f"{PEN_SHORT / max(OPERATE.values()):.0f}x the dearest stage's opex")
''')

    M(r"""
### 3.3 Vintage efficiency: two channels, both indexed by vintage

Yield improves for two separate reasons and the model keeps them apart.

- **A later vintage starts better.** The frontier moves at rate $\alpha$ per
  year, so a facility built in year 20 begins life more efficient than one built
  in year 1 ever becomes.
- **An asset improves with age**, at rate $\beta$, but by at most
  $\bar\delta$ over its whole life. Retrofits help; they do not turn a 1990s
  plant into a new one.

Both are capped by the stage's ceiling $\bar\eta$ and floored at `ETA_FLOOR`.
The result is `ETA[stage, vintage, period]` — a yield that depends on **when it
was built and when it is running**, which is why throughput has to be tracked
per vintage rather than per node.
""")

    C(r'''
VINTAGES = [-1] + P          # -1 is the inherited legacy cohort
BUILD_YEAR = {v: (LEGACY_BYR if v == -1 else START[v]) for v in VINTAGES}

ETA = {}
for s in STAGES:
    for v in VINTAGES:
        frontier = ETA_CEIL[s] - (ETA_CEIL[s] - ETA_BASE[s]) \
            * (1 - ALPHA[s]) ** (BUILD_YEAR[v] - 1)
        frontier = max(ETA_FLOOR, min(frontier, ETA_CEIL[s]))
        for p in P:
            age = max(0, START[p] - BUILD_YEAR[v])
            aged = ETA_CEIL[s] - (ETA_CEIL[s] - frontier) * (1 - BETA[s]) ** age
            ETA[s, v, p] = max(ETA_FLOOR, min(frontier + DELTA_BAR[s], aged))

# the theory, asserted: a yield is a fraction, never exceeds its ceiling, and a
# later vintage is never worse than an earlier one in the same period
for s in STAGES:
    for p in P:
        assert all(ETA_FLOOR - 1e-12 <= ETA[s, v, p] <= ETA_CEIL[s] + 1e-12
                   for v in VINTAGES), f"{s} yield left [floor, ceiling] in period {p}"
        vs = [v for v in P if v <= p]
        assert all(ETA[s, vs[i], p] <= ETA[s, vs[i + 1], p] + 1e-12
                   for i in range(len(vs) - 1)), \
            f"{s}: a later vintage is worse than an earlier one in period {p}"
print(f"{len(ETA)} yields, keyed (stage, vintage, period)")
print("\nPROC yield by vintage and operating period:")
_show_p = [0, len(P) // 3, 2 * len(P) // 3, len(P) - 1]
pd.DataFrame({f"vintage {v}": [round(ETA['PROC', v, p], 4) for p in _show_p]
              for v in [-1, 0, len(P) // 2]},
             index=[f"yr {START[p]}" for p in _show_p]).T
''')

    M(r"""
### 3.4 Which vintages are operating when

A legacy asset runs until its retirement year, **inclusive**. A built asset runs
from `LEAD` years after its decision, for `LIFE` years. `ACTIVE` is the set of
`(stage, region, vintage, period)` combinations that exist at all, and `VIN` is
the same information indexed the way the constraints need it.

Building these sets explicitly, rather than writing `if` conditions inside every
constraint, is what keeps the model readable — and it means a mistake in the
timing shows up here as a wrong count rather than as a silently missing
constraint fifty lines further down.
""")

    C(r'''
ACTIVE = [(s, r, v, p)
          for (s, r) in NODES for v in VINTAGES for p in P
          if (v == -1 and START[p] <= LEGACY_RET[s, r])
          or (v >= 0 and ONLINE[s, v] <= START[p] <= ONLINE[s, v] + LIFE - 1)]

VIN = {}
for (s, r, v, p) in ACTIVE:
    VIN.setdefault((s, r, p), []).append(v)

# a build decision is only meaningful if the asset comes online inside the horizon
BUILD = [(s, r, v) for (s, r) in NODES for v in P if ONLINE[s, v] <= HORIZON]

assert len(ACTIVE) > 0 and len(BUILD) > 0, "an empty index set reports success too"
print(f"{len(ACTIVE)} active (node, vintage, period) triples")
print(f"{len(BUILD)} candidate build decisions -> {len(BUILD)} binaries")
print(f"\nlegacy MINE/R1 retires in year {LEGACY_RET['MINE', 'R1']} and is active "
      f"in {sum(1 for (s, r, v, p) in ACTIVE if (s, r, v) == ('MINE', 'R1', -1))} periods")
''')
    return [(k, _sub(t, agree=agree, blocks=blocks, horizon=horizon,
                     nperiods=nperiods, report_until=report_until))
            for k, t in out]


def network_instance_section(agree=13):
    """Section 2 for Parts 1 and 2: the six-site network's three tables."""
    out, M, C = _cells()

    M(r"""
## 2. The instance tables

Two kinds of number go into this model and they are treated differently.

A **knob** is a scalar carrying a concept — the discount rate, the asset life, the
learning rate. Knobs stay written out in the cell where they are explained, and
this notebook hands every one of them to the package in section @AGREE@, so the
agreement assertion covers them.

A **table** is instance data — many entries, indexed by the model's own sets,
named nowhere in the prose. Tables live in `data/raw/`, and both this notebook and
`src/lithium/` read the same file. Three tables:

| file | keyed by | rows |
|---|---|---|
| `network_sites.csv` | `site` | 6 |
| `network_tiers.csv` | `tier` | 2 |
| `network_demand.csv` | `region` | 2 |

**This is not the Part 4 instance.** Part 4's model is a two-region,
three-stage chain owned by competing *firms*; this is a six-site network owned by
one *planner*, with explicit arcs between sites. Both have a home region, an opex
and a lead time, which makes them easy to confuse — they share nothing.
""")

    M(r"""
Read the site table first and look at it as a **frame** — rows and columns —
before turning it into anything the model can index.
""")

    C(r'''
DATA = Path("data/raw")

if not (DATA / "network_sites.csv").exists():
    print("!" * 78)
    print("! data/raw/ was not found, so this notebook is FALLING BACK to generated")
    print("! numbers. Everything below will run and every figure will render, but the")
    print("! results are NOT the shipped instance and are NOT an acceptable submission.")
    print("! Fix: clone the repo (see section 0) or run this notebook from the repo root.")
    print("!" * 78)
    DATA = Path("_generated_fallback")
    DATA.mkdir(exist_ok=True)
    (DATA / "network_sites.csv").write_text(
        "site,tier,home,cap_unit,lead,capex0,opex,legacy_units,legacy_vintage,legacy_retire\n"
        "M1,M,R1,100,2,2000,1.3,2,-6,8\nM2,M,R2,100,2,2000,1.3,2,-6,8\n"
        "P1,P,R1,100,3,3200,2.1,2,-3,13\nP2,P,R2,100,3,3200,2.1,2,-3,13\n"
        "F1,F,R1,90,2,2800,2.4,2,-1,17\nF2,F,R2,90,2,2800,2.4,2,-1,17\n")
    (DATA / "network_tiers.csv").write_text(
        "tier,eta_bar,eta_0,alpha,beta,dbar\nP,0.95,0.80,0.030,0.010,0.05\n"
        "F,0.93,0.78,0.025,0.008,0.05\n")
    (DATA / "network_demand.csv").write_text(
        "region,base,growth\nR1,100.0,0.03\nR2,100.0,0.03\n")

sites_df = pd.read_csv(DATA / "network_sites.csv")
print(f"network_sites.csv: {len(sites_df)} rows x {len(sites_df.columns)} columns")
sites_df
''')

    M(r"""
The other two tables. `network_tiers.csv` holds the yield-curve parameters for
the two tiers that have a *yield* to speak of — processing and fabrication.
Mining's yield is a single constant, so it is a knob, not a table.
""")

    C(r'''
tiers_df = pd.read_csv(DATA / "network_tiers.csv")
demand_df = pd.read_csv(DATA / "network_demand.csv")
print(f"network_tiers.csv: {len(tiers_df)} rows    "
      f"network_demand.csv: {len(demand_df)} rows")
display(tiers_df)
demand_df
''')

    M(r"""
### 2.1 From table to lookup — see the key

A frame shows rows and columns. **The model does not index by row number.** Every
constraint below looks a value up by a key: `cap_unit['P1']`, `eta_bar['F']`,
`legacy['M1']`. Build the dictionaries and print them in the form the constraints
will use.

The index sets come out of the table itself, in file order — mines, then
processors, then fabricators — so the order the model iterates in is a property
of the data, not of a `sorted()` call somewhere.
""")

    C(r'''
REGIONS = list(dict.fromkeys(demand_df["region"]))
TIER = {r.site: r.tier for r in sites_df.itertuples()}
MINES = [s for s in TIER if TIER[s] == "M"]
PROCS = [s for s in TIER if TIER[s] == "P"]
FABS = [s for s in TIER if TIER[s] == "F"]
SITES = MINES + PROCS + FABS

HOME = {r.site: r.home for r in sites_df.itertuples()}
CAP_UNIT = {r.site: float(r.cap_unit) for r in sites_df.itertuples()}
LEAD = {r.site: int(r.lead) for r in sites_df.itertuples()}
CAPEX0 = {r.site: float(r.capex0) for r in sites_df.itertuples()}
OPEX = {r.site: float(r.opex) for r in sites_df.itertuples()}
LEGACY = {r.site: (int(r.legacy_units), int(r.legacy_vintage), int(r.legacy_retire))
          for r in sites_df.itertuples()}

print(f"index sets:  REGIONS = {REGIONS}")
print(f"             MINES   = {MINES}    PROCS = {PROCS}    FABS = {FABS}")
print(f"             SITES   = {SITES}   <- the order every loop below follows\n")
print(f"{'site':6s} {'tier':5s} {'home':5s} {'cap':>6s} {'lead':>5s} {'capex0':>8s}"
      f" {'opex':>6s}  legacy (units, vintage, retires)")
for s in SITES:
    print(f"{s:6s} {TIER[s]:5s} {HOME[s]:5s} {CAP_UNIT[s]:6.0f} {LEAD[s]:5d}"
          f" {CAPEX0[s]:8.0f} {OPEX[s]:6.2f}  {LEGACY[s]}")
''')

    M(r"""
The same move for the two single-key tables. Note the asymmetry in the demand
table: R2 starts smaller but grows more than twice as fast, so which region the
network should serve changes over the horizon. That is the whole reason the model
is multi-period.
""")

    C(r'''
ETA_BAR = {r.tier: float(r.eta_bar) for r in tiers_df.itertuples()}
ETA_0 = {r.tier: float(r.eta_0) for r in tiers_df.itertuples()}
ALPHA = {r.tier: float(r.alpha) for r in tiers_df.itertuples()}
BETA = {r.tier: float(r.beta) for r in tiers_df.itertuples()}
DBAR = {r.tier: float(r.dbar) for r in tiers_df.itertuples()}

DEMAND_BASE = {r.region: float(r.base) for r in demand_df.itertuples()}
DEMAND_GROWTH = {r.region: float(r.growth) for r in demand_df.itertuples()}

print("keyed by tier:")
for k in ETA_BAR:
    print(f"  {k!r}: ceiling {ETA_BAR[k]:.2f}  vintage-1 {ETA_0[k]:.2f}"
          f"  frontier/yr {ALPHA[k]:.3f}  within-life/yr {BETA[k]:.3f}"
          f"  max lifetime gain {DBAR[k]:.2f}")
print("\nkeyed by region:")
for g in REGIONS:
    print(f"  {g!r}: demand starts at {DEMAND_BASE[g]:6.1f}, "
          f"growing {100 * DEMAND_GROWTH[g]:.1f}% a year")
''')

    M(r"""
### 2.2 Want to experiment? Change a number here, not in the CSV

Each table is now a dictionary keyed the way the model indexes. Assign to a key to
override one entry. The change flows into every model built below **and** into the
section @AGREE@ agreement check, because the package takes the data as an argument
instead of re-reading the file.
""")

    C(r'''
# ---------------------------------------------------------------------------
# Example - make the two processors equally expensive to build:
#
#     CAPEX0['P2'] = CAPEX0['P1']
#
# Uncomment, then re-run this cell and everything below it. P2's build-cost
# advantage disappears, the planner's siting choice shifts toward P1, and the
# section @AGREE@ assertion stays green because the notebook passes CAPEX0 to
# the package. Re-run with it commented out to get the shipped instance back.
# ---------------------------------------------------------------------------
print(f"CAPEX0['P1'] = {CAPEX0['P1']:.0f}, CAPEX0['P2'] = {CAPEX0['P2']:.0f}"
      f"   (P2 is {100 * (1 - CAPEX0['P2'] / CAPEX0['P1']):.0f}% cheaper today)")
''')

    return [(k, _sub(t, agree=agree)) for k, t in out]


def network_structure_section(agree=13, model=6, horizon=20):
    """Section 3 for Parts 1 and 2: everything derived from the tables and knobs."""
    out, M, C = _cells()
    # Five sample years spanning the horizon, for the display tables. At the
    # default T=20 this is exactly (1, 5, 10, 15, 20) -- the literal it replaced.
    grid = [1] + [round(horizon * k / 4) for k in (1, 2, 3, 4)]
    year_grid = "(" + ", ".join(str(y) for y in grid) + ")"
    assert horizon != 20 or year_grid == "(1, 5, 10, 15, 20)"

    M(r"""
## 3. The knobs, and the structure derived from them

Everything in this section is **derived**: the horizon, discount factors, the
capital recovery factor, yields by vintage, the demand path, transport costs.
None of it is data and none of it is a knob — it is arithmetic on the two, and
doing that arithmetic is the point.

`lithium.core.build_core_structure` computes the same things, and section @AGREE@
is what proves the two derivations agree.

### 3.1 The horizon and the time value of money

`T` and `r` are the two knobs everything else in this section hangs off.
""")

    C(r'''
T = @HORIZON@        # horizon, years
r = 0.05      # discount rate
LIFE = 20     # asset life, years
MAX_BUILDS = 3   # units that may be built at one site in one decision year

YEARS = list(range(1, T + 1))
DF = {t: 1.0 / (1 + r) ** t for t in YEARS}
CRF = r * (1 + r) ** LIFE / ((1 + r) ** LIFE - 1)

print(f"horizon {T} years at r = {r}")
print(f"CRF = {CRF:.6f}   (a 1.0 lump becomes {CRF:.4f} per year for {LIFE} years)")
print(f"discount factor: year 1 {DF[1]:.4f}, year {T} {DF[T]:.4f}"
      f"  -> the last year is worth {100 * DF[T]:.0f}% of the first")
''')

    M(r"""
### 3.2 Yields: a vintage effect and an ageing effect

Two things move an asset's yield, and they are not the same thing.

**The frontier improves.** An asset built later starts closer to the ceiling,
because the technology available in that year is better. That is `ALPHA`.

**An asset improves within its own life.** Operating experience lifts it toward
the ceiling too, at rate `BETA` — but by at most `DBAR` above where it started,
because a plant cannot be rebuilt by being run.

`ETA_MIN` clamps the arithmetic: a legacy asset from vintage −6 would otherwise
compute to something absurd.

**These curves never cross.** A later vintage starts higher and ages along a
parallel path, so it stays higher forever. That is worth checking rather than
assuming, and the cell asserts it.
""")

    C(r'''
ETA_MINE = 0.90    # ore -> concentrate; constant, so a knob rather than a table
ETA_MIN = 0.60     # clamp: legacy assets cannot be arbitrarily bad

VINTAGES = sorted({lv for (_, lv, _) in LEGACY.values()} | set(YEARS))
ETA = {}
for tier in ("P", "F"):
    eb, e0 = ETA_BAR[tier], ETA_0[tier]
    a, b, db = ALPHA[tier], BETA[tier], DBAR[tier]
    for v in VINTAGES:
        e_new = max(eb - (eb - e0) * (1 - a) ** (v - 1), ETA_MIN)
        for t in YEARS:
            e_t = eb - (eb - e_new) * (1 - b) ** (t - v)
            ETA[tier, v, t] = max(ETA_MIN, min(e_new + db, e_t))

assert all(ETA_MIN <= v <= 1.0 for v in ETA.values()), "a yield outside [ETA_MIN, 1]"
# a later vintage must stay above an earlier one, in every year both are running
assert all(ETA["P", 10, t] >= ETA["P", 2, t] for t in YEARS if t >= 10), \
    "vintage curves crossed - the frontier and ageing effects are mis-specified"

print(f"{len(ETA)} yields, keyed (tier, vintage, year)\n")
print(f"processing yield, by vintage and year:")
print(f"{'vintage':>8s} " + "".join(f"{'yr ' + str(t):>9s}" for t in @YEAR_GRID@))
for v in (-3, 1, 5, 10, 15):
    print(f"{v:8d} " + "".join(f"{ETA['P', v, t]:9.4f}" if t >= max(v, 1) else f"{'-':>9s}"
                               for t in @YEAR_GRID@))
''')

    M(r"""
### 3.3 Demand, and the transport that makes geography matter

Demand grows from each region's base at its own rate. Transport is four times
dearer across regions than within one, and that single ratio is what stops the
planner simply building everything in whichever region is cheapest.
""")

    C(r'''
TRANSPORT_OWN, TRANSPORT_CROSS = 0.4, 1.6
SLACK_PEN = 45.0     # penalty per unit of demand left unmet

D = {(g, t): DEMAND_BASE[g] * (1 + DEMAND_GROWTH[g]) ** (t - 1)
     for g in REGIONS for t in YEARS}
TC = {(a, b): (TRANSPORT_OWN if HOME[a] == HOME[b] else TRANSPORT_CROSS)
      for a in SITES for b in SITES}
TC_DEM = {(f, g): (TRANSPORT_OWN if HOME[f] == g else TRANSPORT_CROSS)
          for f in FABS for g in REGIONS}

print(f"{'year':>5s} " + "".join(f"{g:>10s}" for g in REGIONS))
for t in @YEAR_GRID@:
    print(f"{t:5d} " + "".join(f"{D[g, t]:10.2f}" for g in REGIONS))
cross = [t for t in YEARS if D[REGIONS[1], t] > D[REGIONS[0], t]]
print(f"\n{REGIONS[1]} overtakes {REGIONS[0]} in year {min(cross)}"
      if cross else f"\n{REGIONS[1]} never overtakes {REGIONS[0]}")
print(f"transport: {TRANSPORT_OWN} within a region, {TRANSPORT_CROSS} across "
      f"({TRANSPORT_CROSS / TRANSPORT_OWN:.0f}x)")
''')

    M(r"""
### 3.4 The learning knobs

Capex splits in two: a **site adder** that never gets cheaper — land, permits,
connection — and a **technology** component that may. `LEARN_FRAC` is the share
that is technology, and only the processing and fabrication tiers learn, because
mining is mature.

`LR` is the learning rate: the fraction by which unit cost falls per doubling of
cumulative capacity. `Q0` is the incumbent cumulative capacity the curve starts
from, and `C_FLOOR_FRAC` stops it falling to zero.
""")

    C(r'''
LEARN_TIERS = ("P", "F")     # mining is mature; recovery technology learns
LEARN_SITES = [s for s in SITES if TIER[s] in LEARN_TIERS]
LEARN_FRAC = 0.70            # share of capex that is learnable technology
LR = 0.20                    # unit cost falls 20% per doubling of capacity
Q0 = 380.0                   # incumbent cumulative capacity
C_FLOOR_FRAC = 0.55          # floor, as a fraction of the starting unit cost
G_EXOG = 0.035               # exogenous capex decline per year, for that mode

print(f"learning sites: {LEARN_SITES}   (mining excluded)")
print(f"of each site's capex0, {100 * LEARN_FRAC:.0f}% is technology that can "
      f"learn and {100 * (1 - LEARN_FRAC):.0f}% is a site adder that cannot")
print(f"learning rate {100 * LR:.0f}% per doubling, floored at "
      f"{100 * C_FLOOR_FRAC:.0f}% of the starting cost")
''')

    return [(k, _sub(t, agree=agree, model=model, horizon=horizon,
                     year_grid=year_grid))
            for k, t in out]
