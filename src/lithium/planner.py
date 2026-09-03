"""The cooperative planner: minimise weighted cost subject to meeting demand.

Used in Part 4c only to *calibrate* the operating-cost learning tiers — the
planner is solved once with ``learning='capacity'`` to find how much cumulative
production the chain can plausibly reach, and the tier thresholds are set off
that. It is also the benchmark the earlier notebooks in the series compare
against, so it lives here rather than inside `games`.
"""
from __future__ import annotations

import gurobipy as gp
from gurobipy import GRB

from .regions import add_region
from .structure import Structure

__all__ = ["solve_planner"]


def solve_planner(struct: Structure, *, w1: float = 0.5, learning: str = "both",
                  pen_short: float, mipgap: float = 0.005, quiet: bool = True,
                  **region_kw) -> gp.Model:
    """Minimise ``w1*cost(R1) + (1-w1)*cost(R2) + shortfall penalty``.

    `region_kw` is forwarded to :func:`lithium.regions.add_region` — the caller
    passes `transport`, `pen_dispose`, `price_fixed`, `capex_curve` and the rest
    explicitly, so every knob crosses the notebook/package boundary in the open.

    Returns the solved model, with `_H` (per-region handles), `_short` and `_pen`
    attached for inspection.
    """
    regions, P, OMEGA = struct.regions, struct.P, struct.OMEGA
    m = gp.Model()
    m.Params.OutputFlag = 0 if quiet else 1
    m.Params.MIPGap = mipgap

    H = {r: add_region(m, r, struct, learning=learning, **region_kw)
         for r in regions}
    short = m.addVars(regions, P, lb=0.0, name='short')
    m.addConstrs((gp.quicksum(H[r]['sale'][rt, p] for r in regions) + short[rt, p]
                  >= struct.DEMAND[rt, p] for rt in regions for p in P),
                 name='demand')
    pen = gp.quicksum(OMEGA[p] * pen_short * short[rt, p]
                      for rt in regions for p in P)
    m.setObjective(w1 * H[regions[0]]['cost'] + (1 - w1) * H[regions[1]]['cost']
                   + pen, GRB.MINIMIZE)
    m.optimize()
    m._H, m._short, m._pen = H, short, pen
    return m
