#!/usr/bin/env python
"""One command reproduces every migrated result in this repo.

    python scripts/run_all.py
    python scripts/run_all.py --only 02
    python scripts/run_all.py --only 4d,4e
    python scripts/run_all.py --quick        # fewer best-response rounds

Writes `results/tables/*.csv` and `results/figures/*.png` and prints the headline
numbers the notebook narrations quote. The teaching notebooks build the same
models by hand and each asserts it agrees with this package to 1e-9; this script
is the machine-facing half.

Knobs live here, written out, exactly as they are in the notebooks. Instance
tables come from `data/raw/` (falling back to the copies inside the installed
package) and are passed to `lithium` as arguments — nothing downstream re-reads a
file.

One section per migrated notebook. Phase 2 adds a function here as each group
lands; `--only` runs a subset while working on one.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                              # noqa: E402
import pandas as pd                                          # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import lithium as L                                          # noqa: E402
from lithium import twostage as T2                           # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "results" / "tables"
FIGURES = ROOT / "results" / "figures"

# ---- knobs ---------------------------------------------------------------
BLOCKS = [(6, 1), (4, 3), (2, 5), (1, 9)]
DR, LIFE = 0.05, 25
LEAD = {"MINE": 1, "PROC": 2, "MFG": 2}
CAP_MIN, CAP_MAX = 60.0, 260.0
LEGACY_BYR, ETA_FLOOR = -8, 0.60
LEARN_STAGES = ["PROC", "MFG"]
LR_CAPEX, Q_START, Q_ADD, CAPEX_FLOOR, NBP = 0.15, 300.0, 700.0, 0.60, 9
LR_OPEX, OPEX_FLOOR, LAG_YEARS, N_TIERS = 0.18, 0.65, 3, 3
TRANSPORT_OWN, TRANSPORT_CROSS = 0.5, 2.4
PRICE_FIXED, PEN_SHORT, PEN_DISPOSE = 12.0, 90.0, 12.0
CHOKE, P_ANCHOR, NBP_REV = 30.0, 13.0, 7
TOL, MIPGAP_GAME, MIPGAP_PLAN = 0.5, 1e-3, 0.005
# Part 4d
LEADER, FOLLOWER = "R1", "R2"
BIG_Q, BIG_L, NQ, CAP_ADDER = 1200.0, 400.0, 6, 4.0
# 1e-3, not 0.01: at 0.01 the tariff-10 deterrence case in 4e stops at a
# worse incumbent (8,794.87 / qL 1,038.44) than the true optimum
# (8,816.86 / qL 1,001.71). Every other MPEC case is identical at both.
MIPGAP_MPEC = 1e-3
# the sweeps the narrations quote
TARIFF_LEVELS = [0.0, 2.0, 5.0, 9.0]
QUOTA_LEVELS = [60.0, 30.0, 10.0]
LCR_LEVELS = [40.0, 70.0]
DETERRENCE_TARIFFS = [0.0, 3.0, 6.0, 10.0]
GRID_POINTS = [3, 4, 6, 8]
# Part 4ab
WEIGHTS = [0.1, 0.3, 0.5, 0.7, 0.9]
MAX_ITER_4B = 10

BLUE, ORANGE, GREEN, RED, PURPLE = "#2471a3", "#d68910", "#196f3d", "#c0392b", "#8e44ad"


# ==========================================================================
def setup(source, max_iter):
    """Instance, derived structure, curves, and the calibrated opex tiers."""
    inst = L.load_instance(source)
    struct = L.build_structure(inst, blocks=BLOCKS, dr=DR, life=LIFE, lead=LEAD,
                               cap_min=CAP_MIN, cap_max=CAP_MAX,
                               legacy_byr=LEGACY_BYR, eta_floor=ETA_FLOOR)
    regions, P = struct.regions, struct.P
    transport = {(rf, rt): (TRANSPORT_OWN if rf == rt else TRANSPORT_CROSS)
                 for rf in regions for rt in regions}
    QBP, CBP = L.capex_breakpoints(Q_START, Q_ADD, NBP, LR_CAPEX, CAPEX_FLOOR)
    a_int, b_slp = L.inverse_demand(struct, CHOKE, P_ANCHOR)

    region_kw = dict(transport=transport, pen_dispose=PEN_DISPOSE,
                     price_fixed=PRICE_FIXED, capex_curve=(QBP, CBP),
                     learn_stages=LEARN_STAGES, n_tiers=N_TIERS,
                     lag_years=LAG_YEARS)
    planner = L.solve_planner(struct, w1=0.5, learning="capacity",
                              pen_short=PEN_SHORT, mipgap=MIPGAP_PLAN, **region_kw)
    assert planner.SolCount > 0, "planner calibration found no solution"
    top = {r: planner._H[r]["cum"][P[-1]].X for r in regions}
    region_kw["tiers"] = L.opex_tiers(top, N_TIERS, LR_OPEX, OPEX_FLOOR)

    cap_cost = (sum(struct.MU["MFG", v] for v in P) / len(P)
                * inst.unit["MFG", FOLLOWER] + CAP_ADDER)

    print(f"tier thresholds : "
          f"{ {r: [round(q, 1) for q in region_kw['tiers'][0][r]] for r in regions} }")
    return dict(inst=inst, struct=struct, transport=transport, a_int=a_int,
                b_slp=b_slp, region_kw=region_kw, planner=planner,
                cap_cost=cap_cost, max_iter=max_iter,
                game_kw=dict(a_int=a_int, b_slp=b_slp, nbp_rev=NBP_REV,
                             mipgap=MIPGAP_GAME, max_iter=max_iter, tol=TOL,
                             **region_kw))


def _last(res, regions):
    return {g["firm"]: g for g in res["log"][-len(regions):]}


def _show(name, frame):
    frame.to_csv(TABLES / f"{name}.csv", index=False)
    print("\n", frame.to_string(index=False), sep="")
    return frame


# ==========================================================================
def run_4ab(ctx):
    """Parts 4a and 4b - the cooperative planner, and the fixed-price game."""
    struct, regions, P = ctx["struct"], ctx["struct"].regions, ctx["struct"].P
    kw = ctx["region_kw"]
    print("\n=== 4ab: planner frontier and the fixed-price game ===")

    rows = []
    for w in WEIGHTS:
        mw = L.solve_planner(struct, w1=w, learning="both", pen_short=PEN_SHORT,
                             mipgap=MIPGAP_PLAN, **kw)
        assert mw.SolCount > 0, f"w={w} found no solution"
        H = mw._H
        rows.append(dict(weight_R1=w, weighted_obj=round(mw.ObjVal, 1),
                         **{f"cost_{r}": round(H[r]["cost"].getValue(), 1)
                            for r in regions},
                         **{f"builds_{r}": sum(1 for k in H[r]["b"]
                                               if H[r]["b"][k].X > 0.5)
                            for r in regions},
                         shortfall=round(sum(mw._short[rt, p].X
                                             for rt in regions for p in P), 2)))
    frontier = _show("pareto_frontier", pd.DataFrame(rows))
    splits = list(zip(frontier.builds_R1, frontier.builds_R2))
    assert len(set(splits)) < len(splits), \
        "the Pareto frontier is smoother than the lumpy-investment story claims"

    runs, rows = {}, []
    for first in regions:
        res = L.iterate_fixed_price(struct, learning="both", first=first,
                                    max_iter=MAX_ITER_4B, mipgap=MIPGAP_PLAN, **kw)
        runs[first] = res
        last = _last(res, regions)
        rows.append(dict(first_mover=first, status=res["status"],
                         repeat_length=res.get("cycle_len"), iterations=res["iters"],
                         **{f"profit_{r}": round(last[r]["profit"], 1)
                            for r in regions},
                         **{f"sales_{r}": round(last[r]["total_sales"], 1)
                            for r in regions}))
    orders = _show("move_order_fixed_price", pd.DataFrame(rows))
    assert (orders.status == "CONVERGED").all(), "a move order failed to converge"
    assert orders.profit_R1[0] != orders.profit_R1[1], \
        "both move orders gave the same equilibrium; no first-mover effect"

    # the cost of rivalry, with the comparison MATCHED - see 04ab section 12
    res = runs[regions[0]]
    comp_cost, served = 0.0, {}
    for r in regions:
        rival = {}
        for other in regions:
            if other == r:
                continue
            for k, v in res["sales"][other].items():
                rival[k] = rival.get(k, 0.0) + v
        br = L.best_response_fixed_price(r, rival, struct, learning="both",
                                         mipgap=MIPGAP_PLAN, **kw)
        comp_cost += br._h["cost"].getValue()
        for rt in regions:
            for p in P:
                served[rt, p] = served.get((rt, p), 0.0) + br._h["sale"][rt, p].X
    coop = L.solve_planner(struct, w1=0.5, learning="both", pen_short=PEN_SHORT,
                           mipgap=MIPGAP_PLAN, **kw)
    coop_cost = sum(coop._H[r]["cost"].getValue() for r in regions)
    coop_total = coop_cost + coop._pen.getValue()
    unserved = sum(struct.DEMAND.values()) - sum(served.values())
    pen_comp = sum(struct.OMEGA[p] * PEN_SHORT
                   * max(0.0, struct.DEMAND[rt, p] - served[rt, p])
                   for rt in regions for p in P)
    rivalry = _show("cost_of_rivalry", pd.DataFrame([
        dict(comparison="naive (different volumes)",
             planner=round(coop_cost, 1), competitive=round(comp_cost, 1),
             pct=round(100 * (comp_cost - coop_cost) / coop_cost, 2),
             valid=False),
        dict(comparison="welfare-inclusive",
             planner=round(coop_total, 1),
             competitive=round(comp_cost + pen_comp, 1),
             pct=round(100 * (comp_cost + pen_comp - coop_total) / coop_total, 1),
             valid=True),
    ]))
    # the naive answer must come out impossible; that is the lesson, not a bug
    assert comp_cost < coop_cost, "the naive comparison was expected to be negative"
    assert coop_total <= comp_cost + pen_comp + 1e-3, \
        "the welfare-inclusive bound is violated"
    print(f"unserved by the firms: {unserved:.1f} of "
          f"{sum(struct.DEMAND.values()):.1f} demanded")
    return dict(frontier=frontier, orders=orders, rivalry=rivalry, runs=runs)


# ==========================================================================
def run_4c(ctx):
    """Part 4c — Cournot with endogenous price, against collusion."""
    struct, regions, P = ctx["struct"], ctx["struct"].regions, ctx["struct"].P
    a_int, b_slp, game_kw = ctx["a_int"], ctx["b_slp"], ctx["game_kw"]
    print("\n=== 4c: Cournot with endogenous price ===")

    runs = {}
    rows = []
    for first in regions:
        res = L.cournot_iterate(struct, learning="both", first=first, **game_kw)
        runs[first] = res
        last = _last(res, regions)
        rows.append(dict(first_mover=first, status=res["status"],
                         iterations=res["iters"],
                         **{f"profit_{r}": round(last[r]["profit"], 1) for r in regions},
                         **{f"sales_{r}": round(last[r]["sales"], 1) for r in regions}))
    order = _show("move_order", pd.DataFrame(rows))
    res = runs[regions[0]]
    assert res["status"] == "CONVERGED", f"game did not converge: {res['status']}"

    jm = L.joint_profit_max(struct, a_int=a_int, b_slp=b_slp, nbp_rev=NBP_REV,
                            learning="both", mipgap=MIPGAP_PLAN, **ctx["region_kw"])
    assert jm.SolCount > 0, "joint profit max found no solution"
    mo = pd.DataFrame(L.market_outcome(res["sales"], struct, a_int, b_slp))
    jsales = {r: {(rt, p): jm._H[r]["sale"][rt, p].X for rt in regions for p in P}
              for r in regions}
    mj = pd.DataFrame(L.market_outcome(jsales, struct, a_int, b_slp))
    cournot_joint = sum(g["profit"] for g in res["log"][-len(regions):])
    _show("market_cournot", mo)
    _show("market_collusion", mj)
    regimes = _show("regimes", pd.DataFrame([
        dict(regime="Cournot duopoly", total_quantity=round(mo.quantity.sum(), 1),
             avg_price=round(mo.price.mean(), 2),
             joint_profit=round(cournot_joint, 1),
             consumer_surplus=round(mo.consumer_surplus.sum(), 1)),
        dict(regime="Collusion (joint max)", total_quantity=round(mj.quantity.sum(), 1),
             avg_price=round(mj.price.mean(), 2), joint_profit=round(jm.ObjVal, 1),
             consumer_surplus=round(mj.consumer_surplus.sum(), 1)),
    ]))
    assert mj.quantity.sum() < mo.quantity.sum(), "collusion did not restrict output"
    assert mj.price.mean() > mo.price.mean(), "collusion did not raise price"
    assert (mo.quantity >= -1e-6).all(), "negative quantity"

    rows = []
    for mode in ("capacity", "both"):
        r2 = L.cournot_iterate(struct, learning=mode, first=regions[0], **game_kw)
        last = _last(r2, regions)
        m2 = pd.DataFrame(L.market_outcome(r2["sales"], struct, a_int, b_slp))
        rows.append(dict(
            learning=mode, status=r2["status"],
            total_quantity=round(m2.quantity.sum(), 1),
            avg_price=round(m2.price.mean(), 2),
            **{f"sales_{r}": round(last[r]["sales"], 1) for r in regions},
            **{f"profit_{r}": round(last[r]["profit"], 1) for r in regions},
            disposal=round(sum(last[r]["disposal"] for r in regions), 2)))
    _show("learning_channels", pd.DataFrame(rows))

    lead = regions[0]
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.3))
    for mk, col in zip(regions, [BLUE, ORANGE]):
        d, dj = mo[mo.market == mk], mj[mj.market == mk]
        ax[0].plot(d.year, d.price, "o-", lw=2.4, color=col, label=f"{mk} Cournot")
        ax[0].plot(dj.year, dj.price, "s--", lw=2.0, color=col, alpha=0.6,
                   label=f"{mk} collusion")
        ax[1].plot(d.year, d[f"share_{lead}"], "o-", lw=2.4, color=col,
                   label=f"market {mk}")
    ax[0].set(xlabel="year", ylabel="price",
              title="Collusion holds price above Cournot")
    ax[0].legend(fontsize=9)
    ax[1].axhline(0.5, ls=":", color="k")
    ax[1].set(xlabel="year", ylabel=f"{lead}'s share of the market", ylim=(0, 1),
              title="Incumbent's share: home market vs entrant's market")
    ax[1].legend(fontsize=10)
    for a in ax:
        a.grid(alpha=0.3)
    plt.tight_layout()
    fig.savefig(FIGURES / "cournot_price_and_share.png", dpi=140)
    plt.close(fig)
    return dict(order=order, regimes=regimes, cournot=runs[regions[0]])


# ==========================================================================
def run_4d(ctx):
    """Part 4d — Stackelberg leadership as a single-level MPEC."""
    struct, regions, P = ctx["struct"], ctx["struct"].regions, ctx["struct"].P
    a_int, b_slp = ctx["a_int"], ctx["b_slp"]
    mpec_kw = dict(a_int=a_int, b_slp=b_slp, cap_cost=ctx["cap_cost"],
                   big_q=BIG_Q, big_l=BIG_L, nq=NQ, learning="both",
                   mipgap=MIPGAP_MPEC, **ctx["region_kw"])
    print("\n=== 4d: Stackelberg as an MPEC ===")
    print(f"follower marginal cost per unit delivered: "
          f"{ {k: round(v, 3) for k, v in L.follower_marginal_cost(struct, FOLLOWER, ctx['transport']).items()} }")
    print(f"annualised cost of follower capacity expansion: {ctx['cap_cost']:.3f}")

    mpec = L.stackelberg(struct, LEADER, FOLLOWER, **mpec_kw)
    assert mpec.SolCount > 0, "MPEC found no solution"
    assert mpec.NumBinVars > 0, "an MPEC with no binaries is not the big-M model"
    print(f"MPEC: {mpec.NumVars} vars, {mpec.NumConstrs} constrs, "
          f"{mpec.NumBinVars} binaries")

    # the check an MPEC most needs: does the embedded KKT block reproduce the
    # follower's true optimum, solved exactly as a QP?
    qL_fix = {(rt, p): mpec._qL[rt, p].X for rt in regions for p in P}
    _, qF_chk, Cap_chk = L.follower_qp(struct, FOLLOWER, qL_fix, a_int=a_int,
                                       b_slp=b_slp, transport=ctx["transport"],
                                       cap_cost=ctx["cap_cost"], big_q=BIG_Q)
    dev = max(abs(mpec._qF[rt, p].X - qF_chk[rt, p].X)
              for rt in regions for p in P)
    print(f"embedded KKT vs direct QP: max deviation {dev:.2e}, "
          f"Cap {mpec._Cap.X:.4f} vs {Cap_chk.X:.4f}")
    assert dev < 1e-4, f"the embedded KKT block does not reproduce the QP ({dev:.2e})"

    mono = L.stackelberg(struct, LEADER, FOLLOWER, deter=False, **mpec_kw)
    assert mono.SolCount > 0
    cr = ctx["_4c"]["cournot"]
    lc = _last(cr, regions)
    qL = sum(mpec._qL[rt, p].X for rt in regions for p in P)
    qF = sum(mpec._qF[rt, p].X for rt in regions for p in P)
    qM = sum(mono._qL[rt, p].X for rt in regions for p in P)
    structures = _show("market_structures", pd.DataFrame([
        dict(structure="Monopoly (no rival)", leader_profit=round(mono.ObjVal, 1),
             leader_qty=round(qM, 1), follower_qty=0.0, total_qty=round(qM, 1)),
        dict(structure=f"Stackelberg (leader {LEADER})",
             leader_profit=round(mpec.ObjVal, 1), leader_qty=round(qL, 1),
             follower_qty=round(qF, 1), total_qty=round(qL + qF, 1)),
        dict(structure="Cournot (simultaneous)",
             leader_profit=round(lc[LEADER]["profit"], 1),
             leader_qty=round(lc[LEADER]["sales"], 1),
             follower_qty=round(lc[FOLLOWER]["sales"], 1),
             total_qty=round(lc[LEADER]["sales"] + lc[FOLLOWER]["sales"], 1)),
    ]))
    # the ordering theory predicts
    assert mono.ObjVal > mpec.ObjVal > lc[LEADER]["profit"], (
        "monopoly > Stackelberg > Cournot failed for the leader")

    # entry deterrence: what would the follower do against a Cournot-quantity leader?
    qL_cournot = {(rt, p): cr["sales"][LEADER][rt, p]
                  for rt in regions for p in P}
    _, qF2, Cap2 = L.follower_qp(struct, FOLLOWER, qL_cournot, a_int=a_int,
                                 b_slp=b_slp, transport=ctx["transport"],
                                 cap_cost=ctx["cap_cost"], big_q=BIG_Q)
    deter = _show("deterrence", pd.DataFrame([
        dict(case="Stackelberg (leader commits)",
             follower_expansion=round(mpec._Cap.X, 2), follower_qty=round(qF, 1)),
        dict(case="vs a Cournot-quantity leader",
             follower_expansion=round(Cap2.X, 2),
             follower_qty=round(sum(qF2[rt, p].X for rt in regions for p in P), 1)),
    ]))
    assert mpec._Cap.X < Cap2.X, "commitment did not suppress follower investment"

    rows = []
    for nq in GRID_POINTS:
        mm = L.stackelberg(struct, LEADER, FOLLOWER,
                           **{**mpec_kw, "nq": nq})
        rows.append(dict(grid_points=nq,
                         leader_profit=round(mm.ObjVal, 1) if mm.SolCount else None,
                         leader_qty=round(sum(mm._qL[rt, p].X for rt in regions
                                              for p in P), 1) if mm.SolCount else None,
                         follower_qty=round(sum(mm._qF[rt, p].X for rt in regions
                                                for p in P), 1) if mm.SolCount else None,
                         binaries=mm.NumBinVars))
    grid = _show("grid_refinement", pd.DataFrame(rows))

    fig, ax = plt.subplots(1, 2, figsize=(12, 4.3))
    ax[0].bar(structures.structure, structures.leader_profit,
              color=[GREEN, BLUE, ORANGE])
    ax[0].set(ylabel="leader profit",
              title="Monopoly > Stackelberg > Cournot")
    ax[0].tick_params(axis="x", labelrotation=20, labelsize=9)
    ax[1].plot(grid.grid_points, grid.leader_profit, "o-", lw=2.4, color=BLUE)
    ax[1].set(xlabel="grid points on the leader's quantity",
              ylabel="leader profit",
              title="A coarse grid understates commitment")
    for a in ax:
        a.grid(alpha=0.3)
    plt.tight_layout()
    fig.savefig(FIGURES / "stackelberg_structures_and_grid.png", dpi=140)
    plt.close(fig)
    return dict(structures=structures, deterrence=deter, mpec_kw=mpec_kw)


# ==========================================================================
def run_4e(ctx):
    """Part 4e — tariffs, quotas and local content, swept."""
    struct, regions, P = ctx["struct"], ctx["struct"].regions, ctx["struct"].P
    a_int, b_slp, game_kw = ctx["a_int"], ctx["b_slp"], ctx["game_kw"]
    print("\n=== 4e: policy instruments ===")

    def run_policy(tag, **policy):
        res = L.cournot_iterate(struct, learning="both", first=regions[0],
                                **policy, **game_kw)
        assert res["status"] == "CONVERGED", f"{tag}: {res['status']}"
        last = _last(res, regions)
        profits = {r: last[r]["profit"] for r in regions}
        W = L.welfare(struct, res["sales"], profits, b_slp=b_slp,
                      tariff=policy.get("tariff"))
        mo = pd.DataFrame(L.market_outcome(res["sales"], struct, a_int, b_slp))
        return dict(policy=tag,
                    **{f"{r}_profit": round(profits[r], 1) for r in regions},
                    **{f"{r}_sales": round(last[r]["sales"], 1) for r in regions},
                    avg_price=round(mo.price.mean(), 2),
                    consumer_surplus=round(W["consumer_surplus"], 1),
                    gov_revenue=round(W["tariff_revenue"], 1),
                    welfare=round(W["total"], 1))

    tariffs = _show("policy_tariffs", pd.DataFrame([
        dict(tariff=t, **run_policy(f"tariff {t:.0f}",
                                    tariff=L.tariff_schedule(regions, t,
                                                             on_imports_to="R2")))
        for t in TARIFF_LEVELS]).drop(columns="policy"))
    # deadweight loss exceeds the revenue collected: welfare falls monotonically
    assert tariffs.welfare.is_monotonic_decreasing, (
        "welfare did not fall monotonically in the tariff")
    assert tariffs.R2_profit.iloc[-1] > tariffs.R2_profit.iloc[0], (
        "protection did not raise the protected firm's profit")

    quotas = _show("policy_quotas", pd.DataFrame(
        [run_policy("no policy")]
        + [run_policy(f"quota {q:.0f}",
                      quota=L.quota_schedule(regions, q, on_imports_to="R2"))
           for q in QUOTA_LEVELS]))
    assert (quotas.gov_revenue == 0).all(), "a quota collected revenue"

    lcr = _show("policy_local_content", pd.DataFrame(
        [run_policy("no policy")]
        + [run_policy(f"local min {lv:.0f} in R2",
                      local_min=L.local_content_schedule(regions, lv, market="R2"))
           for lv in LCR_LEVELS]))

    # can a tariff restore investment against a committed leader?
    mpec_kw = ctx["_4d"]["mpec_kw"]
    rows = []
    for t in DETERRENCE_TARIFFS:
        kw = dict(mpec_kw)
        kw["tariff"] = L.tariff_schedule(regions, t, on_imports_to="R2")
        mm = L.stackelberg(struct, LEADER, FOLLOWER, **kw)
        rows.append(dict(tariff=t,
                         leader_profit=round(mm.ObjVal, 1) if mm.SolCount else None,
                         leader_qty=round(sum(mm._qL[rt, p].X for rt in regions
                                              for p in P), 1) if mm.SolCount else None,
                         follower_qty=round(sum(mm._qF[rt, p].X for rt in regions
                                                for p in P), 1) if mm.SolCount else None,
                         follower_capacity=round(mm._Cap.X, 2) if mm.SolCount else None))
    deter = _show("policy_deterrence", pd.DataFrame(rows))

    fig, ax = plt.subplots(1, 3, figsize=(15, 4.2))
    ax[0].plot(tariffs.tariff, tariffs.R1_profit, "o-", lw=2.5, color=BLUE,
               label="R1 (exporter)")
    ax[0].plot(tariffs.tariff, tariffs.R2_profit, "s-", lw=2.5, color=ORANGE,
               label="R2 (protected)")
    ax[0].set(xlabel="tariff on imports into R2", ylabel="profit",
              title="Tariffs redistribute between producers")
    ax[0].legend()
    ax[1].plot(tariffs.tariff, tariffs.consumer_surplus, "o-", lw=2.5, color=GREEN,
               label="consumer surplus")
    ax[1].plot(tariffs.tariff, tariffs.welfare, "D-", lw=2.5, color=RED,
               label="total welfare")
    ax[1].plot(tariffs.tariff, tariffs.gov_revenue, "^-", lw=2.5, color=PURPLE,
               label="tariff revenue")
    ax[1].set(xlabel="tariff on imports into R2", ylabel="discounted value",
              title="...and shrink the pie")
    ax[1].legend(fontsize=9)
    ax[2].step(deter.tariff, deter.follower_capacity, where="post", lw=2.5,
               color=PURPLE)
    ax[2].plot(deter.tariff, deter.follower_capacity, "o", color=PURPLE)
    ax[2].set(xlabel="tariff, under a committed leader",
              ylabel="follower capacity expansion",
              title="Deterrence breaks as a step, not a slope")
    for a in ax:
        a.grid(alpha=0.3)
    plt.tight_layout()
    fig.savefig(FIGURES / "policy_instruments.png", dpi=140)
    plt.close(fig)
    return dict(tariffs=tariffs, quotas=quotas, lcr=lcr, deterrence=deter)


# ==========================================================================
# Parts 1 and 2 use a DIFFERENT instance from the Part 4 family: a six-site
# network with arc flows and a single planner, not a two-region vertically
# integrated chain. So they carry their own knobs and their own setup, and
# `--only 02` never pays for the Part 4 planner calibration.

# ---- knobs, Parts 1 and 2 ------------------------------------------------
NET_T, NET_R, NET_LIFE, NET_MAX_BUILDS = 20, 0.05, 20, 3
NET_ETA_MINE, NET_ETA_MIN = 0.90, 0.60
NET_TRANSPORT_OWN, NET_TRANSPORT_CROSS, NET_SLACK_PEN = 0.4, 1.6, 45.0
NET_LEARN_FRAC, NET_LR, NET_Q0, NET_C_FLOOR_FRAC, NET_G_EXOG = 0.70, 0.20, 380.0, 0.55, 0.035
NET_INVEST_STEP = 3
# Part 1
GRANULARITIES = {"annual": 1, "triennial": 3, "quinquennial": 5}
# The windows 01_deterministic section 8 sweeps, and its delta. A rolling
# policy that commits 1 year at a time is a DIFFERENT policy from one that
# commits 3, and gives a different answer (+73.5% vs the notebook's +74.6%
# at W=3). These must match the notebook or the two halves of the repo are
# answering different questions - CLAUDE.md Part 6.
ROLLING_W = [3, 4, 5, 6, 8, 10, 20]
ROLLING_DELTA = 3
# 1e-3, not the 0.005 default: section (b) asserts that no coarser mesh beats
# the annual one, and at 0.005 the reported objectives overlap by more than the
# quantity being compared.
MIPGAP_NET = 1e-3
# Part 2 - a shorter horizon, so the extensive form fits the free licence
STO_T, STO_INVEST_YEARS, STO_STAGE1 = 12, [1, 4, 7, 10], [1]
STO_GROWTHS = [(0.010, 0.30), (0.070, 0.40), (0.140, 0.30)]
STO_R2_BASE = 105.0
STO_RHOS, STO_PH_ITERS = [30, 100, 300, 1000, 3000], 40
STO_BLOCK_FRACS = [1.0, 0.67, 0.34]
STO_STAGE1_SETS = [[1], [1, 4], [1, 4, 7], [1, 4, 7, 10]]
# 1e-6: the sections below difference expectations that sit within 0.02% of
# each other, and a looser gap swamps the quantity being measured. It is also
# what makes RP evaluated equal the extensive form's own objective.
MIPGAP_STO = 1e-6


def setup_network(source, T):
    """The six-site network instance and the structure derived from it."""
    inst = L.load_network_instance(source)
    st = L.build_core_structure(
        inst, T=T, r=NET_R, life=NET_LIFE, max_builds=NET_MAX_BUILDS,
        eta_mine=NET_ETA_MINE, eta_min=NET_ETA_MIN,
        transport_own=NET_TRANSPORT_OWN, transport_cross=NET_TRANSPORT_CROSS,
        slack_pen=NET_SLACK_PEN, learn_frac=NET_LEARN_FRAC, lr=NET_LR,
        q0=NET_Q0, c_floor_frac=NET_C_FLOOR_FRAC, g_exog=NET_G_EXOG)
    n_sites = len(inst.mines) + len(inst.procs) + len(inst.fabs)
    print(f"network: {n_sites} sites, {T}-year horizon")
    return dict(inst=inst, st=st, T=T)


# ==========================================================================
def run_01(ctx):
    """Part 1 - four modelling choices that move the answer more than data does."""
    st = ctx["net"]["st"]
    IY = list(range(1, NET_T + 1, NET_INVEST_STEP))
    print("\n=== 01: capex timing, granularity, learning, foresight ===")

    # (a) capex timing. Lump-sum charges the whole cheque in the build year.
    rows = []
    for mode in ("annualized", "lumpsum"):
        r = L.solve(st, mode, invest_years=IY, capex_mode=mode, mipgap=MIPGAP_NET)
        assert r["obj"] is not None, f"capex mode {mode} found no solution"
        rows.append(dict(capex_mode=mode, objective=round(r["obj"], 1),
                         builds=sum(r["plan"].values()),
                         unmet=round(r["slack"], 2), seconds=round(r["sec"], 1)))
    capex = _show("01_capex_timing", pd.DataFrame(rows))
    ann, lump = capex.iloc[0], capex.iloc[1]
    print(f"lump-sum costs {100 * (lump.objective / ann.objective - 1):+.1f}% and "
          f"leaves {lump.unmet / max(ann.unmet, 1e-9):.1f}x the unmet demand")

    # (b) investment granularity. A coarser mesh is a RESTRICTION of the annual
    #     one, so it cannot do better - that is the assertion, not a hope.
    meshes = {k: list(range(1, NET_T + 1, s)) for k, s in GRANULARITIES.items()}
    meshes["staggered"] = L.staggered_years(NET_T)
    rows = []
    for name, iy in meshes.items():
        r = L.solve(st, name, invest_years=iy, mipgap=MIPGAP_NET)
        assert r["obj"] is not None, f"granularity {name} found no solution"
        rows.append(dict(mesh=name, decision_years=len(iy),
                         objective=round(r["obj"], 1), binaries=r["nbin"],
                         seconds=round(r["sec"], 1)))
    gran = _show("01_granularity", pd.DataFrame(rows))
    fine = gran.loc[gran.mesh == "annual", "objective"].iloc[0]
    assert (gran.objective >= fine - 1e-6).all(), (
        "a coarser mesh beat the annual one; a mesh is a restriction of it, so "
        "this is a bug rather than a finding")
    print(f"the annual mesh is the bound at {fine:,.1f}")

    # (c) learning: cheaper capacity later, so does it change WHEN you build?
    rows = []
    for learning in ("none", "capacity"):
        r = L.solve(st, learning, invest_years=IY, learning=learning,
                    mipgap=MIPGAP_NET)
        assert r["obj"] is not None, f"learning {learning} found no solution"
        rows.append(dict(learning=learning, objective=round(r["obj"], 1),
                         builds=sum(r["plan"].values()),
                         early_builds=sum(n for (_, v), n in r["plan"].items()
                                          if v <= 4)))
    _show("01_learning", pd.DataFrame(rows))

    # (d) foresight: a rolling horizon sees W years at a time, not all T
    full = L.solve(st, "full", invest_years=IY, mipgap=MIPGAP_NET)
    rows = [dict(foresight="perfect", W=NET_T, objective=round(full["obj"], 1),
                 vs_perfect_pct=0.0)]
    for W in ROLLING_W:
        # rolling_horizon returns the COMMITTED plan, not a cost: the myopic run
        # never solved the full horizon. Scoring it on the full-horizon model is
        # what makes it comparable to `full` - CLAUDE.md Part 6, match the
        # comparison before interpreting the difference.
        plan, _log = L.rolling_horizon(st, W=W, delta=ROLLING_DELTA,
                                       invest_step=NET_INVEST_STEP,
                                       mipgap=MIPGAP_NET)
        obj = L.evaluate_plan(st, plan, mipgap=MIPGAP_NET)
        assert obj is not None, f"the W={W} rolling plan is infeasible over T"
        rows.append(dict(foresight=f"rolling W={W}", W=W,
                         objective=round(obj, 1), units_built=sum(plan.values()),
                         vs_perfect_pct=round(100 * (obj / full["obj"] - 1), 2)))
    fore = _show("01_foresight", pd.DataFrame(rows))
    assert (fore.vs_perfect_pct >= -1e-6).all(), \
        "limited foresight beat perfect foresight, which is impossible"
    w3 = fore.loc[fore.foresight == "rolling W=3"].iloc[0]
    w20 = fore.loc[fore.foresight == "rolling W=20"].iloc[0]
    assert w3.vs_perfect_pct > 10, \
        "W=3 was expected to be far off; the hard-floor claim needs re-checking"
    assert w20.vs_perfect_pct < 0.1, \
        "a window as long as the horizon must reproduce perfect foresight"
    print(f"myopia is the most expensive choice here: W=3 costs "
          f"{w3.vs_perfect_pct:+.1f}% and builds only {w3.units_built} units; "
          f"W>=5 is within "
          f"{fore[fore.W >= 5].vs_perfect_pct.max():.2f}%")

    fig, ax = plt.subplots(figsize=(6.5, 4))
    ax.bar(fore.foresight, fore.vs_perfect_pct,
           color=[BLUE] + [RED] * len(ROLLING_W))
    ax.tick_params(axis="x", rotation=45)
    ax.set_ylabel("cost above perfect foresight (%)")
    ax.set_title("Part 1: what limited foresight costs")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIGURES / "01_foresight.png", dpi=150)
    plt.close(fig)
    return dict(capex=capex, granularity=gran, foresight=fore)


# ==========================================================================
def run_02(ctx):
    """Part 2 - the extensive form, EVPI and VSS, and progressive hedging."""
    st = setup_network(ctx["_net_source"], STO_T)["st"]
    sc = L.scenarios(st, growths=tuple(STO_GROWTHS), r2_base=STO_R2_BASE)
    IY, S1 = STO_INVEST_YEARS, STO_STAGE1
    print(f"\n=== 02: two-stage stochastic programming "
          f"({len(sc)} scenarios, T={STO_T}) ===")

    # (a) the three strategies, all measured by identical machinery
    r = L.three_case_comparison(st, sc, IY, S1, mipgap=MIPGAP_STO)
    WS, RP, EEV = r["WS"], r["RP"], r["EEV"]
    assert abs(RP - r["ef_obj"]) / abs(RP) < 1e-6, (
        f"RP evaluated ({RP:.6f}) != the extensive form objective "
        f"({r['ef_obj']:.6f}); the two paths measure different things")
    assert WS <= RP + 1e-6, "wait-and-see is not a lower bound"
    assert RP <= EEV + 1e-6, "the mean-value plan beat the stochastic plan"
    detail = _show("02_by_scenario", pd.DataFrame([
        dict(scenario=pi["scenario"], prob=pi["prob"],
             PI_cost=round(pi["cost"], 1), SP_cost=round(sp["cost"], 1),
             EV_cost=round(ev["cost"], 1), PI_unmet=round(pi["unmet"], 2),
             SP_unmet=round(sp["unmet"], 2), EV_unmet=round(ev["unmet"], 2))
        for pi, sp, ev in zip(r["per"]["PI"], r["per"]["SP"], r["per"]["EV"])]))
    print(f"\nWS {WS:,.2f}   RP {RP:,.2f} = ef.ObjVal {r['ef_obj']:,.2f}"
          f"   EEV {EEV:,.2f}")
    print(f"EVPI {RP - WS:,.2f} ({100 * (RP - WS) / RP:.3f}%)   "
          f"VSS {EEV - RP:,.2f} ({100 * (EEV - RP) / RP:.3f}%)")

    # (b) VSS against how much is locked in - the finding Part 2 is built on
    rows = []
    for s1 in STO_STAGE1_SETS:
        rr = L.three_case_comparison(st, sc, IY, s1, mipgap=MIPGAP_STO)
        rows.append(dict(stage1_years=str(s1), WS=round(rr["WS"], 1),
                         RP=round(rr["RP"], 1), EEV=round(rr["EEV"], 1),
                         VSS=round(rr["EEV"] - rr["RP"], 2),
                         VSS_pct=round(100 * (rr["EEV"] - rr["RP"]) / rr["RP"], 3),
                         hi_unmet_SP=round(rr["per"]["SP"][-1]["unmet"], 1),
                         hi_unmet_EV=round(rr["per"]["EV"][-1]["unmet"], 1)))
    lock = _show("02_vss_by_commitment", pd.DataFrame(rows))
    assert lock.WS.nunique() == 1, (
        "WS moved with the stage-1 set; wait-and-see never sees a "
        "nonanticipativity constraint, so this is a plumbing bug")
    assert lock.VSS_pct.max() > 10 * lock.VSS_pct.iloc[0], \
        "locking more in barely moved VSS; Part 2's explanation would be wrong"
    print(f"\nVSS {lock.VSS_pct.iloc[0]:.3f}% -> {lock.VSS_pct.max():.3f}% as the "
          f"commitment lengthens: VSS measures how much you commit, not only "
          f"how uncertain you are")

    # (c) progressive hedging, and the rho trap
    rows = []
    for rho in STO_RHOS:
        t0 = time.time()
        ph = L.progressive_hedging(st, sc, IY, S1, rho=rho, iters=STO_PH_ITERS,
                                   mipgap=MIPGAP_STO)
        cost = L.evaluate_stage1(st, sc, IY, S1, ph["z"], mipgap=MIPGAP_STO)
        rows.append(dict(rho=rho, iterations=ph["iters"],
                         final_residual=round(ph["resid"][-1], 5),
                         evaluated_cost=round(cost, 1),
                         vs_RP_pct=round(100 * (cost / RP - 1), 3),
                         seconds=round(time.time() - t0, 1)))
    rho_tab = _show("02_ph_rho_sweep", pd.DataFrame(rows))
    ibest = rho_tab.vs_RP_pct.idxmin()
    assert 0 < ibest < len(rho_tab) - 1, (
        f"the best rho sat at an end of the range ({rho_tab.rho[ibest]}); the "
        f"point is that it is interior, which is why a sweep is unavoidable")
    snap = rho_tab.loc[rho_tab.final_residual.idxmin()]
    print(f"\nbest rho={rho_tab.rho[ibest]} at {rho_tab.vs_RP_pct[ibest]:+.3f}%, "
          f"interior. rho={snap.rho} agrees perfectly after {snap.iterations} "
          f"iterations and lands {snap.vs_RP_pct:+.3f}% off: a converged "
          f"residual is not a quality guarantee")

    # (d) block-asynchronous: fewer subproblem solves, same answer
    rows = []
    for bf in STO_BLOCK_FRACS:
        ph = L.progressive_hedging(st, sc, IY, S1, rho=300, iters=20,
                                   block_frac=bf, mipgap=MIPGAP_STO)
        cost = L.evaluate_stage1(st, sc, IY, S1, ph["z"], mipgap=MIPGAP_STO)
        rows.append(dict(block_frac=bf, subproblem_solves=ph["subsolves"],
                         final_residual=round(ph["resid"][-1], 5),
                         evaluated_cost=round(cost, 1),
                         vs_RP_pct=round(100 * (cost / RP - 1), 4)))
    block = _show("02_block_async", pd.DataFrame(rows))
    assert block.subproblem_solves.iloc[-1] < block.subproblem_solves.iloc[0], \
        "the block variant solved no fewer subproblems, so it saved nothing"
    # Skipping subproblems is an approximation, not a free saving. If every
    # block fraction returns the SAME cost, the MIP gap is looser than the
    # differences being measured - which is how this check read before
    # MIPGAP_STO was threaded all the way down into the PH subproblems.
    assert block.vs_RP_pct.nunique() > 1, (
        "every block fraction returned an identical cost; that is the signature "
        "of a MIP gap larger than the quantity being measured, not of a free "
        "saving")
    print(f"\nblock asynchrony: {block.subproblem_solves.iloc[0]} -> "
          f"{block.subproblem_solves.iloc[-1]} subsolves, and quality moves "
          f"{block.vs_RP_pct.min():+.4f}% to {block.vs_RP_pct.max():+.4f}% - "
          f"cheaper is not reliably worse, and not reliably the same either")

    fig, ax = plt.subplots(figsize=(6.5, 4))
    ax.plot(lock.stage1_years, lock.VSS_pct, "o-", color=BLUE, lw=2)
    ax.set_xlabel("years committed before the uncertainty resolves")
    ax.set_ylabel("VSS (% of RP)")
    ax.set_title("Part 2: VSS measures how much you commit")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIGURES / "02_vss_by_commitment.png", dpi=150)
    plt.close(fig)
    return dict(three_case=r, by_scenario=detail, lock=lock, rho=rho_tab)


# ==========================================================================
# Parts 2b and 2c share a THIRD instance: a single-period, three-stage,
# two-region capacity network. Not Parts 1/2's six-site multi-period network,
# and not the Part 4 chain. See src/lithium/twostage.py.

# ---- knobs, Parts 2b and 2c ----------------------------------------------
TS_CMIN, TS_CMAX, TS_PEN = 5.0, 70.0, 30.0
TS_TAU_OWN, TS_TAU_CROSS = 0.3, 1.5
# 2b: demand only
TS_SEED_B, TS_NK_B, TS_LO, TS_HI = 11, 24, 0.55, 1.55
TS_SCALE_N = [24, 50, 100, 200]
# 2c: demand plus a region-specific cost shock
TS_SEED_C, TS_NK_C = 7, 40
TS_LO_C, TS_SPAN_C = 0.6, 0.9
TS_HIT_PROB, TS_HIT_SIZE, TS_JITTER = 0.15, 2.6, 0.15
TS_ALPHA, TS_LAM = 0.10, 0.01
TS_LAMS = [0.0, 0.005, 0.01, 0.05, 0.15, 0.3, 0.4, 0.7, 1.0]
TS_ALPHAS = [0.05, 0.10, 0.20, 0.35, 0.50, 1.0]
# 1e-9: Part 2b asserts the L-shaped value reproduces the extensive form to
# 1e-9, and Part 2c differences plan means that sit 0.06% apart.
MIPGAP_TS = 1e-9


def setup_twostage(source):
    """The two-stage capacity network's instance and derived sets."""
    inst = L.load_twostage_instance(source)
    st = L.build_twostage_structure(inst, cmin=TS_CMIN, cmax=TS_CMAX,
                                    pen=TS_PEN, tau_own=TS_TAU_OWN,
                                    tau_cross=TS_TAU_CROSS)
    print(f"two-stage network: {len(st.nodes)} nodes, {len(st.arcs)} arcs")
    return dict(inst=inst, st=st)


# ==========================================================================
def run_02b(ctx):
    """Part 2b - Benders / L-shaped, and what decomposition actually buys."""
    st = ctx["ts"]["st"]
    sc = L.demand_scenarios(st, n=TS_NK_B, seed=TS_SEED_B, lo=TS_LO, hi=TS_HI)
    print(f"\n=== 02b: L-shaped decomposition ({len(sc)} scenarios) ===")

    ef = T2.extensive_form(st, sc, mipgap=MIPGAP_TS)
    ef.optimize()
    assert ef.SolCount > 0, "the extensive form found no solution"
    plan_ef = T2.capacity_plan(ef, st)

    # the optimal plan sits exactly on the yield chain: each stage is sized to
    # what the stage above can feed it, so anything more could never be used
    mine = plan_ef["MINE", "R1"]
    chain = {"MINE": mine, "PROC": mine * ctx["ts"]["inst"].eta["MINE"],
             "MFG": mine * ctx["ts"]["inst"].eta["MINE"]
             * ctx["ts"]["inst"].eta["PROC"]}
    for stg, want in chain.items():
        assert abs(plan_ef[stg, "R1"] - want) < 1e-6, (
            f"{stg} capacity is off the yield chain; the plan is not maximal "
            f"or a flow-balance row is wrong")

    rows = []
    for multi, label in ((True, "multicut"), (False, "single cut")):
        r = L.lshaped(st, sc, multicut=multi, max_iter=200, mipgap=MIPGAP_TS)
        rel = abs(r["value"] - ef.ObjVal) / abs(ef.ObjVal)
        assert rel < 1e-9, f"{label} did not reproduce the extensive form ({rel:.2e})"
        assert r["bound"] <= ef.ObjVal + 1e-6, (
            f"{label}: the final lower bound exceeds the true optimum, so a cut "
            f"removed it")
        rows.append(dict(variant=label, iterations=r["iters"],
                         subsolves=r["subsolves"], value=round(r["value"], 6),
                         rel_vs_EF=f"{rel:.1e}"))
    cuts = _show("02b_cut_variants", pd.DataFrame(rows))
    assert cuts.iterations.iloc[1] > cuts.iterations.iloc[0], \
        "aggregating the cuts did not cost iterations"
    print(f"\nboth variants reproduce {ef.ObjVal:.6f}; single cut takes "
          f"{cuts.iterations.iloc[1] / cuts.iterations.iloc[0]:.2f}x the iterations")

    rows = []
    for n in TS_SCALE_N:
        sc_n = L.demand_scenarios(st, n=n, seed=TS_SEED_B, lo=TS_LO, hi=TS_HI)
        m_n = T2.extensive_form(st, sc_n, mipgap=MIPGAP_TS)
        t0 = time.time()
        m_n.optimize()
        t_ef = time.time() - t0
        t0 = time.time()
        r_n = L.lshaped(st, sc_n, max_iter=200, mipgap=MIPGAP_TS)
        t_ls = time.time() - t0
        rows.append(dict(n=n, EF_vars=m_n.NumVars, EF_sec=round(t_ef, 2),
                         LS_sec=round(t_ls, 2), LS_iters=r_n["iters"],
                         EF_fits_free_licence=m_n.NumVars <= 2000))
    scale = _show("02b_scaling", pd.DataFrame(rows))
    assert scale.LS_iters.nunique() == 1, (
        "the L-shaped iteration count moved with the scenario count; Part 2b's "
        "central claim is that it does not")
    print(f"\niterations at every scenario count: {scale.LS_iters.iloc[0]}. "
          f"The extensive form leaves the free licence behind at n = "
          f"{scale[~scale.EF_fits_free_licence].n.min()}, and decomposition "
          f"never builds it.")

    fig, ax = plt.subplots(figsize=(6.5, 4))
    hist = pd.DataFrame(L.lshaped(st, sc, mipgap=MIPGAP_TS)["hist"])
    ax.plot(hist["iter"], hist["LB"], "o-", color=BLUE, lw=2, label="lower bound")
    ax.plot(hist["iter"], hist["UB"], "s-", color=RED, lw=2, label="upper bound")
    ax.axhline(ef.ObjVal, color=GREEN, ls="--", lw=1.5, label="extensive form")
    ax.set_xlabel("iteration")
    ax.set_ylabel("objective")
    ax.set_title("Part 2b: the bounds close on the optimum")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIGURES / "02b_convergence.png", dpi=150)
    plt.close(fig)
    return dict(ef=ef.ObjVal, cuts=cuts, scale=scale)


# ==========================================================================
def run_02c(ctx):
    """Part 2c - CVaR, and scoring every plan by the same question."""
    st = ctx["ts"]["st"]
    sc = L.shock_scenarios(st, n=TS_NK_C, seed=TS_SEED_C, lo=TS_LO_C,
                           span=TS_SPAN_C, hit_prob=TS_HIT_PROB,
                           hit_size=TS_HIT_SIZE, steady_jitter=TS_JITTER)
    print(f"\n=== 02c: risk-averse planning ({len(sc)} scenarios) ===")

    res, ev = {}, {}
    for mode in T2.RISK_MODES:
        res[mode] = L.risk_model(st, sc, mode, alpha=TS_ALPHA, lam=TS_LAM,
                                 mipgap=MIPGAP_TS)
        ev[mode] = L.evaluate_capacity(st, sc, res[mode]["plan"])

    table = _show("02c_objectives", pd.DataFrame([
        dict(objective=m,
             sited=("R1" if res[m]["plan"]["MINE", "R1"] > 1e-6 else "R2"),
             capex=round(ev[m]["capex"], 1),
             total_capacity=round(sum(res[m]["plan"].values()), 1),
             reported_mean=round(res[m]["mean"], 1),
             true_mean=round(ev[m]["mean"], 1),
             true_cvar=round(T2.cvar_of(ev[m]["dist"], TS_ALPHA), 1),
             true_worst=round(ev[m]["worst"], 1))
        for m in T2.RISK_MODES]))

    for m in T2.RISK_MODES:
        assert (ev[m]["mean"] <= T2.cvar_of(ev[m]["dist"], TS_ALPHA) + 1e-6
                <= ev[m]["worst"] + 1e-6), \
            f"{m}: mean <= CVaR <= worst is violated"

    # the defect this notebook was rebuilt around: several objectives return
    # ONE plan and report different average costs for it. The re-evaluated
    # mean is the only one that is a property of the plan.
    keyed = {}
    for m in T2.RISK_MODES:
        keyed.setdefault(tuple(round(res[m]["plan"][n], 6) for n in st.nodes),
                         []).append(m)
    shared = max(keyed.values(), key=len)
    reported = {round(res[m]["mean"], 4) for m in shared}
    true = {round(ev[m]["mean"], 4) for m in shared}
    print(f"\n{len(keyed)} distinct plans. {len(shared)} objectives share one: "
          f"{sorted(shared)}")
    print(f"  reported means for it : {len(reported)} distinct -> {sorted(reported)}")
    print(f"  re-evaluated          : {len(true)} distinct -> {sorted(true)}")
    assert len(true) == 1, \
        "identical plans re-evaluated to different costs, which cannot happen"
    assert len(reported) > 1, (
        "the reported means agree here, so Part 2c's central defect would be "
        "invisible; check the scenario set before trusting the table")
    print(f"  the dearest reported is "
          f"{100 * (max(reported) / min(reported) - 1):.1f}% above the cheapest, "
          f"for one identical plan")

    rows = []
    for lam in TS_LAMS:
        r = L.risk_model(st, sc, "hybrid", alpha=TS_ALPHA, lam=lam,
                         mipgap=MIPGAP_TS)
        e = L.evaluate_capacity(st, sc, r["plan"])
        rows.append(dict(lam=lam,
                         sited=("R1" if r["plan"]["MINE", "R1"] > 1e-6 else "R2"),
                         true_mean=round(e["mean"], 1),
                         true_cvar=round(T2.cvar_of(e["dist"], TS_ALPHA), 1),
                         true_worst=round(e["worst"], 1)))
    lam_sweep = _show("02c_lambda_sweep", pd.DataFrame(rows))
    n_out = lam_sweep[["true_mean", "true_cvar", "true_worst"]].drop_duplicates().shape[0]
    assert n_out == 2, (
        f"the lambda sweep produced {n_out} distinct outcomes; Part 2c says the "
        f"frontier is a two-step staircase")

    rows = []
    for a in TS_ALPHAS:
        r = L.risk_model(st, sc, "cvar", alpha=a, mipgap=MIPGAP_TS)
        e = L.evaluate_capacity(st, sc, r["plan"])
        rows.append(dict(alpha=a,
                         sited=("R1" if r["plan"]["MINE", "R1"] > 1e-6 else "R2"),
                         true_mean=round(e["mean"], 1),
                         cvar_at_alpha=round(T2.cvar_of(e["dist"], a), 1),
                         true_worst=round(e["worst"], 1)))
    a_sweep = _show("02c_alpha_sweep", pd.DataFrame(rows))
    last = a_sweep.iloc[-1]
    assert abs(last.cvar_at_alpha - last.true_mean) < 0.05, (
        "at alpha = 1 CVaR must equal the mean; it does not, so the "
        "Rockafellar-Uryasev block is wrong")
    print(f"\nat alpha = 1 CVaR equals the mean ({last.cvar_at_alpha}), which is "
          f"the free check on the CVaR block")

    n_, h_ = ev["neutral"], ev["hybrid"]
    assert abs(n_["capex"] - h_["capex"]) < 1e-6, \
        "the risk-averse plan differs in capex, so it is not a pure relocation"
    print(f"the hedge: mean {100 * (h_['mean'] / n_['mean'] - 1):+.2f}%, "
          f"worst {100 * (h_['worst'] / n_['worst'] - 1):+.2f}%, "
          f"capex unchanged at {n_['capex']:.1f} - relocation, not more capacity")

    fig, ax = plt.subplots(figsize=(6.5, 4))
    for m, col in (("neutral", BLUE), ("hybrid", RED)):
        ax.plot(range(1, len(sc) + 1), ev[m]["dist"], "o-", ms=3, color=col,
                label=f"{m} (sited "
                      f"{'R1' if res[m]['plan']['MINE', 'R1'] > 1e-6 else 'R2'})")
    ax.set_xlabel("scenario, sorted cheapest to dearest")
    ax.set_ylabel("total cost")
    ax.set_title("Part 2c: two plans, scored the same way")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIGURES / "02c_distributions.png", dpi=150)
    plt.close(fig)
    return dict(table=table, lam=lam_sweep, alpha=a_sweep)


# Sections are grouped by which setup they need, so `--only 02` never pays for
# the Part 4 planner calibration and `--only 4c` never loads the network.
NET_SECTIONS = {"01": run_01, "02": run_02}
TS_SECTIONS = {"02b": run_02b, "02c": run_02c}
CHAIN_SECTIONS = {"4ab": run_4ab, "4c": run_4c, "4d": run_4d, "4e": run_4e}
SECTIONS = {**NET_SECTIONS, **TS_SECTIONS, **CHAIN_SECTIONS}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--quick", action="store_true",
                    help="cap best-response rounds at 6 (classroom setting)")
    ap.add_argument("--only", default=None,
                    help=f"comma-separated subset of {sorted(SECTIONS)}")
    ap.add_argument("--data", default=None,
                    help="directory holding the three instance CSVs "
                         "(default: data/raw/, then the packaged copies)")
    args = ap.parse_args()

    wanted = [s.strip() for s in args.only.split(",")] if args.only else list(SECTIONS)
    bad = [s for s in wanted if s not in SECTIONS]
    if bad:
        raise SystemExit(f"unknown section(s) {bad}; choose from {sorted(SECTIONS)}")
    # 4d reuses 4c's Cournot equilibrium and 4e reuses 4d's MPEC arguments
    for later, needs in (("4d", "4c"), ("4e", "4d")):
        if later in wanted and needs not in wanted:
            wanted.insert(wanted.index(later), needs)
    wanted.sort(key=lambda n: list(SECTIONS).index(n))

    TABLES.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)

    source = args.data
    if source is None:
        source = ROOT / "data" / "raw"
        if not (source / "market.csv").exists():
            source = None
    print(f"instance tables: {source or 'packaged copies inside lithium'}")
    print(f"sections       : {wanted}")
    t0 = time.time()

    ctx = {"_net_source": source}
    if any(n in NET_SECTIONS for n in wanted):
        ctx["net"] = setup_network(source, NET_T)
    if any(n in TS_SECTIONS for n in wanted):
        ctx["ts"] = setup_twostage(source)
    if any(n in CHAIN_SECTIONS for n in wanted):
        ctx.update(setup(source, max_iter=6 if args.quick else 16))
    for name in wanted:
        ctx[f"_{name}"] = SECTIONS[name](ctx)

    print(f"\n=== done in {time.time() - t0:.1f}s ===")
    print(f"tables  -> {TABLES}")
    print(f"figures -> {FIGURES}")


if __name__ == "__main__":
    main()
