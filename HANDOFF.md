# Handoff — remaining work on the lithium modelling series

*Paste the block below into a new chat opened in this folder. Everything it
refers to is committed here.*

---

I'm continuing work on the lithium optimisation modelling notebook series in this
folder. Phase 0 is done and committed; I want to pick up at Phase 1.

**Read first, in this order:**
1. `CLAUDE.md` — loads automatically. Part 4 is the load-bearing section: `src/`
   is engineering territory, `notebooks/` is teaching territory, and they hold the
   same model on purpose. Part 11 is the project-specific rules.
2. `PLAN.md` — the plan you are executing. §5 is the phases.
3. `AUDIT_AND_REMEDIATION_PLAN.md` §1 — the measured findings, if you need the
   evidence behind a decision. Skip its §2; `PLAN.md` supersedes that ordering.

**Where things stand.** Seven commits, tagged `pre-remediation-2026-09-02` at the
starting state. Phase 0 back-ported a default-argument-capture fix to both call
sites in `Part4c_Cournot_Endogenous_Price.ipynb`, removed a duplicate cell,
corrected Part 0's kernel metadata, and established `.gitignore` with `gurobi.lic`
excluded and verified. Part 4c re-executed clean afterwards: 0 errors, 30.0 s,
every number unchanged.

**Decisions already made — don't re-open these:**
- Public GitHub repo, so the Colab badge is one click and `src/` is installed
  rather than pasted into each notebook.
- All fourteen notebooks get the teaching treatment, production track included.
- Hardcoded numbers in the notebooks stay. That is `CLAUDE.md` Part 4, not debt.

**Phase 1 — the vertical slice on Part 4c.** Do one notebook completely rather
than one phase across fourteen:
- Unzip `dispatch-template.zip` as the repo skeleton. It is already a working
  archetype-A layout — don't design one from scratch.
- Build `src/lithium/` from the Part 4 family's shared code; `pip install -e .`
- Adjudicate each drifted function pair as **feature or drift** and record which:
  `add_region` (4e's tariff/quota/LCR version is a feature — parameterise it),
  `best_response_cournot` (drift — the `len(KR)` version wins), `joint_profit_max`,
  `set_tiers`.
- Rewrite Part 4c to Part 0's shape: markdown above every code cell, one idea per
  cell, a predict-before-you-run prompt before the first solve, and the agreement
  assertion as the last cell.
- Add the Colab bootstrap and badge.
- Separately and immediately: `PROJECT_JOURNAL.md` says commitment is worth ~20%.
  The current run says 24.6%. That is a published claim that is wrong.

**Acceptance:** a student with a Google account and no software opens the badge,
runs Part 4c top to bottom, and the agreement assertion passes.

**Traps specific to this repo:**
- `gurobi.lic` holds a live `WLSSECRET`. It is gitignored as `gurobi.lic` and
  `*.lic`. Run `git check-ignore -v gurobi.lic` before any `git add`. A credential
  in history means rotating the credential, not amending the commit.
- All fourteen notebooks are currently saved **stripped of outputs**. You cannot
  read a number off them — re-run to get one. Committing them executed is Phase 2.
- The free `pip` Gurobi licence allows ~2,000 variables for LP/MILP but only ~150
  for QP/MIQP. `Part4c_exact_MIQP` needs `SMALL = True` on by default.
- Part 2 is 310 s of the 584 s full-series runtime. It needs a `QUICK` switch.
- Part 0 is the template every other notebook should converge on. Don't restructure
  it.

**Do not:**
- Create or push the GitHub repo. I'll do that myself after reviewing what's in it.
- Refactor notebook constants into `config.yaml`. That is the single most likely
  wrong-direction change here.
- DRY away the notebook/package duplication. It is deliberate; the agreement
  assertion is what makes it safe.
- Report anything as working without executing it. Run it and show the output.

Start with Phase 1. Tell me what you find when you adjudicate the drifted pairs
before you commit to an implementation.
