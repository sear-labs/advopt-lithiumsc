"""Derived structure: the sets and coefficients computed from tables plus knobs.

Nothing in here is data and nothing in here is a knob — it is all *derived*, and
in the teaching notebooks deriving it is the lesson (`CLAUDE.md` Part 11:
"Derived structure stays as code in the notebook"). The notebook computes
`OMEGA`, `CRF`, `MU`, `ETA`, `ACTIVE`, `VIN` and `BUILD` by hand; this module
computes the same things once, and the agreement assertion at the end of the
notebook is what proves the two derivations match.

Every knob arrives as an argument. There is no module-level constant here that a
model reads behind the caller's back.
"""
from __future__ import annotations

from dataclasses import dataclass

from .instance import Instance

__all__ = ["Structure", "build_structure"]


@dataclass(frozen=True)
class Structure:
    """Everything the model indexes over, for one horizon and one instance."""

    inst: Instance

    # time
    blocks: tuple[tuple[int, int], ...]
    LEN: list[int]
    START: list[int]
    P: list[int]
    HORIZON: int
    YEARS: dict[int, list[int]]
    OMEGA: dict[int, float]
    YEAR_TO_P: dict[int, int]

    # technology
    dr: float
    life: int
    lead: dict[str, int]
    cap_min: float
    cap_max: float
    CRF: float
    ONLINE: dict[tuple[str, int], int]
    MU: dict[tuple[str, int], float]

    # efficiency
    VINTAGES: list[int]
    BYEAR: dict[int, int]
    ETA: dict[tuple[str, int, int], float]

    # windows
    ACTIVE: dict[str, list[tuple[str, int, int]]]
    VIN: dict[tuple[str, str, int], list[int]]
    BUILD: dict[str, list[tuple[str, int]]]

    # market
    DEMAND: dict[tuple[str, int], float]

    @property
    def regions(self) -> tuple[str, ...]:
        return self.inst.regions

    @property
    def stages(self) -> tuple[str, ...]:
        return self.inst.stages


def build_structure(
    inst: Instance,
    *,
    blocks=((6, 1), (4, 3), (2, 5), (1, 9)),
    dr: float = 0.05,
    life: int = 25,
    lead=None,
    cap_min: float = 60.0,
    cap_max: float = 260.0,
    legacy_byr: int = -8,
    eta_floor: float = 0.60,
) -> Structure:
    """Derive the sets and coefficients from one instance and the horizon knobs.

    Mirrors, line for line, what the teaching notebook writes out by hand. The
    keyword defaults are the values the shipped notebooks use; the notebook still
    passes each one explicitly, so a reader who changes `DR` sees it move both
    the hand-built model and this one.
    """
    lead = dict(lead if lead is not None else {"MINE": 1, "PROC": 2, "MFG": 2})
    blocks = tuple(tuple(b) for b in blocks)
    stages, regions = inst.stages, inst.regions

    # ---- time -------------------------------------------------------------
    LEN: list[int] = []
    START: list[int] = []
    y = 1
    for count, length in blocks:
        for _ in range(count):
            LEN.append(length)
            START.append(y)
            y += length
    P = list(range(len(LEN)))
    HORIZON = y - 1
    YEARS = {p: list(range(START[p], START[p] + LEN[p])) for p in P}
    OMEGA = {p: sum(1 / (1 + dr) ** t for t in YEARS[p]) for p in P}
    YEAR_TO_P = {t: p for p in P for t in YEARS[p]}

    # ---- technology -------------------------------------------------------
    CRF = dr * (1 + dr) ** life / ((1 + dr) ** life - 1)
    ONLINE = {(s, p): START[p] + lead[s] for s in stages for p in P}
    MU = {
        (s, v): CRF * sum(
            1 / (1 + dr) ** t
            for t in range(ONLINE[s, v], ONLINE[s, v] + life)
            if t <= HORIZON
        )
        for s in stages for v in P
    }

    # ---- efficiency by vintage -------------------------------------------
    VINTAGES = [-1] + P
    BYEAR = {v: (legacy_byr if v == -1 else START[v]) for v in VINTAGES}
    ETA: dict[tuple[str, int, int], float] = {}
    for s in stages:
        ceil_, base_ = inst.eta_ceil[s], inst.eta_base[s]
        a, b, dbar = inst.alpha[s], inst.beta[s], inst.delta_bar[s]
        for v in VINTAGES:
            fr = ceil_ - (ceil_ - base_) * (1 - a) ** (BYEAR[v] - 1)
            fr = max(eta_floor, min(fr, ceil_))
            for p in P:
                age = max(0, START[p] - BYEAR[v])
                aged = ceil_ - (ceil_ - fr) * (1 - b) ** age
                ETA[s, v, p] = max(eta_floor, min(fr + dbar, aged))

    # ---- active windows ---------------------------------------------------
    ACTIVE = {
        r: [
            (s, v, p)
            for s in stages for v in VINTAGES for p in P
            if (v == -1 and START[p] <= inst.legacy_ret[s, r])
            or (v >= 0 and ONLINE[s, v] <= START[p] <= ONLINE[s, v] + life - 1)
        ]
        for r in regions
    }
    VIN = {
        (r, s, p): [v for (ss, v, pp) in ACTIVE[r] if (ss, pp) == (s, p)]
        for r in regions for s in stages for p in P
    }
    BUILD = {
        r: [(s, v) for s in stages for v in P if ONLINE[s, v] <= HORIZON]
        for r in regions
    }

    # ---- demand -----------------------------------------------------------
    DEMAND = {
        (r, p): sum(
            inst.demand_base[r] * (1 + inst.demand_growth[r]) ** (t - 1)
            for t in YEARS[p]
        ) / LEN[p]
        for r in regions for p in P
    }

    return Structure(
        inst=inst, blocks=blocks, LEN=LEN, START=START, P=P, HORIZON=HORIZON,
        YEARS=YEARS, OMEGA=OMEGA, YEAR_TO_P=YEAR_TO_P, dr=dr, life=life,
        lead=lead, cap_min=cap_min, cap_max=cap_max, CRF=CRF, ONLINE=ONLINE,
        MU=MU, VINTAGES=VINTAGES, BYEAR=BYEAR, ETA=ETA, ACTIVE=ACTIVE, VIN=VIN,
        BUILD=BUILD, DEMAND=DEMAND,
    )
