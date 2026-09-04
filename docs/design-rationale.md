# Design rationale — why this repo has two tracks

> **This is a record, not an instruction.** It was the plan for a migration that
> completed on 2026-09-03, and its phase-by-phase section has been removed
> because that work is done — `git log` has the original if you want it. What
> remains is the reasoning behind the shape you are looking at: why the package
> and the notebooks deliberately hold the same models, and what makes that safe.
>
> The rule itself lives in the Code Standard, Part 4. This document is why it was
> adopted here.

---

**Supersedes the remediation ordering in `AUDIT_AND_REMEDIATION_PLAN.md`.** That
document's *findings* stand and are still the evidence base; this document
replaces its phase plan, because the goal changed: the point is not to remediate
fourteen notebooks in place, it is to **split them into two folders that each do
one job well** — a streamlined installable package, and teaching notebooks a
student can open in Colab and actually follow.

---

## 1. The shape

```
advopt-lithiumsc/
├── CLAUDE.md               the two standards and the boundary between them
├── README.md               install, run, what is committed, the Colab index
├── pyproject.toml          pinned, `pip install -e .`
│
├── data/raw/               ── THE SHARED INSTANCE ──  read by BOTH tracks
│   ├── instance_base.csv   fixed/unit/opex/legacy, keyed (stage, region)
│   ├── efficiency.csv      eta ceiling/base, alpha, beta, delta, keyed by stage
│   └── market.csv          demand base + growth, experience0, keyed by region
│
├── src/lithium/            ── STREAMLINED TRACK ──  conventions territory
│   ├── regions.py          add_region, set_tiers, _cap_cum_mult
│   ├── curves.py           _rev_breakpoints, learning_breakpoints, capex_pv_multiplier
│   ├── planner.py          solve_planner
│   ├── games.py            best_response_cournot, cournot_iterate, market_outcome,
│   │                       joint_profit_max, stackelberg
│   ├── network.py          max_flow, interdiction, best-response intersection
│   ├── stochastic.py       extensive_form, subproblem, progressive_hedging, benders
│   └── core.py             the one build(), parameterized
│
├── notebooks/              ── TEACHING TRACK ──  teaching-standard territory
│   ├── 00_index.ipynb                 THIN: imports the package, holds no logic,
│   │                                  proves the install and the headline numbers
│   ├── 00_concepts_guide.ipynb        (Part 0 — the template, and the front door)
│   ├── 01_deterministic.ipynb         TEACHING: built by hand, asserts agreement
│   ├── 02_stochastic.ipynb  ... etc
│   └── _bootstrap.py                  the Colab header every notebook opens with
│
├── tools/                  audit.py  dup.py  prosecheck.py  structcheck.py  runall.py
├── scripts/run_all.py      the one documented entry point
└── tests/
```

Two folders, as intended. `src/` is written for a machine to run a thousand
times; `notebooks/` is written for a person to read once.

## 2. The one rule that makes the split safe

The two folders contain **the same model twice, on purpose**. The notebook builds
it by hand because that is the lesson; the package builds it once because that is
the code. Normally duplication is the enemy — here it is the design, so the usual
protection is gone.

What replaces it is an **agreement assertion**, the last cell of every notebook:

```python
from lithium.games import best_response_cournot
packaged = best_response_cournot(r="R1", rival_sales=q_rival, learning="both")
rel = abs(packaged.ObjVal - hand_built.ObjVal) / abs(hand_built.ObjVal)
assert rel < 1e-9, f"notebook and package disagree by {rel:.2e}"
print(f"notebook and package agree to {rel:.1e}")
```

This is not ceremony. `AUDIT_AND_REMEDIATION_PLAN.md` §1.2 documents one function
pasted into eight notebooks with three copies silently drifted, and §1.3 a bug
fixed in three places and missed in a fourth for months. That happened because
nothing compared the copies. This cell compares them, on every run, forever.

**A notebook without this cell is not finished.**

**And the assertion needs shared inputs to mean anything.** If the notebook types
its own 36 instance numbers and the package types its own, a failed assert is
ambiguous — a typo in the data and a bug in a constraint look identical, and in
practice that is how an assert gets switched off. So the instance tables live in
`data/raw/` and both sides read them; the assertion is then unambiguous, and means
exactly one thing when it fires: *somebody's model construction is wrong.*

The CSV and the assertion do different jobs and neither substitutes for the other:
the CSV removes a *reason* the two could differ, the assertion is the check. See
the Code Standard, Part 4, *Tables versus knobs*, for which numbers move and which stay.

## 3. What "easier for students" means concretely

Part 0 already is what the others should be. It has 23 sections; each is a
markdown explanation followed by one short runnable demo, 12–41 lines. Every code
cell has narration above it. It defines five small functions and each one *is* the
lesson being taught. Nothing needs restructuring.

The other thirteen invert that. Measured:

| | Part 0 | the other 13 |
|---|---|---|
| Big functions before the narration | 0 | 12 notebooks, first at 9–45% |
| Code cells with no markdown above | 0 | 106 |
| Longest cell | 41 lines | up to 260 |
| "Predict before you run" prompts | 0 | 0 |

So the conversion, per notebook, is four moves:

1. **The big function leaves the notebook entirely** — into `src/lithium/`. The
   audit said "move it to the bottom"; the two-folder split lets us do better and
   move it *out*.
2. **Write the steps it contained** where it used to sit: one idea per cell,
   markdown above each, print something after each. This is the actual work and
   it is writing, not refactoring.
3. **One predict-prompt** before the first solve. One line of markdown.
4. **The agreement assert** at the bottom, importing what step 1 moved out.

Net effect for a student: they read the model being built, in order, in the same
shape Part 0 taught them — and the tidy version is one import away when they want
to *use* it rather than learn it.

## 4. Colab deployment

**Decided 2026-09-02: a public GitHub repo.** That is what makes the badge a
one-click path — no token, no Drive mount, and `pip install git+https://...`
resolves for an anonymous student. It also means `src/` is installed rather than
pasted into each notebook, which is the whole point of the split; the private and
Drive-only options both force vendoring and re-create the duplication problem.

~~Nothing sensitive ships: `gurobi.lic` is excluded by `.gitignore` as both
`gurobi.lic` and `*.lic`, verified with `git check-ignore` before the first
commit, and the history was started clean.~~

**Corrected 2026-09-03. The last clause was false.** `gurobi.lic` was indeed
excluded and verified — but a live WLS key was sitting in a code cell of
`Part4c_exact_MIQP.ipynb` and in a markdown example in Parts 1, 2 and 3, and went
into commit `9b2c0b7`, the root. The `.gitignore` rule guarded the file form of
the credential and nothing looked at notebook content.

Fixed in the working tree: Parts 1–3 never used the key (zero `env=ENV`
references) so the values became placeholders; `Part4c_exact_MIQP` reads a
licence from the environment or a Colab secret and defaults to `SMALL = True`,
which fits the free licence; and `tools/credscan.py` now scans content in CI.

**The key still has to be rotated** — it is in history from the root commit, and
scrubbing history does not un-expose a key that has existed in a working tree.
**Do not push publicly until it is rotated.**

**What the split costs, stated plainly.** Today each Part 4 notebook is fully
self-contained — every one redefines `REGIONS`, `add_region`, `set_tiers` and the
rest, so a student can open Part 4d alone and run it. Afterwards each notebook
needs one install cell first. The staged progression is untouched; *standalone-ness*
is what is being spent, and it buys the single copy that the agreement assertion
compares against. In Colab the cost is one cell the student never reads.

The package appears in a teaching notebook exactly **twice** — the install in cell
0, and the assertion in the last cell. The middle never imports it, because a
notebook that imported the package to *build* the model would have deleted the
lesson to save typing.

Every notebook opens with a badge and this cell, and nothing else changes:

```python
# --- environment ------------------------------------------------------
try:
    import google.colab                                    # noqa: F401
    IN_COLAB = True
    %pip install -q "gurobipy>=13,<14" "pandas>=2,<3" "matplotlib>=3.8,<4"
    %pip install -q "git+https://github.com/sear-labs/advopt-lithiumsc@v1.0"
except ImportError:
    IN_COLAB = False        # local: assumes `pip install -e .`

import gurobipy as gp
print(f"gurobipy {gp.gurobi.version()}  |  Colab: {IN_COLAB}")
```

Four things this has to get right, all of them recorded in `PROJECT_JOURNAL.md`:

- **The free `pip` licence is the constraint.** ~2,000 variables for LP/MILP,
  but only ~150 for QP/MIQP — a limit found by probe, not documentation. The ten
  instructional notebooks fit. `Part4c_exact_MIQP` does not, and ships with
  `SMALL = True` by default plus a printed line saying why and what changes if a
  student has a full licence.
- **No notebook reads an external file**, which is already true, and is the
  reason Colab deployment is cheap here. Keep it true.
- **`gurobi.lic` never travels.** It is a WLS credential, gitignored as both
  `gurobi.lic` and `*.lic`. The Colab path uses the free licence only.
- **Runtime.** Part 2 is 310 s of the 584 s total. Give it a `QUICK = True`
  scenario-count switch so a student can get through it in a lecture, with the
  full setting documented and used for the committed run.

Part 0 becomes the front door: a table at the top of `README.md` and in Part 0
itself, one row per notebook, each with an "Open in Colab" badge.

## 5. What this deliberately does not do

- **It does not touch the REE 4301 course code.** That is a separate body with the
  same duplication disease (`syntax_check` in six files in five versions) and its
  own generated-notebook drift risk. Worth doing; not this project.
- **It does not erase the instructional/production distinction.** All fourteen get
  the teaching treatment (decided 2026-09-02), but `PROJECT_JOURNAL.md` draws that
  line for a reason: Parts 2b, 2c, 4f and 5 are meant to be scaled and the other
  ten are meant to stay small. That survives as sizing switches and as what CI
  runs nightly versus per-commit — not as a difference in how they are narrated.
- **It does not make the notebooks configurable — but it does give them a shared
  instance.** *Revised 2026-09-02.* Knobs stay written out in the cell: `NBP_REV`,
  `LR_CAPEX`, `DR`, `CHOKE` and the rest are the lesson, and Part 4c cell 31 asks
  the reader to change one. Instance **tables** move to `data/raw/`, because the
  agreement assertion cannot distinguish a data typo from a model bug unless both
  sides start from the same numbers. There is still no `config.yaml` holding model
  parameters. See the Code Standard, Part 4, *Tables versus knobs*.


---

## 6. Adjudications — which copy won, and why

Fourteen notebooks held many functions with the same name. Before any of them
could become one implementation, each group had to be **adjudicated**: hash every
top-level `def` body, group by name, and decide whether the copies are identical
(pick one), a *feature* (one is a superset — take it and make the extra behaviour
optional), or *neither* (they are different functions that happen to share a
name).

`src/lithium/` and `tests/test_smoke.py` cite these findings; this is what they
cite.

### Identical — pick any copy

| function | copies | note |
|---|---|---|
| `best_response_cournot` | 4 | resolved before the migration began |
| `joint_profit_max` | 3 | as above |
| `stackelberg`, `follower_qp`, `follower_marginal_cost`, `follower_legacy` | 2 each | byte-identical across 4d and 4e |
| `build_plan`, `capex_pv_multiplier`, `learning_breakpoints` | 2 each | identical across Parts 1 and 2 |

### Feature — one copy is a strict superset

- **`add_region`** — byte-identical across 4ab, 4c, 4c-exact and 4d; **4e's is a
  superset**, adding quota constraints, a local-content floor, a tariff folded
  into transport, and `tariff_paid` reported separately. It is self-disabling:
  empty `tariff` / `quota` / `local_min` collapse it to the base version exactly.
  Taken as the single implementation with those three optional and defaulting to
  empty, and `test_policy_superset_collapses` asserts the collapse.
- **`build`** (Parts 1 and 2) — a nine-line `mipgap` feature. Part 2's version
  taken; `mipgap=None` reproduces Part 1 exactly, and a test pins that.
- **`build_netcore`** (Parts 3 and 3b) — 3b's is a superset, adding the
  production-learning channel, disposal and local-content minimums. Part 3 is
  `learning='capacity'` with no tiers. Same arrangement as `add_region`.

### Neither — different functions that share a name

- **`set_tiers` / `opex_tiers`** — Part 3b indexes `STAGES` by `prod_by_stage`;
  the Part 4 family indexes `REGIONS` by `top_by_region`. Identical arithmetic,
  different index set, different constants. Resolved as **one pure function
  taking the index set as an argument** and returning the tier dicts, rather than
  mutating module-level state.
- **`solve`** — Part 1's builds the network MILP and returns a result dict;
  Part 2c's selects a risk objective on the two-stage capacity model. A name
  collision on different models. Not merged.
- **`subproblem`, `extensive_form`** — Part 2's act on the six-site network,
  Part 2b's on the two-stage capacity network. Also collisions. `twostage.py` is
  therefore imported as a module rather than flattened into the package
  namespace, so both can exist.
- **`max_flow`, `attacker_best_response`** — Part 0's are miniature hand-solved
  demos (2 and 24 lines); Part 4f's are the real model. The concepts guide
  previewing the thing, not duplicating it.
- **`build`** (Part 5) — only 3.7% similar to Parts 1 and 2's. A different model
  with a recycling loop, and the reason Part 5 has its own module.

### The one that was not a name at all

Parts 3 and 3b each hand-wrote Wright's law and its trapezoid integral under the
names `unit_cost`/`cumulative_cost` and `capex_unit`/`capex_cum`. **A name-based
check finds nothing**, but both are `lithium.curves` scaled by a unit cost —
verified identical at 1.2e-16 and 1.7e-16. There is no fourth copy in the
package. The lesson: hashing function bodies by name catches renamed-but-shared
code only when the names survive.
