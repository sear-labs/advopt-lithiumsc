# Handoff — remaining work on the lithium modelling series

*Paste the block below into a new chat opened in this folder. Everything it
refers to is committed here.*

---

I'm continuing work on the lithium optimisation modelling notebook series in this
folder. Phase 0 is done, the Phase 1 adjudication is done and recorded, and the
design decisions are settled. I want you to **build** Phase 1.

**Read first, in this order:**
1. `CLAUDE.md` — loads automatically. Part 4 is load-bearing: `src/` is
   engineering territory, `notebooks/` is teaching territory, they hold the same
   model on purpose, and *Tables versus knobs* says which numbers live where.
   Part 11 is the project-specific rules and lists the knobs and tables by name.
2. `PLAN.md` — the plan you are executing. §5 is the phases; Phase 1 carries the
   adjudication results already.
3. `AUDIT_AND_REMEDIATION_PLAN.md` §1 — measured findings, if you need the
   evidence behind a decision. Skip its §2; `PLAN.md` supersedes that ordering.

## Where things stand

The starting state is tagged `pre-remediation-2026-09-02`; run `git log --oneline`
for what has happened since. Nothing has been *built* yet — every change so far is
to documentation and to `dispatch-template.zip`, plus Phase 0's fixes to Part 4c.

**Phase 0** back-ported the default-argument-capture fix to both call sites in
`Part4c_Cournot_Endogenous_Price.ipynb`, removed a duplicate cell, corrected
Part 0's kernel metadata, and established `.gitignore` with `gurobi.lic` excluded
and verified. Part 4c re-executed clean: 0 errors, 30.0 s, every number unchanged.

**The adjudication is done** — see `PLAN.md` §5 Phase 1, which records it. Short
version: `best_response_cournot` and `joint_profit_max` were already resolved by
Phase 0 and are single-version now; `add_region` is a **feature** whose 4e version
is a strict superset that self-disables on empty policy dicts; `set_tiers` is
neither feature nor drift, just the same arithmetic over a different index set.
Don't redo this — build on it.

## The design, in three sentences

The notebook builds the model **by hand** so the student reads every constraint;
`src/lithium/` holds the same model as functions so `run_all.py` and CI can call
it; and the last cell of every notebook imports the package, runs the same case,
and asserts the two agree — which is the only thing making the deliberate
duplication safe.

The assertion needs shared inputs to mean anything, so **instance tables live in
`data/raw/` and both sides read them**, while **knobs stay written out in the
notebook cell**. `CLAUDE.md` Part 4 *Tables versus knobs* has the rule and Part 11
has the per-symbol lists. The package takes the instance **as an argument** and
never re-reads the CSV during a notebook run, so a reader who edits a value sees
it flow into both the hand-built model and the check.

## Decisions already made — don't re-open these

- Public GitHub repo, so the Colab badge is one click and `src/` is installed
  rather than pasted into each notebook.
- All fourteen notebooks get the teaching treatment, production track included.
- Knobs stay hardcoded in the notebooks; only instance tables move to CSV.
- The notebooks are **complete worked examples**, not fill-in-the-blank exercises.
  Measured: zero blank markers across all fourteen. "Built by hand" means written
  out longhand *by the author* — the opposite of `results = run_model(config)`,
  not the opposite of "finished". Do not introduce `# YOUR CODE HERE` anywhere.
- `src/lithium/` is a **model-builder library, not a data pipeline** — all
  fourteen notebooks contain zero lines of file I/O. `data/raw/` holds the
  instance tables and nothing else. No `interim`, no `processed`, no `clean.py`.

## Phase 1 — build the vertical slice on Part 4c

- [ ] Unzip `dispatch-template.zip` as the skeleton. Take `pyproject.toml`,
      `tests/`, `.github/workflows/ci.yml`, `scripts/run_all.py`, `results/`.
      **Drop** `data/{interim,processed}`, `clean.py`, and `config.yaml` — see
      above. Don't design a layout from scratch.
- [ ] `src/lithium/` from the Part 4 family's shared code, on the adjudication in
      `PLAN.md` §5. `pip install -e .` and show it importing.
- [ ] Pull the three instance CSVs out of Part 4c (`instance_base.csv`,
      `efficiency.csv`, `market.csv` — Part 11 lists what goes in each). Ship them
      as **package data** under `src/lithium/data/` so `pip install git+...`
      carries them into Colab, with `data/raw/` at the repo root as the editable
      copy.
- [ ] Assert the `add_region` collapse: the 4e superset with empty
      `TARIFF`/`QUOTA`/`LOCAL_MIN` must reproduce 4c's objective to 1e-9.
- [ ] Rewrite `notebooks/04c_cournot.ipynb` to Part 0's shape — markdown above
      every code cell, one idea per cell, print after each step, a
      predict-before-you-run prompt before the first solve. The 85 lines currently
      hidden inside `add_region` become narrated cells; that is the actual work,
      and it is writing rather than refactoring.
- [ ] The instance cells specifically: load the CSV → `display()` the frame →
      build the dicts and print them with the `(stage, region)` keys and the index
      sets visible → a **commented-out** worked example of overriding one entry
      (`OPEX['PROC', 'R2'] = 2.00`) explaining that the edit flows into both the
      model and the assertion. This shape is settled; don't redesign it.
- [ ] Agreement assertion as the last cell, taking the instance as an argument.
- [ ] **Break a constraint in `src/lithium/` on purpose and show the assertion go
      red**, then revert. A green assert that has never failed is not evidence.
- [ ] Colab bootstrap + badge.
- [ ] Independently and immediately: `PROJECT_JOURNAL.md` says commitment is worth
      ~20%. The current run says **24.6%**. That is a published claim that is
      wrong. Fix it from a run, not from this paragraph.

**Acceptance:** a student with a Google account and no software opens the badge,
runs Part 4c top to bottom without writing anything, and the assertion passes.

## The template is already fixed — use it as shipped

`dispatch-template.zip` used to ship `PROJECT_CONVENTIONS.md` as its `CLAUDE.md`
(the engineering-only half, no teaching standard, no boundary section) while its
README claimed *"config.yaml, every parameter, the ONLY place numbers live"* and
its own teaching notebook hardcoded `RAMP_MW = 20  # <-- change me`. Fixed
2026-09-02: it now ships the merged standard, the README carries the tables/knobs
carve-out, and `01_model_explained.ipynb` demonstrates the index-key printout and
the commented edit example. Verified by running `pytest -q` on a fresh extraction
of the rebuilt zip: 6 passed, including the notebook-execution test that runs the
anti-drift assertion.

So take the template's `CLAUDE.md` and its notebook shape at face value — they
agree with this repo's standard now. One thing it still does *not* do: it ships
its notebooks stripped of outputs, against its own "ship it executed" rule. Don't
copy that.

## Traps specific to this repo

- `gurobi.lic` holds a live `WLSSECRET`. Gitignored as `gurobi.lic` and `*.lic`.
  Run `git check-ignore -v gurobi.lic` before any `git add`. A credential in
  history means rotating the credential, not amending the commit.
- All fourteen notebooks are saved **stripped of outputs**. You cannot read a
  number off them — re-run to get one. Committing them executed is Phase 2.
- The free `pip` Gurobi licence allows ~2,000 variables for LP/MILP but only ~150
  for QP/MIQP. `Part4c_exact_MIQP` needs `SMALL = True` on by default.
- Part 2 is 310 s of the 584 s full-series runtime. It needs a `QUICK` switch.
- Part 0 is the template every other notebook converges on. Don't restructure it.
- `_rev_breakpoints` still carries a latent default-argument capture
  (`n=NBP_REV`), unreachable because all seven call sites override it. The default
  goes away in the package rather than being carried across.

## Do not

- Create or push the GitHub repo. I'll do that myself after reviewing what's in it.
- Move knobs into `config.yaml`. Tables to CSV, knobs stay in the cell.
- DRY away the notebook/package duplication. It is deliberate; the agreement
  assertion is what makes it safe.
- Add fill-in-the-blank exercises.
- Report anything as working without executing it. Run it and show the output.
