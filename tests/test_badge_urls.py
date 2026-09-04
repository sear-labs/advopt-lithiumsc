"""Every badge URL must name the branch this repo is actually on.

A Colab badge is `github/<owner>/<repo>/blob/<branch>/<path>` — four values, and
a wrong one in any position produces the same failure: a 404 that presents as a
Colab or hosting problem rather than as a naming one, so the search starts in
the wrong place.

Three of the four are checked by other means. The path is checked because the
notebook must exist. The owner and repo were substituted together after a
near-miss where only the owner looked like a placeholder — 63 and 64 occurrences,
and the invisible half was the larger one. **The branch was the one nobody
looked at**, because `owner/repo` reads as the whole address when it is
two-thirds of it.

This repo was created by `git init` before `init.defaultBranch` was set, so it
sat on `master` while all 45 badges named `main` — as written, every one would
have 404'd on the first push. Renamed in `c038521`, and green since. Renaming
cost nothing because the badges were already right: the fix was making one
branch match 45 files, not editing 45 files to match one branch. After a push
that inverts, because then the badges are the copies and the branch is the
source.

**It was committed red on purpose**, in `0053e0e`. A suite staying green over 45
badges pointing at a branch that did not exist was reporting the wrong thing.
The requirement was prose in `CLAUDE.md` Part 11 first, and prose is the form
that gets read *after* the push.

**What it guards now is the reverse case**: a later branch rename that leaves
the badges behind, a badge added by hand naming something else, or a bulk edit
that rewrites them to a branch nobody created. Either half may move as long as
both move — and nothing satisfies it silently.

One thing it deliberately does not check: whether the branch exists *on the
remote*. There is no remote yet, and a check that quietly passes when it cannot
reach its subject is worse than no check. `test_badges_name_exactly_one_branch`
covers the part that is knowable locally, and fails loudly if the badge set ever
empties rather than reporting success over nothing.
"""
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BADGE = re.compile(r"github/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/blob/([A-Za-z0-9_.-]+)/")


def _tracked():
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True,
                         text=True, encoding="utf-8", check=True).stdout
    return [ROOT / line for line in out.splitlines() if line.strip()]


def _branches_named_in_badges():
    found = {}
    for path in _tracked():
        if path.suffix not in {".ipynb", ".md", ".py"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for branch in BADGE.findall(text):
            found.setdefault(branch, []).append(path.name)
    return found


def test_badges_name_exactly_one_branch():
    """Two branches in the badge set means half of them are wrong either way."""
    found = _branches_named_in_badges()
    assert found, "no badge URLs found at all — this check would pass vacuously"
    assert len(found) == 1, f"badges name more than one branch: { {k: len(v) for k, v in found.items()} }"


def test_badges_name_the_branch_this_repo_is_on():
    """Red on purpose until c038521; now guards a rename that leaves badges behind."""
    current = subprocess.run(["git", "branch", "--show-current"], cwd=ROOT,
                             capture_output=True, text=True,
                             encoding="utf-8").stdout.strip()
    if not current:
        pytest.skip("detached HEAD or no branch; nothing to compare against")

    found = _branches_named_in_badges()
    named = next(iter(found))
    count = len(next(iter(found.values())))

    # Which fix is cheap depends on whether anything has been published, so read
    # that rather than asserting it. Hardcoding "free while there is no remote"
    # would make this message wrong from the first push onwards -- in the very
    # line telling someone what to do about a stale claim.
    has_remote = bool(subprocess.run(["git", "remote"], cwd=ROOT, capture_output=True,
                                     text=True, encoding="utf-8").stdout.strip())
    advice = (
        f"  a remote exists, so renaming the branch moves a published default and\n"
        f"  breaks any link already shared. Rewriting the badges to '{current}'\n"
        f"  is usually the cheaper side now: git branch -m is no longer free."
        if has_remote else
        f"  no remote yet, so the rename is free and edits nothing:\n"
        f"      git branch -m {current} {named}\n"
        f"  or rewrite the badges to '{current}' if that branch is deliberate.")

    assert named == current, (
        f"{count} badge URLs name branch '{named}' but this repo is on "
        f"'{current}'. Pushed as-is, every one of them 404s — and it presents "
        f"as a Colab fault rather than a branch one.\n" + advice)
