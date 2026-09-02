# Project Conventions

Reusable conventions for scaffolding and maintaining repositories.

**How to use this:**
- Drop it in a repo root as `CLAUDE.md` — Claude Code reads it automatically every session.
- Or put it at `~/.claude/CLAUDE.md` to apply to every repo on your machine.
- Or paste it into a Claude Project's custom instructions for non-code chats about the work.

When starting a new repo, tell Claude: *"Scaffold this as a [archetype] per CLAUDE.md."*

---

## Part 1 — The invariant core

These eight rules apply to **every** project type below. If a suggestion
conflicts with one of these, the rule wins unless I say otherwise.

1. **One command reproduces everything.**
   `python scripts/run_all.py`, `make all`, `npm run build`, `pytest` — one
   documented entry point. If a clean clone can't reproduce the outputs, the
   repo is broken. This is the single highest-value property.

2. **Configuration lives outside code.**
   Parameters, paths, thresholds, and credentials never get hardcoded in a
   module. Use `config.yaml`, `.env`, or equivalent. A scenario or environment
   change must be a config edit, never a code edit or a copy-pasted script.

3. **Dependencies are pinned with upper bounds.**
   `pandas>=2.0,<4` not `pandas`. An unpinned dependency will one day install
   a major version with a changed API and either break or — worse — silently
   alter results. Record the interpreter version too.

4. **Inputs are immutable.**
   Whatever comes in from outside (raw data, fixtures, vendor files) is
   read-only. No stage ever writes back to it. Fix the code and re-run;
   never lose the original.

5. **Generated files are gitignored — with deliberate, documented exceptions.**
   Anything regenerable stays out of git. The exception worth making in
   research repos: commit final figures/results so a reader sees outputs
   without running anything, and so an artifact is pinned to a commit. State
   the exception in the README so it reads as a choice, not an accident.

6. **Tests exist and CI runs them on a clean machine.**
   At minimum a smoke test: does it run end to end, and are the outputs
   sane. The clean machine matters more than the test count — it catches
   "works on my laptop," which is the bug class that breaks other people.

7. **The README says how to run it.**
   Install, run, expected inputs, expected outputs, and what's deliberately
   committed. Written for a stranger, or for me in eighteen months.

8. **Commits are meaningful; releases are tagged.**
   Messages describe *why*, not "wip". Tag anything cited externally
   (`git tag paper-2026-ieee`) so ongoing development never invalidates a
   published result.

**Never:** commit secrets, credentials, API keys, or unpublishable data. Git
history is permanent — deleting a file in a later commit does not remove it
from history. Add `.env` and data directories to `.gitignore` before the
first commit, not after.

---

## Part 2 — Archetypes

Pick one. Each lists only its **delta** from the core above.

### A. Batch analysis pipeline *(default for research code)*

Simulation, optimization, statistical analysis, data processing. Inputs go in,
artifacts come out, nothing runs continuously.

```
config.yaml  scenarios/          data/raw/ interim/ processed/
src/<pkg>/   clean.py model.py analyze.py config.py
scripts/run_all.py   notebooks/   results/figures/ tables/   tests/
```

- Three data tiers, one-way flow: `raw → interim → processed`. Never one
  merged "output" folder — you lose track of what derives from what, and
  a plot tweak forces a full re-solve.
- Stages are importable functions, not scripts with logic in `__main__`.
- Two notebooks, two jobs: a thin one that imports and calls the stages, and
  (optionally) a teaching one that may build from scratch **provided** its
  last cell asserts agreement with the production module and CI executes it.
- `pyproject.toml` so `pip install -e .` works — required for Colab, and it
  removes all `sys.path` fragility.
- Smoke test asserts the pipeline runs and the domain invariants hold
  (conservation, capacity limits, non-negativity).

### B. Dashboard / interactive app

Streamlit, Dash, Panel, Shiny. **Keep archetype A underneath it** and add the
app as a presentation layer.

```
src/<pkg>/          (unchanged pipeline stages)
app/main.py         reads data/processed/ — never re-runs the model
data/processed/     precomputed artifacts the app serves
```

- **The app must not run the model on page load.** Precompute into
  `data/processed/`, have the app read it. A dashboard that re-solves per
  request is unusable and will time out on free hosting.
- Cache aggressively (`@st.cache_data` / `@lru_cache`) at the load boundary.
- The one command becomes two: `run_all.py` builds artifacts, then
  `streamlit run app/main.py` serves them. Document both.
- **GitHub Pages cannot host this** — Pages serves static files only, no
  Python process. Use Streamlit Community Cloud, Hugging Face Spaces, Render,
  or Fly.io. Pages works only if you export to static HTML.
- Add a test that imports the app module and checks it constructs without
  error. Cheap, and catches most deploy breakage.

### C. Library / installable package

Something others `pip install` and import. **Drop the data tiers entirely** —
there is no raw data, and `run_all.py` is meaningless because there's no
linear pipeline.

```
src/<pkg>/     tests/ (mirrors src/ file-for-file)
pyproject.toml  CHANGELOG.md  docs/
```

- Real test coverage, not a smoke test. Public API needs unit tests, edge
  cases, and error paths. This is the biggest jump in rigor from archetype A.
- Semantic versioning + a `CHANGELOG.md`. Breaking changes require a major
  bump and a deprecation period.
- The public API is a contract. Anything not underscore-prefixed is something
  you've promised to keep working.
- Test against a matrix of Python versions in CI.
- Branch + PR discipline actually matters here, because others depend on you.

### D. Web service / API

FastAPI, Flask, Django. Like C, plus operational concerns.

- **Twelve-factor config**: environment variables, not `config.yaml`. Secrets
  come from the environment or a secret manager, never from a file in git.
- Integration tests hitting real endpoints, not just unit tests.
- Structured logging, health check endpoint, graceful shutdown.
- Database migrations are versioned and committed (Alembic or equivalent).
- Containerize (`Dockerfile`) — "works on my machine" is a production outage
  here, not an inconvenience.

### E. ML training / experiment sweeps

Archetype A plus experiment management.

- **Experiment tracking is not optional**: MLflow, Weights & Biases, or at
  minimum a `results/runs/<timestamp>/` directory holding config + metrics +
  git SHA for every run. Without it you cannot answer "what produced this
  number," which is the whole point.
- **Model weights and large artifacts do not belong in git.** Use DVC,
  git-LFS, or an external store with a fetch script. Git handles text diffs;
  it handles a 400 MB checkpoint terribly.
- Set and record every seed. Note that GPU nondeterminism means bit-exact
  reproducibility often isn't achievable — document the tolerance instead of
  pretending otherwise.
- Log the git SHA into the run directory so any result traces to code.

### F. Instrument control / data acquisition

Bench testing, sensors, hardware-in-the-loop.

- **Raw immutability is critical, not merely good practice** — you cannot
  re-collect a run. Write raw to a timestamped, append-only location and
  back it up off the acquisition machine.
- Every raw file gets a sidecar metadata record: instrument, operator,
  calibration state, ambient conditions, software version, timestamp.
- Calibration files are versioned and dated; results reference which
  calibration they used.
- `run_all.py` doesn't apply — acquisition is event-driven, not batch. The
  *analysis* of collected data is a separate archetype-A repo (or a separate
  directory) reading acquisition output as its immutable raw tier.

---

## Part 3 — Choosing

| The output is… | Archetype |
|---|---|
| Files: CSVs, figures, tables | A |
| A thing people click through in a browser | B (on top of A) |
| Something others import | C |
| Something others call over a network | D |
| A trained model + metrics | E |
| Measurements from physical equipment | F |

**Mixed projects are normal.** A repo can be A + B (pipeline plus dashboard).
When it's A + C (analysis you also want importable), split it: a library repo
with real tests, and an analysis repo that depends on it. Don't try to make
one repo satisfy both rigor levels.

---

## Part 4 — Anti-patterns

Flag these if you see me doing them:

- A notebook that reimplements what a module already does, with nothing
  checking that they agree.
- Parameters buried in function bodies instead of config.
- A single `output/` folder mixing intermediates with final results.
- Committing large or regenerable data "just in case."
- `sys.path.insert` hacks instead of a proper installable package.
- Unpinned dependencies in a repo tied to published results.
- Deferring the README and tests to "after the paper is done."
- A dashboard that recomputes on every page load.
- Using archetype C's rigor for a one-off analysis (over-engineering) or
  archetype A's looseness for a shared library (under-engineering).

---

## Part 5 — Working with me

- Explain trade-offs rather than presenting one option as the only choice;
  I want to understand *why*, not just receive scaffolding.
- Tell me when a convention here doesn't fit what I'm actually doing. These
  are defaults, not laws.
- Verify by running. Don't tell me code works — execute it, run the tests,
  and show output.
- Prefer the boring, standard tool over the clever one. Research code
  outlives its author's memory of it.

---

# Part 6 — This project specifically

Everything above is portable. This section is not: it says how the two standards
apply *here*, and it is the part an assistant must read before changing anything.

## The two standards, and the boundary between them

This repo is governed by **two** documents that genuinely conflict:

1. `PROJECT_CONVENTIONS.md` (Parts 1–5 above) — how to build a reproducible package.
2. `Teaching Code Standard (portable).md` — how to write code students learn from.

They disagree in two places, and the disagreement is not a mistake:

| Question | Conventions say | Teaching standard says |
|---|---|---|
| Configuration | Lives outside code, never hardcoded (rule 2) | No config dict at the top — every cell becomes a lookup rather than a decision |
| Abstraction | One source of truth; never duplicate a function | No function definitions in the teaching section. None. |

**The resolution — the single most important rule in this file:**

> **`src/` is governed by the conventions. `notebooks/` is governed by the
> teaching standard. Neither document gets to win on the other's territory.**

Concretely:

- Hardcoded numbers in a teaching notebook are **correct**, not debt. Do not
  "fix" them into a config dict.
- A step written out by hand in a notebook that also exists in `src/lithium/`
  is **correct**, not duplication. Do not DRY it away.
- Conversely, a helper function in `src/` that only one caller uses is fine;
  a helper function in the *teaching section* of a notebook is not.

An assistant reading only `PROJECT_CONVENTIONS.md` will refactor the notebooks in
exactly the wrong direction. That has to be said out loud, which is why it is here.

## What keeps the two from drifting

The duplication above is deliberate, so the usual protection (there is only one
copy) is unavailable. The replacement is an **agreement assertion**, and it is
mandatory, not optional:

> Every teaching notebook ends with a cell that imports the package, runs the
> same case, and asserts the hand-built answer and the packaged answer agree.

```python
from lithium.models import build_region_model     # the streamlined version
packaged = build_region_model(**PARAMS_USED_ABOVE).solve()
rel = abs(packaged.obj - hand_built_obj) / abs(hand_built_obj)
assert rel < 1e-9, f"notebook and package disagree by {rel:.2e}"
```

Without that cell, the notebook is not finished. It is the only thing standing
between "two implementations by design" and the §1.2 bug class in
`AUDIT_AND_REMEDIATION_PLAN.md`, where one function was pasted into eight
notebooks and three copies silently drifted.

## Repository shape

```
src/lithium/          conventions territory — one implementation, tested, pinned
notebooks/            teaching territory — step-by-step, Colab-ready, hand-built
tools/                audit + checks (duplication, prose numbers, structure)
scripts/run_all.py    the one documented entry point
tests/                smoke tests + the invariants
```

## Non-negotiables specific to this repo

- **`gurobi.lic` is never committed.** It carries a live `WLSSECRET`. It is in
  `.gitignore` as both `gurobi.lic` and `*.lic`. Verify with
  `git check-ignore -v gurobi.lic` before any `git add` that touches this folder.
- **Notebooks ship executed.** Outputs and figures are committed on purpose, so a
  reader without a Gurobi license can still see what the prose refers to. This is
  the documented exception to rule 5.
- **Every number in prose comes from the committed run.** Not from memory, not
  from an earlier draft. `tools/prosecheck.py` enforces this.
- **Notebooks must run on Colab with the free `pip` Gurobi license** (~2,000
  variables). Anything above that limit is gated behind a `SMALL = True` switch
  that is on by default, with a loud printed message saying so.
- **Where a reader must choose**, raise an explanatory error, never let it fall
  through to a `NameError`.
