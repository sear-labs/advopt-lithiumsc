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

### How copies of this document work

This file is **dropped into project roots as `CLAUDE.md`** and read automatically. Those copies are
the portable half; anything true of one project only goes **below** them, under a heading
`# Part 11 — This project specifically`.

**Syncs run one way: source → copy.** An improvement made in a copy survives exactly until the next
sync overwrites it, and nothing reports the loss. Amendments are approved and committed at the
source first.

**Stamp the copy with the source commit.** Part 11 opens with the SHA it was taken from:

    Parts 0-10 are a copy of sear-labs/code-standard at 9f6358c (2026-09-04).

Without it a copy can only assert that it is current, which is an assertion that rots silently —
true when written, and false the moment the source moves, with nothing in the file to say which.
With it, `git show <sha>:CLAUDE.md` reconstructs exactly what was copied and the drift is one diff
away. **This is the whole reason a copy in version control is acceptable and a copy inside a zip is
not** (Part 8): both go stale, and only one can be asked whether it has.

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

### When the sort key and the readable label disagree, carry both

A name has two jobs: sort correctly for a machine, and read correctly for a person. Words rarely do
both. `Spring`, `Summer`, `Fall` sort alphabetically into `Fall, Spring, Summer` — which is not the
order they happen in, so every listing of a multi-term course is wrong and nothing says so.

**Number first for the machine, word second for the person:**

    2026_01_Spring_IE_5301_001
    2026_06_Summer_IE_5301_001
    2026_08_Fall_IE_5301_001

Use the **month the term starts**, not an ordinal 01/02/03. The month is real information: it
survives a term shifting, it matches how the registrar and Canvas already think, and it needs no
key to interpret. An ordinal is an index into a list somebody has to know.

Neither half is sufficient alone. `2026_01` does not read; `2026_Spring` does not sort.

**Research files take the number alone**, because there is no term and no name anyone uses:

    run045-rev01-leo          zero-padded sequence, where order is the point
    2026-09-03-slug           ISO date, where chronology is the point

Both sort natively and need no label. Adding a season to research output invents a discriminator
that does not exist.

**The general rule: use the discriminator that actually distinguishes, and make it sort.** For
course material that is the term. For runs it is the sequence. For records it is the date.

### Repository names lead with what the searcher already knows

    research     subject-method       sear-labs/lithium-optsc
    teaching     method-application   sear-labs/advopt-lithiumsc
    published    add journal + year   sear-labs/lithium-optsc-energies-2024
    websites     website-<name>       personal account
    grad school  gradschool-<name>    personal account

Lab-era research goes under the organization; personal work under the personal account.

**The first two are deliberately inverted, and the inversion is the rule — not the examples.** A
researcher searches by subject; a student searches by course. Each form leads with the half its
audience already has in mind, which is why `advopt-lithiumsc` reads backwards beside
`lithium-optsc` and is nonetheless correct: the student arriving has a course, not a commodity.

**Anyone who “fixes” the teaching form to match the research one has deleted the reason both
exist.** That is the failure this paragraph is here to prevent, and it is why the reason is written
down beside the forms rather than left to be inferred from a pair of examples.

**American spelling** — `optimization`, not `optimisation`. Lowercase, hyphen-separated, numbers
zero-padded. Not a style preference: see the cost below. A name freezes into every badge URL and
every install line in the repo, and those are not corrected by a rename.

### Published work carries the journal and year

Research repos are named `subject-method` — `lithium-optsc`, `covid-optsc`. **When the work
accompanies a published paper, append the journal abbreviation and year:**

    lithium-optsc-energies-2024
    covid-optsc-ffutr-2021

The suffix does two jobs. It signals at a glance that the repo is a **frozen artifact behind a
publication** rather than active work, and it says **which** publication — which matters when one
project yields several papers.

**Use the DOI stem as the abbreviation** where one exists (`ffutr` for Frontiers in Future
Transportation). It is already the canonical short form and needs no lookup, so two people cannot
invent different abbreviations for the same journal.

**The suffix is only for published work.** Unpublished research keeps plain `subject-method`. A repo
with no paper takes no journal — **inventing one would assert a publication that does not exist.**
`houston-covid-gis` carries no suffix because the map was never written up, even though it sits
under the same award as `covid-optsc-ffutr-2021`.

This **composes with** the table above rather than replacing it — the suffix is appended to a name
already formed by those rules, and a teaching repo behind a paper takes it too.

#### Cost of getting it wrong

A repo name freezes **every hosted-notebook badge URL** and **every `pip install git+https://…`
line** in the repo. A rename redirects the repo URL; it does not redirect anything already copied
out of it.

**Count both substitutions before renaming, and count them again immediately before running the
replace.** There are two, and only one looks like a placeholder — `USERNAME` announces itself, while
the hardcoded repo name sits beside it reading like a real name. Measured in one repo on 2026-09-03:
62 and 64 occurrences across git-tracked files, against 78 and 80 including compiled bytecode, which
regenerates and must not be edited. **A replace run against the wrong figure leaves survivors, and
every survivor is a badge pointing at a repo that does not exist** — which presents as a hosting
fault, so the search starts in the wrong place.

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
| **Nothing that runs** — proposals, deliverables, documents | **not a repo** — see Part 2b |

**Answer the last row first.** Most project folders are not repos and should not be given an
archetype at all; **Part 2b** covers their shape. Reaching for one because the table offers seven
is how a proposal folder of Word and Excel acquires a `src/` directory and a test suite nobody
runs.

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

## Part 2b — Folders that are not repos

Most project folders should never be repos. Proposal folders are Word, PDF and Excel; git stores
binaries badly and they bloat history permanently. They still need a shape.

### The organising rule

**Separate what ACCUMULATES from what PERSISTS.**

    00-ADMIN/           the folder's own metadata. Zero-prefixed so it sorts first.
    code/               PERSISTS  - scripts and models, subfoldered by variant
    reference/          PERSISTS  - source docs, specs, literature, mappings
    automation/         PERSISTS  - the things that run the above
    verification/       PERSISTS  - checks, and evidence they passed
    2025/  2026/        ACCUMULATES - runs, outputs and deliverables of that year
    design-history/     ACCUMULATES - superseded work, archived by year, not deleted

The test for any new item: **would you look for this by "when", or by "what"?** A 2025 simulation
run is found by when. The script that produced it is found by what. They go in different places even
though they were created the same afternoon.

### State where new work goes, or people will guess

A year folder and a function folder sitting at the same level is ambiguous the moment there is new
code: does it go in `code/` or in `2026/`? **Answer it in the folder's own README rather than leaving
it to instinct**, because two people will resolve it differently and both will be reasonable.

The Green Building answer, which generalises: **code lives in `code/`, with the year in the
subfolder name** — `code/ret-2025/`, `code/treed-opt/`. The year folders hold outputs, never sources.

### `00-ADMIN/` earns the zero

It sorts above everything and holds what governs the folder: the README, the naming standard, the
inventory, the decisions log. Somebody arriving cold reads that first because it is first.

### When a folder becomes a repo

The line is the same granularity rule as Part 2: **a repo is a unit that is versioned, released and
cloned together.** Ask whether anyone would ever want this *without the rest of it*.

    Has code that runs, and someone might clone it          -> repo, archetype A
    Finished outputs - papers, posters, reports             -> stays a folder; deposit to Zenodo
    Active working files                                    -> stays a folder
    Binaries over 100 MB                                    -> can never be a repo; GitHub rejects them

A folder can contain a repo — `code/treed-opt/` may be its own repo inside a working folder that is
not. That is normal, and better than promoting the whole tree to satisfy one subdirectory.

---

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

### Leave room — the companion rule, for the prose around the code

*Everything above is about the code. This is about the writing around it, and it
matters as much.*

> **A teaching notebook sets up a discussion. It does not hold one.**

If the material states its own conclusions, the class period has been spent before
it begins. The student arrives having been told what to think about the result, and
there is nothing left to say about it out loud. So: build to the question, pose it,
and stop.

**Do not write these:**

- *"This is the part that is actually graded."* The rubric says what is graded.
- *"This is what sinks first-year solar business cases."* That is the finding. Ask
  instead which assumption moved the answer most.
- *"That is not a bug — it is the most useful result here."* This tells the reader
  how to feel about a number before they have thought about it. Ask what would have
  to be true for it to happen.
- *"Ten percent means your day selection is wrong."* Ask whether the error is in the
  selection or the data, and how they could tell.
- *"What you should take from this,"* followed by bolded conclusions. That is a
  lecture wearing a list.

**Distinguish a derivation from a punchline.** Showing *how* an $80 price arises from
two $40 generators is content, and belongs in the notebook. Announcing that it is
"the single most counter-intuitive number in the course" is a line the instructor
should get to deliver.

**Keep the example minimal.** The reader should think *"oh, it looks like this"* —
not read every branch of possible logic, every failure mode, every this-goes-wrong
warning. Show the shape once. One rewritten example went from 55 cells and 3,558
words to 17 and 514, and taught more.

**Finish what you ask for.** If the assignment asks for a diagram, the worked example
draws the diagram. An example that stops short of the deliverable is where the student
most needed to see the shape.

**Match the reader's scale.** Students model the thing in front of them — a car, a
house, one plant. An example at national scale is the wrong thing to imitate, and it
buries the unit conversions that are half the lesson.

**Use placeholders, not answers.** Give a starting bracket and ask the student to
substitute their own values and cite them. The range is the teaching; the citation is
the grading.

**This rule and the "predict before you run" prompt are the same instinct.** Both
refuse to hand over the answer before the reader has formed one. A prediction prompt
does it for a number; leave room does it for the interpretation.

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

### Every published repo carries a licence AND a citation

A licence sets the terms of reuse. It does **not** get you cited — MIT requires only that the
copyright notice travel with the code, and no permissive licence compels a citation. These are two
mechanisms and a repo meant to be cited needs both.

**LICENSE** — MIT unless the repo has commercial potential, in which case weigh Apache-2.0 for its
patent grant. UTA encourages open-access models and leaves the choice to the author.

**CITATION.cff** in the repo root. GitHub renders a "Cite this repository" button from it, which is
the whole point: people cite what is easy to cite, and friction is what stops them, not ethics.

**A "How to cite" section** at the top of the README, with the BibTeX ready to paste.

#### The DOI does not need remembering

Zenodo issues **two** DOIs on a connected repo:

- a **version DOI**, new for every release
- a **concept DOI**, which always resolves to the latest version and **never changes**

Put the **concept DOI** in `CITATION.cff`. It is correct for the life of the repo, so this is a
one-time edit and not a per-release chore. The order is forced — you cannot have a DOI before the
first release:

1. Add `CITATION.cff` with no `doi:` field
2. Connect the repo in Zenodo, tag a release
3. Zenodo mints both DOIs
4. Add the concept DOI to `CITATION.cff` and commit
5. Never touch it again

For a paper repo, cross-reference both ways: the paper's DOI in `CITATION.cff`, the code's DOI in
the paper's data-availability statement.

---

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
- **A shared document duplicated into a zip, a deck or a PDF.** A copy there cannot be
  diffed, gitignored or checked by CI, so it does not merely go stale — nothing can tell
  you that it has. Ship a pointer to the source instead of a copy. (A `CLAUDE.md` in a repo
  root is fine: it is plain text in version control, so drift is visible.)
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

**Where the portable half comes from.**

    Parts 0-10 are a copy of sear-labs/code-standard at 204d2ab (2026-09-04).

That stamp is required by the source's own Part 0, and this project is why the
requirement exists. The line it replaced said the copy was "byte-identical" and
named no version: true the day it was written, false three commits later, and
nothing in the file could tell the two apart. A stamped copy can be *asked*
whether it has drifted — `git show 204d2ab:CLAUDE.md` reconstructs exactly what
was taken, and `tests/test_standard_sync.py` runs that comparison here.

**Syncs run one way: source → here.** An improvement to the portable half made
in this file survives until the next sync overwrites it, and nothing reports the
loss; the test below fails instead, which is the point of it. Amendments are
approved and committed at the source first. Part 11 is this project's own and
exists nowhere else.

**Archetype: A + T.** `src/lithium/` is Parts 1–2 territory; `notebooks/` is
Part 3 territory; Part 4 is the boundary and the reason this project has two
folders holding the same model. See `docs/design-rationale.md` for why, and
`docs/audit-2026-09-02.md` for the measured findings that motivated it.

`src/lithium/` is a **model-builder library, not a data pipeline** — parameters in
as arguments, a Gurobi model out. Measured 2026-09-02, before the migration: the
notebooks contained **zero** lines of file I/O, every number being a literal. They
now read the instance tables and nothing else. So `data/raw/` holds the tables of
Part 4's *Tables versus knobs* and nothing else; there is no `interim`/`processed`
flow and no `clean.py` stage, and adding empty ones because the archetype-A
template has them would be scaffolding with nothing to hold.

**Part 0 (`notebooks/00_concepts.ipynb`) is the template.** 23 sections, each a
markdown explanation plus one short runnable demo, every code cell narrated, and
its seven small functions each *are* the lesson. When converting any other
notebook, the target shape is Part 0's.

**The migration is complete (2026-09-03).** Fifteen notebooks in `notebooks/`,
each generated by a builder in `tools/build_notebooks/` and shipped executed;
`scripts/run_all.py` reproduces every result in twelve sections. The
pre-migration originals have been deleted — `git log` has them. Six instances
now live in `data/raw/`, and they are genuinely different models rather than
variants of one: the Part 4 chain, the six-site network (Parts 1–2), the
two-stage capacity network (2b–2c), the network core (3–3b), the interdiction
flow network (4f) and the integrated core with its recycling loop (5).

## Non-negotiables here

- **No credential is ever committed, in any form.** `gurobi.lic` is gitignored as
  both `gurobi.lic` and `*.lic`; verify with `git check-ignore -v gurobi.lic`
  before any `git add` here. **That path rule is necessary and was not
  sufficient.** A live WLS key sat in a code cell of `Part4c_exact_MIQP.ipynb`
  (now `notebooks/04c_exact_miqp.ipynb`) and in a markdown example in Parts 1, 2
  and 3, and entered the repository in its first commit — found 2026-09-03 while
  measuring which notebooks needed a licence, not by any guard. The key was
  scrubbed from all 29 commits on 2026-09-03 and the credential rotated;
  **rotation was the remedy, the scrub was defence in depth**, and neither
  removes it from OneDrive's own version history. A path-based rule cannot see a secret pasted into a
  notebook. `tools/credscan.py` scans **content** and runs in CI; run it before
  any commit that touches a notebook. Licences are read from
  `GRB_WLSACCESSID` / `GRB_WLSSECRET` / `GRB_LICENSEID` or a Colab secret, never
  from a literal.
- **The free `pip` Gurobi licence is the deployment constraint:** ~2,000 variables
  for LP/MILP, but only ~150 for QP/MIQP — found by probe, not documentation. The
  instructional notebooks fit. `notebooks/04c_exact_miqp.ipynb` does not, and
  ships `SMALL = True` by default with a printed explanation.
- **Notebooks ship executed**, outputs and figures committed. All fifteen do,
  and `tests/test_notebooks.py` fails any that does not — a reader without a
  licence can check every number in the prose.
- **A switch that trims runtime may trim cost and never the lesson.**
  `02_stochastic` has `QUICK` and `04c_exact_miqp` has `SMALL`, both on by
  default and both printing what they changed. `QUICK`'s first version was wrong
  in the instructive way: it dropped one rho from a sweep, which looked harmless
  and removed the only evidence that the good setting is *interior*. The section's
  own assertion caught it.
- **Knobs stay in the notebook; tables move to `data/raw/`.** This is Part 4's
  *Tables versus knobs*, and it is the rule most likely to be applied in the wrong
  direction here — in *either* direction. It has since been applied to all six
  instances; the Part 4 family below is the worked example, and the others follow
  the same split. Concretely, for the Part 4 family:
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

## Closed defects

- **Part 0 §23's non-reproducible trace — fixed 2026-09-03**, and the defect was
  narrower than this note claimed. Measured over all 120 orderings of the five
  arcs: the final value, the fortification set *and* the iteration count are
  identical every time; only the intermediate trace takes one of **two** forms,
  and the hardcoded sentence about iteration 2 was true in one and false in the
  other. Now asserts the three invariants that hold in every ordering (theta
  never rises, the incumbent never falls, incumbent ≤ theta) and teaches the
  degeneracy — Part 6's second fix.
- **Seeds — closed.** Only `02b` and `02c` contain randomness at all, and both
  set and print a seed. Everything else is deterministic by construction, which
  is stated where a reader might expect a seed and not find one: `02_stochastic`
  says outright that nothing in it is random, and `04f`'s round-robin is
  deliberately not a random sample.

## Known open defects
- **`tools/prosecheck.py` barely checks percentages.** Its tolerance has a flat
  0.06 absolute floor applied to the `val / 100` candidate too, where 0.06 means
  six percentage points, so a prose percentage matches almost any printed
  decimal in 0.6-0.8. Verified 2026-09-03 by planting a stale `+73.5%`, which
  passed. Tightening it raises the repo-wide flag count from 32 to 92 (scaled
  floor) or 117 (precision-aware), and most of that increase is *derived*
  percentages -- prose quoting a ratio of two printed numbers that is never
  itself printed. The real fix is to give the checker derived candidates
  (pairwise ratios and percentage changes) and then adjudicate the remainder.
  Until that lands, a clean prosecheck means the absolute figures are verified
  and the percentages are not.

## Exemptions, and why each one costs something

Three rules in this repo can be waived, and each waiver is deliberately
expensive to take — a stated reason, and a column in
`tools/build_notebooks/build.py --check` so it cannot be taken quietly.

- **`CARRIED OVER`** — a cell holding material another notebook narrates. Exempt
  from the no-functions and cell-length rules, counted in `carried_over`.
- **`THE FUNCTION IS THE LESSON: <reason>`** — a function that *is* the teaching,
  such as an iterative algorithm or machinery whose sameness across call sites is
  the point. The reason is required and must be ≥20 characters; counted in
  `fn_is_lesson`.
- **`NO_AGREEMENT_ASSERTION = "<reason>"`** in a builder — for a notebook that
  duplicates nothing, so has no second copy to disagree with. Reason required and
  must be ≥60 characters; counted in `agreement_exempt`. Exactly two notebooks
  take it: `00_concepts` (hand-solved illustrations, not implementations) and
  `00_start_here` (calls the package and holds no model). The artifact test also
  requires the notebook to state the exemption in prose a reader will meet.

`knob_shadowing` is not an exemption but a hard gate: a later cell must not
rebind a name the shared structure cell defines. It exists because
`02_stochastic`'s rho sweep once used `r` as a loop variable, shadowing the
discount rate, and failed 46 cells later inside the package.
