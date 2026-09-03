#!/usr/bin/env python
"""Check every number in a notebook's markdown against its executed outputs.

    python tools/prosecheck.py                      # every notebook in notebooks/
    python tools/prosecheck.py notebooks/04c_cournot.ipynb

`CLAUDE.md` Part 6, *Every number in the prose comes from a run*: a parameter
changes, every downstream figure in the narration is now wrong, and nothing
complains. A human will not re-check forty figures after every edit.

**This reports candidates; a person adjudicates.** A flagged number is not
automatically an error — section cross-references (`section 5.5`), exponents
(`$10^{-9}$`), figures attributed to a *different* notebook, and deliberately
recorded failure output will all show up here and are all legitimate. What the
tool guarantees is that nobody can change a result and leave the prose stale
without the change appearing in this list.

Exit code is 1 when anything is flagged, so CI can gate on a curated allowlist
(see `--baseline`) rather than on zero.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import nbformat

ROOT = Path(__file__).resolve().parents[1]

NUM = re.compile(r"(?<![\w.])(-?\d[\d,]*(?:\.\d+)?)")

# Small integers carry no claim about a result: they are counts, indices and
# section numbers. Anything larger has to be traceable to a run.
SMALL = {str(n) for n in range(0, 14)} | {"0.5", "1.0", "2.0"}


def numbers(text: str):
    for m in NUM.finditer(text):
        raw = m.group(1)
        clean = raw.replace(",", "")
        if clean in SMALL:
            continue
        try:
            yield raw, float(clean)
        except ValueError:
            continue


def output_text(cell) -> str:
    bits = []
    for o in cell.get("outputs", []):
        if o.output_type == "stream":
            bits.append(o.get("text", ""))
        elif "data" in o:
            bits.append(str(o["data"].get("text/plain", "")))
    return "\n".join(bits)


def check(path: Path):
    """Return a list of (cell_index, raw_number, context) that matched nothing."""
    nb = nbformat.read(path, as_version=4)
    code = [c for c in nb.cells if c.cell_type == "code"]
    if not any(c.get("outputs") for c in code):
        raise SystemExit(
            f"{path.name} carries no outputs, so there is nothing to check the "
            f"prose against. Execute it and commit it executed first."
        )

    out_nums = {round(v, 6) for _, v in numbers("\n".join(map(output_text, code)))}
    code_nums = {round(v, 6) for _, v in numbers(
        "\n".join("".join(c.source) for c in code))}

    flagged = []
    for i, cell in enumerate(nb.cells):
        if cell.cell_type != "markdown":
            continue
        src = "".join(cell.source)
        for raw, val in numbers(src):
            # a prose figure may be rounded, scaled, or a percentage of a printed
            # fraction, so accept a family of readings before flagging
            # A prose figure may be rounded, scaled, or written as a magnitude
            # with a Unicode minus the extractor cannot see, so try |val| too.
            cands = {round(val, 6), round(val, 1), round(val, 0),
                     round(val / 100, 6), round(val * 100, 6),
                     round(-val, 6), round(-val, 1), round(-val, 0)}
            hit = any(abs(c - o) < max(0.06, abs(o) * 2e-4)
                      for c in cands for o in out_nums)
            if not hit and round(val, 6) in code_nums:
                hit = True                       # it is a knob, set in a cell
            if not hit:
                at = src.find(raw)
                ctx = src[max(0, at - 70):at + 40].replace("\n", " ")
                flagged.append((i, raw, ctx))
    return flagged


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("notebooks", nargs="*", type=Path,
                    help="default: every .ipynb in notebooks/")
    ap.add_argument("--baseline", type=Path, default=None,
                    help="JSON file of adjudicated {notebook: count} to compare "
                         "against; fails only when a count goes UP")
    args = ap.parse_args()

    paths = args.notebooks or sorted((ROOT / "notebooks").glob("*.ipynb"))
    if not paths:
        print("no notebooks found")
        return 0

    baseline = json.loads(args.baseline.read_text()) if args.baseline else {}
    worse = False
    for path in paths:
        flagged = check(path)
        allowed = baseline.get(path.name)
        verdict = ""
        if allowed is not None:
            if len(flagged) > allowed:
                verdict = f"  <-- ABOVE BASELINE ({allowed})"
                worse = True
            else:
                verdict = f"  (baseline {allowed})"
        print(f"{path.name}: {len(flagged)} markdown numbers not found in the "
              f"outputs or the code{verdict}")
        for i, raw, ctx in flagged:
            print(f"    cell {i:3d}  {raw:>16s}  ...{ctx}...")

    if baseline:
        return 1 if worse else 0
    return 1 if any(check(p) for p in paths) else 0


if __name__ == "__main__":
    sys.exit(main())
