# Plan — Two Tracks: a Streamlined Package and Colab-Ready Teaching Notebooks

**Supersedes the remediation ordering in `AUDIT_AND_REMEDIATION_PLAN.md`.** That
document's *findings* stand and are still the evidence base; this document
replaces its phase plan, because the goal changed: the point is not to remediate
fourteen notebooks in place, it is to **split them into two folders that each do
one job well** — a streamlined installable package, and teaching notebooks a
student can open in Colab and actually follow.

---

## 1. The shape

```
lithium-modelling/
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
`CLAUDE.md` Part 4, *Tables versus knobs*, for which numbers move and which stay.

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

Nothing sensitive ships: `gurobi.lic` is excluded by `.gitignore` as both
`gurobi.lic` and `*.lic`, verified with `git check-ignore` before the first
commit, and the history was started clean.

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
    %pip install -q "git+https://github.com/USER/lithium-modelling@v1.0"
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

## 5. Phases

### Phase 0 — done (2026-09-02)

`git init`, `.gitignore` with the credential excluded and verified, snapshot
tagged `pre-remediation-2026-09-02`, the `len(KR)` fix back-ported to both Part 4c
call sites, redundant cell removed, Part 0 kernel metadata corrected, `CLAUDE.md`
written, stale references in the audit fixed. Part 4c re-executed: 0 errors,
30.0 s, every number unchanged.

### Phase 1 — one vertical slice, end to end *(a day)*

Do **one** notebook completely rather than one phase across fourteen. Part 4c is
the right choice: it carries the most-duplicated code in the series
(`_rev_breakpoints` ×8, `add_region` ×5), it runs in 30 s, and it exercises every
piece of the pattern at once.

- [ ] Unzip `dispatch-template.zip` as the skeleton — it is already a working
      archetype-A repo and its `CLAUDE.md` is `PROJECT_CONVENTIONS.md` verbatim.
      Do not design this from scratch.
- [ ] `src/lithium/` with the Part 4 family's shared code; `pip install -e .`
- [x] **Adjudicated 2026-09-02** by hashing every top-level `def` body across all
      fourteen notebooks and diffing the groups. Two of the four pairs no longer
      exist — Phase 0 closed them, so the audit's §1.2 table is a pre-Phase-0
      snapshot:
      - `best_response_cournot` — 4 copies, **1 version**. Resolved by Phase 0.
      - `joint_profit_max` — 3 copies, **1 version**. Resolved by Phase 0.
      - `add_region` — **feature**, confirmed. 4e's version is a strict superset:
        quota constraints, an LCR floor, a tariff folded into transport, and
        `tariff_paid` reported separately. It is already self-disabling — empty
        `TARIFF`/`QUOTA`/`LOCAL_MIN` collapse it to the base version exactly. Take
        the 4e version as the single implementation with those three as optional
        arguments defaulting to empty, and assert the collapse.
      - `set_tiers` — **neither**. 3b indexes `STAGES` with `prod_by_stage`; the
        Part 4 family indexes `REGIONS` with `top_by_region`. The arithmetic is
        identical and the constants differ (3b runs `Q_START, Q_ADD = 400, 1000`
        against the Part 4 family's `300, 700`). Same function, different index
        set and instance → one pure function taking both as arguments, returning
        the tier dicts rather than mutating module-level state in place.
      - Also found, not in the audit: the redundant-cell defect Phase 0 fixed in
        4c exists in **three more notebooks** — `Part4c_exact_MIQP` cells 13/14,
        `Part4d` cells 11/12, `Part4e` cells 12/13 each define `_rev_breakpoints`
        twice; `Part4e` cell 9 re-runs the whole learning block from cell 7. Phase 2.
      - Also: the default-argument capture is still latent in the source —
        `def _rev_breakpoints(..., n=NBP_REV)` — and harmless only because all
        seven call sites now override it. The default goes away in the package.
- [ ] Pull the three instance CSVs out of Part 4c per *Tables versus knobs*; ship
      them as package data so `pip install git+...` carries them into Colab
- [ ] Rewrite `notebooks/04c_cournot.ipynb` to the Part 0 shape, with the load /
      render / show-the-keys / commented-edit-example cells, and the agreement
      assert taking the instance as an argument
- [ ] Break a constraint in `src/lithium/` on purpose and confirm the assertion
      goes **red** — a green assert that has never failed is not yet evidence
- [ ] Colab bootstrap + badge; open it in Colab and run it top to bottom
- [ ] Fix the one wrong published claim now, independently: `PROJECT_JOURNAL.md`
      says commitment is worth ~20%; the current run says **24.6%**

**Acceptance:** a student with a Google account and no software opens the badge
and runs Part 4c to completion, and the assert passes.

### Phase 2 — migrate the rest *(the bulk — reckon a day per two notebooks)*

**Scope decided 2026-09-02: all fourteen**, production track included. Parts 2b,
2c, 4f and 5 get narration, predict-prompts and agreement asserts like the rest.
The instructional/production distinction survives as a *sizing* decision — those
four keep their `QUICK`/`SMALL` switches and are still the ones meant to scale —
but not as a pedagogy exemption. Budget roughly 40% more than the ten-notebook
path.

Worst-first by orphan-cell count: 4e (18), 4c-exact (17), Parts 2 and 4d (14),
Parts 1 and 4c (12). Each notebook: the four moves in §3, then execute and
**commit it executed** — outputs and figures included, which is the deliberate
exception to conventions rule 5. Right now all fourteen are saved stripped, so a
reader without Gurobi sees nothing and cannot check a single number in the prose.

Correct the thirteen stale figures in 4c/4d/4e as part of migrating those three,
not as a separate pass — the numbers come from the run that ships with them.

Split the 206-line (Part 1) and 260-line (Part 2) cells here; they are the two
worst offenders against "short enough to read without scrolling".

### Phase 3 — the checks that stop it recurring *(half a day)*

- [ ] `tools/prosecheck.py` — every number in markdown against the executed
      outputs. Would have caught §1.1 the day it appeared.
- [ ] `tools/dup.py` — fails if a function body appears in two places. This is
      the guard that makes the two-folder split hold.
- [ ] `tools/structcheck.py` — no `def` above the teaching section; every code
      cell narrated; at least one predict-prompt.
- [ ] `scripts/run_all.py`, smoke tests on the invariants already used informally
      (`WS <= RP <= EEV`, planner cost ≤ competitive cost at matched volume,
      conservation, non-negativity)
- [ ] GitHub Actions: smoke per commit, full notebook execution nightly (584 s is
      too slow per-commit)

### Phase 4 — the two carried-over defects *(hours)*

- [ ] Part 0 §23: the Best Response Intersection trace names an iteration path
      that is not reproducible — reordering the arcs or renaming the nodes changes
      it, and twelve perturbations failed to stabilise it because the degeneracy is
      structural. Assert only the converged answer (fortify {s→a, b→t}, flow 3,
      3 iterations) and **teach the degeneracy**, which §22 already sets up.
- [ ] Seeds: set and recorded in Parts 2b and 2c only. Set them everywhere
      stochastic, and print them.

---

## 6. What this deliberately does not do

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
  parameters. See `CLAUDE.md` Part 4, *Tables versus knobs*.
