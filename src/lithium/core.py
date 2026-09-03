"""The deterministic multi-period network MILP of Parts 1 and 2.

Six sites — two mines, two processors, two fabricators — with arc flows between
them, lumpy capacity built in discrete units, vintage-indexed yields, and three
learning modes. One decision maker, so it is a planning model, not a game.

**Not the Part 4 model.** `lithium.regions` builds a two-region, three-stage
chain for a *firm*; this builds a six-site network for a *planner*. They share no
code and no instance — see `network_instance.py`.

The adjudication (`PLAN.md` §5, group 3): `build` appears in Parts 1, 2 and 5.
Parts 1 and 2 differ by 9 lines and it is a **feature** — Part 2 adds a `mipgap`
argument, because progressive hedging solves subproblems to a tighter gap than
the 0.005 a standalone solve wants. Part 2's version is the one here, with
`mipgap=None` reproducing Part 1 exactly. Part 5's `build` shares the name and
3.7% of the text; it is a different model and is not in this module.

As in `structure.py`, every knob arrives as an argument. `CoreStructure` holds
what is *derived* from the instance plus those knobs — discount factors, the
capital recovery factor, yields by vintage, the demand path — because deriving
them is what the teaching notebook does by hand.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass

import gurobipy as gp
from gurobipy import GRB

from .network_instance import NetworkInstance

__all__ = ["CoreStructure", "build_core_structure", "capex_pv_multiplier",
           "learning_breakpoints", "build", "build_plan", "solve",
           "evaluate_plan", "rolling_horizon", "staggered_years"]


@dataclass(frozen=True)
class CoreStructure:
    """Everything the network model indexes over, for one instance and horizon."""

    inst: NetworkInstance

    # time
    T: int
    r: float
    years: list[int]
    df: dict[int, float]
    crf: float

    # technology knobs that the model reads everywhere
    life: int
    max_builds: int
    eta_mine: float
    eta_min: float

    # derived
    ETA: dict[tuple[str, int, int], float]      # (tier, vintage, year) -> yield
    D: dict[tuple[str, int], float]             # (region, year) -> demand
    tc: dict[tuple[str, str], float]            # (site, site) -> transport
    tc_dem: dict[tuple[str, str], float]        # (fab, region) -> transport
    slack_pen: float

    # learning
    learn_sites: tuple[str, ...]
    learn_frac: float
    lr: float
    q0: float
    c_floor_frac: float
    g_exog: float

    @property
    def sites(self):
        return self.inst.sites

    @property
    def regions(self):
        return self.inst.regions


def build_core_structure(
    inst: NetworkInstance, *,
    T: int = 20, r: float = 0.05, life: int = 20, max_builds: int = 3,
    eta_mine: float = 0.90, eta_min: float = 0.60,
    transport_own: float = 0.4, transport_cross: float = 1.6,
    slack_pen: float = 45.0,
    learn_tiers=("P", "F"), learn_frac: float = 0.70, lr: float = 0.20,
    q0: float = 380.0, c_floor_frac: float = 0.55, g_exog: float = 0.035,
) -> CoreStructure:
    """Derive the sets and coefficients from one instance and the horizon knobs.

    Mirrors what the teaching notebook writes out by hand. The defaults are the
    values the shipped notebooks use; the notebook still passes each explicitly,
    so a reader who changes `r` sees it move both models.
    """
    years = list(range(1, T + 1))
    df = {t: 1.0 / (1 + r) ** t for t in years}
    crf = r * (1 + r) ** life / ((1 + r) ** life - 1)

    # yields: a vintage-v asset of tier `tier` operating in year t. Two effects -
    # a later vintage starts closer to the ceiling, and an asset improves within
    # its own life, but by at most `dbar`.
    vintages = sorted({lv for (_, lv, _) in inst.legacy.values()} | set(years))
    ETA = {}
    for tier in ("P", "F"):
        eb, e0 = inst.eta_bar[tier], inst.eta_0[tier]
        a, b, db = inst.alpha[tier], inst.beta[tier], inst.dbar[tier]
        for v in vintages:
            e_new = max(eb - (eb - e0) * (1 - a) ** (v - 1), eta_min)
            for t in years:
                e_t = eb - (eb - e_new) * (1 - b) ** (t - v)
                ETA[tier, v, t] = max(eta_min, min(e_new + db, e_t))

    D = {(g, t): inst.demand_base[g] * (1 + inst.demand_growth[g]) ** (t - 1)
         for g in inst.regions for t in years}

    home = inst.home
    tc = {(a, b): (transport_own if home[a] == home[b] else transport_cross)
          for a in inst.sites for b in inst.sites}
    tc_dem = {(f, g): (transport_own if home[f] == g else transport_cross)
              for f in inst.fabs for g in inst.regions}

    learn_sites = tuple(s for s in inst.sites if inst.tier[s] in learn_tiers)

    return CoreStructure(
        inst=inst, T=T, r=r, years=years, df=df, crf=crf, life=life,
        max_builds=max_builds, eta_mine=eta_mine, eta_min=eta_min,
        ETA=ETA, D=D, tc=tc, tc_dem=tc_dem, slack_pen=slack_pen,
        learn_sites=learn_sites, learn_frac=learn_frac, lr=lr, q0=q0,
        c_floor_frac=c_floor_frac, g_exog=g_exog,
    )


# ---------------------------------------------------------------- capex timing
def capex_pv_multiplier(st: CoreStructure, s: str, dec_year: int, mode: str,
                        y_start: int = 1, y_end: int | None = None) -> float:
    """PV (discounted to year 0) of $1 of capex for a facility decided in `dec_year`.

    ``annualized`` : CRF x $1 charged each operating year inside [y_start, y_end]
    ``lumpsum``    : the full $1 paid at the decision year

    The difference is the subject of Part 1 section 4, and it is not cosmetic:
    lump-sum charges the whole cost inside the horizon while annualised charges
    only the part of the asset's life that falls inside it, so lump-sum
    systematically refuses to build late.
    """
    y_end = y_end or st.T
    online = dec_year + st.inst.lead[s]
    if mode == "lumpsum":
        return st.df.get(dec_year, 0.0)
    last = min(online + st.life - 1, y_end)
    if last < online:
        return 0.0
    return st.crf * sum(st.df[t] for t in range(online, last + 1) if t in st.df)


def learning_breakpoints(st: CoreStructure, qmax: float, nbp: int = 7):
    """Breakpoints for cumulative capex C(Q) under Wright's law with a floor.

    Returns ``(Qbp, Cbp, unit)``. The model interpolates **cumulative** cost, not
    unit cost, because the cost of the next unit is what the curve says at that
    point — not what it said at `q0`.
    """
    b = -math.log2(1 - st.lr)
    cf = st.c_floor_frac

    def unit(q):
        return max(cf, (q / st.q0) ** (-b))

    def cum(q):
        # integral of unit() from q0 to q, numerically (robust with the floor)
        n, lo, acc = 400, st.q0, 0.0
        if q <= lo:
            return 0.0
        h = (q - lo) / n
        for i in range(n):
            acc += 0.5 * (unit(lo + i * h) + unit(lo + (i + 1) * h)) * h
        return acc

    Qbp = [st.q0 + (qmax - st.q0) * (i / (nbp - 1)) for i in range(nbp)]
    return Qbp, [cum(q) for q in Qbp], unit


# ------------------------------------------------------------------ the model
def build(st: CoreStructure, invest_years=None, capex_mode="annualized",
          learning="none", y_start=1, y_end=None, fixed_builds=None,
          forced_zero_after=None, relax_int_after=None, quiet=True,
          demand=None, into=None, prefix="", mipgap=None):
    """The deterministic network MILP.

    invest_years      : years in which a build decision may be taken
    capex_mode        : 'annualized' | 'lumpsum'
    learning          : 'none' | 'exogenous' | 'endogenous'
    y_start, y_end    : operating window (for rolling horizon)
    fixed_builds      : {(site, dec_year): units} inherited from earlier rolls
    forced_zero_after : no new builds decided after this year
    relax_int_after   : builds decided after this year are continuous in [0, 1]
    into, prefix      : embed this block into a larger model (the extensive form)
    mipgap            : None means 0.005. Part 2 passes a tighter one.
    """
    d = st.inst
    y_end = y_end or st.T
    yrs = [t for t in st.years if y_start <= t <= y_end]
    if invest_years is None:
        invest_years = list(st.years)
    IY = [v for v in invest_years if y_start <= v <= y_end]
    if forced_zero_after is not None:
        IY = [v for v in IY if v <= forced_zero_after]

    def usable(s, v):
        # a decision only matters if the asset comes online inside the window
        return v + d.lead[s] <= y_end
    site_IY = {s: [v for v in IY if usable(s, v)] for s in d.sites}

    D = demand if demand is not None else st.D
    if into is not None:
        m = into
    else:
        m = gp.Model()
        if quiet:
            m.Params.OutputFlag = 0
        m.Params.MIPGap = 0.005 if mipgap is None else mipgap

    # --- build decisions: y[s, v, k] = k-th unit at site s decided in year v ---
    idx = [(s, v, k) for s in d.sites for v in site_IY[s]
           for k in range(st.max_builds)]
    y = {}
    for (s, v, k) in idx:
        cont = (relax_int_after is not None and v > relax_int_after)
        y[s, v, k] = m.addVar(vtype=GRB.CONTINUOUS if cont else GRB.BINARY,
                              ub=1.0, name=f"{prefix}y_{s}_{v}_{k}")
    # symmetry breaking within a site-year: units are interchangeable, so insist
    # they are taken in order and the solver stops exploring permutations
    for s in d.sites:
        for v in site_IY[s]:
            for k in range(st.max_builds - 1):
                m.addConstr(y[s, v, k] >= y[s, v, k + 1])

    # capacity inherited from earlier rolls, as {(site, decision year): units}
    prebuilt = fixed_builds or {}

    def online_units(s, t):
        """(vintage, units) pairs available at site s in year t."""
        terms = []
        if s in d.legacy:
            ln, lv, lret = d.legacy[s]
            if t <= lret:
                terms.append((lv, float(ln)))
        for v in site_IY[s]:
            on = v + d.lead[s]
            if on <= t <= on + st.life - 1:
                terms.append((v, gp.quicksum(y[s, v, k]
                                             for k in range(st.max_builds))))
        for (ps, pv), n in prebuilt.items():
            if ps == s:
                on = pv + d.lead[s]
                if on <= t <= on + st.life - 1:
                    terms.append((pv, n))
        return terms

    # --- throughput, vintage indexed at the P and F tiers ---
    thr = {}
    for s in d.procs + d.fabs:
        for t in yrs:
            for (v, _) in online_units(s, t):
                if (s, v, t) not in thr:
                    thr[s, v, t] = m.addVar(name=f"{prefix}thr_{s}_{v}_{t}")
    ext = {(s, t): m.addVar(name=f"{prefix}ext_{s}_{t}")
           for s in d.mines for t in yrs}

    # --- arc flows ---
    fmp = {(a, b, t): m.addVar() for a in d.mines for b in d.procs for t in yrs}
    fpf = {(a, b, t): m.addVar() for a in d.procs for b in d.fabs for t in yrs}
    ffr = {(a, g, t): m.addVar() for a in d.fabs for g in d.regions for t in yrs}
    slk = {(g, t): m.addVar() for g in d.regions for t in yrs}

    # --- capacity ---
    for t in yrs:
        for s in d.mines:
            cap = gp.quicksum(n * d.cap_unit[s] for (_, n) in online_units(s, t))
            m.addConstr(ext[s, t] <= cap)
        for s in d.procs + d.fabs:
            for (v, n) in online_units(s, t):
                m.addConstr(thr[s, v, t] <= n * d.cap_unit[s])

    # --- flow balance, tier by tier ---
    for t in yrs:
        for s in d.mines:
            m.addConstr(st.eta_mine * ext[s, t]
                        == gp.quicksum(fmp[s, b, t] for b in d.procs))
        for s in d.procs:
            vints = [v for (v, _) in online_units(s, t)]
            m.addConstr(gp.quicksum(fmp[a, s, t] for a in d.mines)
                        == gp.quicksum(thr[s, v, t] for v in vints))
            m.addConstr(gp.quicksum(st.ETA["P", v, t] * thr[s, v, t] for v in vints)
                        == gp.quicksum(fpf[s, b, t] for b in d.fabs))
        for s in d.fabs:
            vints = [v for (v, _) in online_units(s, t)]
            m.addConstr(gp.quicksum(fpf[a, s, t] for a in d.procs)
                        == gp.quicksum(thr[s, v, t] for v in vints))
            m.addConstr(gp.quicksum(st.ETA["F", v, t] * thr[s, v, t] for v in vints)
                        == gp.quicksum(ffr[s, g, t] for g in d.regions))
        for g in d.regions:
            m.addConstr(gp.quicksum(ffr[f, g, t] for f in d.fabs) + slk[g, t]
                        >= D[g, t])

    # --- capex: a site adder that never learns, plus technology that may ---
    LS = set(st.learn_sites)
    adder = {s: d.capex0[s] * (1 - st.learn_frac) if s in LS else d.capex0[s]
             for s in d.sites}
    tech_rate = (sum(d.capex0[s] * st.learn_frac / d.cap_unit[s] for s in LS)
                 / len(LS))                       # $ per unit of capacity

    capex_expr = gp.LinExpr()
    for s in d.sites:                              # site adders, in every mode
        for v in site_IY[s]:
            mult = capex_pv_multiplier(st, s, v, capex_mode, y_start, y_end)
            for k in range(st.max_builds):
                capex_expr += mult * adder[s] * y[s, v, k]

    if learning in ("none", "exogenous"):
        for s in LS:
            for v in site_IY[s]:
                mult = capex_pv_multiplier(st, s, v, capex_mode, y_start, y_end)
                decay = (1 - st.g_exog) ** (v - 1) if learning == "exogenous" else 1.0
                rate = tech_rate * max(decay, st.c_floor_frac)
                for k in range(st.max_builds):
                    capex_expr += mult * rate * d.cap_unit[s] * y[s, v, k]
    else:  # endogenous: SOS2 on CUMULATIVE technology cost
        qmax = st.q0 + sum(d.cap_unit[s] * st.max_builds for s in LS) * max(
            1, len(IY) // 3)
        Qbp, Cbp, _ = learning_breakpoints(st, qmax)
        allv = sorted({v for s in LS for v in site_IY[s]})
        prevC = None
        for v in allv:
            Qv = m.addVar(lb=st.q0, ub=qmax, name=f"{prefix}Qcum_{v}")
            Cv = m.addVar(lb=0, name=f"{prefix}Ccum_{v}")
            lam = [m.addVar(lb=0, ub=1, name=f"{prefix}lam_{v}_{j}")
                   for j in range(len(Qbp))]
            m.addConstr(gp.quicksum(lam) == 1)
            m.addConstr(Qv == gp.quicksum(l * q for l, q in zip(lam, Qbp)))
            m.addConstr(Cv == gp.quicksum(l * c for l, c in zip(lam, Cbp)))
            m.addSOS(GRB.SOS_TYPE2, lam)           # <-- the essential restriction
            pre_q = sum(d.cap_unit[ps] * n for (ps, pv), n in prebuilt.items()
                        if ps in LS and pv <= v)
            m.addConstr(Qv == st.q0 + pre_q + gp.quicksum(
                d.cap_unit[s] * y[s, vv, k]
                for s in LS for vv in site_IY[s] if vv <= v
                for k in range(st.max_builds)))
            cand = [capex_pv_multiplier(st, s, v, capex_mode, y_start, y_end)
                    for s in LS if v in site_IY[s]]
            mult = sum(cand) / len(cand) if cand else 0.0
            capex_expr += mult * tech_rate * (Cv - (prevC if prevC is not None else 0))
            prevC = Cv

    # --- operating, transport, and the unmet-demand penalty ---
    op = gp.LinExpr()
    for t in yrs:
        w = st.df[t]
        for s in d.mines:
            op += w * d.opex[s] * ext[s, t]
        for s in d.procs + d.fabs:
            for (v, _) in online_units(s, t):
                op += w * d.opex[s] * thr[s, v, t]
        for a in d.mines:
            for b in d.procs:
                op += w * st.tc[a, b] * fmp[a, b, t]
        for a in d.procs:
            for b in d.fabs:
                op += w * st.tc[a, b] * fpf[a, b, t]
        for f in d.fabs:
            for g in d.regions:
                op += w * st.tc_dem[f, g] * ffr[f, g, t]
        for g in d.regions:
            op += w * st.slack_pen * slk[g, t]

    if into is None:
        m.setObjective(capex_expr + op, GRB.MINIMIZE)
    m._y, m._siteIY, m._IY, m._slk, m._ffr, m._st = y, site_IY, IY, slk, ffr, st
    m._capex_expr, m._op_expr = capex_expr, op
    m._adder, m._tech_rate = adder, tech_rate
    if into is not None:
        return m, y, capex_expr + op, slk
    return m


def build_plan(m) -> dict:
    """Extract ``{(site, decision year): units}`` from a solved model."""
    out = {}
    for (s, v, k), var in m._y.items():
        if var.X > 0.5:
            out[s, v] = out.get((s, v), 0) + 1
    return out


# ------------------------------------------------------------- driving it
def solve(st: CoreStructure, tag: str, **kw) -> dict:
    """Build, optimise, and return the result with timing and a build plan."""
    t0 = time.time()
    m = build(st, **kw)
    m.optimize()
    el = time.time() - t0
    if m.Status not in (GRB.OPTIMAL, GRB.TIME_LIMIT) or m.SolCount == 0:
        return dict(tag=tag, obj=None, sec=el, status=m.Status)
    return dict(tag=tag, obj=m.ObjVal, bound=m.ObjBound, sec=el,
                nbin=m.NumBinVars, nvar=m.NumVars, nodes=int(m.NodeCount),
                plan=build_plan(m),
                slack=sum(v.X for v in m._slk.values()), model=m)


def evaluate_plan(st: CoreStructure, plan: dict, capex_mode="annualized",
                  learning="none", mipgap: float | None = None):
    """Cost of a FIXED build plan under the full-horizon model, ops re-optimised.

    `build` charges nothing for prebuilt capacity, so the plan's own capex has to
    be added back here. Forgetting that would make any plan look free.
    """
    m = build(st, invest_years=[], capex_mode=capex_mode, learning=learning,
              fixed_builds=plan, mipgap=mipgap)
    d, LS = st.inst, set(st.learn_sites)
    tech_rate = (sum(d.capex0[x] * st.learn_frac / d.cap_unit[x] for x in LS)
                 / len(LS))
    extra = 0.0
    for (s, v), n in plan.items():
        mult = capex_pv_multiplier(st, s, v, capex_mode)
        unit = (d.capex0[s] * (1 - st.learn_frac) + tech_rate * d.cap_unit[s]
                if s in LS else d.capex0[s])
        extra += n * unit * mult
    m.optimize()
    if m.SolCount == 0:
        return None
    return m.ObjVal + extra


def rolling_horizon(st: CoreStructure, W: int, delta: int, invest_step: int = 1,
                    decision_zone: int | None = None, tail_continuous: bool = True,
                    capex_mode: str = "annualized",
                    mipgap: float | None = None):
    """Re-solve on a moving window, committing `delta` years at a time.

    W               : foresight window length
    delta           : roll step, i.e. years committed per solve
    decision_zone   : years from the window start in which BINARY builds are
                      allowed (None = the whole window)
    tail_continuous : builds beyond the decision zone are continuous rather than
                      banned. Banning them is an artefact generator - Part 1
                      section 7 measures what it costs.
    mipgap          : passed to every window solve. It MUST be the gap the
                      caller compares the result against: each window commits a
                      discrete plan, so a looser gap does not shift the answer
                      slightly, it commits a different plan and the error
                      compounds across windows. At 0.005 rather than the
                      notebook's 0.001, W=3 commits 5 units instead of 4.

    Returns ``(committed plan, log)``.
    """
    committed, log, start = {}, [], 1
    while start <= st.T:
        y_end = min(start + W - 1, st.T)
        dz_end = (y_end if decision_zone is None
                  else min(start + decision_zone - 1, y_end))
        iy = [v for v in range(start, y_end + 1) if (v - 1) % invest_step == 0]
        kw = dict(invest_years=iy, capex_mode=capex_mode, y_start=start,
                  y_end=y_end, fixed_builds=dict(committed), mipgap=mipgap)
        if tail_continuous:
            kw["relax_int_after"] = dz_end
        else:
            kw["forced_zero_after"] = dz_end
        m = build(st, **kw)
        m.optimize()
        if m.SolCount == 0:
            log.append((start, y_end, "INFEASIBLE"))
            break
        newly = {}
        for (s, v, k), var in m._y.items():
            if v <= start + delta - 1 and var.X > 0.5:
                newly[s, v] = newly.get((s, v), 0) + 1
        for key, n in newly.items():
            committed[key] = committed.get(key, 0) + n
        log.append((start, y_end, dz_end, dict(newly)))
        start += delta
    return committed, log


def staggered_years(T: int, fine: int = 6, mid_step: int = 2, mid_end: int = 10,
                    coarse_step: int = 5) -> list[int]:
    """Annual for years 1..fine, every `mid_step` to `mid_end`, then `coarse_step`.

    The point of Part 1 section 5: investment granularity need not be uniform,
    and a staggered mesh buys most of the accuracy of an annual one at a fraction
    of the binary count.
    """
    ys = list(range(1, fine + 1))
    ys += [t for t in range(fine + 1, mid_end + 1) if (t - fine - 1) % mid_step == 0]
    ys += [t for t in range(mid_end + 1, T + 1) if (t - mid_end - 1) % coarse_step == 0]
    return sorted(set(ys))
