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
    left = [m for m in ("@AGREE@", "@CHAIN@", "@REVENUE@") if m in text]
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


def structure_section(agree=12, chain=5):
    """Section 3: everything derived from the tables plus the horizon knobs."""
    out, M, C = _cells()
    M(r"""
## 3. The knobs, and the structure derived from them

Everything from here to section @CHAIN@ is **derived**: sets, windows, discount weights, yields. None of
it is data and none of it is a knob — it is arithmetic on the two, and doing that arithmetic is the
point of this section. `src/lithium/structure.py` computes exactly the same things, and section @AGREE@
is what proves the two derivations agree.

### 3.1 Time: variable-length periods

A 37-year horizon at annual resolution would be 37 copies of every decision. Instead the horizon is
chopped into **13 periods of increasing length** — six 1-year periods while the interesting things
happen, then 3-, 5- and finally 9-year blocks. `OMEGA[p]` is the sum of discount factors for the
years inside period `p`, so a long late period is correctly worth less per year *and* covers more
years.
""")

    C(r"""
BLOCKS = [(6, 1), (4, 3), (2, 5), (1, 9)]   # (how many periods, how many years each)
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
    return [(k, _sub(t, agree=agree, chain=chain)) for k, t in out]


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
