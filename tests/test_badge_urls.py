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
is on `master`, while every badge in it names `main`. That is not a preference
question: as written, all 45 badges 404 on the first push.

**This check fails until that is resolved, and that is what it is for.** The
requirement was recorded as prose in `CLAUDE.md` Part 11 first, which is the
form that gets read after the push rather than before. The fix is one command
while the repo has no remote:

    git branch -m master main

or, if `master` is deliberate, rewrite the badges to match. Either satisfies
this; nothing satisfies it silently.
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
    """The one check that is currently failing, and the reason it exists."""
    current = subprocess.run(["git", "branch", "--show-current"], cwd=ROOT,
                             capture_output=True, text=True,
                             encoding="utf-8").stdout.strip()
    if not current:
        pytest.skip("detached HEAD or no branch; nothing to compare against")

    found = _branches_named_in_badges()
    named = next(iter(found))
    count = len(next(iter(found.values())))
    assert named == current, (
        f"{count} badge URLs name branch '{named}' but this repo is on "
        f"'{current}'. Pushed as-is, every one of them 404s — and it presents "
        f"as a Colab fault rather than a branch one.\n"
        f"  fix, free while there is no remote:  git branch -m {current} {named}\n"
        f"  or rewrite the badges to '{current}' if that branch is deliberate.")
