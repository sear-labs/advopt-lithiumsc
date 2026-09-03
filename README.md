# Lithium supply-chain optimisation — models and teaching notebooks

A staged series of optimisation models for a two-region, three-stage lithium supply chain, built for
a graduate modelling course. The series runs from a deterministic MILP through stochastic
programming, decomposition, and game-theoretic equilibrium models.

The repository holds **the same models twice, on purpose**:

- `src/lithium/` — one implementation of each model, every parameter an argument, written for
  `scripts/run_all.py` and CI to call a thousand times.
- `notebooks/` — the same models built **by hand**, step by step, because the steps are the lesson.

That duplication is a design decision, and the thing that makes it safe is the **agreement
assertion** in the last cell of every teaching notebook: it imports the package, runs the same case,
and asserts the two objectives agree to $10^{-9}$. See `CLAUDE.md` Part 4 for the full reasoning.

---

## Run it

```bash
pip install -e ".[dev]"
python scripts/run_all.py
pytest -q
```

`scripts/run_all.py` writes `results/tables/*.csv` and `results/figures/*.png` and prints the
headline numbers. It takes about 11 s. `--quick` caps the best-response loop at 6 rounds for
classroom use; `--data DIR` points it at a different instance directory.

Gurobi is required. The free `pip` licence is enough for everything in `notebooks/` — see
*The licence is the deployment constraint* below.

## Open it in Colab

| Notebook | What it covers | |
|---|---|---|
| `notebooks/04c_cournot.ipynb` | Cournot competition with endogenous price; piecewise-linear revenue; iterated best response; collusion benchmark | [![Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/USERNAME/lithium-modelling/blob/main/notebooks/04c_cournot.ipynb) |

The badge is a one-click path: it clones this repo, `pip install -e .`, and runs. No local software
and no account beyond a Google login. **The `USERNAME` placeholder in the badge and in each
notebook's cell 0 must be replaced with the real GitHub owner before the badge resolves.**

The other thirteen notebooks are still at the repository root in their pre-migration form
(`Part0_Concepts_Guide.ipynb` and friends) and are migrated in Phase 2 of `PLAN.md`.

---

## Layout

```
data/raw/                 the instance tables, read by BOTH tracks
  instance_base.csv         fixed / unit / opex / legacy, keyed (stage, region)
  efficiency.csv            yield ceiling, base, alpha, beta, delta, keyed by stage
  market.csv                demand base + growth, experience0, keyed by region

src/lithium/              the streamlined track
  instance.py               the three tables -> one Instance
  structure.py              sets, windows, discount weights, yields by vintage
  curves.py                 capex learning, revenue linearisation, opex tiers
  regions.py                add_region: one region's chain, policy-instrument superset
  planner.py                the cooperative benchmark
  games.py                  best response, iterated best response, collusion
  data/                     a copy of data/raw/, shipped as package data

notebooks/                the teaching track
  04c_cournot.ipynb         built by hand, narrated, ends in the agreement assertion

scripts/run_all.py        the one documented entry point
results/{figures,tables}/  generated; figures are committed on purpose
tests/                    smoke tests + notebook execution
```

### What is committed on purpose

Two deliberate exceptions to "generated files are gitignored":

- **`results/figures/`** is tracked, so a reader without a Gurobi licence sees the plots.
- **The notebooks ship executed**, outputs and figures included, so every number in the prose is
  checkable without running anything.

`results/tables/` is *not* tracked — `run_all.py` regenerates it in seconds.

---

## Tables versus knobs

The one rule most likely to be applied in the wrong direction here, in either direction.

A **knob** is a scalar carrying a concept — `DR`, `NBP_REV`, `CHOKE`, `LR_CAPEX`. Knobs stay
**written out in the notebook cell** where the narration explains them, and the notebook hands them
to the package explicitly, so the agreement assertion already proves both sides used the same value.
There is deliberately **no `config.yaml`** holding model parameters.

A **table** is instance data — many entries, indexed by the model's own sets, named nowhere in the
prose. Tables live in `data/raw/` and both sides read them, because a failed assertion cannot
otherwise distinguish a typo in the data from a bug in a constraint.

The package **takes the instance as an argument and never re-reads the CSV** during a notebook run.
That is what lets a reader uncomment `OPEX['PROC', 'R2'] = 2.00` in section 2.2, watch the edit flow
into both the hand-built model and the check, and see the assertion stay green. A check that punishes
experimenting is a check that gets switched off.

The CSVs exist twice — `data/raw/` as the editable copy and `src/lithium/data/` as package data, so
`pip install git+https://...` carries them into Colab with no checkout. `test_smoke.py` asserts the
two copies are identical.

## The licence is the deployment constraint

Gurobi's free `pip` licence allows roughly **2,000 variables for LP/MILP but only about 150 for
QP/MIQP** — a limit found by probing, not from documentation. Everything in `notebooks/` is a MILP
and fits comfortably: the Part 4c best response is 906 variables.

That limit is why `games.best_response_cournot` piecewise-linearises the quadratic revenue instead of
handing Gurobi a MIQP. `Part4c_exact_MIQP.ipynb` is the one notebook that genuinely needs the
quadratic form, and it ships with `SMALL = True` by default.

**`gurobi.lic` is never committed.** It carries a live WLS secret and is gitignored as both
`gurobi.lic` and `*.lic`. Verify with `git check-ignore -v gurobi.lic` before any `git add` here.

---

## Documents

| | |
|---|---|
| `CLAUDE.md` | the code and teaching standard, and the boundary between them |
| `PLAN.md` | the two-track migration, phase by phase |
| `AUDIT_AND_REMEDIATION_PLAN.md` | the measured findings behind it (§2's ordering is superseded) |
| `PROJECT_JOURNAL.md` | the modelling findings, notebook by notebook |
