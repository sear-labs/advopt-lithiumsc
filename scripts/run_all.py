#!/usr/bin/env python
"""One command reproduces every migrated result in this repo.

    python scripts/run_all.py
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


SECTIONS = {"4c": run_4c, "4d": run_4d, "4e": run_4e}


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

    ctx = setup(source, max_iter=6 if args.quick else 16)
    for name in wanted:
        ctx[f"_{name}"] = SECTIONS[name](ctx)

    print(f"\n=== done in {time.time() - t0:.1f}s ===")
    print(f"tables  -> {TABLES}")
    print(f"figures -> {FIGURES}")


if __name__ == "__main__":
    main()
