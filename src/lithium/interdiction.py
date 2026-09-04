"""Network interdiction and defence, behind Part 4f.

A **fifth instance**, and the smallest in the series: a four-stage chain across
three regions expressed as a max-flow network, with a super-source standing for
the reserve base and a super-sink for aggregate demand. Fourteen nodes, thirty-
three arcs.

It is a flow network rather than a capacity-expansion model because the question
is different. Everywhere else in the series the question is *what should be
built*; here the chain already exists and the question is *what breaks it, and
what is worth protecting*. That is a three-level problem -- defender, attacker,
operator -- and it needs a model small enough that the middle level can be solved
exactly.

**The super-source and super-sink are modelling artifacts and are deliberately
not attackable.** They stand for a reserve base and a demand aggregate, not
physical links anyone can sever. Leave them attackable and the attacker simply
cuts the three source arcs, which is both trivial and meaningless.

The attacker's problem is the interesting one. Maximising damage means minimising
the operator's max flow, and a max-flow minimisation cannot be written directly
as a single MILP. Duality fixes it: by max-flow/min-cut the operator's optimum
equals the minimum cut, which IS a minimisation, so the attacker minimises the
cut capacity over cuts and interdiction decisions jointly. `omega >= gamma -
zeta` is the linearisation of "an interdicted arc costs nothing to cut".
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass
from pathlib import Path

import gurobipy as gp
from gurobipy import GRB


@dataclass(frozen=True)
class InterdictionInstance:
    """Per-region reserve and delivery capacities. Stage-to-stage caps are knobs."""
    regions: tuple[str, ...]
    reserve_cap: dict[str, float]
    delivery_cap: dict[str, float]


def load_interdiction_instance(source: Path | str | None = None
                               ) -> InterdictionInstance:
    import pandas as pd

    name = "interdiction_regions.csv"
    roots = []
    if source is not None:
        roots.append(Path(source))
    roots.append(Path(__file__).resolve().parents[2] / "data" / "raw")
    roots.append(Path(__file__).resolve().parent / "data")
    for root in roots:
        if (root / name).exists():
            df = pd.read_csv(root / name)
            return InterdictionInstance(
                regions=tuple(df["region"]),
                reserve_cap=dict(zip(df["region"],
                                     df["reserve_cap"].astype(float))),
                delivery_cap=dict(zip(df["region"],
                                      df["delivery_cap"].astype(float))))
    raise FileNotFoundError(f"could not find {name} in {[str(r) for r in roots]}")


@dataclass(frozen=True)
class FlowNetwork:
    """The expanded network: nodes, arcs, capacities, and what may be attacked."""
    inst: InterdictionInstance
    stages: tuple[str, ...]
    nodes: tuple[str, ...]
    arcs: tuple[tuple[str, str], ...]
    cap: dict[tuple[str, str], float]
    attackable: tuple[tuple[str, str], ...]


def node(stage: str, region: str) -> str:
    return f"{stage}:{region}"


def build_flow_network(inst: InterdictionInstance, *,
                       stages=("MINE", "REF", "CAM", "CELL"),
                       cap_intra: float = 40.0,
                       cap_inter: float = 16.0) -> FlowNetwork:
    """Expand the instance into a flow network.

    `cap_intra` and `cap_inter` are knobs: staying inside a region is generous,
    crossing is thinner. Their ratio is what makes geography matter, and setting
    them equal makes every region interchangeable.
    """
    regions = inst.regions
    nodes = (("SRC",) + tuple(node(s, r) for s in stages for r in regions)
             + ("SNK",))
    cap: dict[tuple[str, str], float] = {}
    for r in regions:
        cap[("SRC", node(stages[0], r))] = inst.reserve_cap[r]
    for a, b in zip(stages, stages[1:]):
        for r1 in regions:
            for r2 in regions:
                cap[(node(a, r1), node(b, r2))] = (cap_intra if r1 == r2
                                                   else cap_inter)
    for r in regions:
        cap[(node(stages[-1], r), "SNK")] = inst.delivery_cap[r]
    arcs = tuple(cap)
    attackable = tuple(a for a in arcs if a[0] != "SRC" and a[1] != "SNK")
    return FlowNetwork(inst=inst, stages=tuple(stages), nodes=nodes, arcs=arcs,
                       cap=cap, attackable=attackable)


# ------------------------------------------------------- the operator (LP) ---
def max_flow(net: FlowNetwork, interdicted=frozenset()):
    """The operator's problem: push as much as possible, given what is cut.

    Returns ``(value, flow)``. This is a pure LP -- no binaries anywhere -- which
    is what makes the duality argument in `attacker_best_response` available.
    """
    m = gp.Model()
    m.Params.OutputFlag = 0
    f = {a: m.addVar(lb=0.0, ub=(0.0 if a in interdicted else net.cap[a]))
         for a in net.arcs}
    for v in net.nodes:
        if v in ("SRC", "SNK"):
            continue
        m.addConstr(gp.quicksum(f[a] for a in net.arcs if a[1] == v)
                    == gp.quicksum(f[a] for a in net.arcs if a[0] == v),
                    name=f"bal_{v}")
    m.setObjective(gp.quicksum(f[a] for a in net.arcs if a[0] == "SRC"),
                   GRB.MAXIMIZE)
    m.optimize()
    assert m.Status == GRB.OPTIMAL, f"max-flow LP not optimal (status {m.Status})"
    return m.ObjVal, {a: f[a].X for a in net.arcs}


# --------------------------------------------------- the attacker (MILP) -----
def attacker_best_response(net: FlowNetwork, budget: int,
                           fortified=frozenset(), *, mipgap: float | None = None):
    """Cut `budget` arcs to minimise the operator's throughput -- exactly.

    Written as a minimum cut rather than as "minimise a max", which no single
    MILP can express. `pi` are the node potentials, `gamma` the arc cut
    indicators, `zeta` the interdiction decisions, and

        omega >= gamma - zeta

    is the linearisation: an arc that has been interdicted contributes nothing to
    the cut's cost, because it is already gone.
    """
    m = gp.Model()
    m.Params.OutputFlag = 0
    if mipgap is not None:
        m.Params.MIPGap = mipgap
    pi = m.addVars(net.nodes, lb=0.0, name="pi")
    gam = m.addVars(net.arcs, lb=0.0, name="gamma")
    om = m.addVars(net.arcs, lb=0.0, name="omega")
    zet = m.addVars(net.arcs, vtype=GRB.BINARY, name="zeta")

    m.addConstrs((gam[a] - pi[a[0]] + pi[a[1]] >= 0 for a in net.arcs), name="cut")
    m.addConstr(pi["SRC"] - pi["SNK"] >= 1, name="sep")
    m.addConstrs((om[a] >= gam[a] - zet[a] for a in net.arcs), name="lin")
    m.addConstr(gp.quicksum(zet[a] for a in net.attackable) <= budget,
                name="budget")
    for a in net.arcs:
        if a not in set(net.attackable) or a in fortified:
            m.addConstr(zet[a] == 0)
    m.setObjective(gp.quicksum(net.cap[a] * om[a] for a in net.arcs), GRB.MINIMIZE)
    m.optimize()
    assert m.SolCount > 0, f"the attacker MILP found no solution ({m.Status})"
    return m.ObjVal, frozenset(a for a in net.arcs if zet[a].X > 0.5)


# ------------------------------------------------------- the defender --------
def defender_enumerate(net: FlowNetwork, bdef: int, batk: int, *,
                       candidates=None):
    """Fortify `bdef` arcs by brute force over every combination.

    `candidates` defaults to the FULL interdictable set. Restricting it to arcs a
    previously-unfortified attacker happened to choose is a heuristic and not an
    economy: Part 4f section 10 exhibits an instance where it loses 5.0 units of
    throughput, because fortifying an arc changes which arcs are worth attacking.

    Returns ``(value, fortification, attacker_response)``.
    """
    cands = sorted(net.attackable) if candidates is None else sorted(candidates)
    best = (-1.0, None, None)
    for combo in itertools.combinations(cands, bdef):
        val, atk = attacker_best_response(net, batk, fortified=frozenset(combo))
        if val > best[0]:
            best = (val, combo, atk)
    return best


def defender_master(net: FlowNetwork, attacks, bdef: int, ub_theta: float):
    """Fortify to maximise the worst throughput over a RETAINED set of attacks.

    A relaxation of the defender's problem -- it only defends against the attacks
    it has been shown -- so its objective is a valid UPPER bound on what any
    fortification can guarantee. That is what makes `best_response_intersection`
    terminate with a certificate rather than a hope.
    """
    m = gp.Model()
    m.Params.OutputFlag = 0
    phi = m.addVars(net.attackable, vtype=GRB.BINARY, name="phi")
    th = m.addVar(lb=0.0, ub=ub_theta, name="theta")
    m.addConstr(gp.quicksum(phi[a] for a in net.attackable) <= bdef, name="budget")

    for j, atk in enumerate(attacks):
        f = m.addVars(net.arcs, lb=0.0, name=f"f{j}")
        for a in net.arcs:
            # an attacked arc survives only where it was fortified
            rhs = net.cap[a] * phi[a] if a in atk else net.cap[a]
            m.addConstr(f[a] <= rhs, name=f"cap{j}_{a}")
        for v in net.nodes:
            if v in ("SRC", "SNK"):
                continue
            m.addConstr(gp.quicksum(f[a] for a in net.arcs if a[1] == v)
                        == gp.quicksum(f[a] for a in net.arcs if a[0] == v))
        m.addConstr(th <= gp.quicksum(f[a] for a in net.arcs if a[0] == "SRC"),
                    name=f"theta{j}")

    m.setObjective(th, GRB.MAXIMIZE)
    m.optimize()
    assert m.SolCount > 0, "the defender master found no solution"
    return m.ObjVal, frozenset(a for a in net.attackable if phi[a].X > 0.5)


def best_response_intersection(net: FlowNetwork, bdef: int, batk: int, *,
                               max_iter: int = 40, tol: float = 1e-6,
                               ub_theta: float | None = None) -> dict:
    """Solve the defender-attacker-operator problem without enumerating.

    Keeps a growing set of attacks; the master defends against those (an upper
    bound), the attacker responds to the resulting fortification (a lower bound,
    because that fortification is feasible and this is its true value), and the
    response is added to the set. It stops when the bounds meet, or when the
    attacker repeats itself and no new information can arrive.
    """
    if ub_theta is None:
        ub_theta, _ = max_flow(net)
    v0, a0 = attacker_best_response(net, batk)
    attacks = [a0]
    lb, best_fort, hist, solves = v0, frozenset(), [], 1
    for it in range(1, max_iter + 1):
        ub, fort = defender_master(net, attacks, bdef, ub_theta)
        val, atk = attacker_best_response(net, batk, fortified=fort)
        solves += 1
        if val > lb:
            lb, best_fort = val, fort
        hist.append(dict(iter=it, UB=round(ub, 6), LB=round(lb, 6),
                         gap=round(ub - lb, 9), attacks=len(attacks)))
        if ub - lb < tol:
            break
        if atk in attacks:
            break                      # no new information; the set is closed
        attacks.append(atk)
    return dict(value=lb, fortification=best_fort, hist=hist,
                iters=len(hist), attacker_solves=solves, attacks=attacks)


def critical_arcs(net: FlowNetwork, budgets=range(1, 7)) -> dict:
    """How often each arc is chosen, across attacker budgets. A cheap diagnostic."""
    from collections import Counter

    seen = Counter()
    for b in budgets:
        _, atk = attacker_best_response(net, b)
        seen.update(atk)
    return dict(seen)
