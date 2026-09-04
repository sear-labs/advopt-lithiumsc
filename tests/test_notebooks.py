"""Execute every notebook in `notebooks/` end to end.

This is what makes the teaching notebooks safe to write. A notebook that
duplicates the package's logic for pedagogy is fine **provided something proves
the two still agree** — the agreement assertion in the last cell of each notebook
does that, and this test is what runs it.

It also catches the failure modes that reading never finds: cell-order
dependence, a silently empty model, a stale number in a print. the Code Standard, Part 6 lists the rest.
"""
from pathlib import Path

import nbformat
import pytest
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parents[1]

# kept in step with tools/build_notebooks/build.py
LESSON_MARK = "THE FUNCTION IS THE LESSON"
# a notebook with nothing to compare against must say so in its own prose
EXEMPTION_PHRASE = "There is no agreement assertion at the end of this notebook"
NOTEBOOKS = sorted((ROOT / "notebooks").glob("*.ipynb"))


@pytest.mark.parametrize("path", NOTEBOOKS, ids=lambda p: p.name)
def test_notebook_executes(path):
    nb = nbformat.read(path, as_version=4)
    client = NotebookClient(nb, timeout=1800, kernel_name="python3",
                            resources={"metadata": {"path": str(path.parent)}})
    client.execute()   # any raised exception, the agreement assert included, fails here


@pytest.mark.parametrize("path", NOTEBOOKS, ids=lambda p: p.name)
def test_notebook_has_an_agreement_assertion(path):
    """A teaching notebook without this cell is not finished (the Code Standard, Part 4)."""
    nb = nbformat.read(path, as_version=4)
    sources = ["".join(c.source) for c in nb.cells if c.cell_type == "code"]
    imports_package = any("lithium" in s for s in sources)
    asserts_agreement = any("disagree" in s and "assert" in s for s in sources)
    # A notebook may be exempt, but it has to SAY so where a reader will see it,
    # not only in its builder. Part 0 is the documented case: it duplicates
    # nothing in the package, so it has nothing to disagree with.
    md = "\n".join("".join(c.source) for c in nb.cells if c.cell_type == "markdown")
    exempt = EXEMPTION_PHRASE in md
    if exempt:
        assert len(md.split(EXEMPTION_PHRASE, 1)[1].strip()) > 80, (
            f"{path.name} claims the agreement exemption but does not explain it"
        )
        return
    assert imports_package, f"{path.name} never imports the package to compare against"
    assert asserts_agreement, f"{path.name} has no agreement assertion"


@pytest.mark.parametrize("path", NOTEBOOKS, ids=lambda p: p.name)
def test_notebook_ships_executed(path):
    """Committed stripped, a reader without a licence can check nothing."""
    nb = nbformat.read(path, as_version=4)
    code = [c for c in nb.cells if c.cell_type == "code"]
    with_output = [c for c in code if c.get("outputs")]
    assert len(with_output) >= 0.8 * len(code), (
        f"{path.name}: only {len(with_output)}/{len(code)} code cells carry output; "
        f"re-run it and commit the outputs"
    )


@pytest.mark.parametrize("path", NOTEBOOKS, ids=lambda p: p.name)
def test_no_function_definitions_before_the_narration(path):
    """the Code Standard, Part 3, the inversion check.

    The first `def` longer than 8 lines must not sit in the first half of the
    notebook — that is the shape where a student meets the abstraction before the
    thing it abstracts.

    A cell marked `THE FUNCTION IS THE LESSON` is also exempt, and that marker
    must state a reason. It covers the case Part 0 already blesses: an iterative
    algorithm, or machinery whose sameness across call sites is the point, where
    the narration sits directly above the function rather than after it.

    A cell marked `CARRIED OVER` is exempt: it holds material that *another*
    notebook narrates, so the abstraction is not above the narration of the same
    material. 04d carries over 04c's supply chain for exactly this reason. The
    exemption is counted by `tools/build_notebooks/build.py --check` so it cannot
    be used quietly.

    This duplicates `test_builder_audit_passes`, deliberately: that one checks the
    builder, this one checks the shipped artifact, and it keeps working for a
    notebook that has no builder.
    """
    nb = nbformat.read(path, as_version=4)
    for i, cell in enumerate(nb.cells):
        if cell.cell_type != "code":
            continue
        src = "".join(cell.source)
        if "CARRIED OVER" in src:
            continue
        # A function that IS the lesson is exempt on the same terms the builder
        # audit applies: the marker must carry a stated reason, so the
        # exemption cannot be taken silently in the shipped artifact either.
        if LESSON_MARK in src:
            marker = next(l for l in src.splitlines() if LESSON_MARK in l)
            assert len(marker.split(LESSON_MARK, 1)[1].strip(": ")) >= 20, (
                f"{path.name} cell {i}: '{LESSON_MARK}' with no reason after "
                f"it. State why this function is the lesson rather than an "
                f"abstraction hiding it."
            )
            continue
        lines = "".join(cell.source).splitlines()
        for j, line in enumerate(lines):
            if not line.startswith("def "):
                continue
            body = 0
            for k in range(j + 1, len(lines)):
                if lines[k] and not lines[k][0].isspace():
                    break
                body += 1
            if body > 8:
                pct = 100 * i / len(nb.cells)
                assert pct >= 50, (
                    f"{path.name}: a {body}-line function at cell {i} "
                    f"({pct:.0f}% through) sits above the narration of the same "
                    f"material"
                )
                return
