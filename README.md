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
headline numbers every notebook narration quotes. It takes about 35 s. `--only 4d,4e` runs a
subset, `--quick` caps the best-response loop at 6 rounds for classroom use, and `--data DIR`
points it at a different instance directory.

The notebooks are **build outputs**: `tools/build_notebooks/` is their source of truth, and
`tests/test_notebook_sources.py` asserts regenerating reproduces what shipped. Never hand-edit a
notebook's cells — edit the builder, run `python tools/build_notebooks/build.py --all`, execute,
and commit executed. `build.py --check` reports the pre-ship measurements without writing.

Gurobi is required. The free `pip` licence is enough for everything in `notebooks/` — see
*The licence is the deployment constraint* below.

## Open it in Colab

| Notebook | What it covers | |
|---|---|---|
| `notebooks/01_deterministic.ipynb` | The deterministic network MILP, and four modelling choices that move the answer more than the data does: capex timing, investment granularity, learning, foresight | [![Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/USERNAME/lithium-modelling/blob/main/notebooks/01_deterministic.ipynb) |
| `notebooks/02_stochastic.ipynb` | Two-stage stochastic programming: nonanticipativity, EVPI and VSS, and why VSS measures how much you commit rather than how uncertain you are; progressive hedging and its rho trap | [![Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/USERNAME/lithium-modelling/blob/main/notebooks/02_stochastic.ipynb) |
| `notebooks/02b_benders.ipynb` | Benders / L-shaped decomposition: cuts from recourse duals, multicut against single cut, and what decomposition actually buys (it is not speed) | [![Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/USERNAME/lithium-modelling/blob/main/notebooks/02b_benders.ipynb) |
| `notebooks/02c_cvar.ipynb` | CVaR, minimax and a hybrid; why a solution vector is not a set of results, and how one plan reported three different average costs | [![Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/USERNAME/lithium-modelling/blob/main/notebooks/02c_cvar.ipynb) |
| `notebooks/04ab_planner_and_game.ipynb` | Cooperative planner and its Pareto frontier; the first game, at a fixed price; the cost of rivalry and a bound that looks violated | [![Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/USERNAME/lithium-modelling/blob/main/notebooks/04ab_planner_and_game.ipynb) |
| `notebooks/04c_cournot.ipynb` | Cournot competition with endogenous price; piecewise-linear revenue; iterated best response; collusion benchmark | [![Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/USERNAME/lithium-modelling/blob/main/notebooks/04c_cournot.ipynb) |
| `notebooks/04c_exact_miqp.ipynb` | The same game as a true MIQP; what a piecewise approximation costs, and why that cost stops being predictable inside a game | [![Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/USERNAME/lithium-modelling/blob/main/notebooks/04c_exact_miqp.ipynb) |
| `notebooks/04d_stackelberg.ipynb` | Bilevel programs; KKT conditions; big-M complementarity; exact linearisation of a bilinear term; entry deterrence | [![Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/USERNAME/lithium-modelling/blob/main/notebooks/04d_stackelberg.ipynb) |
| `notebooks/04e_policy.ipynb` | Tariffs, quotas and local content as exogenous levers; welfare accounting; why a tariff beats a quota | [![Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/USERNAME/lithium-modelling/blob/main/notebooks/04e_policy.ipynb) |

The badge is a one-click path: it clones this repo, `pip install -e .`, and runs. No local software
and no account beyond a Google login. **The `USERNAME` placeholder in the badge and in each
notebook's cell 0 must be replaced with the real GitHub owner before the badge resolves.**

The other eight notebooks are still at the repository root in their pre-migration form
(`Part0_Concepts_Guide.ipynb` and friends) and are migrated in Phase 2 of `PLAN.md`.

---

## Layout

```
data/raw/                 the instance tables, read by BOTH tracks
  -- the Part 4 game: two regions, three stages, competing firms --
  instance_base.csv         fixed / unit / opex / legacy, keyed (stage, region)
  efficiency.csv            yield ceiling, base, alpha, beta, delta, keyed by stage
  market.csv                demand base + growth, experience0, keyed by region
  -- the Parts 1/2 network: six sites, arc flows, one planner --
  network_sites.csv         capacity, lead, capex, opex, legacy, keyed by site
  network_tiers.csv         the yield-curve parameters, keyed by tier
  network_demand.csv        demand base + growth, keyed by region

src/lithium/              the streamlined track
  instance.py               the three tables -> one Instance
  structure.py              sets, windows, discount weights, yields by vintage
  curves.py                 capex learning, revenue linearisation, opex tiers
  regions.py                add_region: one region's chain, policy-instrument superset
  planner.py                the cooperative benchmark
  games.py                  best response, iterated best response, collusion
  core.py                   the Parts 1/2 network MILP - a DIFFERENT model family
  network_instance.py       its three tables -> one NetworkInstance
  mpec.py                   Stackelberg as a single-level MPEC, and the QP that checks it
  policy.py                 tariff / quota / local-content schedules, and welfare
  data/                     a copy of data/raw/, shipped as package data

notebooks/                the teaching track
  01_deterministic.ipynb    the network MILP, and four choices that move the answer
  02_stochastic.ipynb       the extensive form and progressive hedging, by hand
  02b_benders.ipynb         L-shaped by hand; cuts built from recourse duals
  02c_cvar.ipynb            CVaR by hand; scoring every plan the same way
  04ab_planner_and_game.ipynb  the planner and the first game, built by hand
  04c_cournot.ipynb         built by hand, narrated, ends in the agreement assertion
  04c_exact_miqp.ipynb      the exact MIQP; SMALL=True fits the free licence
  04d_stackelberg.ipynb     the MPEC by hand; carries 04c's chain over, marked
  04e_policy.ipynb          the three levers by hand; carries 04c and 04d over, marked

tools/
  build_notebooks/          the notebooks' source of truth; build.py generates and audits
  prosecheck.py             every number in the markdown against the executed outputs

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
QP/MIQP** — a limit found by probing, not from documentation. Everything in `notebooks/` fits, but
the two limits bind on different models, so both matter:

| model | type | size | against a limit of |
|---|---|---|---|
| Part 4c best response | MILP | 906 vars | ~2,000 |
| Part 4d MPEC | MILP | 1,129 vars, 274 binary | ~2,000 |
| Part 4d follower check | **QP** | 27 vars, 26 quadratic terms | ~150 |
| Part 4c-exact, `SMALL = True` | **MIQP** | 50 vars, 6 quadratic terms | ~150 |
| Part 4c-exact, `SMALL = False` | **MIQP** | 541 vars, 26 quadratic terms | ~150 — **does not fit** |

That first limit is why `games.best_response_cournot` piecewise-linearises the quadratic revenue
instead of handing Gurobi a MIQP, and why the MPEC discretises the leader's quantity rather than
keeping the bilinear term. The second is why `mpec.follower_qp` — the only genuine quadratic model
in the migrated set — stays a 27-variable check rather than growing into the follower's full chain.

`notebooks/04c_exact_miqp.ipynb` is the one notebook that genuinely needs the quadratic form, and it
ships with `SMALL = True` by default — at which size it needs no licence at all. Its section 12 runs
at full scale for anyone who configures one via `GRB_WLSACCESSID` / `GRB_WLSSECRET` /
`GRB_LICENSEID` or a Colab secret, and prints an explanation instead of failing for everyone else.
**No notebook in this repository requires a credential**, and `tools/credscan.py` checks in CI that
none contains one.

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
