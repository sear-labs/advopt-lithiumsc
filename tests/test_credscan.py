"""Prove the credential scanner fires before believing it when it says clean.

`credscan` reports "nothing credential-shaped" over every tracked file, and that
sentence is worth exactly as much as the evidence that the scanner can detect
anything at all. **A scanner that returns zero because it is broken and one that
returns zero because the tree is clean produce identical output.**

That is not hypothetical here. On 2026-09-04 two sessions each drew a wrong
conclusion from a search of this repository's history within an hour: one ran a
`git grep` against a commit tree that searched nothing and reported clean, and
one piped grep through a redacting `sed` and then read its own `<REDACTED>`
marker as evidence of a live credential. Both tools looked fine. Neither
announced anything. The rule that came out of it -- never draw a conclusion from
sanitized output, ask a question whose answer is safe to print -- is why the
assertions below are counts and booleans rather than eyeballed text.

So every assertion that the scanner finds nothing is preceded by assertions that
it finds what was planted. Planted values are synthetic: a UUID generated for
this file and example keys from vendor documentation, never a real credential.

The negative controls matter as much. A scanner that flags `<your-key-here>` is
noise, and a noisy check is one somebody eventually stops running.

**Why the strings below are assembled rather than written out.** This file is
itself scanned. Written literally, its planted controls would trip `credscan`
and the repository could never be clean -- so the obvious fix is to exempt this
file, and an exemption is a hole exactly where a real key would hide best.
Assembling the key names and the vendor prefixes instead keeps the scanner's
coverage total: no line here matches its patterns, and nothing is excused.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import credscan  # noqa: E402

# Synthetic UUIDs, generated for this test and never issued to anyone. A bare
# UUID is not credential-shaped to credscan -- only one sitting next to a key
# name is -- so these are safe to write out.
FAKE_ID = "3f2b91c4-7d0e-4a15-9b62-8ce4d071af38"
FAKE_SECRET = "a17c5e90-24bf-4d38-8e71-6b0f39ca25d7"

# Split so this file does not match credscan's own patterns. See the docstring.
K_ID = "WLS" + "ACCESSID"
K_SECRET = "WLS" + "SECRET"
AWS_EXAMPLE = "AKIA" + "IOSFODNN7EXAMPLE"          # from AWS's own docs
PEM_HEADER = "-----BEGIN " + "RSA PRIVATE KEY-----"

PLANTED = [
    ("WLS python dict",
     f"ENV = gp.Env(params={{'{K_ID}': '{FAKE_ID}',\n"
     f"                     '{K_SECRET}': '{FAKE_SECRET}'}})\n"),
    ("WLS KEY=VALUE",
     f"{K_ID}={FAKE_ID}\n{K_SECRET}={FAKE_SECRET}\n"),
    ("generic api key",
     "api" + "_key = " + '"sk-live-9f2b71c4d0e84a15"\n'),
    ("private key block", PEM_HEADER + "\nMIIEowIBAAKCAQEA\n"),
    ("aws access key id", "aws_key = " + AWS_EXAMPLE + "\n"),
]

IGNORED = [
    ("angle-bracket placeholder", f"{K_ID}: <your WLS access id>\n"),
    ("ellipsis placeholder", f'{K_ID}": "..."\n'),
    ("env lookup, not a literal",
     f"{K_ID} = os.environ['GRB_{K_ID}']\n"),
]


def _scan(tmp_path, body, suffix=".py"):
    p = tmp_path / f"planted{suffix}"
    p.write_text(body, encoding="utf-8")
    return credscan.scan([p])


@pytest.mark.parametrize("label,body", PLANTED, ids=[p[0] for p in PLANTED])
def test_scanner_fires_on_a_planted_credential(tmp_path, label, body):
    """The control. If any of these pass silently, a clean report means nothing."""
    assert _scan(tmp_path, body), (
        f"credscan did NOT flag a planted {label}. Every 'nothing "
        f"credential-shaped' result is unreliable until this passes.")


def test_scanner_fires_inside_a_notebook(tmp_path):
    """The shape that actually bit: a key in a .ipynb, where source is JSON.

    `credscan.searchable_text` decodes the notebook first for exactly this
    reason. A regex applied to raw notebook JSON meets escaped quotes and
    matches nothing -- which is how one check in this repo reported no literal
    assignments in a file that had them.
    """
    nb = {"cells": [{"cell_type": "code", "source": [
        f"ENV = gp.Env(params={{'{K_ID}': '{FAKE_ID}',\n",
        f"                     '{K_SECRET}': '{FAKE_SECRET}'}})\n"]}],
        "metadata": {}, "nbformat": 4, "nbformat_minor": 5}
    p = tmp_path / "planted.ipynb"
    p.write_text(json.dumps(nb), encoding="utf-8")
    assert credscan.scan([p]), "credscan did not see a key inside notebook JSON"


def test_scanner_masks_the_value_it_reports(tmp_path):
    """It must never echo the secret it found, or the report becomes the leak."""
    hits = _scan(tmp_path, f"{K_SECRET} = '{FAKE_SECRET}'\n")
    assert hits
    rendered = " ".join(str(h) for h in hits)
    assert FAKE_SECRET not in rendered, "credscan echoed the credential it found"
    assert "36 chars" in rendered, "the mask should still say how long the value was"


@pytest.mark.parametrize("label,body", IGNORED, ids=[p[0] for p in IGNORED])
def test_scanner_ignores_placeholders_and_lookups(tmp_path, label, body):
    """A check that cries wolf is a check that gets switched off."""
    assert not _scan(tmp_path, body), f"credscan flagged {label}, not a credential"


def test_the_scrub_marker_is_flagged_and_that_is_correct(tmp_path):
    """Documenting the scrub's own placeholder trips the scanner, by design.

    `git filter-repo` replaced the exposed value with a marker, so the root
    commit reads like an assignment of that marker. Quoting that assignment in
    prose is indistinguishable from a real one to a shallow content scan -- and
    a scan that tried to tell them apart would be one keyword away from
    excusing a real key. The first draft of `CLAUDE.md`'s correction quoted it
    that way and this check caught it; the prose now names the site and the
    value separately.
    """
    body = f'{K_ID}": "REDACTED-CREDENTIAL-' + 'ROTATED"\n'
    assert _scan(tmp_path, body), (
        "the scrub marker in assignment form is no longer flagged -- if that "
        "was deliberate, a real key in the same shape is now invisible too")


def test_this_test_file_does_not_itself_trip_the_scanner():
    """No exemption. The planted controls are assembled so nothing here matches."""
    assert not credscan.scan([Path(__file__)]), (
        "test_credscan.py matches credscan's own patterns. Assemble the "
        "offending literal from parts rather than exempting this file -- an "
        "exemption is a hole exactly where a real key would hide best.")


def test_the_repository_itself_is_clean():
    """The real assertion -- and it means something because the controls passed."""
    r = subprocess.run([sys.executable, "tools/credscan.py"], cwd=ROOT,
                       capture_output=True, text=True)
    assert r.returncode == 0, f"credscan found something:\n{r.stdout}\n{r.stderr}"
    assert "nothing credential-shaped" in r.stdout
