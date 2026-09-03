"""The two-stage capacity network behind Parts 2b and 2c.

This is a **third instance**, and it is worth being explicit about that. It is
not Parts 1 and 2's six-site multi-period network, and it is not the Part 4
family's two-region Cournot chain. It is a single-period, three-stage,
two-region capacity-and-flow problem: six nodes, twelve arcs, and a scenario set
over demand.

Stage 1 chooses which nodes to open (`y`) and how much capacity to build (`c`).
Stage 2, once the scenario is known, chooses throughput (`x`), inter-region
flows (`f`) and unmet demand (`u`). The recourse is a **linear** program with the
capacity-linking rows ``x[n] <= c[n]``, and the duals of exactly those rows are
what an L-shaped cut is made of. That is why Part 2b uses this model rather than
Part 1's: there, capacity is tangled up with vintages, lead times and binaries,
and the clean dual does not exist.

Parts 2b and 2c share the node structure and the cost tables and differ in what
is uncertain:

- **2b** varies demand only, and asks how to *solve* the problem by
  decomposition (`extensive_form` vs `lshaped`).
- **2c** adds a region-specific cost shock and asks what to *optimise*
  (`risk_model`, with expectation, CVaR, minimax and a hybrid).

`region_cost` and the shock multipliers are therefore used by 2c's model and not
by 2b's. They are different models, not one model with a flag.

**Name collisions are deliberate and are why this module is not flattened into
the package namespace.** `extensive_form`, `subproblem` and `solve` all exist in
`lithium.stochastic` or `lithium.core` meaning something else, on a different
model. Import this module by name::

    from lithium import twostage as T
    inst = T.load_twostage_instance()
    st = T.build_twostage_structure(inst)
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from pathlib import Path

import gurobipy as gp
from gurobipy import GRB

# Solve every LP and MILP here at a gap far tighter than anything being
# measured. Part 2b differences an L-shaped bound against the extensive form's
# objective and asserts they agree to 1e-5; Part 2c differences plan means that
# sit 0.06% apart. See CLAUDE.md Part 6, and the note in stochastic.py.
MIPGAP_DEFAULT = 1e-9


# ---------------------------------------------------------------- instance ---
@dataclass(frozen=True)
class TwoStageInstance:
    """The tables both Part 2b and Part 2c read. Knobs are NOT in here."""
    stages: tuple[str, ...]
    regions: tuple[str, ...]
    fix: dict[str, float]           # stage -> fixed cost of opening a node
    unit: dict[str, float]          # stage -> cost per unit of capacity
    opc: dict[str, float]           # stage -> operating cost per unit throughput
    eta: dict[str, float]           # stage -> yield
    demand_base: dict[str, float]   # region -> demand scale
    region_cost: dict[str, float]   # region -> operating cost multiplier (2c only)


def read_twostage_tables(source: Path | str | None = None):
    """Read the two CSVs, from `source`, then `data/raw/`, then package data."""
    import pandas as pd

    names = ("twostage_stages.csv", "twostage_regions.csv")
    roots = []
    if source is not None:
        roots.append(Path(source))
    roots.append(Path(__file__).resolve().parents[2] / "data" / "raw")
    roots.append(Path(__file__).resolve().parent / "data")
    for root in roots:
        if all((root / n).exists() for n in names):
            return tuple(pd.read_csv(root / n) for n in names), root
    raise FileNotFoundError(
        f"could not find {names} in any of {[str(r) for r in roots]}")


def load_twostage_instance(source: Path | str | None = None) -> TwoStageInstance:
    (stages_df, regions_df), _root = read_twostage_tables(source)
    return TwoStageInstance(
        stages=tuple(stages_df["stage"]),
        regions=tuple(regions_df["region"]),
        fix=dict(zip(stages_df["stage"], stages_df["fix"].astype(float))),
        unit=dict(zip(stages_df["stage"], stages_df["unit"].astype(float))),
        opc=dict(zip(stages_df["stage"], stages_df["opc"].astype(float))),
        eta=dict(zip(stages_df["stage"], stages_df["eta"].astype(float))),
        demand_base=dict(zip(regions_df["region"],
                             regions_df["demand_base"].astype(float))),
        region_cost=dict(zip(regions_df["region"],
                             regions_df["region_cost"].astype(float))),
    )


# --------------------------------------------------------------- structure ---
@dataclass(frozen=True)
class TwoStageStructure:
    """Sets derived from the instance, plus the knobs the model needs."""
    inst: TwoStageInstance
    nodes: tuple[tuple[str, str], ...]
    arcs: tuple[tuple[str, str, str], ...]
    tau: dict[tuple[str, str], float]
    cmin: float
    cmax: float
    pen: float

    @property
    def stages(self):
        return self.inst.stages

    @property
    def regions(self):
        return self.inst.regions


def build_twostage_structure(inst: TwoStageInstance, *, cmin: float = 5.0,
                             cmax: float = 70.0, pen: float = 30.0,
                             tau_own: float = 0.3,
                             tau_cross: float = 1.5) -> TwoStageStructure:
    """Nodes, arcs and the transport matrix. Everything here is arithmetic."""
    nodes = tuple((s, r) for s in inst.stages for r in inst.regions)
    arcs = tuple((s, a, b) for s in inst.stages
                 for a in inst.regions for b in inst.regions)
    tau = {(a, b): (tau_own if a == b else tau_cross)
           for a in inst.regions for b in inst.regions}
    return TwoStageStructure(inst=inst, nodes=nodes, arcs=arcs, tau=tau,
                             cmin=cmin, cmax=cmax, pen=pen)


# --------------------------------------------------------------- scenarios ---
def demand_scenarios(st: TwoStageStructure, n: int = 24, seed: int = 11,
                     lo: float = 0.55, hi: float = 1.55):
    """Part 2b's tree: demand only, uniform on [lo, hi] times the base.

    The draw order is fixed and reproduced exactly: one call per region per
    scenario, regions in instance order. Changing that order changes the tree
    even at the same seed, so it is part of the definition, not an detail.
    """
    rng = random.Random(seed)
    out = []
    for k in range(n):
        d = {}
        for r in st.regions:
            d[r] = st.inst.demand_base[r] * (lo + (hi - lo) * rng.random())
        out.append((f"k{k}", 1.0 / n, d))
    return out


def shock_scenarios(st: TwoStageStructure, n: int = 40, seed: int = 7,
                    lo: float = 0.6, span: float = 0.9,
                    hit_prob: float = 0.15, hit_size: float = 2.6,
                    steady_jitter: float = 0.15, disrupted: str | None = None):
    """Part 2c's tree: demand PLUS a region-specific operating-cost shock.

    A shock that scaled every region equally could not change which plan is
    best -- it would only rescale the objective. The shock has to fall unevenly
    for risk aversion to move the *plan* rather than only the reported metric.
    `disrupted` (default: the first region) is cheap but occasionally hit;
    the others carry a small steady jitter.

    Draw order per scenario: the disruption coin, then demand for each region in
    order, then the multiplier for each region in order -- and the disrupted
    region only consumes a draw when the coin came up. Reproduced exactly.
    """
    rng = random.Random(seed)
    hot = disrupted if disrupted is not None else st.regions[0]
    out = []
    for k in range(n):
        hit = rng.random() < hit_prob
        d = {}
        for r in st.regions:
            d[r] = st.inst.demand_base[r] * (lo + span * rng.random())
        mult = {}
        for r in st.regions:
            if r == hot:
                mult[r] = 1.0 + (hit_size * rng.random() if hit else 0.0)
            else:
                mult[r] = 1.0 + steady_jitter * rng.random()
        out.append((f"k{k}", 1.0 / n, d, mult))
    return out


def _demand_of(scen):
    return scen[2]


def _mult_of(scen, regions):
    return scen[3] if len(scen) > 3 else {r: 1.0 for r in regions}


# ------------------------------------------------------- the shared blocks ---
def _second_stage(st: TwoStageStructure, m: gp.Model, cap, scen, *,
                  suffix: str = "", use_region_cost: bool = False):
    """Add one scenario's recourse block and return (its cost expression, u).

    `cap` maps a node to either a Gurobi variable (extensive form) or a float
    (a fixed plan). Both work: the capacity rows are built the same way, which
    is what makes the recourse LP and the monolithic model the same model.
    """
    inst, nodes, arcs, regions = st.inst, st.nodes, st.arcs, st.regions
    x = m.addVars(nodes, lb=0.0, name=f"x{suffix}")
    f = m.addVars(arcs, lb=0.0, name=f"f{suffix}")
    u = m.addVars(regions, lb=0.0, name=f"u{suffix}")

    link = m.addConstrs((x[n] <= cap[n] for n in nodes), name=f"cap{suffix}")
    m.addConstrs((inst.eta[s] * x[s, r] == f.sum(s, r, "*")
                  for (s, r) in nodes), name=f"out{suffix}")
    for i, s in enumerate(inst.stages):
        if i == 0:
            continue
        prev = inst.stages[i - 1]
        m.addConstrs((f.sum(prev, "*", r) == x[s, r] for r in regions),
                     name=f"in_{s}{suffix}")
    last = inst.stages[-1]
    d = _demand_of(scen)
    m.addConstrs((f.sum(last, "*", r) + u[r] >= d[r] for r in regions),
                 name=f"dem{suffix}")

    mult = _mult_of(scen, regions)
    rc = inst.region_cost if use_region_cost else {r: 1.0 for r in regions}
    cost = (gp.quicksum(mult[r] * rc[r] * inst.opc[s] * x[s, r]
                        for (s, r) in nodes)
            + gp.quicksum(st.tau[a, b] * f[s, a, b] for (s, a, b) in arcs)
            + gp.quicksum(st.pen * u[r] for r in regions))
    return cost, u, link


def _first_stage(st: TwoStageStructure, m: gp.Model):
    """Open/size decisions and their cost. Returns (y, c, cost expression)."""
    inst, nodes = st.inst, st.nodes
    y = m.addVars(nodes, vtype=GRB.BINARY, name="y")
    c = m.addVars(nodes, lb=0.0, ub=st.cmax, name="c")
    m.addConstrs((c[n] <= st.cmax * y[n] for n in nodes), name="ub")
    m.addConstrs((c[n] >= st.cmin * y[n] for n in nodes), name="lb")
    cost = gp.quicksum(inst.fix[s] * y[s, r] + inst.unit[s] * c[s, r]
                       for (s, r) in nodes)
    return y, c, cost


# ------------------------------------------------------------ Part 2b: L-shaped
def recourse(st: TwoStageStructure, scen, cap, *, duals: bool = True,
             use_region_cost: bool = False):
    """Q_k(cap): the recourse LP for one scenario, given a FIXED capacity plan.

    Returns ``(value, beta)`` where `beta` are the duals of the capacity-linking
    rows. Those duals are the subgradient of Q_k with respect to capacity, which
    is precisely what an optimality cut needs -- see `lshaped`.
    """
    m = gp.Model()
    m.Params.OutputFlag = 0
    cost, _u, link = _second_stage(st, m, cap, scen,
                                   use_region_cost=use_region_cost)
    m.setObjective(cost, GRB.MINIMIZE)
    m.optimize()
    assert m.Status == GRB.OPTIMAL, (
        f"recourse LP for {scen[0]} is not optimal (status {m.Status}); an "
        f"L-shaped cut built from a non-optimal subproblem is not valid")
    beta = {n: link[n].Pi for n in st.nodes} if duals else None
    return m.ObjVal, beta


def extensive_form(st: TwoStageStructure, scens, *,
                   mipgap: float | None = MIPGAP_DEFAULT,
                   use_region_cost: bool = False) -> gp.Model:
    """Every scenario in one monolithic model. The answer decomposition must match.

    Not to be confused with `lithium.stochastic.extensive_form`, which is the
    same idea on Parts 1 and 2's network. See this module's docstring.
    """
    m = gp.Model("twostage_extensive_form")
    m.Params.OutputFlag = 0
    if mipgap is not None:
        m.Params.MIPGap = mipgap
    y, c, first = _first_stage(st, m)
    second = gp.LinExpr()
    for j, scen in enumerate(scens):
        cost, _u, _link = _second_stage(st, m, c, scen, suffix=f"_{j}",
                                        use_region_cost=use_region_cost)
        second += scen[1] * cost
    m.setObjective(first + second, GRB.MINIMIZE)
    m._y, m._c, m._first = y, c, first
    return m


def capacity_plan(m: gp.Model, st: TwoStageStructure) -> dict:
    return {n: m._c[n].X for n in st.nodes}


def lshaped(st: TwoStageStructure, scens, *, max_iter: int = 60,
            tol: float = 1e-6, multicut: bool = True,
            mipgap: float | None = MIPGAP_DEFAULT, verbose: bool = False) -> dict:
    """Benders / L-shaped decomposition.

    The master holds only the first-stage decisions plus a placeholder `theta`
    for the recourse cost. Each iteration solves the master (a relaxation, so
    its objective is a valid LOWER bound), evaluates the true recourse at the
    proposed plan (giving a valid UPPER bound), and adds an optimality cut

        theta_k >= Q_k(chat) + beta_k . (c - chat)

    which is exact at `chat` and an underestimate everywhere else, because Q_k
    is convex in the capacity right-hand side.

    `multicut=False` keeps one aggregated theta instead of one per scenario:
    fewer rows per iteration, a weaker master, and more iterations.
    """
    m = gp.Model("twostage_master")
    m.Params.OutputFlag = 0
    if mipgap is not None:
        m.Params.MIPGap = mipgap
    y, c, first = _first_stage(st, m)
    # lb=0 is valid because every second-stage cost coefficient is nonnegative.
    if multicut:
        th = m.addVars(range(len(scens)), lb=0.0, name="theta")
        recourse_term = gp.quicksum(scens[j][1] * th[j]
                                    for j in range(len(scens)))
    else:
        th_one = m.addVar(lb=0.0, name="theta")
        recourse_term = th_one
    m.setObjective(first + recourse_term, GRB.MINIMIZE)

    hist, UB, best_plan, subsolves = [], float("inf"), None, 0
    for it in range(1, max_iter + 1):
        m.optimize()
        assert m.SolCount > 0, f"the master is infeasible at iteration {it}"
        LB = m.ObjVal
        chat = {n: c[n].X for n in st.nodes}
        fc = sum(st.inst.fix[s] * y[s, r].X + st.inst.unit[s] * c[s, r].X
                 for (s, r) in st.nodes)

        total, ncuts = fc, 0
        if multicut:
            for j, scen in enumerate(scens):
                Qj, beta = recourse(st, scen, chat)
                subsolves += 1
                total += scen[1] * Qj
                if th[j].X < Qj - tol * max(1.0, abs(Qj)):
                    m.addConstr(th[j] >= Qj + gp.quicksum(
                        beta[n] * (c[n] - chat[n]) for n in st.nodes))
                    ncuts += 1
        else:
            Qbar, bbar = 0.0, {n: 0.0 for n in st.nodes}
            for scen in scens:
                Qj, beta = recourse(st, scen, chat)
                subsolves += 1
                Qbar += scen[1] * Qj
                for n in st.nodes:
                    bbar[n] += scen[1] * beta[n]
            total += Qbar
            if th_one.X < Qbar - tol * max(1.0, abs(Qbar)):
                m.addConstr(th_one >= Qbar + gp.quicksum(
                    bbar[n] * (c[n] - chat[n]) for n in st.nodes))
                ncuts += 1

        if total < UB:
            UB, best_plan = total, dict(chat)
        gap = (UB - LB) / max(1e-9, abs(UB))
        hist.append(dict(iter=it, LB=LB, UB=UB, gap=gap, cuts=ncuts))
        if verbose:
            print(f"  it {it:3d}  LB {LB:10.3f}  UB {UB:10.3f}  "
                  f"gap {100 * gap:7.4f}%  cuts {ncuts}")
        if ncuts == 0 or gap < 1e-6:
            break
    return dict(value=UB, bound=hist[-1]["LB"], iters=len(hist), hist=hist,
                plan=best_plan, subsolves=subsolves, model=m)


# ---------------------------------------------------------- Part 2c: risk ---
RISK_MODES = ("neutral", "cvar", "robust", "hybrid")


def risk_model(st: TwoStageStructure, scens, mode: str, *, alpha: float = 0.10,
               lam: float = 0.01, tiebreak: float = 0.0,
               mipgap: float | None = MIPGAP_DEFAULT) -> dict:
    """One model, four objectives, over the same scenario set.

    ``neutral`` minimises the expectation. ``cvar`` minimises CVaR at level
    `alpha` via the Rockafellar-Uryasev linearisation. ``robust`` minimises the
    worst case. ``hybrid`` minimises ``lam * E + (1 - lam) * CVaR``.

    `tiebreak` adds a small multiple of the expectation to the CVaR objective.
    It changes nothing about which plans are CVaR-optimal; it only selects the
    lowest-mean plan among them. On this instance that set is large, so without
    it the reported mean is whichever tied plan the solver happened to return.

    **The returned per-scenario costs are the model's own, and for `robust` they
    are not a property of the plan** -- minimax constrains only the worst
    scenario, leaving recourse in every other one free. Use
    `evaluate_capacity` to score a plan; see its docstring.
    """
    if mode not in RISK_MODES:
        raise ValueError(f"unknown mode {mode!r}; expected one of {RISK_MODES}")
    m = gp.Model(f"twostage_{mode}")
    m.Params.OutputFlag = 0
    if mipgap is not None:
        m.Params.MIPGap = mipgap
    y, c, first = _first_stage(st, m)

    cost = {}
    for j, scen in enumerate(scens):
        cost[j], _u, _link = _second_stage(st, m, c, scen, suffix=f"_{j}",
                                           use_region_cost=True)

    n = len(scens)
    # Rockafellar-Uryasev: eta is the VaR level and z the excess above it.
    eta = m.addVar(lb=-GRB.INFINITY, name="eta")
    z = m.addVars(range(n), lb=0.0, name="z")
    m.addConstrs((z[j] >= first + cost[j] - eta for j in range(n)), name="cvar")
    CVAR = eta + (1.0 / alpha) * gp.quicksum(scens[j][1] * z[j]
                                             for j in range(n))
    EXP = first + gp.quicksum(scens[j][1] * cost[j] for j in range(n))

    if mode == "neutral":
        m.setObjective(EXP, GRB.MINIMIZE)
    elif mode == "cvar":
        m.setObjective(CVAR + tiebreak * EXP, GRB.MINIMIZE)
    elif mode == "robust":
        w = m.addVar(lb=0.0, name="worst")
        m.addConstrs((w >= first + cost[j] for j in range(n)), name="minimax")
        m.setObjective(w + tiebreak * EXP, GRB.MINIMIZE)
    else:
        m.setObjective(lam * EXP + (1 - lam) * CVAR, GRB.MINIMIZE)

    m.optimize()
    assert m.SolCount > 0, f"the {mode} model found no solution"
    realised = sorted(first.getValue() + cost[j].getValue() for j in range(n))
    ncrit = max(1, int(round(alpha * n)))
    return dict(mode=mode, model=m,
                mean=sum(realised) / n,
                cvar=sum(realised[-ncrit:]) / ncrit,
                worst=realised[-1],
                capex=first.getValue(),
                plan={nd: c[nd].X for nd in st.nodes},
                dist=realised)


def evaluate_capacity(st: TwoStageStructure, scens, plan: dict, *,
                      use_region_cost: bool = True) -> dict:
    """Score a FIXED capacity plan by re-optimising recourse in every scenario.

    This is the only way to compare plans from different objectives, and it is
    not a formality. Minimax constrains only the worst scenario, so the recourse
    variables in every other scenario are free as far as its objective is
    concerned and the solver may return any feasible values for them. Part 2c
    originally reported the mean of exactly those values: 2245.5 for a plan
    whose true mean is 1642.2 -- a 37% overstatement, on a plan identical to the
    CVaR one.

    CLAUDE.md Part 6: match the comparison before interpreting the difference.
    """
    capex = sum(st.inst.fix[s] * (1.0 if plan[s, r] > 1e-6 else 0.0)
                + st.inst.unit[s] * plan[s, r] for (s, r) in st.nodes)
    totals, probs = [], []
    for scen in scens:
        q, _ = recourse(st, scen, plan, duals=False,
                        use_region_cost=use_region_cost)
        totals.append(capex + q)
        probs.append(scen[1])
    order = sorted(range(len(totals)), key=lambda i: totals[i])
    srt = [totals[i] for i in order]
    return dict(capex=capex, dist=srt, totals=totals,
                mean=sum(p * t for p, t in zip(probs, totals)),
                worst=max(totals))


def cvar_of(dist, alpha: float) -> float:
    """CVaR at level `alpha` of an equally weighted, ASCENDING cost sample."""
    n = len(dist)
    ncrit = max(1, int(round(alpha * n)))
    return sum(sorted(dist)[-ncrit:]) / ncrit
