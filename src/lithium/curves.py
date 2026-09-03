"""The three learning and revenue curves, as pure functions.

Each takes every number it uses as an argument. That is not style: the notebook
version of `_rev_breakpoints` carried ``n=NBP_REV`` as a *default*, which froze
the breakpoint count at definition time and made a later ``NBP_REV = 3`` silently
do nothing. It was harmless only because every call site happened to override it.
The default is gone here — `n` is required — so the bug cannot come back.
(`CLAUDE.md` Part 6, "Default-argument capture".)
"""
from __future__ import annotations

import math

__all__ = [
    "capex_unit_multiplier", "capex_cum_multiplier", "capex_breakpoints",
    "revenue_breakpoints", "opex_tiers",
]


def capex_unit_multiplier(q: float, q_start: float, lr_capex: float,
                          capex_floor: float) -> float:
    """Unit capex multiplier after `q` cumulative units built.

    A learning rate of `lr_capex` means unit cost falls by that fraction per
    doubling, so the exponent is ``-log2(1 - lr)``. `capex_floor` stops the
    curve running to zero.
    """
    b = -math.log2(1 - lr_capex)
    return max(capex_floor, (q / q_start) ** (-b))


def capex_cum_multiplier(q: float, q_start: float, lr_capex: float,
                         capex_floor: float, n: int = 400) -> float:
    """Cumulative (integrated) capex multiplier from `q_start` to `q`.

    Trapezoid rule with `n` panels. The model needs the *area* under the unit
    curve, not the unit cost itself, because building the 401st unit costs what
    the curve says at 401 — not what it said at 300.
    """
    if q <= q_start:
        return 0.0
    h = (q - q_start) / n
    return sum(
        0.5 * (capex_unit_multiplier(q_start + i * h, q_start, lr_capex, capex_floor)
               + capex_unit_multiplier(q_start + (i + 1) * h, q_start, lr_capex,
                                       capex_floor)) * h
        for i in range(n)
    )


def capex_breakpoints(q_start: float, q_add: float, nbp: int, lr_capex: float,
                      capex_floor: float, panels: int = 400):
    """Breakpoint quantities and cumulative multipliers for the capex curve.

    Returns ``(QBP, CBP)``. This curve is **convex-decreasing in unit terms and
    concave cumulative**, and it enters a *minimisation*, so the chords lie below
    the truth and a free convex combination would exploit them — which is why the
    model that uses these adds SOS2. Compare :func:`revenue_breakpoints`, where
    the same shape in a maximisation needs no SOS2 at all.
    """
    QBP = [q_start + q_add * k / (nbp - 1) for k in range(nbp)]
    CBP = [capex_cum_multiplier(q, q_start, lr_capex, capex_floor, panels)
           for q in QBP]
    return QBP, CBP


def revenue_breakpoints(a_eff: float, b: float, smax: float, n: int):
    """Breakpoints for ``revenue(s) = a_eff*s - b*s^2`` on ``[0, smax]``.

    The function is CONCAVE and we MAXIMISE, so the chord between any two
    breakpoints lies BELOW the curve. A free convex combination therefore has no
    incentive to mix non-adjacent points — unlike the concave-MINIMISE case in
    Part 3, this needs no SOS2 and adds no binaries.

    `n` is required on purpose; see the module docstring.
    """
    if n < 2:
        raise ValueError(f"need at least 2 breakpoints, got n={n}")
    S = [smax * k / (n - 1) for k in range(n)]
    R = [a_eff * x - b * x * x for x in S]
    return S, R


def opex_tiers(top_by_key: dict, n_tiers: int, lr_opex: float,
               opex_floor: float):
    """Operating-cost learning tiers, calibrated off an observed top quantity.

    Returns ``(thresholds, multipliers)``, both keyed exactly as `top_by_key` is.
    Pure: it returns the dicts rather than mutating module state, which is what
    lets one implementation serve both index sets in the series — Part 3b tiers
    by stage off `prod_by_stage`, the Part 4 family tiers by region off
    `top_by_region`. Same arithmetic, different key.

    There are `n_tiers` multipliers and `n_tiers - 1` thresholds: thresholds are
    the boundaries *between* tiers, so k tiers need k-1 of them.
    """
    thresholds, multipliers = {}, {}
    for key, top in top_by_key.items():
        top = max(top, 1.0)
        q1 = top / 8.0
        thresholds[key] = [q1 * 2 ** j for j in range(n_tiers - 1)]
        multipliers[key] = [max(opex_floor, (1 - lr_opex) ** j)
                            for j in range(n_tiers)]
    return thresholds, multipliers
