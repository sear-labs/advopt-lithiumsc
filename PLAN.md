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
├── config.yaml
├── scenarios/
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
│   ├── 00_concepts_guide.ipynb        (Part 0 — the template, and the front door)
│   ├── 01_deterministic.ipynb
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
- [ ] Adjudicate the drifted pairs this touches: `add_region` (4e's tariff/quota/
      LCR version is a **feature** → parameterize), `best_response_cournot`
      (**drift** → the `len(KR)` version wins), `joint_profit_max`, `set_tiers`
- [ ] Rewrite `notebooks/04c_cournot.ipynb` to the Part 0 shape, with the
      agreement assert
- [ ] Colab bootstrap + badge; open it in Colab and run it top to bottom
- [ ] Fix the one wrong published claim now, independently: `PROJECT_JOURNAL.md`
      says commitment is worth ~20%; the current run says **24.6%**

**Acceptance:** a student with a Google account and no software opens the badge
and runs Part 4c to completion, and the assert passes.

### Phase 2 — migrate the rest *(the bulk — reckon a day per two notebooks)*

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
- **It does not merge the instructional and production tracks.**
  `PROJECT_JOURNAL.md` draws that line for a reason — Parts 2b, 2c, 4f and 5 are
  meant to be scaled, the other ten are meant to be small. They share `src/`; they
  do not share pedagogy requirements.
- **It does not make the notebooks configurable.** Hardcoded numbers in a teaching
  notebook are correct. See `CLAUDE.md` Part 6.
