# CODE AND TEACHING STANDARD

*Portable. Nothing below is specific to one course, language, library or project.*

**How to use this:**
- Drop it in a repo root as `CLAUDE.md` — Claude Code reads it automatically every session.
- Or put it at `~/.claude/CLAUDE.md` to apply to every repo on the machine.
- Or paste it into a Claude Project's custom instructions for non-code chats about the work.

When starting a new repo: *"Scaffold this as a [archetype] per CLAUDE.md."*
When starting a teaching notebook: *"Teaching-code style per CLAUDE.md Part 3."*

---

## Part 0 — What this document is, and why it is one document

This merges two standards that are each correct and that **contradict each other
in two specific places**:

- **Engineering conventions** (Parts 1–2): how to build something reproducible.
- **Teaching code standard** (Part 3): how to write code somebody learns from.

They were previously separate files. That was the mistake. An assistant — or a
person — reading only the engineering half will "clean up" a teaching notebook in
exactly the wrong direction, and reading only the teaching half will ship research
code with no tests and unpinned dependencies. **Part 4 is the boundary between
them and is the most important section here.** If you read nothing else, read
Part 4.

---

## Part 1 — The invariant core

These apply to **every** project. If a suggestion conflicts with one of these,
the rule wins unless overridden explicitly.

1. **One command reproduces everything.** `make all`, `pytest`,
   `python scripts/run_all.py` — one documented entry point. If a clean clone
   can't reproduce the outputs, the repo is broken. Highest-value property here.

2. **Configuration lives outside code.** Parameters, paths, thresholds and
   credentials never hardcoded in a module. A scenario change is a config edit,
   never a code edit or a copy-pasted script. *(Part 4 carves out the exception.)*

3. **Dependencies are pinned with upper bounds.** `pandas>=2.0,<4`, not `pandas`.
   An unpinned dependency will one day install a major version with a changed API
   and either break or — worse — silently alter results. Record the interpreter
   version too, and make it match what actually ran.

4. **Inputs are immutable.** Whatever comes from outside is read-only. No stage
   writes back to it. Fix the code and re-run; never lose the original.

5. **Generated files are gitignored — with deliberate, documented exceptions.**
   The exception worth making: commit final figures and results so a reader sees
   outputs without running anything. State it in the README so it reads as a
   choice, not an accident.

6. **Tests exist and CI runs them on a clean machine.** At minimum a smoke test:
   does it run end to end, are the outputs sane. The clean machine matters more
   than the test count — it catches "works on my laptop."

7. **The README says how to run it.** Install, run, expected inputs, expected
   outputs, what's deliberately committed. Written for a stranger, or for you in
   eighteen months.

8. **Commits are meaningful; releases are tagged.** Messages describe *why*. Tag
   anything cited externally or handed to students, so ongoing development never
   invalidates a published result or a link someone is using.

**Never:** commit secrets, credentials, API keys, or unpublishable data.

> **Git history is permanent.** Deleting a file in a later commit does not remove
> it. Add `.env`, `*.lic`, `*_key*`, and data directories to `.gitignore` **before
> the first commit**, and *verify* — `git check-ignore -v <file>` — rather than
> assuming the pattern matched. A credential in history means rotating the
> credential, not amending the commit. This is the one mistake in this document
> that cannot be undone.

---

## Part 2 — Archetypes

Pick one. Each lists only its **delta** from Part 1.

| The output is… | Archetype |
|---|---|
| Files: CSVs, figures, tables | **A** batch analysis pipeline |
| A thing people click through in a browser | **B** dashboard, on top of A |
| Something others import | **C** library |
| Something others call over a network | **D** web service |
| A trained model + metrics | **E** ML sweeps, A plus tracking |
| Measurements from physical equipment | **F** acquisition |
| **Something people learn from** | **T** — see Part 3 |

**A — Batch analysis pipeline** *(default for research code)*
`config.yaml`, `scenarios/`, `data/{raw,interim,processed}/`, `src/<pkg>/`,
`scripts/run_all.py`, `notebooks/`, `results/{figures,tables}/`, `tests/`.
Three data tiers, one-way flow — never one merged `output/` folder, or you lose
track of what derives from what and a plot tweak forces a full recompute. Stages
are importable functions, not logic in `__main__`. `pyproject.toml` so
`pip install -e .` works — required for Colab, and it removes all `sys.path`
fragility. Smoke test asserts the domain invariants — whatever must be true of
any correct output, such as totals that have to balance or quantities that
cannot go negative.

**B — Dashboard.** Keep A underneath; the app is a presentation layer. **It must
not run the model on page load** — precompute into `data/processed/` and have the
app read it. Cache at the load boundary. GitHub Pages cannot host it (static files
only); use Streamlit Cloud, HF Spaces, Render or Fly.

**C — Library.** Drop the data tiers; there is no linear pipeline. Real coverage,
not a smoke test — the public API is a contract. SemVer + `CHANGELOG.md`. Test
across a Python version matrix.

**D — Web service.** Twelve-factor config (environment variables, not
`config.yaml`). Integration tests against real endpoints. Structured logging,
health check, graceful shutdown. Versioned migrations. Containerize.

**E — ML sweeps.** Experiment tracking is not optional: MLflow, W&B, or at minimum
`results/runs/<timestamp>/` holding config + metrics + git SHA. Weights don't
belong in git. Record every seed, and document the tolerance rather than
pretending GPU bit-exactness.

**F — Acquisition.** Raw immutability is critical, not merely good practice — you
cannot re-collect a run. Sidecar metadata per raw file: instrument, operator,
calibration, conditions, software version. `run_all.py` doesn't apply; the
*analysis* is a separate archetype-A project reading acquisition output as raw.

**Mixed projects are normal.** A + B is common. A + C should be *split* into a
library repo with real tests and an analysis repo that depends on it — don't make
one repo satisfy both rigor levels. **A + T is the subject of Part 4.**

---

## Part 3 — Archetype T: code meant for instruction

### The rule

> **The top of a teaching notebook is step-by-step. The bottom may be
> streamlined.**

Good production code hides repetition; that is what it is for. But **abstraction
hides exactly the thing the student came to learn.** So: a chunk of code carrying
one step, with markdown above it saying what it does and why. The tidy version
with the functions and loops comes later, clearly labelled, after the reader
already knows what it contains.

### Why, in increasing order of importance

1. **A function is a promise that the details don't matter** — true for a working
   engineer, false for a learner. `results = run_model(config)` teaches one line.
   The eight decisions inside are invisible, and invisible decisions cannot be
   questioned, adapted or debugged.
2. **Students cannot debug what they have not seen assembled.** The common failure
   is not "my code broke," it is "my code ran and I don't know if the answer is
   right." Someone who typed each component knows where to look.
3. **The steps are the content.** In a modelling course the sequence *is* the
   syllabus. Wrapping it in `build()` does not compress the lesson, it deletes it.
   The student ends the term able to operate a tool and unable to build one.

### Do

- **One idea per cell.** If you can't write a one-sentence heading for a cell, it
  is doing two things — split it.
- **Markdown above every code cell**, saying what it does and, where there's a
  choice, why this choice.
- **Name the argument that matters.** When one keyword carries the concept, say so:
  *this one flag is the difference between a dry run and a real one.*
  Students skim code; they do not skim a sentence that says "this is the important
  line."
- **Print something after each step** — the shape of a table, the number of rows,
  the value of a parameter. Evidence, not decoration. It turns a silent cell into
  a checkpoint.
- **Ask for a prediction before every solve or fit.** *Write down what you expect
  before you run this.* A result the student had no expectation about teaches
  nothing, because there is nothing for it to contradict.

### Don't

- **No function definitions in the teaching section.** None. If you need one, you
  are either past the teaching section or the step should be a cell.
- **No loop that hides a decision.** Looping over years to build a table is fine.
  Looping over technologies whose parameters each have different reasoning is not
  — write them out.
- **No configuration dictionary at the top** that the rest reads from. It looks
  tidy and it makes every subsequent cell a lookup rather than a decision.
- **Never put the abstraction before the thing it abstracts.**

### The inversion — check for this first

A notebook opens with a large helper function, then follows it with a beautifully
narrated walkthrough of the same material. The narration is good; its *position*
is wrong. The student met the abstracted version before the thing it abstracts.

**The fix costs no new content** — you are reordering cells, not writing. Measure
it: *where does the first function longer than ~8 lines sit, as a percentage of
the way through?* Under ~50% and there is an inversion.

### When to wrap, and how to do it honestly

Wrapping is not forbidden; it is *sequenced*. You wrap when the notebook needs the
same thing several times and the reader has already seen the parts. Three
requirements:

1. **An explicit heading.** "Now the streamlined version." The reader should know
   they've crossed from learning into convenience.
2. **A sentence saying why now.** *We are about to run this a dozen times at
   different sizes, and you have built every one of these components by hand.*
   Without it the wrap reads as a style inconsistency.
3. **A check that the wrapper reproduces the hand-built result.** See Part 4 —
   this is the requirement people skip and it is the one that earns the wrap.

---

## Part 4 — THE BOUNDARY

### Where the two halves contradict each other

| Question | Parts 1–2 say | Part 3 says |
|---|---|---|
| Configuration | Outside code, never hardcoded (rule 2) | No config dict at the top — every cell becomes a lookup rather than a decision |
| Abstraction | One source of truth; never duplicate a function | No function definitions in the teaching section. None. |

Both are right. They are describing different artifacts.

### The resolution

> **`src/` is governed by Parts 1–2. `notebooks/` is governed by Part 3.
> Neither half gets to win on the other's territory.**

Concretely:

- Hardcoded **knobs** in a teaching notebook are **correct**, not debt. Do not
  refactor them into a config dict. See *Tables versus knobs* below for the one
  class of number that does belong in a file.
- A step written out by hand in a notebook that also exists in `src/` is
  **correct**, not duplication. Do not DRY it away.
- Conversely: a helper used by one caller in `src/` is fine; a helper function in
  the *teaching section* of a notebook is not.

### Tables versus knobs — the one class of number that leaves the notebook

The rule above is right about parameters and wrong about instance data, and the
distinction is not stylistic. It falls out of the agreement assertion itself:

> **A number the notebook hands to the package may stay hardcoded — the assertion
> proves both sides used it.
> A number both sides look up independently must live in one file both sides
> read — nothing else can prove they agree.**

Call the first a **knob** and the second a **table**.

- A **knob** is a scalar carrying a concept: a discount rate, a learning rate, a
  breakpoint count — anything the narration explains, or invites the reader to
  change. It stays written out in the cell. Seeing `NBP_REV = 7` beside the
  sentence explaining what a breakpoint mesh does *is* the lesson, and the
  notebook passes it into the package explicitly, so the assertion covers it.
- A **table** is instance data: many entries, indexed by the model's own sets,
  named nowhere in the prose. Typing it into the notebook and again into the
  package duplicates *data* with nothing comparing the copies — the same failure
  as duplicated code, one level down, and harder to spot, because a mismatch
  surfaces as a failed assertion pointing at the model rather than at the number.

So tables live in `data/raw/` and both sides read them. Three requirements make
the loaded version teach *more* than the literals it replaces, not less:

1. **Render the table.** A printed frame reads better than a page of dict
   literals.
2. **Show the key structure.** A frame shows rows and columns; the model indexes
   by `(stage, region)`, or whatever its sets are, and every constraint below
   looks values up by that key. Print the dictionary form so the index set is
   explicit rather than implied by punctuation.
3. **The package takes the data as an argument and never re-reads the file.**
   Then a reader who edits a value sees it flow into both the hand-built model
   and the check, and the assertion stays green. A check that punishes
   experimenting is a check that gets switched off.

### The shape: two folders, three roles

```
src/<pkg>/                  written for a machine to run a thousand times
data/raw/                   the instance tables both sides read
notebooks/
  00_walkthrough.ipynb      THIN: imports the package, holds no logic
  NN_topic.ipynb            TEACHING: builds by hand, asserts agreement
```

Same model, twice, **on purpose**. The notebook builds it by hand because that is
the lesson; the package builds it once because that is the code.

**The thin notebook is the cheapest reconciliation available.** It calls the same
functions the entry point calls and holds no logic of its own, so it cannot
drift — there is nothing in it to go stale. Worth having exactly once, as the
front door: it proves the install works and reproduces the headline numbers
before a reader invests an hour in the teaching notebooks.

### The agreement assertion — the mechanism that makes this safe

Deliberate duplication removes the usual protection, which is that only one copy
exists. Something must replace it. **Every teaching notebook ends with a cell that
imports the package, runs the same case, and asserts the two agree:**

```python
from mypkg.models import build_model
packaged = build_model(**PARAMS_USED_ABOVE).solve()
rel = abs(packaged.value - hand_built.value) / abs(hand_built.value)
assert rel < 1e-9, f"notebook and package disagree by {rel:.2e}"
print(f"notebook and package agree to {rel:.1e}")
```

**A teaching notebook without this cell is not finished.** This is not ceremony.
The failure it prevents is well documented and looks like this:

> One helper function pasted into eight notebooks. Over time three copies drifted.
> A bug was found and fixed — in three of the four places it appeared. The fourth
> was the notebook the published results came from. Nobody noticed for months,
> because nothing compared the copies.

Deliberate duplication is a design. Deliberate duplication with nothing checking
it is just duplication with a story attached.

### Corollary: generated artifacts

If a notebook, document or dataset is **generated by a script**, the script is the
source of truth and the artifact is a build output. Something must check that
regenerating reproduces what shipped. A build script and its output drift exactly
as fast as two pasted copies do, and for the same reason — nobody is comparing
them.

---

## Part 5 — Shipping teaching material

Everything here is about the gap between "it runs for me" and "a student can run
it."

- **One click, no install.** Assume a student with a browser, a free account, and
  no software. In practice: a public repo, a hosted-notebook badge, and a first
  cell that installs pinned dependencies plus the package itself. A private repo
  forces token-pasting or vendoring the package into each notebook — which
  re-creates the duplication problem the split exists to remove.
- **Runs top to bottom on a clean machine with no local files.** Test this by
  deleting the files and running the whole thing. If a cell reads a file the
  student doesn't have, it must fail with an *explanation*, not a stack trace:
  fall back to generated data, print loudly that it has done so, and state that
  the fallback is not an acceptable submission.
- **Ship it executed.** Commit the outputs and figures. A reader without a licence,
  a GPU, or twenty minutes should still see what the prose refers to. This is
  rule 5's documented exception, and it is what makes every number in the prose
  checkable by the reader.
- **Respect the free tier explicitly.** Free/community licences and runtimes have
  limits, often undocumented and found only by probing. Anything past the limit
  ships behind a `SMALL = True` / `QUICK = True` switch that is **on by default**,
  printing what it changed and what a full licence would give.
- **Deliberate blanks fail with a message.** Where the student must choose,
  "run all" should not produce a bare `NameError`:

  ```python
  if "choice" not in globals():
      raise NameError("Choose one of the three options above. "
                      "This notebook will not choose for you.")
  ```

- **Tag what you hand out.** Students following a link months later should get the
  version you taught, not the branch you are mid-refactor on.

---

## Part 6 — Verification: the bugs that produce plausible output

Reading does not find these. Only running does. Every one of the following shipped
and looked fine:

- **A silently empty object.** An API called in the wrong order returns an empty
  model / frame / result. It "succeeds," reports success, evaluates to zero, and
  passes any assertion written against it. Guard with a *shape* assert —
  `assert len(result.rows) > 0`, `assert model.n_constraints > 0` — not a
  status check.
- **Default-argument capture.** `def f(..., n=GLOBAL)` freezes the value at
  definition time. Sweeping `GLOBAL` afterwards changes nothing, silently, and the
  reader concludes the sweep did nothing interesting.
- **Stale embedded source.** Code pasted from a module into a notebook (or into a
  slide, or a doc) is a snapshot. It does not update. See Part 4.
- **Chained assignment / aliasing.** `a = b = c` binds a name to the wrong object.
  Caught by execution, never by review.
- **Cell-order dependence.** A cell that only works because of what an earlier
  *manual* run left in the kernel. A fresh-kernel top-to-bottom execution is the
  only real test; a static scope check catches most of it cheaply.
- **Comparing two different measurements.** A value taken from an early-terminated
  run, differenced against one computed exactly, produced an impossible negative
  statistic. If two numbers are compared, one function should produce both.
- **Comparing two things that were not asked the same question.** A "cost of X"
  came out negative because one configuration was required to satisfy a constraint
  the other was free to ignore. Match the comparison before interpreting the
  difference.

### Assert the theory in code

Domain invariants belong in assertions, not in prose. When they fail, the plumbing
is wrong — not the science. Examples of the shape: a chain of bounds that must stay
ordered, an approximation that must not beat the exact answer it approximates, a
quantity that must be conserved, a value that cannot go negative, a wrapper
reproducing a hand-built result.

### Non-reproducible prose

If prose names a specific outcome — *"it charges in hours 11–16"*, *"the second
iteration is where it drops"* — **verify the answer is unique.** Wherever several
answers tie, different libraries, versions, orderings or seeds hand students
different results and your text is wrong for some of them.

Two fixes, in order of preference: add a small real effect that breaks the tie (a
decay, a cost, a tolerance) — then say so, because ties are a real thing and
detecting one is worth teaching; or, where the degeneracy is *structural* and no
perturbation fixes it, assert only the invariant quantities and **teach the
degeneracy** instead of asserting the path.

### Every number in the prose comes from a run

Not from memory, not from an earlier draft. This decays silently and continuously:
a parameter changes, every downstream figure in the narration is now wrong, and
nothing complains. Automate it — a checker that extracts numbers from markdown and
compares them against the executed outputs — because a human will not re-check
forty figures after every edit.

---

## Part 7 — Auditing an existing set of notebooks

Measure, don't estimate. These are the checks that pay, roughly in order:

| Check | How | What "good" looks like |
|---|---|---|
| Does it run? | Execute every notebook in a fresh kernel, `allow_errors=True` | 0 errors; record the wall time |
| Prose vs output | Every number in markdown against the executed outputs | 0 unexplained mismatches |
| Duplication and drift | Hash each function body, group by name across files | 0 names with >1 version |
| The inversion | Position of the first function >8 lines, as % through | no big function before its narration |
| Orphan cells | Code cells with no markdown immediately above | 0 |
| Cell length | Longest cell, in lines | readable without scrolling |
| Predict prompts | Count per notebook | ≥1, before the first result |
| Reproduction asserts | Count per notebook | ≥1 (the Part 4 assertion) |
| Pinning | Unpinned installs; interpreter version vs what ran | 0 unpinned; metadata matches reality |
| Seeds | Set and printed wherever anything is stochastic | all |

Two of these are worth keeping permanently as CI tests rather than running once:
**the prose-number check** and **the duplication check**. They are the two failure
modes that recur, and both are invisible until someone looks.

---

## Part 8 — Anti-patterns

Flag these on sight:

- A notebook that reimplements what a module does, **with nothing checking they
  agree**. (The notebook reimplementing it is fine — see Part 4. The missing check
  is the defect.)
- Parameters buried in function bodies instead of config *(in `src/`)*.
- Instance data typed into both the notebook and the package, with nothing
  comparing the two copies.
- A single `output/` folder mixing intermediates with final results.
- Committing large or regenerable data "just in case."
- `sys.path.insert` hacks instead of a proper installable package.
- Unpinned dependencies in a repo tied to published results or handed to students.
- Deferring the README and tests to "after the paper is done."
- A dashboard that recomputes on every page load.
- Version control by filename: `script_v2.py`, `module.py.bak`, `final_FINAL/`.
- Library-grade rigor for a one-off analysis (over-engineering) or analysis-grade
  looseness for a shared library (under-engineering).
- A helper function above the narration of the same material *(in `notebooks/`)*.
- A teaching notebook whose numbers cannot be checked because it shipped stripped
  of outputs.

---

## Part 9 — Working style

- Explain trade-offs rather than presenting one option as the only choice. The
  *why* matters more than the scaffolding.
- Say when a convention here doesn't fit the actual work. These are defaults, not
  laws — but say it, rather than quietly ignoring one.
- **Verify by running.** Don't say code works — execute it, run the tests, show the
  output. Part 6 exists because this is not optional.
- Prefer the boring, standard tool over the clever one. Research and teaching code
  both outlive their author's memory of them.
- Measure before planning a fix. An audit that reports counts is actionable; one
  that reports impressions is an opinion.

---

## Part 10 — Two things to copy

### The pre-ship checklist

Before a teaching notebook goes to students:

- [ ] Zero function definitions above the "streamlined version" heading.
- [ ] Every code cell in the teaching section has markdown above it.
- [ ] Longest teaching cell is short enough to read without scrolling.
- [ ] At least one "predict before you run" prompt, before the first result.
- [ ] Any wrapper appears *after* the narration, with a reproduction check.
- [ ] The Part 4 agreement assertion is present and passes.
- [ ] Instance tables loaded from one shared file; knobs written out inline.
- [ ] The package takes the data as an argument, so a reader's edit keeps the
      assertion green.
- [ ] Runs top to bottom in a fresh kernel, on a clean machine, with no local files.
- [ ] Shipped executed — outputs and figures committed.
- [ ] Every specific number in the prose came from that run, not from memory.
- [ ] Deliberate blanks fail with a message, not a traceback.
- [ ] Seeds set and printed wherever anything is stochastic.
- [ ] Dependencies pinned with upper bounds; kernel metadata matches what ran.

### The prompt block

Paste this into a chat when asking an assistant to write or revise teaching code.

> **Teaching-code style — follow this exactly.**
>
> Write the top of the notebook step by step, not abstracted. One idea per cell,
> with a markdown cell above each code cell explaining what it does and why.
> **No function definitions and no loops in the teaching section** unless the loop
> is genuinely mechanical repetition of an identical step. Print something after
> each step so the reader can see it worked.
>
> Where a single argument or line carries the concept, say so in the markdown
> explicitly. Before any solve, fit or simulation, add a one-line prompt asking the
> reader to predict the result first.
>
> If the notebook needs the same construction several times, you may add a
> streamlined version **at the bottom**, under a heading that says so, with one
> sentence explaining why it is being wrapped now.
>
> Do not put a helper function before the narrated walkthrough of the same
> material. If one already exists there, move it to the bottom — or, if the project
> has a package, move it out of the notebook into the package.
>
> **If a package holds the same model, the notebook's last cell must import it,
> run the same case, and assert the two agree to within 1e-9.** Deliberate
> duplication is fine; deliberate duplication with nothing comparing the copies is
> how a fix gets applied in three places out of four.
>
> **Split the numbers into tables and knobs.** A knob is a scalar carrying a
> concept — a rate, a count, a limit, anything the narration explains or invites
> the reader to change. Knobs stay written out in the cell, and the notebook hands
> them to the package explicitly, so the assertion already covers them. A table is
> instance data — many entries, indexed by the model's sets, named nowhere in the
> prose. Tables live in one file both the notebook and the package read, because
> if each types its own copy a failed assertion cannot distinguish a typo in the
> data from a bug in a constraint. Load the table, render it, and then print the
> dictionary form so the key — `gen`, `(stage, region)`, whatever the model looks
> values up by — is explicit rather than implied by punctuation. Have the package
> take the data as an argument and never re-read the file, so a reader's edit
> flows into both the hand-built model and the check and the assertion stays
> green. Then add a commented-out worked example of overriding one entry.
>
> Every specific number in the prose must come from actually running the code, not
> from memory. If the prose names a particular outcome, check the answer is unique
> — where several answers tie, different libraries or seeds produce different results
> and the text is wrong for some readers. Break the tie with a real effect rather
> than vaguer prose; where the degeneracy is structural, assert the invariants and
> teach the degeneracy.
>
> The notebook must run top to bottom on a clean machine with no local data files:
> fall back to generated data with a loud message saying the fallback is not an
> acceptable submission. Where the reader must make a choice, raise an explanatory
> error rather than letting it crash with a `NameError`.

---

## The one-line versions

> **Engineering:** if a clean clone can't reproduce it with one command, it's broken.
>
> **Teaching:** abstraction is the reward for understanding, not the route to it.
> Put it at the bottom.
>
> **The boundary:** keep both copies on purpose — and make one assertion compare them.

---

# Part 11 — This project specifically

Everything above is portable. This section is not.

**Archetype: A + T.** `src/lithium/` is Parts 1–2 territory; `notebooks/` is
Part 3 territory; Part 4 is the boundary and the reason this project has two
folders holding the same model. See `PLAN.md` for the migration and
`AUDIT_AND_REMEDIATION_PLAN.md` for the measured findings that motivated it.

`src/lithium/` is a **model-builder library, not a data pipeline** — parameters in
as arguments, a Gurobi model out. Measured 2026-09-02: all fourteen notebooks
contain **zero** lines of file I/O. So `data/raw/` holds the instance tables of
Part 4's *Tables versus knobs* and nothing else; there is no `interim`/`processed`
flow and no `clean.py` stage, and adding empty ones because the archetype-A
template has them would be scaffolding with nothing to hold.

**Part 0 (`Part0_Concepts_Guide.ipynb`) is the template.** 23 sections, each a
markdown explanation plus one short runnable demo, every code cell narrated, and
its five small functions each *are* the lesson. When converting any other
notebook, the target shape is Part 0's.

## Non-negotiables here

- **No credential is ever committed, in any form.** `gurobi.lic` is gitignored as
  both `gurobi.lic` and `*.lic`; verify with `git check-ignore -v gurobi.lic`
  before any `git add` here. **That path rule is necessary and was not
  sufficient.** A live WLS key sat in a code cell of `Part4c_exact_MIQP.ipynb`
  and in a markdown example in Parts 1, 2 and 3, and entered the repository in
  its first commit — found 2026-09-03 while measuring which notebooks needed a
  licence, not by any guard. A path-based rule cannot see a secret pasted into a
  notebook. `tools/credscan.py` scans **content** and runs in CI; run it before
  any commit that touches a notebook. Licences are read from
  `GRB_WLSACCESSID` / `GRB_WLSSECRET` / `GRB_LICENSEID` or a Colab secret, never
  from a literal.
- **The free `pip` Gurobi licence is the deployment constraint:** ~2,000 variables
  for LP/MILP, but only ~150 for QP/MIQP — found by probe, not documentation. The
  instructional notebooks fit. `Part4c_exact_MIQP` does not, and ships
  `SMALL = True` by default with a printed explanation.
- **Notebooks ship executed**, outputs and figures committed. All fourteen are
  currently saved stripped, so a reader without a licence sees nothing and cannot
  check a single number. Fixing this is Phase 2 of `PLAN.md`.
- **Part 2 is 310 s of the 584 s full-series runtime.** It needs a `QUICK` switch
  for classroom use, with the full setting used for the committed run.
- **Knobs stay in the notebook; tables move to `data/raw/`.** This is Part 4's
  *Tables versus knobs*, and it is the rule most likely to be applied in the wrong
  direction here — in *either* direction. Concretely, for the Part 4 family:
  - **Knobs — stay written out inline.** `DR`, `LIFE`, `CAP_MIN/MAX`, `BLOCKS`,
    `CHOKE`, `P_ANCHOR`, `NBP_REV`, `LR_CAPEX`, `LR_OPEX`, `N_TIERS`,
    `CAPEX_FLOOR`, `OPEX_FLOOR`, `LAG_YEARS`, `NBP`, `PRICE_FIXED`, `PEN_SHORT`,
    `PEN_DISPOSE`, `TRANSPORT`. Do **not** move these to `config.yaml`. Cell 31
    of Part 4c tells the reader to set `NBP_REV = 3`; that exercise requires the
    value to be visible and assignable in the notebook.
  - **Tables — load from `data/raw/`.** `FIXED`, `UNIT`, `OPEX`, `LEGACY_CAP`,
    `LEGACY_RET` (6 rows keyed by stage x region); `ETA_CEIL`, `ETA_BASE`,
    `ALPHA`, `BETA`, `DELTA_BAR` (3 rows keyed by stage); demand base/growth and
    `EXPERIENCE0` (2 rows keyed by region).
  - **Derived structure stays as code in the notebook.** `OMEGA`, `CRF`, `MU`,
    `ETA`, `ACTIVE`, `VIN`, `BUILD`, `QBP`, `CBP` are computed, and computing
    them is the lesson. They are neither knobs nor tables.
  - The CSVs ship **inside the package** (`src/lithium/data/`) so that
    `pip install git+https://...` carries them into Colab, with `data/raw/` at the
    repo root as the editable copy.
  - `lithium` functions take the instance **as an argument** and never read the
    CSV during a notebook run, so a reader's edit flows into both the hand-built
    model and the agreement assertion.

## Known open defects

- Part 0 §23's Best Response Intersection trace names an iteration path that is
  not reproducible — reordering arcs or renaming nodes changes it, and twelve
  perturbations failed to stabilise it because the degeneracy is structural. The
  converged answer is stable. Apply Part 6's second fix: assert the invariants,
  teach the degeneracy.
- Seeds are set only in Parts 2b and 2c.
