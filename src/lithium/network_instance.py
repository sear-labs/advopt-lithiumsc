"""The instance tables for the Parts 1, 2 and 5 network model.

**This is a different model family from `instance.py`.** That one describes the
Part 4 game: two regions, three stages, one vertically-integrated chain per firm.
This one describes a six-site network — two mines, two processors, two
fabricators — with arc flows between them and a single decision maker.

They share nothing but a repository, which is worth stating plainly because both
have a `home region`, an `opex` and a `lead` and it is easy to assume otherwise.

Three tables, three key structures:

    network_sites.csv    keyed site   6 rows   capacity, lead, capex, opex, legacy
    network_tiers.csv    keyed tier   2 rows   the yield-curve parameters
    network_demand.csv   keyed region 2 rows   demand base and growth

`CLAUDE.md` Part 4's *Tables versus knobs* is the rule. What is **not** here, and
belongs in the notebook cell that explains it: the horizon `T`, the discount rate
`r`, `max_builds`, `life`, the learning rate and its floor, the slack penalty,
the transport costs, and the mining yield. Those are knobs — scalars carrying a
concept — and the agreement assertion covers them because the notebook hands them
to the package explicitly.
"""
from __future__ import annotations

from dataclasses import dataclass
from importlib import resources
from pathlib import Path

import pandas as pd

__all__ = ["NetworkInstance", "load_network_instance", "read_network_tables"]

DATA_FILES = ("network_sites.csv", "network_tiers.csv", "network_demand.csv")


@dataclass(frozen=True)
class NetworkInstance:
    """One six-site network instance: the three tables, keyed as models index."""

    regions: tuple[str, ...]
    mines: tuple[str, ...]
    procs: tuple[str, ...]
    fabs: tuple[str, ...]

    # keyed site
    tier: dict[str, str]
    home: dict[str, str]
    cap_unit: dict[str, float]
    lead: dict[str, int]
    capex0: dict[str, float]
    opex: dict[str, float]
    legacy: dict[str, tuple[int, int, int]]   # (units, vintage, retirement year)

    # keyed tier ('P' and 'F'; mining yield is a knob, being constant)
    eta_bar: dict[str, float]
    eta_0: dict[str, float]
    alpha: dict[str, float]
    beta: dict[str, float]
    dbar: dict[str, float]

    # keyed region
    demand_base: dict[str, float]
    demand_growth: dict[str, float]

    @property
    def sites(self) -> list[str]:
        """Mines, then processors, then fabricators — the order models iterate."""
        return list(self.mines) + list(self.procs) + list(self.fabs)


def read_network_tables(source: Path | str | None = None) -> dict[str, pd.DataFrame]:
    """Read the three CSVs as frames, without interpreting them.

    `source` is a directory; `None` means the copies shipped inside the package,
    so `pip install git+https://...` carries them into Colab with no checkout.
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


def load_network_instance(source: Path | str | None = None) -> NetworkInstance:
    """Load the three tables into one :class:`NetworkInstance`.

    Row order in the CSVs fixes the order every model iterates in, so results are
    reproducible without sorting anything. Sites are grouped by tier: the file
    lists mines, then processors, then fabricators.
    """
    t = read_network_tables(source)
    sites, tiers, dem = (t["network_sites.csv"], t["network_tiers.csv"],
                         t["network_demand.csv"])

    for name, frame, cols in (
        ("network_sites.csv", sites,
         ["site", "tier", "home", "cap_unit", "lead", "capex0", "opex",
          "legacy_units", "legacy_vintage", "legacy_retire"]),
        ("network_tiers.csv", tiers, ["tier", "eta_bar", "eta_0", "alpha",
                                      "beta", "dbar"]),
        ("network_demand.csv", dem, ["region", "base", "growth"]),
    ):
        gap = [c for c in cols if c not in frame.columns]
        if gap:
            raise ValueError(f"{name} missing required columns: {gap}")

    regions = tuple(dict.fromkeys(dem["region"]))
    unknown = set(sites["home"]) - set(regions)
    if unknown:
        raise ValueError(
            f"network_sites.csv puts sites in regions absent from "
            f"network_demand.csv: {sorted(unknown)}"
        )
    by_tier = {k: tuple(sites.loc[sites["tier"] == k, "site"])
               for k in ("M", "P", "F")}
    if not all(by_tier.values()):
        raise ValueError(
            f"network_sites.csv needs at least one site of each tier M/P/F; got "
            f"{ {k: len(v) for k, v in by_tier.items()} }"
        )
    missing_tiers = set(by_tier["P"] + by_tier["F"]) and (
        {"P", "F"} - set(tiers["tier"]))
    if missing_tiers:
        raise ValueError(f"network_tiers.csv is missing tier(s) {missing_tiers}")

    def by_site(col, cast=float):
        return {r.site: cast(getattr(r, col)) for r in sites.itertuples()}

    return NetworkInstance(
        regions=regions,
        mines=by_tier["M"], procs=by_tier["P"], fabs=by_tier["F"],
        tier=by_site("tier", str),
        home=by_site("home", str),
        cap_unit=by_site("cap_unit"),
        lead=by_site("lead", int),
        capex0=by_site("capex0"),
        opex=by_site("opex"),
        legacy={r.site: (int(r.legacy_units), int(r.legacy_vintage),
                         int(r.legacy_retire)) for r in sites.itertuples()},
        eta_bar={r.tier: float(r.eta_bar) for r in tiers.itertuples()},
        eta_0={r.tier: float(r.eta_0) for r in tiers.itertuples()},
        alpha={r.tier: float(r.alpha) for r in tiers.itertuples()},
        beta={r.tier: float(r.beta) for r in tiers.itertuples()},
        dbar={r.tier: float(r.dbar) for r in tiers.itertuples()},
        demand_base={r.region: float(r.base) for r in dem.itertuples()},
        demand_growth={r.region: float(r.growth) for r in dem.itertuples()},
    )
