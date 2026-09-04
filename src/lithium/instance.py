"""The instance tables — the numbers both the notebooks and this package read.

the Code Standard, Part 4, *Tables versus knobs*, is the rule this module implements.
A **knob** is a scalar carrying a concept (a discount rate, a breakpoint count).
Knobs stay written out in the notebook cell and are handed to this package
explicitly, so the agreement assertion already covers them. A **table** is
instance data — many entries, indexed by the model's own sets, named nowhere in
the prose. Tables live here, in one file both sides read, because a failed
assertion cannot otherwise distinguish a typo in the data from a bug in a
constraint.

Three tables, three key structures:

    instance_base.csv   keyed (stage, region)   6 rows
    efficiency.csv      keyed stage             3 rows
    market.csv          keyed region            2 rows

`load_instance()` reads the copies shipped *inside the package*, so
`pip install git+https://...` carries them into Colab with no repo checkout.
`load_instance(Path("data/raw"))` reads the editable copies at the repo root.
"""
from __future__ import annotations

from dataclasses import dataclass
from importlib import resources
from pathlib import Path

import pandas as pd

__all__ = ["Instance", "load_instance", "read_tables"]


@dataclass(frozen=True)
class Instance:
    """One market instance: the three tables, already keyed the way models index.

    Nothing here is computed. Everything derived from these numbers — yields by
    vintage, active windows, discount weights — is built by
    :func:`lithium.structure.build_structure`, because deriving it is the lesson
    the notebook teaches by hand.
    """

    regions: tuple[str, ...]
    stages: tuple[str, ...]

    # keyed (stage, region)
    fixed: dict[tuple[str, str], float]
    unit: dict[tuple[str, str], float]
    opex: dict[tuple[str, str], float]
    legacy_cap: dict[tuple[str, str], float]
    legacy_ret: dict[tuple[str, str], int]

    # keyed stage
    eta_ceil: dict[str, float]
    eta_base: dict[str, float]
    alpha: dict[str, float]
    beta: dict[str, float]
    delta_bar: dict[str, float]

    # keyed region
    demand_base: dict[str, float]
    demand_growth: dict[str, float]
    experience0: dict[str, float]

    def replace(self, **overrides: dict) -> "Instance":
        """Return a copy with whole tables swapped — for sweeps in `src/`.

        A notebook reader overriding *one entry* should assign into the dict it
        built (``OPEX['PROC', 'R2'] = 2.00``) and pass that dict on; that is what
        keeps the edit visible next to the narration.
        """
        from dataclasses import replace as _replace

        return _replace(self, **overrides)


DATA_FILES = ("instance_base.csv", "efficiency.csv", "market.csv")


def read_tables(source: Path | str | None = None) -> dict[str, pd.DataFrame]:
    """Read the three CSVs as frames, without interpreting them.

    `source` is a directory; `None` means the copies shipped inside the package.
    The notebook calls this so it can `display()` the frames before building any
    dictionary — see the frame first, then the key structure.
    """
    if source is None:
        base = resources.files("lithium") / "data"
        return {n: pd.read_csv(base.joinpath(n).open("r", encoding="utf-8"))
                for n in DATA_FILES}
    base = Path(source)
    missing = [n for n in DATA_FILES if not (base / n).exists()]
    if missing:
        raise FileNotFoundError(
            f"{base} is missing {missing}. Pass source=None to read the copies "
            f"shipped inside the installed package instead."
        )
    return {n: pd.read_csv(base / n) for n in DATA_FILES}


def load_instance(source: Path | str | None = None) -> Instance:
    """Load the three tables into one :class:`Instance`.

    Row order in the CSVs sets the order of `regions` and `stages`, and every
    model below iterates those sets in that order, so results are reproducible
    without sorting anything.
    """
    t = read_tables(source)
    base, eff, mkt = t["instance_base.csv"], t["efficiency.csv"], t["market.csv"]

    for name, frame, cols in (
        ("instance_base.csv", base,
         ["stage", "region", "fixed", "unit", "opex", "legacy_cap", "legacy_ret"]),
        ("efficiency.csv", eff,
         ["stage", "eta_ceil", "eta_base", "alpha", "beta", "delta_bar"]),
        ("market.csv", mkt,
         ["region", "demand_base", "demand_growth", "experience0"]),
    ):
        gap = [c for c in cols if c not in frame.columns]
        if gap:
            raise ValueError(f"{name} missing required columns: {gap}")

    stages = tuple(dict.fromkeys(eff["stage"]))
    regions = tuple(dict.fromkeys(mkt["region"]))

    unknown = set(base["stage"]) - set(stages) | set(base["region"]) - set(regions)
    if unknown:
        raise ValueError(
            f"instance_base.csv references keys absent from efficiency.csv / "
            f"market.csv: {sorted(unknown)}"
        )
    if len(base) != len(stages) * len(regions):
        raise ValueError(
            f"instance_base.csv has {len(base)} rows; {len(stages)} stages x "
            f"{len(regions)} regions needs {len(stages) * len(regions)}"
        )

    def by_sr(col):
        return {(r.stage, r.region): float(getattr(r, col))
                for r in base.itertuples()}

    def by_stage(col):
        return {r.stage: float(getattr(r, col)) for r in eff.itertuples()}

    def by_region(col):
        return {r.region: float(getattr(r, col)) for r in mkt.itertuples()}

    return Instance(
        regions=regions,
        stages=stages,
        fixed=by_sr("fixed"),
        unit=by_sr("unit"),
        opex=by_sr("opex"),
        legacy_cap=by_sr("legacy_cap"),
        legacy_ret={k: int(v) for k, v in by_sr("legacy_ret").items()},
        eta_ceil=by_stage("eta_ceil"),
        eta_base=by_stage("eta_base"),
        alpha=by_stage("alpha"),
        beta=by_stage("beta"),
        delta_bar=by_stage("delta_bar"),
        demand_base=by_region("demand_base"),
        demand_growth=by_region("demand_growth"),
        experience0=by_region("experience0"),
    )
