"""Two-stage stochastic programming on the Part 1 network: EV, PI, SP, and PH.

Uncertainty is Region 2's demand growth. The **build plan for the early years has
to be chosen before it resolves** — that is what nonanticipativity means, and it
is the only thing separating this from Part 1 solved three times.

Four quantities, and keeping them straight is most of the subject:

    WS   wait-and-see: each scenario solved knowing which one it is. A LOWER
         bound nobody can achieve, because it needs information you do not have.
    RP   the recourse problem: one stage-1 plan, stage 2 re-optimised per
         scenario. What stochastic programming actually buys.
    EEV  the mean-value plan, evaluated the same way. What you get by planning
         for the average and hoping.

    EVPI = RP - WS    the value of a crystal ball
    VSS  = EEV - RP   the value of not planning for the average

**Theory says WS <= RP <= EEV**, and `three_case_comparison` computes all three
through *identical* evaluation machinery so the comparison is meaningful. Every
number it returns is an evaluated expectation; none is a raw solve value. Getting
that wrong is the Code Standard, Part 6's "comparing two things that were not asked the
same question", and it is very easy here.

Two changes from the notebook this was extracted from, both deliberate:

- `ph` took a `seed` and built a `random.Random` that **nothing ever used** — the
  block selection is a deterministic round-robin, as its own comment says. A
  parameter that cannot change the answer is worse than no parameter, because
  someone will change it and conclude the method is insensitive. Removed.
- `scenarios_n` built its scenario names with a broken f-string patched by a
  trailing `.replace('", ', '')`. Same output, written properly.
"""
from __future__ import annotations

import math

import gurobipy as gp
from gurobipy import GRB

from .core import CoreStructure, build

__all__ = ["scenarios", "scenarios_n", "extensive_form", "stage1_keys",
           "subproblem", "progressive_hedging", "evaluate_stage1",
           "wait_and_see", "mean_value_stage1", "eval_strategy_by_scenario",
           "strategy_stage1", "perfect_info_by_scenario",
           "three_case_comparison", "ph_three_case"]


# ------------------------------------------------------------ scenario trees
# Every function below differences one expectation against another -- VSS is
# EEV - RP, EVPI is RP - WS, and the PH sweep reads costs 0.04% apart. `build`
# defaults to a 0.005 MIP gap, which is an order of magnitude LARGER than the
# quantities being measured, so a loose gap here does not add noise, it
# manufactures the answer. Hence one tight default, shared, and threaded all the
# way down rather than accepted and quietly dropped.
MIPGAP_DEFAULT = 1e-6

def scenarios(st: CoreStructure,
              growths=((0.010, 0.30), (0.070, 0.40), (0.140, 0.30)),
              r2_base: float = 105.0):
    """Demand scenarios: the uncertainty is Region 2's growth rate.

    Returns ``[(name, probability, demand dict)]``. Region 1's demand is the
    deterministic path from the structure; only R2 varies, which keeps the tree
    small enough to read while still being a real hedge.

    `r2_base` deliberately differs from the instance's own R2 base: the scenario
    set is a *what-if*, not the deterministic case re-labelled.
    """
    out = []
    for j, (g, p) in enumerate(growths):
        D = {}
        for t in st.years:
            D["R1", t] = st.D["R1", t]                    # R1 known
            D["R2", t] = r2_base * ((1 + g) ** (t - 1))   # R2 uncertain
        out.append((f"s{j}_g{g:.3f}", p, D))
    return out


def scenarios_n(st: CoreStructure, n: int, lo: float = 0.01, hi: float = 0.14,
                base: float = 105.0):
    """Equiprobable discretisation of the R2 growth rate into `n` scenarios.

    ``n = 1`` collapses to the mean, which is useful as a reference: it is
    exactly the mean-value problem, so RP and EEV must coincide there.
    """
    gs = [0.5 * (lo + hi)] if n == 1 else [lo + (hi - lo) * j / (n - 1)
                                           for j in range(n)]
    p = 1.0 / len(gs)
    out = []
    for j, g in enumerate(gs):
        D = {}
        for t in st.years:
            D["R1", t] = st.D["R1", t]
            D["R2", t] = base * ((1 + g) ** (t - 1))
        out.append((f"s{j:02d}_g{g:.4f}", p, D))
    return out


def stage1_keys(y, stage1_years):
    """The build decisions that must be identical across scenarios."""
    return [k for k in y if k[1] in stage1_years]


# --------------------------------------------------------- the extensive form
def extensive_form(st: CoreStructure, scens, invest_years, stage1_years,
                   quiet: bool = True,
                   mipgap: float | None = MIPGAP_DEFAULT) -> gp.Model:
    """One monolithic MILP over all scenarios, with explicit nonanticipativity.

    Each scenario gets its own copy of the whole network, built into the same
    model with a name prefix — that is what `build`'s `into` and `prefix`
    arguments exist for. The scenarios are then tied together by forcing the
    **stage-1** build decisions to be equal across them.

    Those equalities are the model. Without them this is three independent
    problems wearing one objective, which is the wait-and-see bound, not a
    stochastic program.

    It also does not scale: the model grows linearly in the scenario count, and
    Part 2 section 5 is where it stops fitting. `progressive_hedging` is the
    answer to that.
    """
    m = gp.Model()
    if quiet:
        m.Params.OutputFlag = 0
    m.Params.MIPGap = 0.005 if mipgap is None else mipgap
    ys, objs = [], gp.LinExpr()
    for (nm, p, D) in scens:
        _, y, obj, _ = build(st, invest_years=invest_years, demand=D,
                             into=m, prefix=nm + "_", mipgap=mipgap)
        ys.append(y)
        objs += p * obj
    # nonanticipativity: stage-1 builds identical across scenarios
    for key in ys[0]:
        if key[1] in stage1_years:
            for j in range(1, len(ys)):
                m.addConstr(ys[0][key] == ys[j][key], name=f"NA_{key}_{j}")
    m.setObjective(objs, GRB.MINIMIZE)
    m._ys = ys
    return m


# ------------------------------------------------------- progressive hedging
def subproblem(st: CoreStructure, D, invest_years, stage1_years,
               mipgap: float | None = MIPGAP_DEFAULT) -> gp.Model:
    """One scenario's problem, kept open so PH can re-set its objective."""
    m = build(st, invest_years=invest_years, demand=D, mipgap=mipgap)
    m._base_obj = m._capex_expr + m._op_expr
    m._s1 = stage1_keys(m._y, stage1_years)
    return m


def progressive_hedging(st: CoreStructure, scens, invest_years, stage1_years,
                        rho: float | None = None, iters: int = 40,
                        tol: float = 1e-4, block_frac: float = 1.0,
                        mipgap: float | None = MIPGAP_DEFAULT,
                        verbose: bool = False) -> dict:
    """Progressive hedging: solve the scenarios separately, agree by negotiation.

    Each iteration solves every scenario against a penalty for disagreeing with
    the current consensus `z`, averages the answers into a new `z`, and updates
    the multipliers `w`. It never builds the monolithic model, so it scales past
    the point where the extensive form stops fitting.

    **The trick that keeps the subproblems MILPs.** The natural PH penalty is
    quadratic, ``(rho/2)||x - z||^2``, which would make every subproblem a MIQP.
    But stage-1 `x` is **binary**, and for binary x, ``x^2 = x``. So

        (rho/2)||x - z||^2  ==  (rho/2) * [ x(1 - 2z) + z^2 ]

    which is **linear**. No MIQP, and no licence problem — see `README.md` on why
    that matters here.

    `block_frac < 1` gives the APH-style block-asynchronous variant: only a
    subset of subproblems is re-solved per iteration. The subset is a
    **deterministic round-robin**, not a random sample, because fairness
    (Assumption A3 in Eckstein et al.) requires every scenario to be revisited
    within a bounded number of iterations and random sampling does not guarantee
    that. There is deliberately no seed: nothing here is stochastic.
    """
    subs = [(nm, p, subproblem(st, D, invest_years, stage1_years, mipgap=mipgap))
            for (nm, p, D) in scens]
    n = len(subs)
    if rho is None:                      # scale rho to the capex of one build
        rho = 0.5 * sum(st.inst.capex0.values()) / len(st.inst.capex0)

    keys = subs[0][2]._s1
    w = [{k: 0.0 for k in keys} for _ in range(n)]
    xv = [{k: 0.0 for k in keys} for _ in range(n)]
    z = {k: 0.0 for k in keys}
    hist, solved_count = [], 0

    nblock = max(1, int(round(block_frac * n)))
    cursor = 0
    for it in range(iters):
        if it == 0 or nblock >= n:
            I = list(range(n))                 # everyone, to seed every x_i
        else:
            I = [(cursor + j) % n for j in range(nblock)]
            cursor = (cursor + nblock) % n
        for i in I:
            nm, p, m = subs[i]
            obj = gp.LinExpr(m._base_obj)
            for k in keys:
                # linear Lagrange term + LINEARISED quadratic penalty
                obj += w[i][k] * m._y[k]
                obj += 0.5 * rho * (m._y[k] * (1 - 2 * z[k]) + z[k] ** 2)
            m.setObjective(obj, GRB.MINIMIZE)
            m.optimize()
            solved_count += 1
            for k in keys:
                xv[i][k] = m._y[k].X
        # average: the projection onto the nonanticipativity subspace
        z = {k: sum(subs[i][1] * xv[i][k] for i in range(n)) for k in keys}
        for i in range(n):                     # multiplier update
            for k in keys:
                w[i][k] += rho * (xv[i][k] - z[k])
        resid = math.sqrt(sum(subs[i][1] * (xv[i][k] - z[k]) ** 2
                              for i in range(n) for k in keys))
        hist.append(resid)
        if verbose:
            print(f"  it {it:3d} block={len(I)}/{n} resid={resid:.5f}")
        if resid < tol and it > 0:
            break
    return dict(z=z, resid=hist, iters=len(hist), subsolves=solved_count,
                rho=rho, x=xv)


# ------------------------------------------------- evaluating a stage-1 plan
def evaluate_stage1(st: CoreStructure, scens, invest_years, stage1_years, z,
                    quiet: bool = True,
                    mipgap: float | None = MIPGAP_DEFAULT):
    """Fix stage-1 builds to a rounded `z`, re-optimise stage 2 per scenario.

    The result is compared against RP, so it must be measured the same way RP
    was -- see MIPGAP_DEFAULT above.
    """
    fixed = {k: (1 if z.get(k, 0) > 0.5 else 0) for k in z}
    tot = 0.0
    for (nm, p, D) in scens:
        m = build(st, invest_years=invest_years, demand=D, mipgap=mipgap)
        for k, val in fixed.items():
            if k in m._y:
                m._y[k].LB = m._y[k].UB = val
        m.optimize()
        if m.SolCount == 0:
            return None
        tot += p * m.ObjVal
    return tot


def wait_and_see(st: CoreStructure, scens, invest_years,
                 mipgap: float | None = MIPGAP_DEFAULT):
    """Each scenario solved with full knowledge. A lower bound; RP - WS is EVPI."""
    tot = 0.0
    for (nm, p, D) in scens:
        m = build(st, invest_years=invest_years, demand=D, mipgap=mipgap)
        m.optimize()
        tot += p * m.ObjVal
    return tot


def mean_value_stage1(st: CoreStructure, scens, invest_years, stage1_years,
                      mipgap: float | None = MIPGAP_DEFAULT):
    """Solve the deterministic mean-demand problem; return its stage-1 decisions.

    This is the strategy that "plans for the average". Evaluating it against the
    real scenarios is what produces EEV, and the gap to RP is the value of
    stochastic solution.
    """
    Dm = {key: sum(p * D[key] for (_, p, D) in scens) for key in scens[0][2]}
    m = build(st, invest_years=invest_years, demand=Dm, mipgap=mipgap)
    m.optimize()
    return {k: m._y[k].X for k in stage1_keys(m._y, stage1_years)}


def eval_strategy_by_scenario(st: CoreStructure, scens, invest_years,
                              stage1_years, s1_fix, mipgap: float | None = None):
    """Fix a stage-1 strategy, re-optimise stage 2 in EVERY scenario separately.

    Returns the per-scenario cost and unmet demand — the **distribution**, not
    just the mean. A strategy can have a fine expectation and an unacceptable
    worst case, and the mean alone hides that.
    """
    rows = []
    for (nm, p, D) in scens:
        m = build(st, invest_years=invest_years, demand=D, mipgap=mipgap)
        for k, val in s1_fix.items():
            if k in m._y:
                m._y[k].LB = m._y[k].UB = (1 if val > 0.5 else 0)
        m.optimize()
        if m.SolCount == 0:
            rows.append(dict(scenario=nm, prob=p, cost=None, unmet=None))
            continue
        rows.append(dict(scenario=nm, prob=p, cost=m.ObjVal,
                         unmet=sum(v.X for v in m._slk.values())))
    return rows


def perfect_info_by_scenario(st: CoreStructure, scens, invest_years,
                             mipgap: float | None = None):
    """PI / wait-and-see, per scenario, with full knowledge of which one it is."""
    rows = []
    for (nm, p, D) in scens:
        m = build(st, invest_years=invest_years, demand=D, mipgap=mipgap)
        m.optimize()
        rows.append(dict(scenario=nm, prob=p, cost=m.ObjVal,
                         unmet=sum(v.X for v in m._slk.values())))
    return rows


def strategy_stage1(st: CoreStructure, scens, invest_years, stage1_years, which,
                    rho: float = 300, iters: int = 60,
                    mipgap: float | None = MIPGAP_DEFAULT):
    """The stage-1 decision each strategy produces.

    ``'EV'`` mean-demand deterministic, ``'SP'`` the extensive form, ``'PH'``
    progressive hedging.
    """
    if which == "EV":
        return mean_value_stage1(st, scens, invest_years, stage1_years,
                                 mipgap=mipgap)
    if which == "SP":
        ef = extensive_form(st, scens, invest_years, stage1_years, mipgap=mipgap)
        ef.optimize()
        return {k: ef._ys[0][k].X
                for k in stage1_keys(ef._ys[0], stage1_years)}
    if which == "PH":
        return progressive_hedging(st, scens, invest_years, stage1_years,
                                   rho=rho, iters=iters, mipgap=mipgap)["z"]
    raise ValueError(f"unknown strategy {which!r}; expected 'EV', 'SP' or 'PH'")


# ------------------------------------------------------- the three-way compare
def three_case_comparison(st: CoreStructure, scens, invest_years, stage1_years,
                          mipgap: float = 1e-6) -> dict:
    """EV / SP / PI computed through IDENTICAL evaluation machinery.

    PI  each scenario solved deterministically, probability-weighted (WS)
    SP  stage-1 from the extensive form, FIXED, stage 2 re-optimised (RP)
    EV  stage-1 from the mean-demand problem, FIXED, stage 2 re-optimised (EEV)

    **Every number is an evaluated expectation. None is a raw solve value.** The
    extensive form's own objective is returned separately as `ef_obj` precisely
    so it is not mistaken for RP — they are close but they are not the same
    quantity, and quoting one for the other is how a bound gets "violated".

    Theory: ``WS <= RP <= EEV``, and per scenario ``PI <= SP`` and ``PI <= EV``.
    """
    ef = extensive_form(st, scens, invest_years, stage1_years, mipgap=mipgap)
    ef.optimize()
    sp_fix = {k: ef._ys[0][k].X for k in stage1_keys(ef._ys[0], stage1_years)}
    ev_fix = mean_value_stage1(st, scens, invest_years, stage1_years,
                               mipgap=mipgap)

    per = {
        "PI": perfect_info_by_scenario(st, scens, invest_years, mipgap=mipgap),
        "SP": eval_strategy_by_scenario(st, scens, invest_years, stage1_years,
                                        sp_fix, mipgap=mipgap),
        "EV": eval_strategy_by_scenario(st, scens, invest_years, stage1_years,
                                        ev_fix, mipgap=mipgap),
    }
    exp = {k: sum(r["prob"] * r["cost"] for r in v) for k, v in per.items()}
    return dict(per=per, WS=exp["PI"], RP=exp["SP"], EEV=exp["EV"],
                ef_obj=ef.ObjVal, sp_fix=sp_fix, ev_fix=ev_fix)


def ph_three_case(st: CoreStructure, scens, invest_years, stage1_years,
                  rho: float = 300, iters: int = 60, block_frac: float = 1.0,
                  mipgap: float = MIPGAP_DEFAULT) -> dict:
    """EV / SP / PI at ANY scenario count — no extensive form required.

    SP's stage-1 comes from progressive hedging rather than the monolithic model,
    so this scales past the point where that stops fitting. WS and EEV are
    per-scenario solves and were never size-constrained.
    """
    # mipgap MUST reach the PH call: its `z` becomes SP's stage-1 plan, and
    # that plan is then evaluated at `mipgap` and differenced against EEV. A
    # plan found at a looser gap than it is scored at is the Part 6 defect.
    r = progressive_hedging(st, scens, invest_years, stage1_years, rho=rho,
                            iters=iters, block_frac=block_frac, mipgap=mipgap)
    sp_fix = {k: (1.0 if v > 0.5 else 0.0) for k, v in r["z"].items()}
    ev_fix = mean_value_stage1(st, scens, invest_years, stage1_years,
                               mipgap=mipgap)
    per = {
        "PI": perfect_info_by_scenario(st, scens, invest_years, mipgap=mipgap),
        "SP": eval_strategy_by_scenario(st, scens, invest_years, stage1_years,
                                        sp_fix, mipgap=mipgap),
        "EV": eval_strategy_by_scenario(st, scens, invest_years, stage1_years,
                                        ev_fix, mipgap=mipgap),
    }
    exp = {k: sum(x["prob"] * x["cost"] for x in v) for k, v in per.items()}
    return dict(per=per, WS=exp["PI"], RP=exp["SP"], EEV=exp["EV"],
                sp_fix=sp_fix, ev_fix=ev_fix, ph=r)
