"""The notebooks are build outputs; this proves regenerating reproduces them.

the Code Standard, Part 4, *Corollary: generated artifacts*: if a notebook is generated
by a script, the script is the source of truth and the artifact is a build
output — and something must check that regenerating reproduces what shipped. "A
build script and its output drift exactly as fast as two pasted copies do, and
for the same reason: nobody is comparing them."

This is that comparison. It checks **sources only**, cell by cell, because a
shipped notebook also carries executed outputs that a regeneration cannot know.
`tests/test_notebooks.py` is what checks the outputs are there and that running
them passes the agreement assertion.

If this fails, someone hand-edited a notebook. The fix is to move the edit into
`tools/build_notebooks/`, regenerate, re-execute, and commit executed — because
the next `build.py --all` would otherwise throw the edit away.
"""
import sys
from pathlib import Path

import nbformat
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from build_notebooks import build                            # noqa: E402

TAGS = sorted(build.BUILDERS)


@pytest.mark.parametrize("tag", TAGS)
def test_regeneration_reproduces_the_shipped_sources(tag):
    mod = build.load(tag)
    path = ROOT / "notebooks" / mod.NOTEBOOK
    assert path.exists(), f"{mod.NOTEBOOK} has not been built yet"

    shipped = nbformat.read(path, as_version=4)
    rebuilt = build.notebook(tag)

    assert len(shipped.cells) == len(rebuilt.cells), (
        f"{mod.NOTEBOOK}: shipped has {len(shipped.cells)} cells, the builder "
        f"produces {len(rebuilt.cells)}"
    )
    for i, (a, b) in enumerate(zip(shipped.cells, rebuilt.cells)):
        assert a.cell_type == b.cell_type, f"cell {i}: type differs"
        if "".join(a.source) != "".join(b.source):
            pytest.fail(
                f"{mod.NOTEBOOK} cell {i} ({a.cell_type}) differs from what the "
                f"builder produces.\n--- shipped ---\n"
                f"{''.join(a.source)[:600]}\n--- rebuilt ---\n"
                f"{''.join(b.source)[:600]}"
            )


@pytest.mark.parametrize("tag", TAGS)
def test_shipped_kernel_metadata_matches_the_builder(tag):
    """Rule 3: record the interpreter version, and make it match what ran."""
    mod = build.load(tag)
    shipped = nbformat.read(ROOT / "notebooks" / mod.NOTEBOOK, as_version=4)
    assert shipped.metadata["language_info"]["version"] == \
        build.KERNEL["language_info"]["version"]
    assert shipped.metadata["kernelspec"]["name"] == \
        build.KERNEL["kernelspec"]["name"]


@pytest.mark.parametrize("tag", TAGS)
def test_builder_audit_passes(tag):
    """The Part 10 pre-ship checklist, as measurements rather than impressions."""
    cells = build.load(tag).cells()
    row = build.audit(tag, cells)
    assert row["defs_in_teaching"] == 0, (
        "a function definition sits in the teaching section without a "
        "'CARRIED OVER' marker saying which notebook narrated it"
    )
    assert row["orphan_code_cells"] == 0, "a code cell has no markdown above it"
    assert row["predict_prompts"] >= 1, "no predict-before-you-run prompt"
    assert row["agreement_assert"] or row["agreement_exempt"], (
        "no agreement assertion, and no NO_AGREEMENT_ASSERTION reason declared "
        "in the builder. A teaching notebook that duplicates the package needs "
        "the assertion; one that duplicates nothing must say so."
    )
    assert row["blank_markers"] == 0, "these are worked examples, not exercises"
    assert row["knob_shadowing"] == 0, (
        "a later cell rebinds a name the shared structure cell defines. Part 2's "
        "rho sweep used `r` as a loop variable, shadowing the discount rate, and "
        "the notebook failed 46 cells later inside the package. Run "
        "`python tools/build_notebooks/build.py --all` to see which name"
    )
    assert row["longest_teaching_cell"] <= 40, (
        f"longest teaching cell is {row['longest_teaching_cell']} lines; split it"
    )
