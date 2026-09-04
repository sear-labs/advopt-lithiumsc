"""Parts 0-10 of `CLAUDE.md` are a copy. This checks it is the copy it claims.

`CLAUDE.md` Part 0, *How copies of this document work*: syncs run one way,
source -> here, and Part 11 opens with the source SHA. That stamp exists so the
copy can be **asked** whether it has drifted, rather than merely asserting that
it has not -- an assertion that rots silently, true when written and false the
moment the source moves.

This is the asking. Three failures, each with its own message:

1. **The stamp and the record disagree.** Someone edited the SHA in the prose
   without re-syncing, or re-synced without updating the record.
2. **The portable half was edited here.** The most likely failure by far, and
   the one Part 11 warns about: an improvement made in this copy survives until
   the next sync silently discards it. Fails loudly instead.
3. **The stamp names the wrong commit.** Only checkable where the source repo
   is on the machine, so it SKIPS on a clean clone, in CI and for a student --
   which is why check 2 does not depend on it.

The same shape as `test_notebook_sources.py`: a build output and its source
drift exactly as fast as two pasted copies do, unless something compares them.
"""
import hashlib
import json
import pathlib
import re
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
CLAUDE = ROOT / "CLAUDE.md"
RECORD = pathlib.Path(__file__).parent / "standard_sync.json"

# The heading, anchored to a line start. Part 0 QUOTES this heading as an
# example, so an unanchored search finds the quotation ~800 lines too early and
# both halves still look plausible.
MARK = "\n# Part 11 — This project specifically"


def portable_half():
    """Everything above Part 11, with the separator this file adds removed."""
    text = CLAUDE.read_text(encoding="utf-8")
    assert text.count(MARK) == 1, f"expected exactly one Part 11 heading, found {text.count(MARK)}"
    head = text.split(MARK, 1)[0]
    SEP = "\n\n---\n"
    assert head.endswith(SEP), f"unexpected join before Part 11: {head[-12:]!r}"
    return head[: -len(SEP)]


@pytest.fixture(scope="module")
def record():
    return json.loads(RECORD.read_text(encoding="utf-8"))


def part_eleven():
    """Part 11 alone. Scoping matters: Part 0 quotes the stamp FORMAT as an
    example, so a whole-file search finds that example and not the stamp."""
    text = CLAUDE.read_text(encoding="utf-8")
    assert text.count(MARK) == 1, f"expected exactly one Part 11 heading, found {text.count(MARK)}"
    return MARK + text.split(MARK, 1)[1]


def test_stamp_matches_the_record(record):
    """The SHA a reader sees in Part 11 is the SHA this test checks against."""
    text = part_eleven()
    assert text.count("Parts 0-10 are a copy of") == 1, "Part 11 carries more than one stamp"
    found = re.search(r"Parts 0-10 are a copy of (\S+) at ([0-9a-f]{7,40}) \((\d{4}-\d\d-\d\d)\)", text)
    assert found, (
        "Part 11 does not open with a source stamp. CLAUDE.md Part 0 requires\n"
        "    Parts 0-10 are a copy of sear-labs/code-standard at <sha> (<date>)."
    )
    repo, sha, date = found.groups()
    assert repo == record["repo"], f"stamp names {repo}, record names {record['repo']}"
    assert sha == record["sha"], (
        f"Part 11 says the copy came from {sha}; {RECORD.name} says {record['sha']}. "
        "One of them was updated without the other."
    )
    assert date == record["date"], f"stamp dated {date}, record dated {record['date']}"


def test_portable_half_was_not_edited_here(record):
    """An edit to Parts 0-10 in THIS file is lost at the next sync. Fail now."""
    got = hashlib.sha256(portable_half().encode("utf-8")).hexdigest()
    assert got == record["sha256"], (
        "Parts 0-10 of CLAUDE.md no longer match what was synced from the source.\n"
        "Syncs run ONE WAY: source -> here. If you meant to improve the portable\n"
        "half, make the change in the source repo, commit it there, re-sync, and\n"
        "update tests/standard_sync.json. If you meant to add something specific\n"
        "to this project, it belongs below the Part 11 heading.\n"
        f"  expected {record['sha256'][:16]}\n  got      {got[:16]}"
    )


def test_stamp_names_the_right_commit(record):
    """Where the source is on this machine, check the stamp against it."""
    src = pathlib.Path(record["source_path"])
    if not (src / ".git").is_dir():
        pytest.skip(f"source repo not on this machine ({src}); stamp unverifiable here")
    shown = subprocess.run(
        ["git", "-C", str(src), "show", f"{record['sha']}:CLAUDE.md"],
        capture_output=True, text=True, encoding="utf-8")
    if shown.returncode != 0:
        pytest.skip(f"commit {record['sha']} not in the local source repo; fetch it to check")
    assert shown.stdout.rstrip("\n") == portable_half(), (
        f"Parts 0-10 differ from {record['repo']} at {record['sha']}.\n"
        f"Diff them with:  git -C \"{src}\" show {record['sha']}:CLAUDE.md"
    )
