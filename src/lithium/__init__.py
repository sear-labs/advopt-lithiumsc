"""lithium — the streamlined half of the lithium supply-chain modelling series.

`CLAUDE.md` Part 4 is the map. This package is engineering territory: one
implementation of each model, every parameter arriving as an argument, written
for a machine to run a thousand times. The notebooks are teaching territory:
they build the same models **by hand**, because the steps are the lesson.

The two halves hold the same model on purpose. What makes that safe is the
agreement assertion at the end of every teaching notebook, which imports this
package, runs the same case, and asserts the two objectives agree to 1e-9.

Quick start::

    from lithium import load_instance, build_structure
    inst = load_instance()                 # the packaged CSVs
    struct = build_structure(inst)         # sets, windows, discount weights
"""
from .curves import (capex_breakpoints, capex_cum_multiplier,
                     capex_unit_multiplier, opex_tiers, revenue_breakpoints)
from .games import (best_response_cournot, cournot_iterate, inverse_demand,
                    joint_profit_max, market_outcome)
from .instance import Instance, load_instance, read_tables
from .planner import solve_planner
from .regions import add_region
from .structure import Structure, build_structure

__version__ = "0.1.0"

__all__ = [
    "Instance", "load_instance", "read_tables",
    "Structure", "build_structure",
    "capex_unit_multiplier", "capex_cum_multiplier", "capex_breakpoints",
    "revenue_breakpoints", "opex_tiers",
    "add_region", "solve_planner",
    "inverse_demand", "best_response_cournot", "cournot_iterate",
    "joint_profit_max", "market_outcome",
    "__version__",
]
