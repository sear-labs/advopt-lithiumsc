"""The network-core capacity expansion model behind Parts 3 and 3b.

A **fourth instance**, and the family resemblance to Part 4's chain is close
enough to be worth stating plainly, because the differences are the point:

===================  ==============================  ==========================
                     this module (Parts 3, 3b)       `regions.add_region` (Part 4)
===================  ==============================  ==========================
who decides          one planner, minimising cost    two firms, maximising profit
trade between        every stage: a mine in R1 can   finished goods only; each
regions              feed a processor in R2          chain is internally closed
learning pool        industry-wide -- one `Q` over   per firm, so each carries
                     both regions                    its own experience
prices               none; demand must be served     endogenous, or fixed
costs by region      symmetric                       asymmetric (R2 builds
                                                     cheaper, operates dearer)
===================  ==============================  ==========================

The efficiency table is shared with the Part 4 family verbatim
(`efficiency.csv`), because it *is* the same table. The cost tables are not:
Part 3's are keyed by stage alone and identical across regions, which is what
makes it a clean setting for studying the model's machinery before regional
asymmetry starts driving the answer.

**One builder covers both notebooks.** `build_netcore` with `learning='capacity'`
and no tiers is Part 3; adding tiers, disposal and local-content minimums gives
Part 3b. That is the same superset-collapses-to-subset arrangement
`regions.add_region` uses for Parts 4c and 4e, and it is preferable to two
near-identical functions for the same reason: there is only one place for a
constraint to be wrong.

The learning curves are **not** reimplemented here. `curves.capex_breakpoints`
and `curves.opex_tiers` already hold them, and both notebooks' hand-written
versions were verified identical to them (relative difference 1.2e-16 and
1.7e-16) during migration. Note `panels`: Parts 3 and 3b integrate the capex
curve with 600 trapezoid panels where the package default is 400, which moves
the cumulative cost by about 2e-7 relative. Small, but it is a knob and it is
passed explicitly rather than left to a default.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import gurobipy as gp
from gurobipy import GRB

# Parts 3 and 3b compare model variants whose objectives differ by 0.6% to 12%,
# and section-by-section they compare BUILD PLANS, which a loose gap can change
# outright. Verified during migration that Part 3's four variants give identical
# objectives from gap 5e-3 down to 1e-6 -- but that is a property of this
# instance, not a licence to rely on it.
MIPGAP_DEFAULT = 1e-6


# ---------------------------------------------------------------- instance ---
@dataclass(frozen=True)
class NetCoreInstance:
    """The tables Parts 3 and 3b read. Knobs are not in here."""
    stages: tuple[str, ...]
    regions: tuple[str, ...]
    fixed: dict[str, float]          # stage -> cost per facility
    unit: dict[str, float]           # stage -> cost per unit of capacity
    operate: dict[str, float]        # stage -> cost per unit of throughput
    lead: dict[str, int]             # stage -> years from decision to operation
    legacy_cap: dict[tuple[str, str], float]
    legacy_ret: dict[tuple[str, str], int]
    demand_base: dict[str, float]
    demand_growth: dict[str, float]
    eta_ceil: dict[str, float]
    eta_base: dict[str, float]
    alpha: dict[str, float]
    beta: dict[str, float]
    delta_bar: dict[str, float]


def read_netcore_tables(source: Path | str | None = None):
    """Read the four CSVs: three netcore tables plus the shared efficiency one."""
    import pandas as pd

    names = ("netcore_stages.csv", "netcore_nodes.csv", "netcore_regions.csv",
             "efficiency.csv")
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


def load_netcore_instance(source: Path | str | None = None) -> NetCoreInstance:
    (stg, nod, reg, eff), _root = read_netcore_tables(source)
    col = lambda df, k, v: dict(zip(df[k], df[v]))          # noqa: E731
    pair = lambda v: {(s, r): x for s, r, x in                # noqa: E731
                      zip(nod["stage"], nod["region"], nod[v])}
    return NetCoreInstance(
        stages=tuple(stg["stage"]), regions=tuple(reg["region"]),
        fixed=col(stg, "stage", "fixed"), unit=col(stg, "stage", "unit"),
        operate=col(stg, "stage", "operate"),
        lead={k: int(v) for k, v in col(stg, "stage", "lead").items()},
        legacy_cap={k: float(v) for k, v in pair("legacy_cap").items()},
        legacy_ret={k: int(v) for k, v in pair("legacy_ret").items()},
        demand_base=col(reg, "region", "demand_base"),
        demand_growth=col(reg, "region", "demand_growth"),
        eta_ceil=col(eff, "stage", "eta_ceil"), eta_base=col(eff, "stage", "eta_base"),
        alpha=col(eff, "stage", "alpha"), beta=col(eff, "stage", "beta"),
        delta_bar=col(eff, "stage", "delta_bar"),
    )


# --------------------------------------------------------------- structure ---
@dataclass(frozen=True)
class NetCoreStructure:
    """Everything derived from the instance and the horizon knobs."""
    inst: NetCoreInstance
    nodes: tuple
    arcs: tuple
    LEN: list
    START: list
    P: list
    HORIZON: int
    YEARS: dict
    OMEGA: dict
    YEAR_TO_P: dict
    CRF: float
    MU: dict
    ETA: dict
    ACTIVE: tuple
    VIN: dict
    BUILD: tuple
    DEMAND: dict
    TRANSPORT: dict
    cap_min: float
    cap_max: float
    dr: float
    life: int
    legacy_byr: int

    @property
    def stages(self):
        return self.inst.stages

    @property
    def regions(self):
        return self.inst.regions


def build_netcore_structure(inst: NetCoreInstance, *,
                            blocks=((8, 1), (4, 3), (2, 5), (1, 9)),
                            dr: float = 0.05, life: int = 25,
                            cap_min: float = 60.0, cap_max: float = 260.0,
                            legacy_byr: int = -8, eta_floor: float = 0.60,
                            transport_own: float = 0.5,
                            transport_cross: float = 2.0) -> NetCoreStructure:
    """Derive the period mesh, discount weights, yields and active sets.

    `blocks` is a list of ``(count, length)``: Part 3 uses 8 single years then
    coarser blocks (15 periods over 39 years), Part 3b uses 6 (13 periods over
    37). Everything downstream follows from it, which is why it is a knob and
    not a table.
    """
    stages, regions = inst.stages, inst.regions
    nodes = tuple((s, r) for s in stages for r in regions)
    arcs = tuple((s, a, b) for s in stages for a in regions for b in regions)

    LEN, START, year = [], [], 1
    for count, length in blocks:
        for _ in range(count):
            LEN.append(length)
            START.append(year)
            year += length
    P = list(range(len(LEN)))
    HORIZON = year - 1
    YEARS = {p: list(range(START[p], START[p] + LEN[p])) for p in P}
    OMEGA = {p: sum(1 / (1 + dr) ** t for t in YEARS[p]) for p in P}
    YEAR_TO_P = {t: p for p in P for t in YEARS[p]}

    CRF = dr * (1 + dr) ** life / ((1 + dr) ** life - 1)
    ONLINE = {(s, p): START[p] + inst.lead[s] for s in stages for p in P}
    MU = {(s, v): CRF * sum(1 / (1 + dr) ** t
                            for t in range(ONLINE[s, v], ONLINE[s, v] + life)
                            if t <= HORIZON)
          for s in stages for v in P}

    vintages = [-1] + P
    build_year = {v: (legacy_byr if v == -1 else START[v]) for v in vintages}
    ETA = {}
    for s in stages:
        for v in vintages:
            frontier = inst.eta_ceil[s] - (inst.eta_ceil[s] - inst.eta_base[s]) \
                * (1 - inst.alpha[s]) ** (build_year[v] - 1)
            frontier = max(eta_floor, min(frontier, inst.eta_ceil[s]))
            for p in P:
                age = max(0, START[p] - build_year[v])
                aged = inst.eta_ceil[s] - (inst.eta_ceil[s] - frontier) \
                    * (1 - inst.beta[s]) ** age
                ETA[s, v, p] = max(eta_floor,
                                   min(frontier + inst.delta_bar[s], aged))

    ACTIVE = tuple(
        (s, r, v, p)
        for s in stages for r in regions for v in vintages for p in P
        # the retirement year is INCLUSIVE: an asset retiring in year 9 still
        # operates through a period starting in year 9
        if (START[p] <= inst.legacy_ret[s, r] if v == -1
            else (START[p] >= START[v] + inst.lead[s]
                  and START[p] <= START[v] + inst.lead[s] + life - 1)))
    VIN = {}
    for (s, r, v, p) in ACTIVE:
        VIN.setdefault((s, r, p), []).append(v)
    BUILD = tuple((s, r, v) for s in stages for r in regions for v in P
                  if START[v] + inst.lead[s] <= HORIZON)

    DEMAND = {}
    for r in regions:
        base, g = inst.demand_base[r], inst.demand_growth[r]
        for p in P:
            DEMAND[r, p] = sum(base * (1 + g) ** (t - 1) for t in YEARS[p]) / LEN[p]

    TRANSPORT = {(a, b): (transport_own if a == b else transport_cross)
                 for a in regions for b in regions}
    return NetCoreStructure(
        inst=inst, nodes=nodes, arcs=arcs, LEN=LEN, START=START, P=P,
        HORIZON=HORIZON, YEARS=YEARS, OMEGA=OMEGA, YEAR_TO_P=YEAR_TO_P, CRF=CRF,
        MU=MU, ETA=ETA, ACTIVE=ACTIVE, VIN=VIN, BUILD=BUILD, DEMAND=DEMAND,
        TRANSPORT=TRANSPORT, cap_min=cap_min, cap_max=cap_max, dr=dr, life=life,
        legacy_byr=legacy_byr)


# ------------------------------------------------------------------- model ---
def build_netcore(st: NetCoreStructure, *, learning: str = "capacity",
                  capex_mode: str = "annualized", capex_curve=None,
                  learn_stages=("PROC", "MFG"), tiers=None,
                  learn_scope: str = "regional", n_tiers: int = 3,
                  lag_years: int = 3, tier_min=None, allow_dispose: bool = True,
                  pen_short: float = 90.0, pen_dispose: float = 12.0,
                  pen_deviate: float = 35.0,
                  mipgap: float | None = MIPGAP_DEFAULT) -> gp.Model:
    """The Part 3 / Part 3b planner.

    ``learning``
        ``'none'``, ``'capacity'`` (Channel A: capex falls with cumulative
        capacity, via SOS2), ``'production'`` (Channel B: opex falls with lagged
        cumulative production, via tiers) or ``'both'``.
    ``capex_curve``
        ``(QBP, CBP)`` where CBP is in **money**, not multipliers. Build it with
        ``curves.capex_breakpoints(..., panels=600)`` scaled by the mean unit
        cost of the learning stages -- see the module docstring.
    ``tiers``
        ``(thresholds, multipliers)`` from ``curves.opex_tiers`` keyed by stage.
        Production learning is skipped when this is ``None``, which is what the
        calibration solve relies on.
    ``tier_min``
        ``{(stage, region, period): floor}``, the local-content lever. Empty
        reproduces Part 3.

    Part 3 is ``learning='capacity'`` with no tiers and no tier_min.
    """
    inst = st.inst
    stages, regions, P = inst.stages, inst.regions, st.P
    NODES, ARCS, ACTIVE, BUILD, VIN = st.nodes, st.arcs, st.ACTIVE, st.BUILD, st.VIN
    LEN, START, OMEGA, MU, ETA = st.LEN, st.START, st.OMEGA, st.MU, st.ETA
    learn_stages = tuple(learn_stages)
    tier_min = dict(tier_min or {})
    if learning not in ("none", "capacity", "production", "both"):
        raise ValueError(f"unknown learning mode {learning!r}")
    if learning in ("capacity", "both") and capex_curve is None:
        raise ValueError(f"learning={learning!r} needs a capex_curve")

    m = gp.Model("netcore")
    m.Params.OutputFlag = 0
    if mipgap is not None:
        m.Params.MIPGap = mipgap

    build = m.addVars(BUILD, vtype=GRB.BINARY, name="build")
    size = m.addVars(BUILD, lb=0.0, ub=st.cap_max, name="size")
    thr = m.addVars(ACTIVE, lb=0.0, name="thr")
    flow = m.addVars(ARCS, P, lb=0.0, name="flow")
    short = m.addVars(regions, P, lb=0.0, name="short")
    dev = m.addVars(NODES, P, lb=0.0, name="dev")
    disp = m.addVars(regions, P, lb=0.0, name="disp")

    m.addConstrs((size[s, r, v] <= st.cap_max * build[s, r, v]
                  for (s, r, v) in BUILD), name="size_ub")
    m.addConstrs((size[s, r, v] >= st.cap_min * build[s, r, v]
                  for (s, r, v) in BUILD), name="size_lb")
    m.addConstrs((thr[s, r, v, p] <= (inst.legacy_cap[s, r] if v == -1
                                      else size[s, r, v])
                  for (s, r, v, p) in ACTIVE), name="cap")
    # a node's yield-converted throughput leaves on its outbound arcs
    m.addConstrs((gp.quicksum(ETA[s, v, p] * thr[s, r, v, p] for v in VIN[s, r, p])
                  == flow.sum(s, r, "*", p)
                  for (s, r) in NODES for p in P), name="node_out")
    for i, s in enumerate(stages):
        if i == 0:
            continue
        prev = stages[i - 1]
        m.addConstrs((flow.sum(prev, "*", r, p)
                      == gp.quicksum(thr[s, r, v, p] for v in VIN[s, r, p])
                      for r in regions for p in P), name=f"in_{s}")
    last = stages[-1]
    if allow_dispose:
        m.addConstrs((flow.sum(last, "*", r, p) + short[r, p] - disp[r, p]
                      == st.DEMAND[r, p] for r in regions for p in P),
                     name="demand")
    else:
        m.addConstrs((flow.sum(last, "*", r, p) + short[r, p]
                      >= st.DEMAND[r, p] for r in regions for p in P),
                     name="demand")
    if tier_min:
        m.addConstrs((gp.quicksum(thr[s, r, v, p] for v in VIN[s, r, p])
                      + dev[s, r, p] >= tier_min.get((s, r, p), 0.0)
                      for (s, r) in NODES for p in P), name="local_content")

    # cumulative production state. Undiscounted on purpose: know-how accumulates
    # in physical units, so this uses LEN (years per period), never OMEGA.
    scope = ([(s, r) for (s, r) in NODES] if learn_scope == "regional"
             else [(s, "ALL") for s in stages])
    cum_ub = 3.0 * st.cap_max * st.HORIZON * (len(regions)
                                              if learn_scope == "global" else 1)
    cumprod = m.addVars(scope, P, lb=0.0, ub=cum_ub, name="cumprod")
    m.addConstrs((cumprod[s, rk, p]
                  == gp.quicksum(LEN[q] * thr[s, r, v, q]
                                 for r in (regions if rk == "ALL" else [rk])
                                 for q in P if q <= p
                                 for v in VIN[s, r, q])
                  for (s, rk) in scope for p in P), name="cum_prod")

    mult = ({(s, v): MU[s, v] for (s, r, v) in BUILD} if capex_mode == "annualized"
            else {(s, v): 1 / (1 + st.dr) ** START[v] for (s, r, v) in BUILD})
    capex = (gp.quicksum(mult[s, v] * inst.fixed[s] * build[s, r, v]
                         for (s, r, v) in BUILD)
             + gp.quicksum(mult[s, v] * inst.unit[s] * size[s, r, v]
                           for (s, r, v) in BUILD if s not in learn_stages))

    if learning in ("capacity", "both"):
        QBP, CBP = capex_curve
        K = list(range(len(QBP)))
        Q = m.addVars(P, lb=QBP[0], ub=QBP[-1], name="Qcum")
        Cc = m.addVars(P, lb=0.0, name="Ccum")
        lam = m.addVars(P, K, lb=0.0, ub=1.0, name="lam")
        m.addConstrs((lam.sum(p, "*") == 1 for p in P), name="sos_cvx")
        m.addConstrs((Q[p] == gp.quicksum(QBP[k] * lam[p, k] for k in K)
                      for p in P), name="sosQ")
        m.addConstrs((Cc[p] == gp.quicksum(CBP[k] * lam[p, k] for k in K)
                      for p in P), name="sosC")
        m.addConstrs((Q[p] == QBP[0] + gp.quicksum(size[s, r, v]
                                                   for (s, r, v) in BUILD
                                                   if s in learn_stages and v <= p)
                      for p in P), name="cumcap")
        # SOS2, not a free convex combination: the cumulative curve is CONCAVE
        # and this is a minimisation, so the chords lie below the truth and an
        # unrestricted lambda would buy capacity at a price that does not exist.
        for p in P:
            m.addSOS(GRB.SOS_TYPE2, [lam[p, k] for k in K])
        mu_tech = {p: MU[learn_stages[0], p] for p in P}
        capex += gp.quicksum(mu_tech[p] * (Cc[p] - (Cc[p - 1] if p > 0 else 0.0))
                             for p in P)
        m._Q, m._lam, m._K = Q, lam, K
    else:
        capex += gp.quicksum(mult[s, v] * inst.unit[s] * size[s, r, v]
                             for (s, r, v) in BUILD if s in learn_stages)
        m._Q = m._lam = m._K = None

    if learning in ("production", "both") and tiers:
        tier_q, tier_m = tiers
        J = list(range(n_tiers))
        z = m.addVars(scope, P, J, vtype=GRB.BINARY, name="tier")
        m.addConstrs((z.sum(s, rk, p, "*") == 1 for (s, rk) in scope for p in P),
                     name="one_tier")
        # the lag is defined in YEARS and then mapped to whichever period holds
        # that year, so it does not silently stretch as the periods coarsen
        lagp = {p: st.YEAR_TO_P[max(1, START[p] - lag_years)] for p in P}
        bigq = cum_ub
        m.addConstrs((cumprod[s, rk, lagp[p]]
                      >= tier_q[s][j - 1] - bigq * (1 - z[s, rk, p, j])
                      for (s, rk) in scope for p in P for j in J if j > 0),
                     name="tier_floor")
        m.addConstrs((cumprod[s, rk, lagp[p]]
                      <= tier_q[s][j] + bigq * (1 - z[s, rk, p, j])
                      for (s, rk) in scope for p in P for j in J
                      if j < n_tiers - 1), name="tier_ceil")
        # Split throughput across tiers so multiplier x throughput stays LINEAR.
        # The opex rate does not depend on vintage, so splitting at node level is
        # exactly equivalent to splitting per vintage, and far smaller.
        tsplit = m.addVars(NODES, P, J, lb=0.0, name="tsplit")
        m.addConstrs((tsplit.sum(s, r, p, "*")
                      == gp.quicksum(thr[s, r, v, p] for v in VIN[s, r, p])
                      for (s, r) in NODES for p in P), name="tsplit_sum")
        m.addConstrs((tsplit[s, r, p, j]
                      <= 3 * st.cap_max * z[s, (r if learn_scope == "regional"
                                                else "ALL"), p, j]
                      for (s, r) in NODES for p in P for j in J), name="tier_link")
        operate = gp.quicksum(OMEGA[p] * inst.operate[s] * tier_m[s][j]
                              * tsplit[s, r, p, j]
                              for (s, r) in NODES for p in P for j in J)
        m._z = z
    else:
        operate = gp.quicksum(OMEGA[p] * inst.operate[s] * thr[s, r, v, p]
                              for (s, r, v, p) in ACTIVE)
        m._z = None

    transport = gp.quicksum(OMEGA[p] * st.TRANSPORT[a, b] * flow[s, a, b, p]
                            for (s, a, b) in ARCS for p in P)
    penalty = (gp.quicksum(OMEGA[p] * pen_short * short[r, p]
                           for r in regions for p in P)
               + gp.quicksum(OMEGA[p] * pen_deviate * dev[s, r, p]
                             for (s, r) in NODES for p in P)
               + gp.quicksum(OMEGA[p] * pen_dispose * disp[r, p]
                             for r in regions for p in P))

    m.setObjective(capex + operate + transport + penalty, GRB.MINIMIZE)
    m._e = dict(capex=capex, operate=operate, transport=transport,
                penalty=penalty)
    m._v = dict(build=build, size=size, thr=thr, flow=flow, short=short,
                dev=dev, disp=disp, cumprod=cumprod)
    m._scope = scope
    return m


def netcore_plan(m: gp.Model) -> dict:
    """The build decisions, as ``{(stage, region, period): size}``."""
    b, c = m._v["build"], m._v["size"]
    return {k: round(c[k].X, 6) for k in b if b[k].X > 0.5}


def solve_netcore(st: NetCoreStructure, **kw) -> dict:
    """Build, optimise, and return the plan alongside the cost components."""
    m = build_netcore(st, **kw)
    m.optimize()
    if m.SolCount == 0:
        return dict(obj=None, status=m.Status, model=m)
    plan = netcore_plan(m)
    return dict(
        obj=m.ObjVal, model=m, plan=plan,
        builds=len(plan), capacity=round(sum(plan.values()), 4),
        build_years=sorted(st.START[v] for (_s, _r, v) in plan),
        components={k: v.getValue() for k, v in m._e.items()},
        short=sum(m._v["short"][r, p].X for r in st.regions for p in st.P),
        dispose=sum(m._v["disp"][r, p].X for r in st.regions for p in st.P),
        deviate=sum(m._v["dev"][s, r, p].X for (s, r) in st.nodes for p in st.P),
        nvars=m.NumVars, nbin=m.NumBinVars,
    )


def calibrate_tiers(st: NetCoreStructure, *, n_tiers: int = 3,
                    lr_opex: float = 0.18, opex_floor: float = 0.65, **kw):
    """Run the no-learning solve and place the tier thresholds off its production.

    The thresholds have to come from *somewhere*, and taking them from a solve
    that already has production learning would be circular. So: solve without
    it, observe how much each stage actually produces, and put the thresholds at
    doublings of that. Returns ``(tiers, objective, prod_by_stage)``.
    """
    from .curves import opex_tiers

    kw.setdefault("learning", "none")
    m = build_netcore(st, **kw)
    m.optimize()
    assert m.SolCount > 0, "the calibration solve found no solution"
    cum = m._v["cumprod"]
    prod = {}
    for s in st.inst.stages:
        prod[s] = max(cum[s, rk, st.P[-1]].X for (ss, rk) in m._scope if ss == s)
    return opex_tiers(prod, n_tiers, lr_opex, opex_floor), m.ObjVal, prod


def utilization(st: NetCoreStructure, m: gp.Model) -> dict:
    """Throughput as a fraction of installed capacity, per node."""
    thr, size = m._v["thr"], m._v["size"]
    out = {}
    for (s, r) in st.nodes:
        used = cap = 0.0
        for p in st.P:
            for v in st.VIN[s, r, p]:
                used += st.LEN[p] * thr[s, r, v, p].X
                cap += st.LEN[p] * (st.inst.legacy_cap[s, r] if v == -1
                                    else size[s, r, v].X)
        out[s, r] = 100.0 * used / cap if cap > 0 else 0.0
    return out


def tier_minimums(st: NetCoreStructure, level: float, phase_in: int = 6) -> dict:
    """The local-content lever: a floor on throughput at every node.

    `phase_in` is a calendar YEAR, not a period index: a minimum that binds from
    day one would simply forbid the legacy fleet's retirement profile.
    """
    if level <= 0:
        return {}
    return {(s, r, p): (0.0 if st.START[p] < phase_in else level)
            for (s, r) in st.nodes for p in st.P}
