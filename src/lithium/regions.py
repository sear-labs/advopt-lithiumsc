"""One region's vertically-integrated chain, attached to a Gurobi model.

This is the single implementation of `add_region`. Across the notebook series
there were two versions of it, and the adjudication in `docs/design-rationale.md` §6 found the
difference was a **feature, not drift**: Part 4e's version is a strict superset
of Part 4c's, adding quotas, a local-content floor, and a tariff folded into the
transport cost. It is already self-disabling — with `tariff`, `quota` and
`local_min` all empty it collapses to the base version *exactly*, adding no
constraint and no term. So the superset is the one implementation, the policy
instruments are optional arguments defaulting to empty, and
`tests/test_smoke.py::test_policy_superset_collapses` asserts the collapse.

Every knob is an argument. The arithmetic is preserved verbatim from the
notebooks, including the literal big-M factors, because a port that "tidies" a
big-M can change which optimal solution is returned.
"""
from __future__ import annotations

import gurobipy as gp
from gurobipy import GRB

from .structure import Structure

__all__ = ["add_region"]


def add_region(
    m: gp.Model,
    r: str,
    struct: Structure,
    *,
    learning: str = "both",
    transport: dict,
    pen_dispose: float,
    price_fixed: float,
    capex_curve=None,
    learn_stages=("PROC", "MFG"),
    tiers=None,
    n_tiers: int = 3,
    lag_years: int = 3,
    tariff: dict | None = None,
    quota: dict | None = None,
    local_min: dict | None = None,
) -> dict:
    """Attach region `r`'s chain to model `m` and return the variable handles.

    Parameters
    ----------
    learning
        ``'none'``, ``'capacity'``, ``'production'`` or ``'both'``. Selects which
        of the two learning channels are built.
    capex_curve
        ``(QBP, CBP)`` from :func:`lithium.curves.capex_breakpoints`. Required
        when `learning` includes capacity learning.
    tiers
        ``(thresholds, multipliers)`` from :func:`lithium.curves.opex_tiers`,
        both keyed by region. Production learning is skipped when this is
        ``None`` — matching the notebooks, where the first planner solve runs
        with ``learning='capacity'`` precisely to *calibrate* these tiers.
    tariff, quota, local_min
        The Part 4e policy instruments. Empty or ``None`` reproduces Part 4c.
    """
    inst = struct.inst
    stages, regions, P = struct.stages, struct.regions, struct.P
    LEN, START, HORIZON = struct.LEN, struct.START, struct.HORIZON
    OMEGA, MU, ETA = struct.OMEGA, struct.MU, struct.ETA
    ACTIVE, VIN, BUILD = struct.ACTIVE[r], struct.VIN, struct.BUILD[r]
    CAP_MIN, CAP_MAX = struct.cap_min, struct.cap_max
    tariff = dict(tariff or {})
    quota = dict(quota or {})
    local_min = dict(local_min or {})
    learn_stages = tuple(learn_stages)

    b = m.addVars(BUILD, vtype=GRB.BINARY, name=f'b_{r}')
    c = m.addVars(BUILD, lb=0.0, ub=CAP_MAX, name=f'c_{r}')
    x = m.addVars(ACTIVE, lb=0.0, name=f'x_{r}')
    f_mp = m.addVars(P, lb=0.0, name=f'fmp_{r}')
    f_pf = m.addVars(P, lb=0.0, name=f'fpf_{r}')
    sale = m.addVars(regions, P, lb=0.0, name=f'sale_{r}')
    disp = m.addVars(P, lb=0.0, name=f'disp_{r}')

    m.addConstrs((c[s, v] <= CAP_MAX * b[s, v] for (s, v) in BUILD), name=f'su_{r}')
    m.addConstrs((c[s, v] >= CAP_MIN * b[s, v] for (s, v) in BUILD), name=f'sl_{r}')
    m.addConstrs((x[s, v, p] <= (inst.legacy_cap[s, r] if v == -1 else c[s, v])
                  for (s, v, p) in ACTIVE), name=f'cap_{r}')
    m.addConstrs((gp.quicksum(ETA['MINE', v, p] * x['MINE', v, p]
                              for v in VIN[r, 'MINE', p]) == f_mp[p] for p in P),
                 name=f'mine_{r}')
    m.addConstrs((f_mp[p] == gp.quicksum(x['PROC', v, p] for v in VIN[r, 'PROC', p])
                  for p in P), name=f'pin_{r}')
    m.addConstrs((gp.quicksum(ETA['PROC', v, p] * x['PROC', v, p]
                              for v in VIN[r, 'PROC', p]) == f_pf[p] for p in P),
                 name=f'pout_{r}')
    m.addConstrs((f_pf[p] == gp.quicksum(x['MFG', v, p] for v in VIN[r, 'MFG', p])
                  for p in P), name=f'min_{r}')
    m.addConstrs((gp.quicksum(ETA['MFG', v, p] * x['MFG', v, p]
                              for v in VIN[r, 'MFG', p])
                  == sale.sum('*', p) + disp[p] for p in P), name=f'mout_{r}')

    # cumulative production (undiscounted), regional scope, with initial experience
    exp0 = inst.experience0[r]
    cum = m.addVars(P, lb=0.0, ub=3 * CAP_MAX * HORIZON + exp0, name=f'cum_{r}')
    m.addConstrs((cum[p] == exp0 +
                  gp.quicksum(LEN[q] * x['MFG', v, q] for q in P if q <= p
                              for v in VIN[r, 'MFG', q]) for p in P), name=f'cp_{r}')

    capex = gp.quicksum(MU[s, v] * inst.fixed[s, r] * b[s, v] for (s, v) in BUILD) \
        + gp.quicksum(MU[s, v] * inst.unit[s, r] * c[s, v]
                      for (s, v) in BUILD if s not in learn_stages)

    if learning in ('capacity', 'both'):
        if capex_curve is None:
            raise ValueError(
                f"learning={learning!r} builds the capacity-learning curve, so "
                f"capex_curve=(QBP, CBP) is required. Build it with "
                f"lithium.curves.capex_breakpoints(...)."
            )
        QBP, CBP = capex_curve
        K = list(range(len(QBP)))
        q_start, q_top = QBP[0], QBP[-1]
        Q = m.addVars(P, lb=q_start, ub=q_top, name=f'Q_{r}')
        Cc = m.addVars(P, lb=0.0, name=f'C_{r}')
        lam = m.addVars(P, K, lb=0.0, ub=1.0, name=f'lam_{r}')
        m.addConstrs((lam.sum(p, '*') == 1 for p in P), name=f'sc_{r}')
        m.addConstrs((Q[p] == gp.quicksum(QBP[k] * lam[p, k] for k in K) for p in P),
                     name=f'sQ_{r}')
        m.addConstrs((Cc[p] == gp.quicksum(CBP[k] * lam[p, k] for k in K) for p in P),
                     name=f'sC_{r}')
        m.addConstrs((Q[p] == q_start + gp.quicksum(c[s, v] for (s, v) in BUILD
                                                    if s in learn_stages and v <= p)
                      for p in P), name=f'cc_{r}')
        for p in P:
            m.addSOS(GRB.SOS_TYPE2, [lam[p, k] for k in K])
        rate = sum(inst.unit[s, r] for s in learn_stages) / len(learn_stages)
        capex += gp.quicksum(MU[learn_stages[0], p]
                             * rate * (Cc[p] - (Cc[p - 1] if p > 0 else 0.0))
                             for p in P)
    else:
        capex += gp.quicksum(MU[s, v] * inst.unit[s, r] * c[s, v]
                             for (s, v) in BUILD if s in learn_stages)

    if learning in ('production', 'both') and tiers is not None:
        tier_q, tier_m = tiers
        J = list(range(n_tiers))
        z = m.addVars(P, J, vtype=GRB.BINARY, name=f'z_{r}')
        m.addConstrs((z.sum(p, '*') == 1 for p in P), name=f'ot_{r}')
        LAGP = {p: struct.YEAR_TO_P[max(1, START[p] - lag_years)] for p in P}
        BIGQ = 3 * CAP_MAX * HORIZON + exp0
        m.addConstrs((cum[LAGP[p]] >= tier_q[r][j - 1] - BIGQ * (1 - z[p, j])
                      for p in P for j in J if j > 0), name=f'tf_{r}')
        m.addConstrs((cum[LAGP[p]] <= tier_q[r][j] + BIGQ * (1 - z[p, j])
                      for p in P for j in J if j < n_tiers - 1), name=f'tc_{r}')
        ts = m.addVars(stages, P, J, lb=0.0, name=f'ts_{r}')
        m.addConstrs((ts.sum(s, p, '*') == gp.quicksum(x[s, v, p]
                                                       for v in VIN[r, s, p])
                      for s in stages for p in P), name=f'tss_{r}')
        m.addConstrs((ts[s, p, j] <= 3 * CAP_MAX * z[p, j]
                      for s in stages for p in P for j in J), name=f'tl_{r}')
        opex = gp.quicksum(OMEGA[p] * inst.opex[s, r] * tier_m[r][j] * ts[s, p, j]
                           for s in stages for p in P for j in J)
    else:
        z = None
        opex = gp.quicksum(OMEGA[p] * inst.opex[s, r] * x[s, v, p]
                           for (s, v, p) in ACTIVE)

    # --- policy instruments. All three collapse to nothing when empty. -------
    m.addConstrs((sale[rt, p] <= quota[r, rt] for rt in regions for p in P
                  if (r, rt) in quota), name=f'quota_{r}')
    m.addConstrs((sale[r, p] >= local_min[r] for p in P
                  if r in local_min), name=f'lcr_{r}')

    trans = gp.quicksum(OMEGA[p] * (transport[r, rt] + tariff.get((r, rt), 0.0))
                        * sale[rt, p] for rt in regions for p in P)
    tariff_paid = gp.quicksum(OMEGA[p] * tariff.get((r, rt), 0.0) * sale[rt, p]
                              for rt in regions for p in P)
    dcost = gp.quicksum(OMEGA[p] * pen_dispose * disp[p] for p in P)
    revenue = gp.quicksum(OMEGA[p] * price_fixed * sale[rt, p]
                          for rt in regions for p in P)
    return dict(b=b, c=c, x=x, sale=sale, disp=disp, cum=cum, z=z,
                capex=capex, opex=opex, trans=trans, dcost=dcost, revenue=revenue,
                tariff_paid=tariff_paid, cost=capex + opex + trans + dcost)
