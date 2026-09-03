#!/usr/bin/env python
"""One command reproduces every Part 4c result in this repo.

    python scripts/run_all.py
    python scripts/run_all.py --quick        # 6 best-response rounds, not 16

Writes `results/tables/*.csv` and `results/figures/*.png`, and prints the
headline numbers the Part 4c narration quotes. The teaching notebook
`notebooks/04c_cournot.ipynb` builds the same models by hand and asserts it
agrees with this package to 1e-9; this script is the machine-facing half.

Knobs live here, written out, exactly as they are in the notebook. Instance
tables come from `data/raw/` (falling back to the copies inside the installed
package) and are passed to `lithium` as arguments — nothing downstream re-reads
a file.
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


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--quick", action="store_true",
                    help="cap best-response rounds at 6 (classroom setting)")
    ap.add_argument("--data", default=None,
                    help="directory holding the three instance CSVs "
                         "(default: data/raw/, then the packaged copies)")
    args = ap.parse_args()
    max_iter = 6 if args.quick else 16

    TABLES.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)

    source = args.data
    if source is None:
        source = ROOT / "data" / "raw"
        if not (source / "market.csv").exists():
            source = None
    print(f"=== Part 4c: Cournot with endogenous price ===")
    print(f"instance tables: {source or 'packaged copies inside lithium'}")
    t0 = time.time()

    inst = L.load_instance(source)
    struct = L.build_structure(inst, blocks=BLOCKS, dr=DR, life=LIFE, lead=LEAD,
                               cap_min=CAP_MIN, cap_max=CAP_MAX,
                               legacy_byr=LEGACY_BYR, eta_floor=ETA_FLOOR)
    regions, P = struct.regions, struct.P
    transport = {(rf, rt): (TRANSPORT_OWN if rf == rt else TRANSPORT_CROSS)
                 for rf in regions for rt in regions}
    QBP, CBP = L.capex_breakpoints(Q_START, Q_ADD, NBP, LR_CAPEX, CAPEX_FLOOR)
    A_INT, B_SLP = L.inverse_demand(struct, CHOKE, P_ANCHOR)

    region_kw = dict(transport=transport, pen_dispose=PEN_DISPOSE,
                     price_fixed=PRICE_FIXED, capex_curve=(QBP, CBP),
                     learn_stages=LEARN_STAGES, n_tiers=N_TIERS,
                     lag_years=LAG_YEARS)

    # ---- calibrate the operating-cost tiers off a planner solve ------------
    m0 = L.solve_planner(struct, w1=0.5, learning="capacity", pen_short=PEN_SHORT,
                         mipgap=MIPGAP_PLAN, **region_kw)
    assert m0.SolCount > 0, "planner calibration found no solution"
    top = {r: m0._H[r]["cum"][P[-1]].X for r in regions}
    tiers = L.opex_tiers(top, N_TIERS, LR_OPEX, OPEX_FLOOR)
    region_kw["tiers"] = tiers
    print(f"tier thresholds : { {r: [round(q, 1) for q in tiers[0][r]] for r in regions} }")

    game_kw = dict(a_int=A_INT, b_slp=B_SLP, nbp_rev=NBP_REV, mipgap=MIPGAP_GAME,
                   max_iter=max_iter, tol=TOL, **region_kw)

    # ---- move order: does going first still pay? --------------------------
    order_rows = []
    runs = {}
    for first in regions:
        res = L.cournot_iterate(struct, learning="both", first=first, **game_kw)
        runs[first] = res
        last = {g["firm"]: g for g in res["log"][-len(regions):]}
        order_rows.append(dict(first_mover=first, status=res["status"],
                               iterations=res["iters"],
                               **{f"profit_{r}": round(last[r]["profit"], 1)
                                  for r in regions},
                               **{f"sales_{r}": round(last[r]["sales"], 1)
                                  for r in regions}))
    order = pd.DataFrame(order_rows)
    order.to_csv(TABLES / "move_order.csv", index=False)
    print("\n", order.to_string(index=False), sep="")

    res = runs[regions[0]]
    assert res["status"] == "CONVERGED", f"game did not converge: {res['status']}"

    # ---- Cournot against collusion ----------------------------------------
    jm = L.joint_profit_max(struct, a_int=A_INT, b_slp=B_SLP, nbp_rev=NBP_REV,
                            learning="both", mipgap=MIPGAP_PLAN, **region_kw)
    assert jm.SolCount > 0, "joint profit max found no solution"
    mo = pd.DataFrame(L.market_outcome(res["sales"], struct, A_INT, B_SLP))
    jsales = {r: {(rt, p): jm._H[r]["sale"][rt, p].X for rt in regions for p in P}
              for r in regions}
    mj = pd.DataFrame(L.market_outcome(jsales, struct, A_INT, B_SLP))
    cournot_joint = sum(g["profit"] for g in res["log"][-len(regions):])
    regimes = pd.DataFrame([
        dict(regime="Cournot duopoly", total_quantity=round(mo.quantity.sum(), 1),
             avg_price=round(mo.price.mean(), 2),
             joint_profit=round(cournot_joint, 1),
             consumer_surplus=round(mo.consumer_surplus.sum(), 1)),
        dict(regime="Collusion (joint max)", total_quantity=round(mj.quantity.sum(), 1),
             avg_price=round(mj.price.mean(), 2), joint_profit=round(jm.ObjVal, 1),
             consumer_surplus=round(mj.consumer_surplus.sum(), 1)),
    ])
    regimes.to_csv(TABLES / "regimes.csv", index=False)
    mo.to_csv(TABLES / "market_cournot.csv", index=False)
    mj.to_csv(TABLES / "market_collusion.csv", index=False)
    print("\n", regimes.to_string(index=False), sep="")

    # domain invariants: collusion restricts output and lifts price
    assert mj.quantity.sum() < mo.quantity.sum(), "collusion did not restrict output"
    assert mj.price.mean() > mo.price.mean(), "collusion did not raise price"
    assert (mo.quantity >= -1e-6).all(), "negative quantity"

    # ---- does production learning drive output? ---------------------------
    learn_rows = []
    for mode in ("capacity", "both"):
        r2 = L.cournot_iterate(struct, learning=mode, first=regions[0], **game_kw)
        last = {g["firm"]: g for g in r2["log"][-len(regions):]}
        m2 = pd.DataFrame(L.market_outcome(r2["sales"], struct, A_INT, B_SLP))
        learn_rows.append(dict(
            learning=mode, status=r2["status"],
            total_quantity=round(m2.quantity.sum(), 1),
            avg_price=round(m2.price.mean(), 2),
            **{f"sales_{r}": round(last[r]["sales"], 1) for r in regions},
            **{f"profit_{r}": round(last[r]["profit"], 1) for r in regions},
            disposal=round(sum(last[r]["disposal"] for r in regions), 2)))
    learn = pd.DataFrame(learn_rows)
    learn.to_csv(TABLES / "learning_channels.csv", index=False)
    print("\n", learn.to_string(index=False), sep="")

    # ---- figure -----------------------------------------------------------
    lead = regions[0]
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.3))
    for mk, col in zip(regions, ["#2471a3", "#d68910"]):
        d = mo[mo.market == mk]
        ax[0].plot(d.year, d.price, "o-", lw=2.4, color=col, label=f"{mk} Cournot")
        dj = mj[mj.market == mk]
        ax[0].plot(dj.year, dj.price, "s--", lw=2.0, color=col, alpha=0.6,
                   label=f"{mk} collusion")
    ax[0].set_xlabel("year"); ax[0].set_ylabel("price"); ax[0].legend(fontsize=9)
    ax[0].set_title("Collusion holds price above Cournot")
    for mk, col in zip(regions, ["#2471a3", "#d68910"]):
        d = mo[mo.market == mk]
        ax[1].plot(d.year, d[f"share_{lead}"], "o-", lw=2.4, color=col,
                   label=f"market {mk}")
    ax[1].axhline(0.5, ls=":", color="k")
    ax[1].set_xlabel("year"); ax[1].set_ylabel(f"{lead}'s share of the market")
    ax[1].set_ylim(0, 1); ax[1].legend(fontsize=10)
    ax[1].set_title("Incumbent's share: home market vs entrant's market")
    ax[0].grid(alpha=0.3); ax[1].grid(alpha=0.3)
    plt.tight_layout()
    fig.savefig(FIGURES / "cournot_price_and_share.png", dpi=140)
    plt.close(fig)

    print(f"\n=== done in {time.time() - t0:.1f}s ===")
    print(f"tables  -> {TABLES}")
    print(f"figures -> {FIGURES}")


if __name__ == "__main__":
    main()
