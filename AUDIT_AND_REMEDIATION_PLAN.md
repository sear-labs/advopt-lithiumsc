# Audit and Remediation Plan — Lithium Modelling Notebook Series

**Date:** 2026-09-02
**Scope:** the fourteen `Part*.ipynb` notebooks in `Advanced Opt Modeling Examples/`, audited against
[PROJECT_CONVENTIONS.md](PROJECT_CONVENTIONS.md) and
[Teaching Code Standard (portable).md](../REE%204301%20-%20Energy%20System%20Modeling/Teaching%20Code%20Standard%20(portable).md).

---

## 0. How this audit was produced

Everything below is measured, not estimated.

| What | How |
|---|---|
| Structural metrics | AST/regex pass over every notebook's cell list |
| Duplication and drift | MD5 of each function body, grouped by name across notebooks |
| Execution status | all 14 executed in a fresh kernel via `nbclient`, `allow_errors=True` |
| Stale prose numbers | every number in markdown compared against the executed outputs |

**Result of the execution run: 14/14 pass, 0 errors, 584.4 s total** (Part 2 alone is 310.5 s).

The audit scripts (`audit.py`, `dup.py`, `runall.py`, `prosecheck.py`) currently live in a session
temp directory and **are not yet saved into this project** — see Phase 4.

---

## 1. Findings

### 1.1 Stale prose numbers in Parts 4c / 4d / 4e — HIGH

Violates the teaching standard's *"every specific number in the prose was copied from actual
output, not from memory or an earlier draft."* Thirteen figures verified by hand against the
tables the current run prints:

| Notebook | Prose says | Current run prints |
|---|---|---|
| 4d | commitment worth **+20%** (13,790 vs **11,527**) | 13,789.8 vs **11,070.7** → **+24.6%** |
| 4d | follower "1,469 vs **1,267**" | 1,468.7 vs **1,247.7** |
| 4c | price "20.21 vs **16.05**" | 20.21 vs **15.81** |
| 4c | collusion "1,572 vs **2,238**" | 1,571.7 vs **2,276.5** |
| 4c | R1 "1,061 → **1,267**", R2 "916 → **971**" | 1,060.7 → **1,247.7**, 915.8 → **1,028.8** |
| 4e | R1 falls "**11,527** to **7,175**" | **11,070.7** to **6,889.7** |
| 4e | price "**16.05** to **17.86**" | **15.81** to **17.70** |
| 4e | consumer surplus "**20,756** → **15,772**" | **21,204.2** → **16,038.9** |
| 4e | welfare "38,995 → **35,859**" | 38,995.6 → **35,840.5** |
| 4e | R2 profit rises from "**6,713**" | **6,720.8** |

**Every qualitative finding survives.** Tariffs still shrink welfare monotonically; the local
content requirement at 70 still backfires (6,720.8 → 5,289.2); entry deterrence still jumps only
at tariff 10; collusion still restricts output. But **one headline claim is wrong**: commitment is
worth **+24.6%**, not "+20%", and `PROJECT_JOURNAL.md` repeats the stale figure.

Cause: the prose was written against an earlier run and never refreshed. It is *not* caused by the
drift in §1.2 — 4c, 4d and 4e all print R1 = 11,070.7 today, so the baseline is currently
consistent across notebooks.

### 1.2 The same code is pasted into up to 8 notebooks, and some copies have drifted — HIGH

This is the bug class `PROJECT_JOURNAL.md` already records once ("stale embedded source — Part 2
carried an older snapshot of `build()`"). It was never fixed; it was replicated.

| Function | Copies | Status |
|---|---|---|
| `_rev_breakpoints` | 8 | identical |
| `set_tiers` | 7 | **2 versions** (3b vs the Part 4 family) |
| `_cap_cum_mult` | 6 | identical |
| `add_region` (84 lines) | 5 | **2 versions** — 4e adds quota/LCR/tariff (deliberate) |
| `solve_planner` | 5 | identical |
| `best_response_cournot` | 4 | **2 versions** — see §1.3 |
| `cournot_iterate`, `market_outcome` | 4 each | identical |
| `build` | 3 | **3 versions** (197 / 198 / 117 lines) |
| `joint_profit_max` | 3 | **2 versions** |
| `stackelberg` (79 lines) | 2 | identical |

### 1.3 The `len(KR)` fix was never back-ported to Part 4c — MEDIUM

The only difference between the two `best_response_cournot` versions:

```diff
-  S, R = _rev_breakpoints(a_eff, B_SLP[rt, p], smax)
+  S, R = _rev_breakpoints(a_eff, B_SLP[rt, p], smax, len(KR))
```

That is the fix for the default-argument-capture bug in the journal. It was applied to 4c-exact,
4d and 4e — and never to **Part 4c**, which is where the Cournot results come from. Note there are
**two** unfixed call sites in 4c, not one: `best_response_cournot` and `joint_profit_max`.

As shipped this produces correct numbers, because `NBP_REV` is never reassigned in 4c. But cell 31
tells the reader to try exactly that: *"`NBP_REV = 3` — a coarse revenue mesh; quantities should
get visibly blocky."* A reader who sets it in a new cell without re-running cell 12 gets `S`/`R`
with 7 breakpoints and `KR` with 3, so the sale variable is confined to a convex combination of
the **first three of seven** points — the firm's strategy space is silently truncated to
`[0, smax/3]`. They see blocky quantities, conclude the prose was right, and are wrong about why.

Minor, same notebook: cells 12 and 13 both define `_rev_breakpoints`; 13 is a strict subset of 12.

### 1.4 The inversion, in 12 of 14 notebooks — MEDIUM

The teaching standard calls this "the one to check for first." Large helper functions sit in the
first third, with the narration of the same material after them.

| Notebook | cells | big fns | first big fn at | streamlined heading | code cells w/o markdown | longest cell | asserts |
|---|---|---|---|---|---|---|---|
| Part 0 | 49 | 0 | — | — | 0 | 41 | 1 |
| Part 1 | 56 | 9 | **9%** | none | 12 | **206** | 0 |
| Part 2 | 57 | 11 | **9%** | none | 14 | **260** | 3 |
| Part 2b | 21 | 4 | 33% | none | 0 | 37 | 2 |
| Part 2c | 18 | 1 | **22%** | none | 2 | 55 | 1 |
| **Part 3** | 45 | 1 | **91%** | **yes (cell 40)** | 4 | 53 | 0 |
| Part 3b | 47 | 3 | 45% | none | 5 | 121 | 0 |
| Part 4ab | 39 | 4 | 28% | none | 5 | 85 | 0 |
| Part 4c | 32 | 7 | 28% | none | 12 | 85 | 0 |
| Part 4c-exact | 40 | 10 | 28% | none | 17 | 85 | 0 |
| Part 4d | 36 | 8 | 25% | none | 14 | 85 | 0 |
| Part 4e | 36 | 9 | 28% | none | 18 | 92 | 0 |
| Part 4f | 28 | 5 | **18%** | none | 1 | 41 | 2 |
| Part 5 | 23 | 6 | 30% | none | 2 | 118 | 6 |

Totals: **106 code cells with no markdown above them**; **zero** predict-before-you-run prompts
across all fourteen.

**Part 3 is the exception and is the template for the fix.** Its cell 40 reads:

> *"Now we re-solve variants, which is the one place a function is genuinely warranted — three
> near-identical models differing in two switches. Everything inside is the same code as above."*

That satisfies requirements 1 (explicit heading) and 2 (why now). It is missing only requirement 3
— the assertion that the wrapper reproduces the hand-built result. Part 3's own cell 44 already
states the principle in the author's words: *"Code style: Parts 1 & 2 — helper functions; Part 3 —
inline `addConstrs`, readable as algebra."*

### 1.5 No repository — MEDIUM

`.git`, `pyproject.toml`, `tests/`, `scripts/run_all.py`, `README.md`, `config.yaml`, `.github/` —
none exist, so most of conventions Part 1 is currently aspirational.

Already satisfied: no notebook reads an external data file (inputs-immutable holds trivially); no
notebook stores outputs. Violated: `!pip install gurobipy` unpinned in ten notebooks; seeds set
only in Parts 2b and 2c.

### 1.6 Where the two standards conflict

Conventions rule 2 says configuration lives outside code, never hardcoded. The teaching standard
says *"No configuration dictionary at the top that the rest of the notebook reads from — every
subsequent cell becomes a lookup rather than a decision."*

**Resolution adopted here:** conventions rule 2 governs `src/`; the teaching standard governs
notebooks. Hardcoded numbers in a teaching notebook are correct. This needs stating explicitly in
`CLAUDE.md`, because an assistant reading only the conventions would "fix" the notebooks in the
wrong direction.

---

## 2. Plan

### Phase 0 — Stop the bleeding *(hours)*

- [ ] `git init`, add `.gitignore` (`.env`, `__pycache__`, `*.lp`, `*.mps`, `*.sol`, `gurobi.log`, `.ipynb_checkpoints/`) **before** the first commit
- [ ] Commit the current state and tag it (`git tag pre-remediation-2026-09-02`) so every number below traces to a commit
- [ ] Copy `PROJECT_CONVENTIONS.md` to `CLAUDE.md` at this root, appending §1.6's resolution and a pointer to the teaching standard. **It does not load today** — Claude Code reads `CLAUDE.md`, not `PROJECT_CONVENTIONS.md`
- [ ] Fix Part 4c per §1.3: pass `len(KR)` explicitly; delete the redundant cell 13
- [ ] Fix Part 0: kernel metadata says 3.11 but it executed under 3.13.9; and rewrite the §23 BRI trace, whose intermediate path is not reproducible (see §3)

**Acceptance:** clean `git status`, a tag, `CLAUDE.md` present, Part 4c re-executes with identical output.

### Phase 1 — Refresh every number from the executed run *(half a day)*

Ahead of the package work, because stale published numbers are the thing with an outside audience.

- [ ] Re-execute all 14 and keep the outputs
- [ ] Correct the thirteen figures in §1.1 in Parts 4c, 4d, 4e
- [ ] Correct `PROJECT_JOURNAL.md`: "Commitment is worth ~20%" becomes **~25%**; check its tariff and welfare figures against the same run
- [ ] Re-run the prose checker; triage what remains

**Acceptance:** every number the checker flags is either corrected or annotated as a deliberate
cross-reference to another notebook's run.

### Phase 2 — One source of truth *(a day)*

- [ ] `src/lithium/` + `pyproject.toml`; `pip install -e .`
- [ ] Move in the shared code: `add_region`, `build`, `solve_planner`, `cournot_iterate`,
      `market_outcome`, `stackelberg`, `_rev_breakpoints`, `set_tiers`, `_cap_cum_mult`,
      `learning_breakpoints`, `capex_pv_multiplier`, `max_flow`
- [ ] For each drifted pair, decide **feature or drift**, and record which:
      - `add_region` 4e — **feature** (tariff/quota/LCR) → parameterize, one implementation
      - `best_response_cournot` 4c — **drift** → adopt the fixed version
      - `build` ×3, `set_tiers` ×2, `joint_profit_max` ×2 — adjudicate the same way
- [ ] Pin dependencies with upper bounds; record the interpreter version
- [ ] Smoke test asserting the invariants already used informally: `WS <= RP <= EEV`,
      planner cost <= competitive cost at matched volume, conservation, non-negativity

**Acceptance:** every notebook produces the same numbers as at the Phase 1 tag, now importing one
implementation. Any change in a number is investigated, not accepted.

### Phase 3 — Re-sequence the notebooks *(a day)*

Part 3 is the template.

- [ ] Move large functions below a "Now the streamlined version" heading with a sentence saying
      why now, and an assertion that the wrapper reproduces the hand-built result
- [ ] Add that missing assertion to Part 3 itself
- [ ] Split the 206-line (Part 1) and 260-line (Part 2) cells
- [ ] Add markdown above the 106 orphan code cells, worst first: 4e (18), 4c-exact (17), Parts 2 and 4d (14 each), Parts 1 and 4c (12 each)
- [ ] Add at least one predict-before-you-run prompt per notebook, before the first solve
- [ ] Part 0 only: inline the five functions whose bodies are the lesson (`eta`, `Q`/`dual_slope`,
      `follower_kkt`, `max_flow`); leave the one-line lambdas that merely restate a symbol

**Acceptance:** zero function definitions above the streamlined heading; every teaching cell has
markdown above it; every wrapper has a reproduction assert.

### Phase 4 — CI *(half a day)*

- [ ] Commit the audit tooling as `tools/` (`audit.py`, `dup.py`, `runall.py`, `prosecheck.py`)
- [ ] `scripts/run_all.py` — the one documented entry point
- [ ] GitHub Actions: smoke tests per commit; **nightly** full notebook execution (584 s is too
      slow for per-commit)
- [ ] Add the prose-number checker as a test — it would have caught §1.1 the day it appeared
- [ ] Add the duplication checker as a test — it fails if a function body appears in two places
- [ ] `README.md`: install, run, expected outputs, and what is deliberately committed

**Acceptance:** a clean clone reproduces every reported number with one command.

---

## 3. Known defect carried over from the Part 0 rewrite

Part 0 §23's Best Response Intersection trace names a specific iteration path. It is not robust:

| variant | undefended best attack | iteration-1 ABR | the "ABR fell" teaching moment |
|---|---|---|---|
| as published | b→t | 3 | at iteration 2 |
| arcs listed in a different order | b→t | **2** | at iteration 1 |
| nodes renamed a,b → x,y | **s→a** | **2** | at iteration 1 |

The converged answer is stable in every variant (fortify {s→a, b→t}, guaranteed flow 3, 3
iterations); only the trace differs. Twelve capacity perturbations and a stated secondary
tie-break rule were tested — **none makes it invariant**, because the degeneracy is structural:
with one retained attack, every fortification covering that arc scores θ = full flow.

**Fix:** assert only the invariant quantities in prose and teach the degeneracy — which fits, since
§22 already notes three cuts tie at 5 and §23 already says runtime is governed by near-tied cuts.

---

## 4. Priority

1. **Phase 0** — small, and makes everything after it reversible
2. **Phase 1** — one published claim is currently wrong
3. **Phase 2** — removes the mechanism that produced Phase 1
4. **Phases 3–4** — pedagogy and prevention
