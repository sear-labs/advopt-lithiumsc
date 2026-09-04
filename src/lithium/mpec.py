"""Stackelberg leadership as a single-level MPEC.

the original plan listed `stackelberg` under `games.py`. It lives in its own module
instead, for one reason worth stating rather than quietly ignoring: `games.py`
holds *simultaneous-move* models, where every firm solves the same kind of
problem, and this holds a **bilevel** model, where the follower's problem has
been replaced by its optimality conditions. Mixing them in one file would put
two different contracts behind one import — the functions here only make sense
if you know the follower is continuous and concave.

The adjudication (2026-09-03): `stackelberg`, `follower_marginal_cost` and
`follower_legacy` are defined in both Part 4d and Part 4e and are **byte-identical**
in both. Not drift, not a feature — just the same code twice. One version, here.

**What makes any of this valid.** KKT conditions are necessary and sufficient for
a concave program and say nothing useful about a MILP. The follower's problem is
continuous and concave, which is a consequence of the decision made in Part 3 to
keep the operational layer an LP and put the integers only in investment. If the
follower ever gets binaries, none of this works and the method has to change.
"""
from __future__ import annotations

import gurobipy as gp
from gurobipy import GRB

from .regions import add_region
from .structure import Structure

__all__ = ["follower_marginal_cost", "follower_legacy", "stackelberg",
           "follower_qp"]


def follower_marginal_cost(struct: Structure, follower: str,
                           transport: dict) -> dict:
    """The follower's cost per unit *delivered* to each market.

    Works back up the chain: a unit of finished good needs ``1/eta_mfg`` units
    into manufacturing, which needs ``1/(eta_mfg * eta_proc)`` into processing,
    and so on — so an inefficient stage multiplies every cost upstream of it.

    Deliberately evaluated at the **legacy vintage in period 0**, which makes
    this a constant rather than a decision. That is the simplification that keeps
    the follower's problem concave and therefore KKT-representable; it is also
    the reason the follower cannot make lumpy investments. State it, do not hide
    it.
    """
    e_m = struct.ETA['MINE', -1, 0]
    e_p = struct.ETA['PROC', -1, 0]
    e_f = struct.ETA['MFG', -1, 0]
    thr_f = 1.0 / e_f
    thr_p = thr_f / e_p
    thr_m = thr_p / e_m
    opex = struct.inst.opex
    chain = (opex['MFG', follower] * thr_f + opex['PROC', follower] * thr_p
             + opex['MINE', follower] * thr_m)
    return {rt: chain + transport[follower, rt] for rt in struct.regions}


def follower_legacy(struct: Structure, follower: str, p: int) -> float:
    """The follower's inherited deliverable capacity in period `p`, or zero.

    Zero once its manufacturing legacy has retired — and that cliff is the
    interesting moment in Part 4d, because from then on the follower can only
    serve the market by paying for expansion.
    """
    inst = struct.inst
    if struct.START[p] <= inst.legacy_ret['MFG', follower]:
        return inst.legacy_cap['MFG', follower] * struct.ETA['MFG', -1, p]
    return 0.0


def stackelberg(struct: Structure, leader: str, follower: str, *,
                a_int: dict, b_slp: dict, transport: dict,
                cap_cost: float, big_q: float, big_l: float, nq: int,
                learning: str = "both", mipgap: float = 0.01,
                deter: bool = True, env=None, **region_kw) -> gp.Model:
    """Single-level MPEC: leader commits, follower best-responds.

    The leader's revenue contains ``-B * qF * qL``, a product of two decision
    variables. It is kept **exact** by restricting the leader's quantity to a
    finite grid chosen by binaries: ``qL = sum_k S_k * bq_k`` with
    ``sum_k bq_k = 1``. Then ``qF * qL = sum_k S_k * (qF * bq_k)``, and each
    ``qF * bq_k`` is a continuous-times-binary product, which linearises exactly.

    `deter=False` drops the follower entirely, giving the leader as monopolist —
    an upper bound on leader profit.

    `big_q` and `big_l` are **chosen, not derived**. Too small silently forces a
    dual to zero and returns a wrong answer that still solves; too large destroys
    the relaxation. They deserve the same scrutiny as any other big-M, and
    `follower_qp` is what checks the choice was not fatal.
    """
    regions, P, OMEGA = struct.regions, struct.P, struct.OMEGA
    m = gp.Model(env=env) if env is not None else gp.Model()
    m.Params.OutputFlag = 0
    m.Params.MIPGap = mipgap

    L = add_region(m, leader, struct, learning=learning, transport=transport,
                   **region_kw)
    qL = L['sale']
    c_f = follower_marginal_cost(struct, follower, transport)
    KQ = list(range(nq))

    # leader quantity on a binary-selected grid
    bq = m.addVars(regions, P, KQ, vtype=GRB.BINARY, name='bq')
    GRID = {}
    for rt in regions:
        for p in P:
            smax = a_int[rt, p] / b_slp[rt, p]
            GRID[rt, p] = [smax * k / (nq - 1) for k in KQ]
            m.addConstr(bq.sum(rt, p, '*') == 1, name=f'gsel_{rt}_{p}')
            m.addConstr(qL[rt, p] == gp.quicksum(GRID[rt, p][k] * bq[rt, p, k]
                                                 for k in KQ),
                        name=f'gq_{rt}_{p}')

    if deter:
        qF = m.addVars(regions, P, lb=0.0, ub=big_q, name='qF')
        Cap = m.addVar(lb=0.0, ub=big_q, name='CapF')
        lam = m.addVars(P, lb=0.0, name='lam')
        nu = m.addVars(regions, P, lb=0.0, name='nu')
        mcap = m.addVar(lb=0.0, name='mcap')
        yc = m.addVars(P, vtype=GRB.BINARY, name='yc')
        zq = m.addVars(regions, P, vtype=GRB.BINARY, name='zq')
        ycap = m.addVar(vtype=GRB.BINARY, name='ycap')
        slack = m.addVars(P, lb=0.0, name='slk')

        # follower primal feasibility
        m.addConstrs((qF.sum('*', p) + slack[p]
                      == follower_legacy(struct, follower, p) + Cap for p in P),
                     name='fcap')
        # follower stationarity
        m.addConstrs((OMEGA[p] * (a_int[rt, p]
                                  - b_slp[rt, p] * (2 * qF[rt, p] + qL[rt, p])
                                  - c_f[rt]) - lam[p] + nu[rt, p] == 0
                      for rt in regions for p in P), name='stat_q')
        m.addConstr(-cap_cost + gp.quicksum(lam[p] for p in P) + mcap == 0,
                    name='stat_cap')
        # complementarity (big-M)
        m.addConstrs((lam[p] <= big_l * yc[p] for p in P), name='cc1')
        m.addConstrs((slack[p] <= big_q * (1 - yc[p]) for p in P), name='cc2')
        m.addConstrs((nu[rt, p] <= big_l * zq[rt, p]
                      for rt in regions for p in P), name='cc3')
        m.addConstrs((qF[rt, p] <= big_q * (1 - zq[rt, p])
                      for rt in regions for p in P), name='cc4')
        m.addConstr(mcap <= big_l * ycap, name='cc5')
        m.addConstr(Cap <= big_q * (1 - ycap), name='cc6')

        # exact linearisation of w[rt, p, k] = qF[rt, p] * bq[rt, p, k]
        w = m.addVars(regions, P, KQ, lb=0.0, name='w')
        m.addConstrs((w[rt, p, k] <= big_q * bq[rt, p, k]
                      for rt in regions for p in P for k in KQ), name='w1')
        m.addConstrs((w[rt, p, k] <= qF[rt, p]
                      for rt in regions for p in P for k in KQ), name='w2')
        m.addConstrs((w[rt, p, k] >= qF[rt, p] - big_q * (1 - bq[rt, p, k])
                      for rt in regions for p in P for k in KQ), name='w3')
    else:
        qF, Cap = None, None

    # leader revenue = A*qL - B*qL^2 - B*qF*qL, all linear on the grid
    rev = gp.LinExpr()
    for rt in regions:
        for p in P:
            for k in KQ:
                Sk = GRID[rt, p][k]
                rev += OMEGA[p] * (a_int[rt, p] * Sk
                                   - b_slp[rt, p] * Sk * Sk) * bq[rt, p, k]
                if deter:
                    rev -= OMEGA[p] * b_slp[rt, p] * Sk * w[rt, p, k]

    m.setObjective(rev - L['cost'], GRB.MAXIMIZE)
    m.optimize()
    m._L, m._qL, m._qF, m._Cap, m._rev = L, qL, qF, Cap, rev
    return m


def follower_qp(struct: Structure, follower: str, qL_fixed: dict, *,
                a_int: dict, b_slp: dict, transport: dict, cap_cost: float,
                big_q: float, env=None):
    """Solve the follower's problem DIRECTLY as a QP, given the leader's quantities.

    This is the check on the MPEC, and it is the one an MPEC most needs. A sign
    error in stationarity, a big-M too small to let a dual move, a missing
    complementarity pair — the model still solves and returns plausible numbers.
    Take the leader's committed quantities out of the MPEC solution, hand them to
    the follower solved exactly, and the two must agree.

    Returns ``(model, qF, Cap)``.
    """
    regions, P, OMEGA = struct.regions, struct.P, struct.OMEGA
    m = gp.Model(env=env) if env is not None else gp.Model()
    m.Params.OutputFlag = 0
    c_f = follower_marginal_cost(struct, follower, transport)
    qF = m.addVars(regions, P, lb=0.0, ub=big_q, name='qF')
    Cap = m.addVar(lb=0.0, ub=big_q, name='Cap')
    m.addConstrs((qF.sum('*', p) <= follower_legacy(struct, follower, p) + Cap
                  for p in P), name='cap')
    obj = gp.QuadExpr()
    for rt in regions:
        for p in P:
            obj += OMEGA[p] * ((a_int[rt, p] - b_slp[rt, p] * qL_fixed[rt, p]
                                - c_f[rt]) * qF[rt, p]
                               - b_slp[rt, p] * qF[rt, p] * qF[rt, p])
    obj -= cap_cost * Cap
    m.setObjective(obj, GRB.MAXIMIZE)
    m.optimize()
    return m, qF, Cap
