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
from .core import (CoreStructure, build, build_core_structure, build_plan,
                   capex_pv_multiplier, evaluate_plan, learning_breakpoints,
                   rolling_horizon, solve, staggered_years)
from .curves import (capex_breakpoints, capex_cum_multiplier,
                     capex_unit_multiplier, opex_tiers, revenue_breakpoints)
from .games import (best_response_cournot, best_response_fixed_price,
                    best_response_miqp, cournot_iterate,
                    cournot_iterate_miqp, inverse_demand,
                    iterate_fixed_price, joint_profit_max, market_outcome)
from .instance import Instance, load_instance, read_tables
from .network_instance import (NetworkInstance, load_network_instance,
                               read_network_tables)
from .mpec import (follower_legacy, follower_marginal_cost, follower_qp,
                   stackelberg)
from .planner import solve_planner
from .policy import (local_content_schedule, quota_schedule, tariff_schedule,
                     welfare)
from .regions import add_region
from .stochastic import (eval_strategy_by_scenario, evaluate_stage1,
                         extensive_form, mean_value_stage1,
                         perfect_info_by_scenario, ph_three_case,
                         progressive_hedging, scenarios, scenarios_n,
                         stage1_keys, strategy_stage1, subproblem,
                         three_case_comparison, wait_and_see)
from .structure import Structure, build_structure
# `twostage` is imported as a MODULE, not flattened. Its `extensive_form`,
# `recourse` and `risk_model` act on a different instance from the
# same-named things in `stochastic` and `core`, and flattening them would
# shadow one with the other. See twostage.py's docstring.
from . import twostage
from .twostage import (TwoStageInstance, TwoStageStructure,
                       build_twostage_structure, demand_scenarios,
                       evaluate_capacity, load_twostage_instance, lshaped,
                       risk_model, shock_scenarios)

__version__ = "0.1.0"

__all__ = [
    "Instance", "load_instance", "read_tables",
    "NetworkInstance", "load_network_instance", "read_network_tables",
    "Structure", "build_structure",
    "capex_unit_multiplier", "capex_cum_multiplier", "capex_breakpoints",
    "revenue_breakpoints", "opex_tiers",
    "add_region", "solve_planner",
    "CoreStructure", "build_core_structure", "build", "build_plan",
    "capex_pv_multiplier", "learning_breakpoints", "solve",
    "evaluate_plan", "rolling_horizon", "staggered_years",
    "scenarios", "scenarios_n", "extensive_form", "stage1_keys",
    "subproblem", "progressive_hedging", "evaluate_stage1",
    "wait_and_see", "mean_value_stage1", "eval_strategy_by_scenario",
    "strategy_stage1", "perfect_info_by_scenario",
    "three_case_comparison", "ph_three_case",
    "twostage", "TwoStageInstance", "TwoStageStructure",
    "load_twostage_instance", "build_twostage_structure",
    "demand_scenarios", "shock_scenarios", "lshaped", "risk_model",
    "evaluate_capacity",
    "stackelberg", "follower_qp", "follower_marginal_cost", "follower_legacy",
    "tariff_schedule", "quota_schedule", "local_content_schedule", "welfare",
    "inverse_demand", "best_response_cournot", "cournot_iterate",
    "joint_profit_max", "market_outcome",
    "best_response_fixed_price", "iterate_fixed_price",
    "best_response_miqp", "cournot_iterate_miqp",
    "__version__",
]
