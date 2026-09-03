"""Smoke test: the models build, solve, and obey the invariants they must obey.

Not testing for research correctness — testing that nothing is broken. This is
what CI runs on every push, and it is the single highest-value test for research
code.

The interesting one here is `test_policy_superset_collapses`: `PLAN.md` §5
adjudicated the two versions of `add_region` as a *feature*, not drift, on the
grounds that Part 4e's superset reduces exactly to Part 4c's base version when
the policy dictionaries are empty. That claim is the reason there is one
implementation instead of two, so it is asserted rather than believed.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import lithium as L                                          # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

# knobs, matching notebooks/04c_cournot.ipynb and scripts/run_all.py
BLOCKS = [(6, 1), (4, 3), (2, 5), (1, 9)]
DR, LIFE = 0.05, 25
LEAD = {"MINE": 1, "PROC": 2, "MFG": 2}
CAP_MIN, CAP_MAX = 60.0, 260.0
LEARN_STAGES = ["PROC", "MFG"]
LR_CAPEX, Q_START, Q_ADD, CAPEX_FLOOR, NBP = 0.15, 300.0, 700.0, 0.60, 9
LR_OPEX, OPEX_FLOOR, LAG_YEARS, N_TIERS = 0.18, 0.65, 3, 3
PRICE_FIXED, PEN_SHORT, PEN_DISPOSE = 12.0, 90.0, 12.0
CHOKE, P_ANCHOR, NBP_REV = 30.0, 13.0, 7


@pytest.fixture(scope="module")
def setup():
    """One instance, one structure, one tier calibration — reused by every test."""
    inst = L.load_instance(ROOT / "data" / "raw")
    struct = L.build_structure(inst, blocks=BLOCKS, dr=DR, life=LIFE, lead=LEAD,
                               cap_min=CAP_MIN, cap_max=CAP_MAX)
    transport = {(a, b): (0.5 if a == b else 2.4)
                 for a in struct.regions for b in struct.regions}
    QBP, CBP = L.capex_breakpoints(Q_START, Q_ADD, NBP, LR_CAPEX, CAPEX_FLOOR)
    a_int, b_slp = L.inverse_demand(struct, CHOKE, P_ANCHOR)
    kw = dict(transport=transport, pen_dispose=PEN_DISPOSE, price_fixed=PRICE_FIXED,
              capex_curve=(QBP, CBP), learn_stages=LEARN_STAGES,
              n_tiers=N_TIERS, lag_years=LAG_YEARS)
    planner = L.solve_planner(struct, w1=0.5, learning="capacity",
                              pen_short=PEN_SHORT, mipgap=0.005, **kw)
    top = {r: planner._H[r]["cum"][struct.P[-1]].X for r in struct.regions}
    kw["tiers"] = L.opex_tiers(top, N_TIERS, LR_OPEX, OPEX_FLOOR)
    return dict(inst=inst, struct=struct, kw=kw, a_int=a_int, b_slp=b_slp,
                planner=planner)


# ---------------------------------------------------------------- the instance
def test_instance_loads_from_both_sources():
    packaged = L.load_instance()
    editable = L.load_instance(ROOT / "data" / "raw")
    assert packaged == editable, (
        "src/lithium/data/ has drifted from data/raw/ — they are two copies of "
        "the same tables and must stay identical"
    )
    assert packaged.regions == ("R1", "R2")
    assert packaged.stages == ("MINE", "PROC", "MFG")


def test_instance_rejects_a_missing_column(tmp_path):
    for name in ("efficiency.csv", "market.csv"):
        (tmp_path / name).write_bytes((ROOT / "data" / "raw" / name).read_bytes())
    (tmp_path / "instance_base.csv").write_text("stage,region,fixed\nMINE,R1,900.0\n")
    with pytest.raises(ValueError, match="missing required columns"):
        L.load_instance(tmp_path)


def test_instance_rejects_an_incomplete_grid(tmp_path):
    for name in ("efficiency.csv", "market.csv"):
        (tmp_path / name).write_bytes((ROOT / "data" / "raw" / name).read_bytes())
    rows = (ROOT / "data" / "raw" / "instance_base.csv").read_text().splitlines()
    (tmp_path / "instance_base.csv").write_text("\n".join(rows[:-1]) + "\n")
    with pytest.raises(ValueError, match="rows"):
        L.load_instance(tmp_path)


# ------------------------------------------------------------------- the curves
def test_revenue_breakpoints_have_no_captured_default():
    """The bug this guards: `def f(..., n=NBP_REV)` froze the mesh at import."""
    import inspect
    sig = inspect.signature(L.revenue_breakpoints)
    assert sig.parameters["n"].default is inspect.Parameter.empty
    S3, R3 = L.revenue_breakpoints(30.0, 0.1, 100.0, 3)
    S7, R7 = L.revenue_breakpoints(30.0, 0.1, 100.0, 7)
    assert len(S3) == 3 and len(S7) == 7, "n is not reaching the mesh"


def test_revenue_curve_is_concave_and_chords_lie_below():
    """Why no SOS2 is needed on the revenue mesh, asserted rather than argued."""
    S, R = L.revenue_breakpoints(30.0, 0.1, 100.0, 9)
    mid_chord = 0.5 * (R[0] + R[-1])
    mid_true = 30.0 * 50.0 - 0.1 * 50.0 ** 2
    assert mid_chord < mid_true, "chord is not below the curve; it is not concave"


def test_opex_tiers_shape_and_monotonicity():
    thresholds, mult = L.opex_tiers({"R1": 8000.0, "R2": 4000.0}, 3, 0.18, 0.65)
    assert set(thresholds) == {"R1", "R2"}
    for r in thresholds:
        assert len(thresholds[r]) == 2 and len(mult[r]) == 3
        assert thresholds[r] == sorted(thresholds[r])
        assert mult[r] == sorted(mult[r], reverse=True)
        assert min(mult[r]) >= 0.65


def test_capex_curve_is_increasing_and_starts_at_zero():
    QBP, CBP = L.capex_breakpoints(Q_START, Q_ADD, NBP, LR_CAPEX, CAPEX_FLOOR)
    assert CBP[0] == 0.0, "no capacity added means no learning-curve spend"
    assert CBP == sorted(CBP), "cumulative spend went down"
    assert QBP[0] == Q_START and QBP[-1] == Q_START + Q_ADD


# ------------------------------------------------------------------- the models
def test_planner_solves_and_meets_demand(setup):
    m, struct = setup["planner"], setup["struct"]
    assert m.SolCount > 0
    assert m.NumVars > 0 and m.NumConstrs > 0, "a silently empty model also succeeds"
    assert m.NumSOS == len(struct.P) * len(struct.regions)
    short = sum(m._short[rt, p].X for rt in struct.regions for p in struct.P)
    assert short < 1e-6, f"planner left {short:.3f} of demand unserved"


def test_chain_conserves_material(setup):
    """Manufactured output must equal sales plus disposal, period by period."""
    struct, H = setup["struct"], setup["planner"]._H
    for r in struct.regions:
        for p in struct.P:
            made = sum(struct.ETA["MFG", v, p] * H[r]["x"]["MFG", v, p].X
                       for v in struct.VIN[r, "MFG", p])
            went = (sum(H[r]["sale"][rt, p].X for rt in struct.regions)
                    + H[r]["disp"][p].X)
            assert abs(made - went) < 1e-6, f"{r} period {p}: {made} made, {went} used"


def test_no_negative_quantities(setup):
    struct, H = setup["struct"], setup["planner"]._H
    for r in struct.regions:
        assert all(v.X >= -1e-9 for v in H[r]["x"].values())
        assert all(v.X >= -1e-9 for v in H[r]["sale"].values())


def test_policy_superset_collapses(setup):
    """PLAN.md §5: 4e's add_region reduces exactly to 4c's when policy is empty.

    This is the assertion that justifies having one implementation instead of
    two. If it ever fails, the superset is no longer a superset.
    """
    struct = setup["struct"]
    zero = {(rt, p): 0.0 for rt in struct.regions for p in struct.P}
    common = dict(a_int=setup["a_int"], b_slp=setup["b_slp"], nbp_rev=NBP_REV,
                  learning="both", mipgap=1e-3, **setup["kw"])
    base = L.best_response_cournot("R1", zero, struct, **common)
    with_policy = L.best_response_cournot("R1", zero, struct, tariff={}, quota={},
                                          local_min={}, **common)
    assert base.SolCount > 0 and with_policy.SolCount > 0
    rel = abs(with_policy.ObjVal - base.ObjVal) / abs(base.ObjVal)
    assert rel < 1e-9, f"empty policy args changed the answer by {rel:.2e}"
    assert with_policy.NumConstrs == base.NumConstrs, "empty policy added constraints"


def test_a_real_tariff_does_change_the_answer(setup):
    """The mirror of the test above: the superset must not be inert."""
    struct = setup["struct"]
    zero = {(rt, p): 0.0 for rt in struct.regions for p in struct.P}
    common = dict(a_int=setup["a_int"], b_slp=setup["b_slp"], nbp_rev=NBP_REV,
                  learning="both", mipgap=1e-3, **setup["kw"])
    base = L.best_response_cournot("R1", zero, struct, **common)
    taxed = L.best_response_cournot("R1", zero, struct,
                                    tariff={("R1", "R2"): 5.0}, **common)
    assert taxed.ObjVal < base.ObjVal, "a 5.0 tariff on cross-region sales did nothing"


def test_collusion_restricts_output_and_raises_price(setup):
    """The theory, as code. Domain invariants belong in assertions, not prose."""
    struct = setup["struct"]
    common = dict(a_int=setup["a_int"], b_slp=setup["b_slp"], nbp_rev=NBP_REV,
                  learning="both", **setup["kw"])
    game = L.cournot_iterate(struct, first="R1", max_iter=16, tol=0.5,
                             mipgap=1e-3, **common)
    assert game["status"] == "CONVERGED", f"game status {game['status']}"
    jm = L.joint_profit_max(struct, mipgap=0.005, **common)
    assert jm.SolCount > 0

    import pandas as pd
    cournot = pd.DataFrame(L.market_outcome(game["sales"], struct,
                                            setup["a_int"], setup["b_slp"]))
    jsales = {r: {(rt, p): jm._H[r]["sale"][rt, p].X
                  for rt in struct.regions for p in struct.P}
              for r in struct.regions}
    collusion = pd.DataFrame(L.market_outcome(jsales, struct,
                                              setup["a_int"], setup["b_slp"]))
    assert collusion.quantity.sum() < cournot.quantity.sum()
    assert collusion.price.mean() > cournot.price.mean()
    assert collusion.consumer_surplus.sum() < cournot.consumer_surplus.sum()
    cournot_joint = sum(g["profit"] for g in game["log"][-2:])
    assert jm.ObjVal > cournot_joint, "collusion did not beat competition"


def test_a_readers_instance_edit_flows_through(setup):
    """The point of taking the instance as an argument rather than re-reading it."""
    struct = setup["struct"]
    edited_opex = dict(setup["inst"].opex)
    edited_opex["PROC", "R2"] = 2.00
    edited = setup["inst"].replace(opex=edited_opex)
    assert edited.opex["PROC", "R2"] == 2.00
    assert setup["inst"].opex["PROC", "R2"] == 2.2, "the original was mutated"
    struct2 = L.build_structure(edited, blocks=BLOCKS, dr=DR, life=LIFE, lead=LEAD,
                                cap_min=CAP_MIN, cap_max=CAP_MAX)
    zero = {(rt, p): 0.0 for rt in struct.regions for p in struct.P}
    common = dict(a_int=setup["a_int"], b_slp=setup["b_slp"], nbp_rev=NBP_REV,
                  learning="both", mipgap=1e-3, **setup["kw"])
    # 2.00 is R1's processing opex; R2's shipped value is 2.2, so this is a CUT
    before = L.best_response_cournot("R2", zero, struct, **common)
    after = L.best_response_cournot("R2", zero, struct2, **common)
    assert after.ObjVal > before.ObjVal, (
        "cutting R2's processing opex from 2.2 to 2.00 did not raise its profit; "
        "the edit is not reaching the model"
    )


# ------------------------------------------- the Parts 1/2/5 network instance
def test_network_instance_loads_from_both_sources():
    """A different model family from the Part 4 chain; same tables/knobs rule."""
    packaged = L.load_network_instance()
    editable = L.load_network_instance(ROOT / "data" / "raw")
    assert packaged == editable, (
        "src/lithium/data/ has drifted from data/raw/ for the network tables"
    )
    assert packaged.sites == ["M1", "M2", "P1", "P2", "F1", "F2"], (
        "site order is what models iterate in; it must follow the CSV"
    )
    assert packaged.regions == ("R1", "R2")


def test_network_instance_rejects_a_site_in_an_unknown_region(tmp_path):
    for name in ("network_tiers.csv", "network_demand.csv"):
        (tmp_path / name).write_bytes((ROOT / "data" / "raw" / name).read_bytes())
    rows = (ROOT / "data" / "raw" / "network_sites.csv").read_text().splitlines()
    rows[1] = rows[1].replace(",R1,", ",R9,")
    (tmp_path / "network_sites.csv").write_text("\n".join(rows) + "\n")
    with pytest.raises(ValueError, match="regions absent"):
        L.load_network_instance(tmp_path)


def test_network_instance_needs_all_three_tiers(tmp_path):
    for name in ("network_tiers.csv", "network_demand.csv"):
        (tmp_path / name).write_bytes((ROOT / "data" / "raw" / name).read_bytes())
    rows = (ROOT / "data" / "raw" / "network_sites.csv").read_text().splitlines()
    keep = [rows[0]] + [r for r in rows[1:] if not r.startswith(("M1", "M2"))]
    (tmp_path / "network_sites.csv").write_text("\n".join(keep) + "\n")
    with pytest.raises(ValueError, match="at least one site of each tier"):
        L.load_network_instance(tmp_path)


def test_network_demand_rebuilds_from_base_and_growth():
    """The 240-entry demand table is derived, not stored - so it must derive right."""
    inst = L.load_network_instance(ROOT / "data" / "raw")
    d = {(g, t): inst.demand_base[g] * (1 + inst.demand_growth[g]) ** (t - 1)
         for g in inst.regions for t in range(1, 21)}
    assert len(d) == 40
    assert abs(d["R1", 1] - 110.0) < 1e-12
    assert abs(d["R2", 1] - 85.0) < 1e-12
    # R2 grows faster, so it must overtake R1 inside a 20-year horizon
    assert d["R2", 20] > d["R1", 20], "the asymmetry the instance exists for is gone"
