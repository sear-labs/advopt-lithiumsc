"""The three government levers, as schedules rather than as mutable state.

In the notebooks these were `set_tariff` / `set_quota` / `set_local_min` /
`clear_policy`, four functions mutating three module-level dicts that
`add_region` then read behind the caller's back. That works in a notebook run
top to bottom and is a trap everywhere else: the model's behaviour depends on
which sweep cell ran last, and forgetting `clear_policy()` silently carries a
tariff into the next scenario.

So they are **builders** here. Each returns a fresh dict, `add_region` takes it
as an argument, and there is nothing to clear — the same treatment `set_tiers`
got when it became :func:`lithium.curves.opex_tiers`. Passing no schedule at all
is the Part 4c baseline, which
`tests/test_smoke.py::test_policy_superset_collapses` asserts is exact.

Who pays what, because it decides the welfare sum: a tariff is a **cost to the
exporting firm** and **revenue to the importing government**, so it appears twice
with opposite signs and nets out except for the behavioural change it induces. A
quota induces the same behavioural change and collects nothing — the scarcity
rent goes to whoever holds the quota rather than to the treasury. That asymmetry
is the entire reason the two instruments differ in welfare.
"""
from __future__ import annotations

from .structure import Structure

__all__ = ["tariff_schedule", "quota_schedule", "local_content_schedule",
           "welfare"]


def tariff_schedule(regions, rate: float, on_imports_to: str | None = None) -> dict:
    """Per-unit duty on cross-region sales, keyed ``(seller, market)``.

    `on_imports_to=None` tariffs every market; naming a region tariffs only
    imports into that one. Own-region sales are never tariffed — a government
    does not levy a duty on its own firm's domestic sales.
    """
    return {(rf, rt): rate
            for rf in regions for rt in regions
            if rf != rt and (on_imports_to is None or rt == on_imports_to)}


def quota_schedule(regions, cap: float, on_imports_to: str | None = None) -> dict:
    """Per-period cap on cross-region sales, keyed ``(seller, market)``."""
    return {(rf, rt): cap
            for rf in regions for rt in regions
            if rf != rt and (on_imports_to is None or rt == on_imports_to)}


def local_content_schedule(regions, level: float,
                           market: str | None = None) -> dict:
    """Per-period floor on the domestic firm's own-market sales, keyed by market.

    Note the direction of this one. A tariff raises a *rival's* cost; a local
    content floor constrains *your own* firm's optimisation. If it binds in an
    unwanted direction it destroys value domestically, which is why it can
    backfire on its intended beneficiary.
    """
    return {rt: level for rt in regions
            if market is None or rt == market}


def welfare(struct: Structure, sales: dict, profits: dict, *, b_slp: dict,
            tariff: dict | None = None) -> dict:
    """Consumer surplus + producer profit + tariff revenue, all discounted.

    `sales` is ``{region: {(market, period): quantity}}`` as `cournot_iterate`
    returns it; `profits` is ``{region: profit}``.

    Consumer surplus is the triangle under linear inverse demand,
    ``0.5 * B * Q^2`` — which is *not* the same as the area above price, and is
    the form consistent with how price is computed elsewhere in this package.
    """
    tariff = dict(tariff or {})
    regions, P, OMEGA = struct.regions, struct.P, struct.OMEGA
    cs = sum(OMEGA[p] * 0.5 * b_slp[rt, p]
             * (sum(sales[r][rt, p] for r in regions)) ** 2
             for rt in regions for p in P)
    tr = sum(OMEGA[p] * tariff.get((r, rt), 0.0) * sales[r][rt, p]
             for r in regions for rt in regions for p in P)
    return dict(consumer_surplus=cs, tariff_revenue=tr,
                producer_profit=sum(profits.values()),
                total=cs + tr + sum(profits.values()))
