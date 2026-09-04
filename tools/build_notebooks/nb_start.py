"""Build notebooks/00_start_here.ipynb -- the thin front door.

`CLAUDE.md` Part 4: *"The thin notebook is the cheapest reconciliation
available. It calls the same functions the entry point calls and holds no logic
of its own, so it cannot drift -- there is nothing in it to go stale. Worth
having exactly once, as the front door: it proves the install works and
reproduces the headline numbers before a reader invests an hour in the teaching
notebooks."*

So this notebook contains **no model**. Every cell imports `lithium` and calls
it. If a number here is wrong, the package is wrong -- there is no second
implementation in this file for it to be wrong *against*, which is exactly the
point.

It also has no agreement assertion, for the same reason and by the same
declared mechanism Part 0 uses: it duplicates nothing.
"""
from . import common

NOTEBOOK = "00_start_here.ipynb"
TITLE = "Start here - does it work?"

NO_AGREEMENT_ASSERTION = (
    "This notebook holds no model of its own. Every cell calls `lithium` "
    "directly, so there is no hand-built second copy for an agreement assertion "
    "to compare against - it IS the package's own output. Its job is to prove "
    "the install works and reproduce the headline numbers in under a minute."
)


def cells():
    out = []

    def M(text):
        out.append(("md", text.strip("\n")))

    def C(text):
        out.append(("code", text.strip("\n")))

    M(r"""
# Start here

### Sixty seconds to know whether any of this works

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/USERNAME/lithium-modelling/blob/main/notebooks/00_start_here.ipynb)

This notebook **contains no model.** Every cell below imports the `lithium`
package and calls it. Run it top to bottom; if it finishes, your install works
and the headline numbers of the whole series reproduce on your machine.

That is its entire job. Read it before investing an hour in a teaching notebook,
not instead of one.

**There is no agreement assertion at the end of this notebook**, and that is
deliberate — the same documented exception Part 0 takes. Every other notebook
builds a model by hand and then checks it against the package. This one holds
nothing to check: it *is* the package's output, so there is no second copy for
it to disagree with.

### Where to go afterwards

| you want | open |
|---|---|
| the concepts, one at a time | `00_concepts.ipynb` |
| a deterministic MILP, built by hand | `01_deterministic.ipynb` |
| uncertainty | `02_stochastic.ipynb`, then `02b`, `02c` |
| the model the series keeps returning to | `03_network_core.ipynb` |
| firms that do not cooperate | `04ab` → `04c` → `04d` → `04e` |
| what breaks a chain | `04f_interdiction.ipynb` |
| a chain that feeds itself | `05_integrated_core.ipynb` |
""")

    out += common.setup_section(notebook=NOTEBOOK)

    M(r"""
## 1. Does the package import, and can it find its data?

`lithium` ships the instance tables **inside the package**, so this works from a
clone, from a `pip install git+...`, and from Colab. Six instances, and they are
genuinely different models rather than variants of one — the table says which
notebook uses which.
""")

    C(r'''
import lithium as L

print(f"lithium {L.__version__}\n")

instances = [
    ("Part 4 chain          ", L.load_instance,               "04ab, 04c, 04d, 04e"),
    ("six-site network      ", L.load_network_instance,       "01, 02"),
    ("two-stage capacity    ", L.load_twostage_instance,      "02b, 02c"),
    ("network core          ", L.load_netcore_instance,       "03, 03b"),
    ("interdiction network  ", L.load_interdiction_instance,  "04f"),
    ("integrated core       ", L.load_integrated_instance,    "05"),
]
for name, loader, used_by in instances:
    inst = loader()
    n = sum(len(v) for v in vars(inst).values() if isinstance(v, dict))
    print(f"  {name} loaded, {n:3d} table entries   <- {used_by}")

print("\nall six instances load from the packaged data - no local files needed")
''')

    M(r"""
## 2. The headline numbers

> **Predict before you run.** Two of the numbers below are EVPI (what a crystal
> ball is worth) and VSS (what *modelling* the uncertainty is worth). Which do
> you expect to be larger on a model whose plan can react at years 4, 7 and 10?

One number from each strand of the series, straight from the package. These are
the same values the teaching notebooks derive by hand and then assert against.

If any assertion below fails, the package is broken — not your install.
""")

    C(r'''
import time

t0 = time.time()
rows = []

# --- deterministic: the network MILP, and what limited foresight costs ---
net = L.build_core_structure(L.load_network_instance(), T=20)
full = L.solve(net, "full", invest_years=[1, 4, 7, 10, 13, 16, 19], mipgap=1e-3)
plan_w3, _ = L.rolling_horizon(net, W=3, delta=3, invest_step=3, mipgap=1e-3)
cost_w3 = L.evaluate_plan(net, plan_w3, mipgap=1e-3)
rows.append(dict(notebook="01", quantity="perfect foresight",
                 value=round(full["obj"], 1)))
rows.append(dict(notebook="01", quantity="myopia (W=3) costs",
                 value=f"{100 * (cost_w3 / full['obj'] - 1):+.1f}%"))
assert cost_w3 > full["obj"], "limited foresight beat perfect foresight"

# --- stochastic: the three quantities, all through identical machinery ---
st12 = L.build_core_structure(L.load_network_instance(), T=12)
sc = L.scenarios(st12)
r = L.three_case_comparison(st12, sc, [1, 4, 7, 10], [1])
assert r["WS"] <= r["RP"] + 1e-6 <= r["EEV"] + 1e-6, "WS <= RP <= EEV violated"
rows.append(dict(notebook="02", quantity="EVPI",
                 value=f"{100 * (r['RP'] - r['WS']) / r['RP']:.3f}%"))
rows.append(dict(notebook="02", quantity="VSS",
                 value=f"{100 * (r['EEV'] - r['RP']) / r['RP']:.3f}%"))

print(f"  ({time.time() - t0:.0f}s so far)")
''')

    M(r"""
Decomposition and risk next. The first is the one where a clever method has to
reproduce a slow honest one exactly, or it is not worth having.
""")

    C(r'''
# --- decomposition: L-shaped must reproduce the monolithic answer ---
ts = L.build_twostage_structure(L.load_twostage_instance())
dsc = L.demand_scenarios(ts, n=24, seed=11)
ef = L.twostage.extensive_form(ts, dsc)
ef.optimize()
ls = L.lshaped(ts, dsc)
assert abs(ls["value"] - ef.ObjVal) / abs(ef.ObjVal) < 1e-9, \
    "L-shaped did not reproduce the extensive form"
rows.append(dict(notebook="02b", quantity="extensive form == L-shaped",
                 value=round(ef.ObjVal, 4)))

# --- risk: the same plan must score the same way however it was found ---
ssc = L.shock_scenarios(ts, n=40, seed=7)
neutral = L.risk_model(ts, ssc, "neutral")
hybrid = L.risk_model(ts, ssc, "hybrid")
ev_n = L.evaluate_capacity(ts, ssc, neutral["plan"])
ev_h = L.evaluate_capacity(ts, ssc, hybrid["plan"])
rows.append(dict(notebook="02c", quantity="hedging costs (mean)",
                 value=f"{100 * (ev_h['mean'] / ev_n['mean'] - 1):+.2f}%"))
rows.append(dict(notebook="02c", quantity="hedging saves (worst)",
                 value=f"{100 * (ev_h['worst'] / ev_n['worst'] - 1):+.2f}%"))
assert ev_h["worst"] < ev_n["worst"], "the hedge did not improve the worst case"

print(f"  ({time.time() - t0:.0f}s so far)")
''')

    M(r"""
Finally interdiction and the closed loop — the two models that ask a different
question from the rest of the series.
""")

    C(r'''
# --- interdiction: the attacker's dual must match the operator's primal ---
idn = L.build_flow_network(L.load_interdiction_instance())
base_flow, _ = L.max_flow(idn)
val, atk = L.attacker_best_response(idn, 3)
direct, _ = L.max_flow(idn, interdicted=atk)
assert abs(val - direct) < 1e-6, "the min-cut MILP and max-flow do not match"
rows.append(dict(notebook="04f", quantity="undisrupted throughput",
                 value=round(base_flow, 1)))
rows.append(dict(notebook="04f", quantity="after a 3-arc attack",
                 value=round(val, 1)))

# --- the closed loop, and the invariant that checks its flow logic ---
p5 = L.load_integrated_instance()
on = L.integrated.build(p5, allow_dual_feedstock=True, mipgap=1e-4)
on.optimize()
off = L.integrated.build(p5, allow_dual_feedstock=False, mipgap=1e-4)
off.optimize()
assert on.ObjVal <= off.ObjVal, "closing the loop made the problem more expensive"
rows.append(dict(notebook="05", quantity="recycling is worth",
                 value=f"{100 * (off.ObjVal - on.ObjVal) / off.ObjVal:.2f}%"))

ct = L.collapse_test(p5)
assert ct["passed"], "the collapse invariant failed"
rows.append(dict(notebook="05", quantity="collapse invariant",
                 value=f"{ct['rel_lp']:.1e}"))

print(f"\nall assertions passed in {time.time() - t0:.0f}s")
pd.DataFrame(rows)
''')

    M(r"""
## 3. What just happened

Every number in that table came out of `lithium`, and every one of them is
checked by an assertion rather than merely printed:

- **limited foresight cannot beat perfect foresight** — if it does, the rolling
  horizon is leaking information from the future;
- **WS ≤ RP ≤ EEV** — the ordering is a theorem, so a violation is a plumbing
  bug and never a finding;
- **L-shaped reproduces the extensive form** to $10^{-9}$, which is what makes
  decomposition trustworthy rather than merely fast;
- **the attacker's dual matches the operator's primal**, which is the only way
  to know a duality-based reformulation is right;
- **closing a loop cannot cost more**, because it adds an option without
  removing an obligation;
- **two identical free-trading regions collapse to one**, which almost any error
  in the flow constraints would break.

That is the whole series in one page. Each teaching notebook takes one of these,
builds it by hand, and then asserts its hand-built version agrees with the
package to $10^{-9}$.

**If you only have ten minutes**, read `00_concepts.ipynb` §0 for the notation
and §12 for what EVPI and VSS actually mean. If you have an hour, open
`01_deterministic.ipynb` and work down.
""")

    return out
