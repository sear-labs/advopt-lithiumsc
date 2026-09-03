"""Cournot competition with an endogenous price.

Four things live here, and they are the four the notebook builds by hand:

    inverse_demand         A and B from the choke price and an anchor
    best_response_cournot  one firm's profit-maximising reply to a rival schedule
    cournot_iterate        iterated best response, with a tolerance-based test
    joint_profit_max       the collusive benchmark
    market_outcome         prices, quantities and shares implied by a profile

`best_response_cournot` and `joint_profit_max` were each duplicated across
several notebooks; the `PLAN.md` §5 adjudication found every copy identical
after Phase 0, so there is one version and this is it.
"""
from __future__ import annotations

import gurobipy as gp
from gurobipy import GRB

from .curves import revenue_breakpoints
from .regions import add_region
from .structure import Structure

__all__ = ["inverse_demand", "best_response_cournot", "cournot_iterate",
           "joint_profit_max", "market_outcome",
           "best_response_fixed_price", "iterate_fixed_price",
           "best_response_miqp", "cournot_iterate_miqp"]


def inverse_demand(struct: Structure, choke: float, p_anchor: float):
    """Return ``(A, B)`` for ``p[rt,p] = A - B * total_quantity``.

    `choke` is the price at zero quantity. `B` is calibrated so that price equals
    `p_anchor` when quantity equals the reference demand — which is what makes
    the fixed-price and Cournot notebooks comparable at a reference point.
    """
    A = {(rt, p): choke for rt in struct.regions for p in struct.P}
    B = {(rt, p): (choke - p_anchor) / struct.DEMAND[rt, p]
         for rt in struct.regions for p in struct.P}
    return A, B


def best_response_cournot(r: str, rival_sales: dict, struct: Structure, *,
                          a_int: dict, b_slp: dict, nbp_rev: int,
                          learning: str = "both", mipgap: float = 0.005,
                          **region_kw) -> gp.Model:
    """Firm `r` maximises profit facing ``p[rt,p] = A - B*(own + rival)``.

    Revenue is piecewise-linearised in own quantity, which keeps the model a
    MILP: the quadratic form would make it a MIQP, and Gurobi's size-limited
    `pip` licence refuses quadratic objectives at this size. Because revenue is
    concave and this is a *maximisation*, every chord lies below the curve, so
    the convex-combination weights need no SOS2 and add no binaries.
    """
    regions, P, OMEGA = struct.regions, struct.P, struct.OMEGA
    m = gp.Model()
    m.Params.OutputFlag = 0
    m.Params.MIPGap = mipgap

    h = add_region(m, r, struct, learning=learning, **region_kw)
    s = h['sale']
    KR = list(range(nbp_rev))
    mu = m.addVars(regions, P, KR, lb=0.0, ub=1.0, name='mu')
    rev_t = m.addVars(regions, P, lb=-GRB.INFINITY, name='revt')
    for rt in regions:
        for p in P:
            q_bar = rival_sales.get((rt, p), 0.0)
            a_eff = a_int[rt, p] - b_slp[rt, p] * q_bar
            smax = max(1e-6, a_int[rt, p] / b_slp[rt, p] - q_bar)
            S, R = revenue_breakpoints(a_eff, b_slp[rt, p], smax, len(KR))
            m.addConstr(mu.sum(rt, p, '*') == 1, name=f'rcvx_{rt}_{p}')
            m.addConstr(s[rt, p] == gp.quicksum(S[k] * mu[rt, p, k] for k in KR),
                        name=f'rS_{rt}_{p}')
            m.addConstr(rev_t[rt, p] == gp.quicksum(R[k] * mu[rt, p, k] for k in KR),
                        name=f'rR_{rt}_{p}')
    revenue = gp.quicksum(OMEGA[p] * rev_t[rt, p] for rt in regions for p in P)
    m.setObjective(revenue - h['cost'], GRB.MAXIMIZE)
    m.optimize()
    m._h, m._rev = h, revenue
    return m


def cournot_iterate(struct: Structure, *, a_int: dict, b_slp: dict, nbp_rev: int,
                    learning: str = "both", first: str | None = None,
                    max_iter: int = 16, tol: float = 0.5, mipgap: float = 1e-3,
                    **region_kw) -> dict:
    """Iterated best response under Cournot competition.

    Convergence for a game with CONTINUOUS strategies must be tested with a
    TOLERANCE, not by exact state matching: each best response is a MILP solved
    to a finite gap, so the returned quantities wobble slightly between
    iterations. Exact hashing reads that wobble as a cycle — in this model, as a
    spurious 5-cycle.
    """
    regions, P = struct.regions, struct.P
    first = first or regions[0]
    if first not in regions:
        raise ValueError(f"first={first!r} is not one of {regions}")

    def dist(a, b):
        return max(abs(a[r][k] - b[r][k]) for r in regions for k in a[r])

    sales = {r: {(rt, p): 0.0 for rt in regions for p in P} for r in regions}
    plans, hist, log = {}, [], []
    order = [first] + [r for r in regions if r != first]
    for it in range(max_iter):
        prev = {r: dict(sales[r]) for r in regions}
        for r in order:
            rival = {}
            for other in regions:
                if other == r:
                    continue
                for k, v in sales[other].items():
                    rival[k] = rival.get(k, 0.0) + v
            m = best_response_cournot(r, rival, struct, a_int=a_int, b_slp=b_slp,
                                      nbp_rev=nbp_rev, learning=learning,
                                      mipgap=mipgap, **region_kw)
            if m.SolCount == 0:
                return dict(status='INFEASIBLE', iters=it, log=log)
            sales[r] = {(rt, p): m._h['sale'][rt, p].X for rt in regions for p in P}
            plans[r] = tuple(sorted((s_, v) for (s_, v) in m._h['b']
                                    if m._h['b'][s_, v].X > 0.5))
            log.append(dict(iter=it, firm=r, profit=m.ObjVal,
                            revenue=m._rev.getValue(), cost=m._h['cost'].getValue(),
                            builds=len(plans[r]), sales=sum(sales[r].values()),
                            disposal=sum(m._h['disp'][p].X for p in P)))
        cur = {r: dict(sales[r]) for r in regions}
        if it > 0 and dist(cur, prev) < tol:
            return dict(status='CONVERGED', cycle_len=1, iters=it + 1, log=log,
                        plans=plans, sales=sales, drift=dist(cur, prev))
        for k, past in enumerate(hist):                  # genuine k-cycle, k >= 2
            if dist(cur, past) < tol:
                return dict(status='CYCLE', cycle_len=len(hist) - k, iters=it + 1,
                            log=log, plans=plans, sales=sales)
        hist.append(cur)
    return dict(status='MAX_ITER', iters=max_iter, log=log, plans=plans, sales=sales)


def joint_profit_max(struct: Structure, *, a_int: dict, b_slp: dict, nbp_rev: int,
                     learning: str = "both", mipgap: float = 0.005,
                     **region_kw) -> gp.Model:
    """Collusive benchmark: one decision maker maximising the SUM of profits."""
    regions, P, OMEGA = struct.regions, struct.P, struct.OMEGA
    m = gp.Model()
    m.Params.OutputFlag = 0
    m.Params.MIPGap = mipgap

    H = {r: add_region(m, r, struct, learning=learning, **region_kw)
         for r in regions}
    KR = list(range(nbp_rev))
    mu = m.addVars(regions, P, KR, lb=0.0, ub=1.0, name='mu')
    rev_t = m.addVars(regions, P, lb=-GRB.INFINITY, name='revt')
    for rt in regions:
        for p in P:
            smax = a_int[rt, p] / b_slp[rt, p]
            S, R = revenue_breakpoints(a_int[rt, p], b_slp[rt, p], smax, len(KR))
            m.addConstr(mu.sum(rt, p, '*') == 1)
            m.addConstr(gp.quicksum(H[r]['sale'][rt, p] for r in regions)
                        == gp.quicksum(S[k] * mu[rt, p, k] for k in KR))
            m.addConstr(rev_t[rt, p] == gp.quicksum(R[k] * mu[rt, p, k] for k in KR))
    revenue = gp.quicksum(OMEGA[p] * rev_t[rt, p] for rt in regions for p in P)
    m.setObjective(revenue - gp.quicksum(H[r]['cost'] for r in regions),
                   GRB.MAXIMIZE)
    m.optimize()
    m._H, m._rev = H, revenue
    return m


def market_outcome(sales: dict, struct: Structure, a_int: dict, b_slp: dict):
    """Price, quantity, consumer surplus and share, market by market and period."""
    lead = struct.regions[0]
    rows = []
    for rt in struct.regions:
        for p in struct.P:
            q = sum(sales[r][rt, p] for r in struct.regions)
            price = a_int[rt, p] - b_slp[rt, p] * q
            rows.append(dict(market=rt, period=p, year=struct.START[p], quantity=q,
                             price=price,
                             consumer_surplus=0.5 * b_slp[rt, p] * q * q,
                             **{f'share_{lead}': (sales[lead][rt, p] / q
                                                  if q > 1e-6 else None)}))
    return rows


# ===========================================================================
# Part 4b: the same game at a FIXED price
# ===========================================================================
def best_response_fixed_price(r: str, rival_sales: dict, struct: Structure, *,
                              learning: str = "both", mipgap: float = 0.005,
                              **region_kw) -> gp.Model:
    """Firm `r` maximises profit at an exogenous price, given the rival's schedule.

    The contrast with :func:`best_response_cournot` is the whole point of the
    step from Part 4b to Part 4c. Here price is a constant, so the only channel
    between the firms is a **quantity rationing rule**: nobody sells more than
    the demand the rival left behind. There is the residual cap, and it is doing
    all of the strategic work.

    `region_kw` must carry `price_fixed`, since `add_region`'s revenue term is
    what this maximises.
    """
    regions, P = struct.regions, struct.P
    m = gp.Model()
    m.Params.OutputFlag = 0
    m.Params.MIPGap = mipgap
    h = add_region(m, r, struct, learning=learning, **region_kw)
    # at a fixed price nobody buys more than residual demand
    m.addConstrs((h['sale'][rt, p] <= max(0.0, struct.DEMAND[rt, p]
                                          - rival_sales.get((rt, p), 0.0))
                  for rt in regions for p in P), name='residual')
    m.setObjective(h['revenue'] - h['cost'], GRB.MAXIMIZE)
    m.optimize()
    m._h = h
    return m


def iterate_fixed_price(struct: Structure, *, learning: str = "both",
                        first: str | None = None, max_iter: int = 12,
                        mipgap: float = 0.005, **region_kw) -> dict:
    """Iterated best response at a fixed price, terminating on the BUILD PLAN.

    Compare :func:`cournot_iterate`, which needs a tolerance. Here the strategy
    that matters is the set of plants built - a tuple of ``(stage, vintage)``
    pairs, which is **discrete** - so exact state matching is correct and a
    tolerance would be wrong. The distinction is not stylistic: hashing a
    floating-point quantity vector is exactly what invented a spurious 5-cycle in
    Part 4c.

    Three exits, and the third is the interesting one:

    - **CONVERGED** - the profile repeats immediately: a pure-strategy Nash
      equilibrium of the discretised game.
    - **CYCLE** - it repeats after k >= 2 rounds. **No pure-strategy equilibrium
      was found**, and the cycle is the result: each firm builds only if the
      other does not. That is real economics, and suppressing it would be the
      actual error.
    - **MAX_ITER** - report non-convergence honestly.
    """
    regions, P = struct.regions, struct.P
    first = first or regions[0]
    if first not in regions:
        raise ValueError(f"first={first!r} is not one of {regions}")

    sales = {r: {(rt, p): 0.0 for rt in regions for p in P} for r in regions}
    plans, hist, log = {}, [], []
    order = [first] + [r for r in regions if r != first]
    for it in range(max_iter):
        for r in order:
            rival = {}
            for other in regions:
                if other == r:
                    continue
                for k, v in sales[other].items():
                    rival[k] = rival.get(k, 0.0) + v
            m = best_response_fixed_price(r, rival, struct, learning=learning,
                                          mipgap=mipgap, **region_kw)
            if m.SolCount == 0:
                return dict(status='INFEASIBLE', iters=it, log=log)
            sales[r] = {(rt, p): m._h['sale'][rt, p].X
                        for rt in regions for p in P}
            plans[r] = tuple(sorted((s, v) for (s, v) in m._h['b']
                                    if m._h['b'][s, v].X > 0.5))
            log.append(dict(iter=it, firm=r, profit=m.ObjVal,
                            builds=len(plans[r]),
                            total_sales=sum(sales[r].values())))
        state = tuple(plans.get(r) for r in regions)
        if state in hist:
            # repeating IMMEDIATELY is a fixed point; repeating after k rounds is
            # a genuine k-cycle with no pure-strategy equilibrium found
            clen = len(hist) - hist.index(state)
            return dict(status=('CONVERGED' if clen == 1 else 'CYCLE'),
                        cycle_len=clen, iters=it + 1, log=log,
                        plans=plans, sales=sales, hist=hist)
        hist.append(state)
    return dict(status='MAX_ITER', iters=max_iter, log=log, plans=plans,
                sales=sales)


# ===========================================================================
# Part 4c-exact: the same Cournot game with revenue kept quadratic
# ===========================================================================
def best_response_miqp(r: str, rival_sales: dict, struct: Structure, *,
                       a_int: dict, b_slp: dict, learning: str = "both",
                       mipgap: float = 0.005, env=None, **region_kw) -> gp.Model:
    """EXACT Cournot best response: revenue kept as a true quadratic.

    Identical to :func:`best_response_cournot` except that revenue is written
    directly as ``(A - B*(s + q_bar)) * s`` instead of being interpolated - no
    `mu` weights, no convexity constraint, no breakpoint mesh.

    **Needs a licence that permits quadratic objectives at this size.** Measured
    against the free `pip` licence's ~150-variable cap: 50 variables on a
    3-period horizon, 541 on the full 13-period one. So the small horizon
    validates the approximation for everyone and the full one does not.

    The `choke` constraint keeps price non-negative. The model would never *want*
    a negative price, but the bound tightens the relaxation.
    """
    regions, P, OMEGA = struct.regions, struct.P, struct.OMEGA
    m = gp.Model(env=env) if env is not None else gp.Model()
    m.Params.OutputFlag = 0
    m.Params.MIPGap = mipgap
    h = add_region(m, r, struct, learning=learning, **region_kw)
    s = h['sale']
    m.addConstrs((s[rt, p] <= max(0.0, a_int[rt, p] / b_slp[rt, p]
                                  - rival_sales.get((rt, p), 0.0))
                  for rt in regions for p in P), name='choke')
    revenue = gp.QuadExpr()
    for rt in regions:
        for p in P:
            q_bar = rival_sales.get((rt, p), 0.0)
            revenue += OMEGA[p] * ((a_int[rt, p] - b_slp[rt, p] * q_bar) * s[rt, p]
                                   - b_slp[rt, p] * s[rt, p] * s[rt, p])
    m.setObjective(revenue - h['cost'], GRB.MAXIMIZE)
    m.optimize()
    m._h, m._rev = h, revenue
    return m


def cournot_iterate_miqp(struct: Structure, *, a_int: dict, b_slp: dict,
                         learning: str = "both", first: str | None = None,
                         max_iter: int = 16, tol: float = 0.5,
                         mipgap: float = 1e-3, env=None, **region_kw) -> dict:
    """Iterated best response with the exact quadratic revenue.

    Same tolerance-based convergence test as :func:`cournot_iterate`, and for the
    same reason: the strategy is a continuous quantity schedule.
    """
    regions, P = struct.regions, struct.P
    first = first or regions[0]

    def dist(a, b):
        return max(abs(a[r][k] - b[r][k]) for r in regions for k in a[r])

    sales = {r: {(rt, p): 0.0 for rt in regions for p in P} for r in regions}
    plans, hist, log = {}, [], []
    order = [first] + [r for r in regions if r != first]
    for it in range(max_iter):
        prev = {r: dict(sales[r]) for r in regions}
        for r in order:
            rival = {}
            for other in regions:
                if other == r:
                    continue
                for k, v in sales[other].items():
                    rival[k] = rival.get(k, 0.0) + v
            m = best_response_miqp(r, rival, struct, a_int=a_int, b_slp=b_slp,
                                   learning=learning, mipgap=mipgap, env=env,
                                   **region_kw)
            if m.SolCount == 0:
                return dict(status='INFEASIBLE', iters=it, log=log)
            sales[r] = {(rt, p): m._h['sale'][rt, p].X
                        for rt in regions for p in P}
            plans[r] = tuple(sorted((s_, v) for (s_, v) in m._h['b']
                                    if m._h['b'][s_, v].X > 0.5))
            log.append(dict(iter=it, firm=r, profit=m.ObjVal,
                            revenue=m._rev.getValue(),
                            cost=m._h['cost'].getValue(),
                            builds=len(plans[r]), sales=sum(sales[r].values()),
                            disposal=sum(m._h['disp'][p].X for p in P)))
        cur = {r: dict(sales[r]) for r in regions}
        if it > 0 and dist(cur, prev) < tol:
            return dict(status='CONVERGED', cycle_len=1, iters=it + 1, log=log,
                        plans=plans, sales=sales, drift=dist(cur, prev))
        for k, past in enumerate(hist):
            if dist(cur, past) < tol:
                return dict(status='CYCLE', cycle_len=len(hist) - k,
                            iters=it + 1, log=log, plans=plans, sales=sales)
        hist.append(cur)
    return dict(status='MAX_ITER', iters=max_iter, log=log, plans=plans,
                sales=sales)
