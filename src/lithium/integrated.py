"""The integrated deterministic core behind Part 5.

A **sixth instance**, and the only one in the series with a **closed loop**. Five
stages -- MINE, PROC, CATH, CELL, PACK -- plus a sixth, REC, which is not part of
the chain but feeds back into it: packs sold `pack_life` years ago become scrap,
and a `recovery` fraction of that returns as PROC-grade material that CATH can
consume instead of freshly processed ore.

That loop is the whole point, and it is what makes this model different from
Part 3's. There, material flows one way and the only question is how much
capacity to build where. Here a decision made in period 3 changes what is
*available* in period 8, so the model has to reason about its own output as a
future input.

Two consequences worth knowing before reading the code:

- **The recycling constraint is an inequality, not an equality.** Scrap is an
  upper bound on what recycling can process, not a quota it must meet. Written as
  an equality the model would be forced to recycle everything it ever sold,
  including in periods where doing so is absurd.
- **`allow_dual_feedstock` is not cosmetic.** With it off, recycled material has
  nowhere to go, and the model must be told so explicitly -- otherwise REC
  capacity is free to be built and its output silently vanishes, which reports a
  cheaper answer than the truth. `build` adds `f.sum("REC", ...) == 0` for
  exactly that reason.

Part 5's original notebook kept every parameter in one `BASE` dict. Here they are
split the way `CLAUDE.md` Part 4 asks: instance **tables** in `data/raw/`
(per-stage costs and lifetimes, per-region demand, the legacy fleet) and
**knobs** as keyword arguments (the period plan, the discount rate, the size
bounds, the loop's `pack_life` and `recovery`).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import gurobipy as gp
from gurobipy import GRB

# Part 5 differences objectives against each other -- the value of dual feedstock
# is 2.2% -- so the gap has to sit well under that. Verified during migration
# that the objective is identical from 5e-3 down to 1e-5 on this instance, but
# that is a property of the instance and not a licence to rely on it.
MIPGAP_DEFAULT = 1e-4


@dataclass(frozen=True)
class IntegratedInstance:
    """The tables Part 5 reads. Knobs are arguments, not fields."""
    regions: tuple[str, ...]
    chain: tuple[str, ...]           # the one-way stages, in order
    stages: tuple[str, ...]          # chain + the recycling stage
    recycle_stage: str
    lead: dict[str, int]
    life: dict[str, int]
    yield_: dict[str, float]
    fixed_cost: dict[str, float]
    unit_cost: dict[str, float]
    op_cost: dict[str, float]
    demand0: dict[str, float]
    legacy_cap: dict[tuple[str, str], float]


def load_integrated_instance(source: Path | str | None = None
                             ) -> IntegratedInstance:
    import pandas as pd

    names = ("integrated_stages.csv", "integrated_regions.csv",
             "integrated_legacy.csv")
    roots = []
    if source is not None:
        roots.append(Path(source))
    roots.append(Path(__file__).resolve().parents[2] / "data" / "raw")
    roots.append(Path(__file__).resolve().parent / "data")
    for root in roots:
        if all((root / n).exists() for n in names):
            stg, reg, leg = (pd.read_csv(root / n) for n in names)
            break
    else:
        raise FileNotFoundError(
            f"could not find {names} in {[str(r) for r in roots]}")

    chain = tuple(stg.loc[stg["in_chain"] == 1, "stage"])
    rec = tuple(stg.loc[stg["in_chain"] == 0, "stage"])
    if len(rec) != 1:
        raise ValueError(f"expected exactly one recycling stage, found {rec}")
    col = lambda c, cast: {s: cast(v) for s, v in zip(stg["stage"], stg[c])}  # noqa: E731
    return IntegratedInstance(
        regions=tuple(reg["region"]), chain=chain, stages=chain + rec,
        recycle_stage=rec[0],
        lead=col("lead", int), life=col("life", int),
        yield_=col("yield", float), fixed_cost=col("fixed_cost", float),
        unit_cost=col("unit_cost", float), op_cost=col("op_cost", float),
        demand0={r: float(d) for r, d in zip(reg["region"], reg["demand0"])},
        legacy_cap={(s, r): float(c) for s, r, c
                    in zip(leg["stage"], leg["region"], leg["legacy_cap"])},
    )


def periods_from_plan(plan):
    """``[(count, years_each), ...]`` -> ``(lengths, starts, horizon)``."""
    lens = [L for n, L in plan for _ in range(n)]
    starts, t = [], 0
    for L in lens:
        starts.append(t)
        t += L
    return lens, starts, t


def build(inst: IntegratedInstance, *,
          period_plan=((6, 1), (4, 3), (3, 5)), rho: float = 0.05,
          cap_min: float = 8.0, cap_max: float = 60.0,
          tau_intra: float = 0.3, tau_inter: float = 1.6,
          penalty: float = 40.0, pack_life: int = 10, recovery: float = 0.55,
          demand_growth: float = 0.045, allow_dual_feedstock: bool = True,
          mipgap: float | None = MIPGAP_DEFAULT,
          demand0: dict | None = None, legacy_cap: dict | None = None,
          regions=None, verbose: bool = False) -> gp.Model:
    """The integrated core.

    `demand0`, `legacy_cap` and `regions` override the instance's own tables.
    They exist for `collapse_test`, which needs to pose the same model on two
    different region sets -- and for a reader who wants to change one number
    without editing a CSV.
    """
    R = tuple(regions) if regions is not None else inst.regions
    chain, stages = inst.chain, inst.stages
    rec = inst.recycle_stage
    d0 = demand0 if demand0 is not None else inst.demand0
    leg = legacy_cap if legacy_cap is not None else inst.legacy_cap

    lens, starts, H = periods_from_plan(period_plan)
    P = list(range(len(lens)))
    # a period's weight is the SUM of the annual discount factors inside it, so
    # a 5-year period carries five years of cost. Not an average.
    omega = {p: sum((1 + rho) ** -(starts[p] + k) for k in range(lens[p]))
             for p in P}
    VIN = [-1] + P

    def online(s, v, p):
        if v == -1:
            return True
        ready = starts[v] + inst.lead[s]
        return ready <= starts[p] < ready + inst.life[s]

    BUILD = [(s, r, v) for s in stages for r in R for v in P]
    ACTIVE = [(s, r, v, p) for s in stages for r in R for v in VIN for p in P
              if online(s, v, p) and (v != -1 or (s, r) in leg)]
    ARCS = [(s, r1, r2) for s in stages for r1 in R for r2 in R]

    def mu(s, v):
        life = inst.life[s]
        crf = rho * (1 + rho) ** life / ((1 + rho) ** life - 1)
        t0 = starts[v] + inst.lead[s]
        yrs = list(range(t0, min(t0 + life, H)))
        return crf * sum((1 + rho) ** -t for t in yrs) if yrs else 0.0

    DEM = {(r, p): d0[r] * (1 + demand_growth) ** starts[p] for r in R for p in P}

    m = gp.Model("integrated_core")
    m.Params.OutputFlag = 1 if verbose else 0
    if mipgap is not None:
        m.Params.MIPGap = mipgap

    y = m.addVars(BUILD, vtype=GRB.BINARY, name="y")
    c = m.addVars(BUILD, lb=0.0, ub=cap_max, name="c")
    x = m.addVars(ACTIVE, lb=0.0, name="x")
    f = m.addVars(ARCS, P, lb=0.0, name="f")
    u = m.addVars(R, P, lb=0.0, name="u")

    m.addConstrs((c[s, r, v] <= cap_max * y[s, r, v] for (s, r, v) in BUILD),
                 name="size_hi")
    m.addConstrs((c[s, r, v] >= cap_min * y[s, r, v] for (s, r, v) in BUILD),
                 name="size_lo")
    m.addConstrs((x[s, r, v, p] <= (leg[s, r] if v == -1 else c[s, r, v])
                  for (s, r, v, p) in ACTIVE), name="cap")

    def thr(s, r, p):
        return gp.quicksum(x[s, r, v, p] for v in VIN if (s, r, v, p) in x)

    m.addConstrs((inst.yield_[s] * thr(s, r, p) == f.sum(s, r, "*", p)
                  for s in stages for r in R for p in P), name="out")

    for i, s in enumerate(chain):
        if i == 0:
            continue                     # the first stage draws on reserves
        prev = chain[i - 1]
        for r in R:
            for p in P:
                inflow = f.sum(prev, "*", r, p)
                if s == "CATH" and allow_dual_feedstock:
                    inflow = inflow + f.sum(rec, "*", r, p)      # the loop closes
                m.addConstr(inflow == thr(s, r, p), name=f"in_{s}_{r}_{p}")

    if not allow_dual_feedstock:
        # Without this the recycled flow has no consumer and simply disappears,
        # so REC capacity looks free and the objective comes out too low.
        m.addConstrs((f.sum(rec, "*", r, p) == 0 for r in R for p in P),
                     name="rec_sink")

    def pack_period(p):
        """The period containing ``start[p] - pack_life``, or None if pre-horizon."""
        t = starts[p] - pack_life
        if t < 0:
            return None
        for q in P:
            if starts[q] <= t < starts[q] + lens[q]:
                return q
        return None

    for r in R:
        for p in P:
            q = pack_period(p)
            if q is None:
                m.addConstr(thr(rec, r, p) == 0, name=f"rec0_{r}_{p}")
            else:
                # <=, not ==: scrap BOUNDS what recycling can process. As an
                # equality the model would be forced to recycle everything it
                # ever sold, in every period, whether or not that made sense.
                m.addConstr(thr(rec, r, p)
                            <= recovery * f.sum(chain[-1], "*", r, q),
                            name=f"rec_{r}_{p}")

    m.addConstrs((f.sum(chain[-1], "*", r, p) + u[r, p] >= DEM[r, p]
                  for r in R for p in P), name="dem")

    capex = gp.quicksum(mu(s, v) * (inst.fixed_cost[s] * y[s, r, v]
                                    + inst.unit_cost[s] * c[s, r, v])
                        for (s, r, v) in BUILD)
    opex = gp.quicksum(omega[p] * inst.op_cost[s] * x[s, r, v, p]
                       for (s, r, v, p) in ACTIVE)
    trans = gp.quicksum(omega[p] * (tau_intra if r1 == r2 else tau_inter)
                        * f[s, r1, r2, p] for (s, r1, r2) in ARCS for p in P)
    short = gp.quicksum(omega[p] * penalty * u[r, p] for r in R for p in P)
    m.setObjective(capex + opex + trans + short, GRB.MINIMIZE)

    # required before .relax(): without it the copy is of an empty model, which
    # solves to 0 and passes any test written against its status
    m.update()
    m._sets = dict(R=R, STAGES=stages, CHAIN=chain, REC=rec, P=P, VIN=VIN,
                   BUILD=BUILD, ACTIVE=ACTIVE, ARCS=ARCS, omega=omega, DEM=DEM,
                   starts=starts, lens=lens, H=H)
    m._vars = dict(y=y, c=c, x=x, f=f, u=u)
    m._e = dict(capex=capex, opex=opex, trans=trans, short=short)
    return m


def build_plan(m: gp.Model) -> list:
    """The build decisions as ``(stage, region, vintage, start_year, size)``."""
    S, V = m._sets, m._vars
    return sorted((s, r, v, S["starts"][v], round(V["c"][s, r, v].X, 2))
                  for (s, r, v) in S["BUILD"] if V["y"][s, r, v].X > 0.5)


def recycled_share(m: gp.Model) -> list:
    """Per period: recycled feed, fresh feed, and recycling's share of CATH input."""
    S, V, rec = m._sets, m._vars, m._sets["REC"]
    out = []
    for p in S["P"]:
        recycled = sum(V["f"][rec, r1, r2, p].X for r1 in S["R"] for r2 in S["R"])
        fresh = sum(V["f"]["PROC", r1, r2, p].X for r1 in S["R"] for r2 in S["R"])
        tot = recycled + fresh
        out.append(dict(period=p, year=S["starts"][p], recycled=round(recycled, 2),
                        fresh=round(fresh, 2),
                        share_pct=round(100 * recycled / tot, 1) if tot > 1e-9 else 0.0,
                        unmet=round(sum(V["u"][r, p].X for r in S["R"]), 2)))
    return out


def collapse_test(inst: IntegratedInstance, *, tol: float = 1e-4, **kw) -> dict:
    """Two identical regions with free trade must equal one region, doubled.

    This is the series' cleanest structural invariant: if geography costs nothing
    and the regions are the same, the arc and balance logic has to collapse. It
    is asserted on the **LP relaxation**, where it is exact -- the MILP versions
    differ by integer lumpiness, which is a real effect and not a bug, so the
    MILP line below is a diagnostic and never an assertion.

    Both models are solved at `mipgap=0` so the reported lumpiness is a property
    of the integrality and not of the tolerance.
    """
    kw = {**kw, "mipgap": 0.0, "tau_inter": kw.get("tau_intra", 0.3)}
    common = dict(kw)
    multi = build(inst, regions=("A", "B"), demand0={"A": 12.0, "B": 12.0},
                  legacy_cap={(s, r): 6.0 for s in inst.chain for r in ("A", "B")},
                  **common)
    single = build(inst, regions=("A",), demand0={"A": 24.0},
                   legacy_cap={(s, "A"): 12.0 for s in inst.chain}, **common)

    ra, rb = multi.relax(), single.relax()
    for r in (ra, rb):
        r.Params.OutputFlag = 0
        r.optimize()
    # a silently empty relaxation solves to 0 and would pass any status check
    assert ra.NumConstrs > 0 and rb.NumConstrs > 0, \
        "the relaxation is empty - a missing m.update() before .relax()"
    assert ra.ObjVal > 1.0, "the relaxed objective is ~0; the model was not copied"
    rel_lp = abs(ra.ObjVal - rb.ObjVal) / max(1.0, abs(rb.ObjVal))

    multi.optimize()
    single.optimize()
    rel_ip = abs(multi.ObjVal - single.ObjVal) / max(1.0, abs(single.ObjVal))
    return dict(lp_multi=ra.ObjVal, lp_single=rb.ObjVal, rel_lp=rel_lp,
                ip_multi=multi.ObjVal, ip_single=single.ObjVal, rel_ip=rel_ip,
                passed=rel_lp < tol)
