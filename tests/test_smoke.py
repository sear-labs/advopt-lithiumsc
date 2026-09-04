"""Smoke test: the models build, solve, and obey the invariants they must obey.

Not testing for research correctness — testing that nothing is broken. This is
what CI runs on every push, and it is the single highest-value test for research
code.

The interesting one here is `test_policy_superset_collapses`: `docs/design-rationale.md` §6
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
    """docs/design-rationale.md §6: 4e's add_region reduces exactly to 4c's when policy is empty.

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


# ------------------------------------------ the Parts 1/2 network core model
CORE_KNOBS = dict(T=20, r=0.05, life=20, max_builds=3, eta_mine=0.90,
                  eta_min=0.60, transport_own=0.4, transport_cross=1.6,
                  slack_pen=45.0, learn_tiers=("P", "F"), learn_frac=0.70,
                  lr=0.20, q0=380.0, c_floor_frac=0.55, g_exog=0.035)


@pytest.fixture(scope="module")
def core():
    inst = L.load_network_instance(ROOT / "data" / "raw")
    return L.build_core_structure(inst, **CORE_KNOBS)


def test_core_structure_derives_the_sets(core):
    assert core.years == list(range(1, 21))
    assert core.learn_sites == ("P1", "P2", "F1", "F2"), "mining should not learn"
    assert len(core.ETA) == 920, "yields by (tier, vintage, year)"
    assert all(core.eta_min <= v <= 1.0 for v in core.ETA.values()), \
        "a yield outside [eta_min, 1] is not a yield"


def test_core_yields_improve_with_vintage_and_age(core):
    """The two effects the vintage model exists to represent."""
    # a later vintage starts closer to the ceiling
    assert core.ETA["P", 10, 12] > core.ETA["P", 2, 12]
    # and an asset improves within its own life
    assert core.ETA["P", 2, 12] > core.ETA["P", 2, 3]


def test_core_lumpsum_costs_more_than_annualized(core):
    """Part 1 section 4: lump-sum charges the whole asset inside the horizon."""
    iy = list(range(1, 21, 3))
    a = L.build(core, invest_years=iy, capex_mode="annualized", learning="none")
    a.optimize()
    b = L.build(core, invest_years=iy, capex_mode="lumpsum", learning="none")
    b.optimize()
    assert a.SolCount > 0 and b.SolCount > 0
    assert b.ObjVal > a.ObjVal, "lump-sum should charge more inside the horizon"


def test_core_endogenous_learning_adds_sos2(core):
    """The SOS2 sets are what stop the convex combination exploiting the chord."""
    iy = list(range(1, 21, 3))
    none = L.build(core, invest_years=iy, learning="none")
    endo = L.build(core, invest_years=iy, learning="endogenous")
    none.update(); endo.update()
    assert none.NumSOS == 0
    assert endo.NumSOS > 0, "endogenous learning without SOS2 is the Part 3 bug"


def test_core_learning_never_raises_cost(core):
    """Learning is a cost reduction; a mode that raised cost would be a bug."""
    iy = list(range(1, 21, 3))
    objs = {}
    for mode in ("none", "exogenous", "endogenous"):
        m = L.build(core, invest_years=iy, learning=mode)
        m.optimize()
        assert m.SolCount > 0, f"learning={mode} found no solution"
        objs[mode] = m.ObjVal
    assert objs["exogenous"] < objs["none"]
    assert objs["endogenous"] < objs["none"]


def test_core_mipgap_collapse(core):
    """docs/design-rationale.md §6: Part 2's build adds `mipgap`; None must reproduce Part 1."""
    iy = list(range(1, 21, 3))
    a = L.build(core, invest_years=iy, mipgap=None)
    a.optimize()
    b = L.build(core, invest_years=iy)
    b.optimize()
    assert abs(a.ObjVal - b.ObjVal) / abs(b.ObjVal) < 1e-9
    assert a.NumVars == b.NumVars and a.NumConstrs == b.NumConstrs


def test_core_staggered_mesh_is_cheaper_than_annual(core):
    """Part 1 section 5: a staggered mesh buys most of the accuracy for fewer bins."""
    annual = L.build(core, invest_years=list(range(1, 21)))
    stag = L.build(core, invest_years=L.staggered_years(20))
    annual.update(); stag.update()
    assert stag.NumBinVars < annual.NumBinVars
    assert L.staggered_years(20) == [1, 2, 3, 4, 5, 6, 7, 9, 11, 16]


# ------------------------------------------- Parts 2: two-stage stochastic
@pytest.fixture(scope="module")
def stoch(core):
    """A small tree on a short horizon; the theory does not need a big one."""
    small = L.build_core_structure(L.load_network_instance(ROOT / "data" / "raw"),
                                   **{**CORE_KNOBS, "T": 12})
    return dict(st=small, scens=L.scenarios(small), iy=[1, 4, 7, 10], s1=[1])


def test_scenario_tree_is_a_probability_distribution(stoch):
    scens = stoch["scens"]
    assert abs(sum(p for _, p, _ in scens) - 1.0) < 1e-12, "probabilities must sum to 1"
    # R1 is known in every scenario; only R2 varies. That IS the uncertainty.
    r1 = {tuple(sorted((k, v) for k, v in D.items() if k[0] == "R1"))
          for _, _, D in scens}
    assert len(r1) == 1, "R1 demand differs across scenarios; it is meant to be known"
    r2 = {tuple(sorted((k, v) for k, v in D.items() if k[0] == "R2"))
          for _, _, D in scens}
    assert len(r2) == len(scens), "R2 demand is identical across scenarios"


def test_scenarios_n_of_one_is_the_mean_case(stoch):
    one = L.scenarios_n(stoch["st"], 1)
    assert len(one) == 1 and one[0][1] == 1.0


def test_nonanticipativity_is_what_the_extensive_form_adds(stoch):
    """Without the NA constraints this is three separate problems, not a program."""
    ef = L.extensive_form(stoch["st"], stoch["scens"], stoch["iy"], stoch["s1"],
                          mipgap=1e-6)
    ef.update()
    na = [c for c in ef.getConstrs() if c.ConstrName.startswith("NA_")]
    assert na, "no nonanticipativity constraints; the scenarios are not linked"
    n_s1 = len([k for k in ef._ys[0] if k[1] in stoch["s1"]])
    assert len(na) == n_s1 * (len(stoch["scens"]) - 1)


def test_the_ws_rp_eev_chain_holds(stoch):
    """the Code Standard, Part 6: assert the theory, and evaluate all three identically."""
    r = L.three_case_comparison(stoch["st"], stoch["scens"], stoch["iy"],
                                stoch["s1"], mipgap=1e-6)
    assert r["WS"] <= r["RP"] + 1e-6, "wait-and-see must be a lower bound on RP"
    assert r["RP"] <= r["EEV"] + 1e-6, "the mean-value plan cannot beat the SP plan"
    # and per scenario, perfect information beats both
    for i, (pi, sp, ev) in enumerate(zip(r["per"]["PI"], r["per"]["SP"],
                                         r["per"]["EV"])):
        assert pi["cost"] <= sp["cost"] + 1e-6, f"scenario {i}: PI > SP"
        assert pi["cost"] <= ev["cost"] + 1e-6, f"scenario {i}: PI > EV"


def test_plan_building_entry_points_accept_a_mipgap():
    """A function that commits a DISCRETE plan must be told its precision.

    `rolling_horizon` had no `mipgap`, so it solved every window at `build`'s
    0.005 default while 01_deterministic's own `rolling()` uses 0.001. A looser
    gap there does not shift the answer slightly: each window commits a
    different set of builds and the error compounds across the windows that
    follow. At W=3 it committed 5 units instead of 4.
    """
    import inspect
    for name in ("build", "solve", "rolling_horizon", "evaluate_plan"):
        sig = inspect.signature(getattr(L, name))
        assert "mipgap" in sig.parameters or "kw" in sig.parameters, (
            f"{name} cannot be told a MIP gap, so it cannot be made to agree "
            f"with a notebook that sets one")


def test_rolling_horizon_gap_changes_the_committed_plan(core):
    """Evidence for the test above, rather than an assertion about an API.

    If this ever stops holding, the gap no longer matters here and the
    docstrings above should be corrected rather than trusted.
    """
    loose, _ = L.rolling_horizon(core, W=3, delta=3, invest_step=3, mipgap=0.005)
    tight, _ = L.rolling_horizon(core, W=3, delta=3, invest_step=3, mipgap=0.001)
    assert sum(loose.values()) != sum(tight.values()) or loose != tight, (
        "the MIP gap no longer changes the committed plan at W=3; the warning "
        "in rolling_horizon's docstring is now misleading")


def test_progressive_hedging_is_deterministic(stoch):
    """There is no seed because nothing is random. Two runs must be identical."""
    kw = dict(rho=300, iters=8)
    a = L.progressive_hedging(stoch["st"], stoch["scens"], stoch["iy"],
                              stoch["s1"], **kw)
    b = L.progressive_hedging(stoch["st"], stoch["scens"], stoch["iy"],
                              stoch["s1"], **kw)
    assert a["resid"] == b["resid"], "PH is not reproducible run to run"
    assert a["z"] == b["z"]


def test_ph_block_variant_solves_fewer_subproblems(stoch):
    """The point of the block-asynchronous variant, asserted rather than claimed."""
    full = L.progressive_hedging(stoch["st"], stoch["scens"], stoch["iy"],
                                 stoch["s1"], rho=300, iters=8, block_frac=1.0)
    half = L.progressive_hedging(stoch["st"], stoch["scens"], stoch["iy"],
                                 stoch["s1"], rho=300, iters=8, block_frac=0.5)
    assert half["subsolves"] < full["subsolves"]


# --------------------------------------------------------------------------
# Parts 2b and 2c: the two-stage capacity network


@pytest.fixture(scope="module")
def ts():
    inst = L.load_twostage_instance(ROOT / "data" / "raw")
    st = L.build_twostage_structure(inst)
    return dict(st=st, demand=L.demand_scenarios(st, n=12, seed=11),
                shock=L.shock_scenarios(st, n=16, seed=7))


def test_twostage_instance_tables_load(ts):
    inst = ts["st"].inst
    assert inst.stages == ("MINE", "PROC", "MFG")
    assert inst.regions == ("R1", "R2")
    assert len(ts["st"].nodes) == 6 and len(ts["st"].arcs) == 12
    assert all(0 < e <= 1 for e in inst.eta.values()), "a yield must be in (0, 1]"


def test_lshaped_reproduces_the_extensive_form(ts):
    """The cuts are exact at the point they are generated, so this is not
    'close enough' - at convergence the two are the same problem."""
    st, sc = ts["st"], ts["demand"]
    ef = L.twostage.extensive_form(st, sc)
    ef.optimize()
    r = L.lshaped(st, sc, max_iter=200)
    rel = abs(r["value"] - ef.ObjVal) / abs(ef.ObjVal)
    assert rel < 1e-9, f"L-shaped disagrees with the extensive form by {rel:.2e}"


def test_lshaped_bounds_bracket_the_optimum(ts):
    """The master is a relaxation and the evaluated plan is feasible, so the
    optimum must lie between them. If it does not, a cut removed it."""
    st, sc = ts["st"], ts["demand"]
    ef = L.twostage.extensive_form(st, sc)
    ef.optimize()
    r = L.lshaped(st, sc, max_iter=200)
    assert r["bound"] <= ef.ObjVal + 1e-6, "a cut cut off the true optimum"
    assert r["value"] >= ef.ObjVal - 1e-9, "a feasible plan beat the optimum"


def test_single_cut_finds_the_same_optimum_more_slowly(ts):
    st, sc = ts["st"], ts["demand"]
    multi = L.lshaped(st, sc, max_iter=200)
    single = L.lshaped(st, sc, max_iter=400, multicut=False)
    rel = abs(multi["value"] - single["value"]) / abs(multi["value"])
    assert rel < 1e-9, "the two cut styles found different optima"
    assert single["iters"] > multi["iters"], \
        "aggregating 12 cuts into 1 cost no iterations, which would be a surprise"


def test_recourse_duals_are_nonpositive(ts):
    """More capacity can never make a minimisation problem worse, so every dual
    on `x[n] <= c[n]` must be <= 0. A positive one means the cut has the wrong
    sign and the L-shaped loop will converge to the wrong answer."""
    st = ts["st"]
    zero = {n: 0.0 for n in st.nodes}
    for scen in ts["demand"][:4]:
        _, beta = L.twostage.recourse(st, scen, zero)
        assert all(b <= 1e-9 for b in beta.values()), \
            f"a capacity dual came out positive: {beta}"
        assert any(abs(b) > 1e-9 for b in beta.values()), \
            "every dual was zero, so the cut from this scenario is a flat line"


def test_optimal_plan_sits_on_the_yield_chain(ts):
    """Each stage is sized to what the stage above can feed it; more would be
    capacity that can never be used. A structural property, not a coincidence."""
    st = ts["st"]
    ef = L.twostage.extensive_form(st, ts["demand"])
    ef.optimize()
    plan = L.twostage.capacity_plan(ef, st)
    built = [r for r in st.regions if plan["MINE", r] > 1e-6]
    assert built, "nothing was built at all"
    for r in built:
        mine = plan["MINE", r]
        assert abs(plan["PROC", r] - mine * st.inst.eta["MINE"]) < 1e-6
        assert abs(plan["MFG", r]
                   - mine * st.inst.eta["MINE"] * st.inst.eta["PROC"]) < 1e-6


def test_cvar_at_alpha_one_is_the_mean(ts):
    """The whole distribution is the tail. If this fails, the
    Rockafellar-Uryasev block is wrong."""
    st, sc = ts["st"], ts["shock"]
    r = L.risk_model(st, sc, "cvar", alpha=1.0)
    ev = L.evaluate_capacity(st, sc, r["plan"])
    assert abs(L.twostage.cvar_of(ev["dist"], 1.0) - ev["mean"]) < 1e-6


def test_risk_ordering_holds_for_every_plan(ts):
    st, sc = ts["st"], ts["shock"]
    for mode in L.twostage.RISK_MODES:
        r = L.risk_model(st, sc, mode)
        ev = L.evaluate_capacity(st, sc, r["plan"])
        cv = L.twostage.cvar_of(ev["dist"], 0.10)
        assert ev["mean"] <= cv + 1e-6 <= ev["worst"] + 1e-6, \
            f"{mode}: mean <= CVaR <= worst is violated"


def test_the_reported_mean_is_not_a_property_of_the_plan(ts):
    """Part 2c's central defect, pinned.

    Minimax constrains only the worst scenario, so recourse in every other
    scenario is free and the solver returns arbitrary values. Averaging those
    gave 2245.5 for a plan whose true mean is 1642.2. This asserts BOTH halves:
    identical plans must re-evaluate identically, and the reported means must
    disagree -- because if they ever stop disagreeing, the notebook's whole
    section 6 has become invisible and needs rewriting rather than trusting.
    """
    st, sc = ts["st"], ts["shock"]
    res = {m: L.risk_model(st, sc, m) for m in L.twostage.RISK_MODES}
    keyed = {}
    for m, r in res.items():
        keyed.setdefault(tuple(round(r["plan"][n], 6) for n in st.nodes),
                         []).append(m)
    shared = max(keyed.values(), key=len)
    assert len(shared) > 1, "no two objectives shared a plan on this instance"
    true = {round(L.evaluate_capacity(st, sc, res[m]["plan"])["mean"], 6)
            for m in shared}
    assert len(true) == 1, \
        "identical plans re-evaluated to different costs, which cannot happen"
    reported = {round(res[m]["mean"], 6) for m in shared}
    assert len(reported) > 1, (
        "the reported means agreed, so Part 2c section 6's defect is not "
        "reproducible here any more")


def test_evaluate_capacity_is_indifferent_to_how_the_plan_was_found(ts):
    """The same six numbers must score the same way however they arrived."""
    st, sc = ts["st"], ts["shock"]
    a = L.risk_model(st, sc, "cvar")["plan"]
    ev1 = L.evaluate_capacity(st, sc, a)
    ev2 = L.evaluate_capacity(st, sc, dict(a))
    assert abs(ev1["mean"] - ev2["mean"]) < 1e-12
    assert abs(ev1["worst"] - ev2["worst"]) < 1e-12


def test_scenario_generators_are_reproducible(ts):
    """No seed is hidden and the draw order is part of the definition."""
    st = ts["st"]
    assert L.demand_scenarios(st, n=8, seed=3) == L.demand_scenarios(st, n=8, seed=3)
    assert L.shock_scenarios(st, n=8, seed=3) == L.shock_scenarios(st, n=8, seed=3)
    assert L.demand_scenarios(st, n=8, seed=3) != L.demand_scenarios(st, n=8, seed=4)
    for _, p, d in L.demand_scenarios(st, n=8, seed=3):
        assert p == 1 / 8 and set(d) == set(st.regions)


# --------------------------------------------------------------------------
# Parts 3 and 3b: the network-core chain


@pytest.fixture(scope="module")
def nc():
    inst = L.load_netcore_instance(ROOT / "data" / "raw")
    # a coarse mesh: the theory does not need 15 periods and the tests are run
    # on every commit
    st = L.build_netcore_structure(inst, blocks=[(3, 1), (2, 3), (1, 9)])
    u0 = sum(inst.unit[s] for s in ("PROC", "MFG")) / 2
    QBP, CBPm = L.capex_breakpoints(400.0, 1000.0, 9, 0.20, 0.55, panels=600)
    return dict(inst=inst, st=st, curve=(QBP, [u0 * c for c in CBPm]))


def test_netcore_instance_shares_efficiency_with_part_4():
    """`efficiency.csv` is one table read by two instances, not two copies."""
    nc_inst = L.load_netcore_instance(ROOT / "data" / "raw")
    p4 = L.load_instance(ROOT / "data" / "raw")
    for s in nc_inst.stages:
        assert nc_inst.eta_ceil[s] == p4.eta_ceil[s]
        assert nc_inst.alpha[s] == p4.alpha[s]
        assert nc_inst.delta_bar[s] == p4.delta_bar[s]


def test_netcore_costs_are_symmetric_across_regions(nc):
    """Part 3's whole setting: any asymmetry in the answer came from demand,
    legacy fleets or geography, never from one region being cheaper."""
    inst = nc["inst"]
    for s in inst.stages:
        assert isinstance(inst.fixed[s], float)
    # the cost tables are keyed by STAGE alone, so symmetry is structural
    assert set(inst.fixed) == set(inst.stages)
    assert set(inst.unit) == set(inst.stages)
    assert set(inst.operate) == set(inst.stages)


def test_netcore_legacy_retirement_is_inclusive(nc):
    """An asset retiring in year 9 still runs in a period starting in year 9.

    Off by one here silently removes capacity, and the model absorbs it as
    unmet demand rather than failing.
    """
    st = nc["st"]
    for (s, r) in st.nodes:
        ret = st.inst.legacy_ret[s, r]
        periods = [p for p in st.P if (s, r, -1, p) in set(st.ACTIVE)]
        latest = max((st.START[p] for p in periods), default=None)
        if latest is not None:
            assert latest <= ret, f"{s}/{r} legacy runs past its retirement year"
        due = [p for p in st.P if st.START[p] == ret]
        if due:
            assert (s, r, -1, due[0]) in set(st.ACTIVE), (
                f"{s}/{r} legacy is missing from the period starting in its "
                f"retirement year {ret}; the bound should be inclusive")


def test_netcore_yields_stay_between_floor_and_ceiling(nc):
    st = nc["st"]
    for s in st.inst.stages:
        for v in [-1] + st.P:
            for p in st.P:
                assert 0.60 - 1e-12 <= st.ETA[s, v, p] <= st.inst.eta_ceil[s] + 1e-12


def test_netcore_solves_and_meets_demand(nc):
    r = L.solve_netcore(nc["st"], learning="capacity", capex_curve=nc["curve"],
                        allow_dispose=False, pen_short=90.0)
    assert r["obj"] is not None and r["builds"] > 0
    assert r["short"] < 1e-6, "demand went unserved despite the penalty"


def test_netcore_learning_never_costs_more(nc):
    """Endogenous learning is a discount that must be earned, but it is still a
    discount: the same model with it cannot come out dearer."""
    with_ = L.solve_netcore(nc["st"], learning="capacity",
                            capex_curve=nc["curve"], allow_dispose=False)
    without = L.solve_netcore(nc["st"], learning="none",
                              capex_curve=nc["curve"], allow_dispose=False)
    assert with_["obj"] <= without["obj"] + 1e-6


def test_netcore_sos2_keeps_lambda_adjacent(nc):
    """The cumulative curve is CONCAVE and this is a minimisation, so without
    SOS2 the model buys capacity along a chord at a price the curve never
    offers. Adjacency is the observable symptom that it is enforced."""
    m = L.build_netcore(nc["st"], learning="capacity", capex_curve=nc["curve"],
                        allow_dispose=False)
    m.optimize()
    assert m.SolCount > 0
    for p in nc["st"].P:
        ks = sorted(k for k in m._K if m._lam[p, k].X > 1e-6)
        assert len(ks) <= 1 or (len(ks) == 2 and ks[1] == ks[0] + 1), \
            f"period {p} used non-adjacent breakpoints {ks}"


def test_netcore_capex_curve_matches_the_shared_one(nc):
    """Parts 3 and 3b do NOT get a fourth copy of Wright's law."""
    QBP, CBP = nc["curve"]
    u0 = sum(nc["inst"].unit[s] for s in ("PROC", "MFG")) / 2
    for q, c in zip(QBP, CBP):
        want = u0 * L.capex_cum_multiplier(q, 400.0, 0.20, 0.55, 600)
        assert abs(c - want) <= 1e-9 * max(abs(want), 1.0)
    slopes = [(CBP[i + 1] - CBP[i]) / (QBP[i + 1] - QBP[i])
              for i in range(len(QBP) - 1)]
    assert all(slopes[i] >= slopes[i + 1] - 1e-9 for i in range(len(slopes) - 1)), \
        "the cumulative capex curve is not concave, so SOS2 is the wrong tool"


def test_netcore_learning_channels_are_separable(nc):
    """Part 3b's structural check: Channel A moves capex and Channel B moves
    opex, and neither touches the other's term."""
    st, curve = nc["st"], nc["curve"]
    kw = dict(capex_curve=curve, n_tiers=3, lag_years=3, allow_dispose=True)
    (tq, tm), _obj, _prod = L.calibrate_tiers(
        st, n_tiers=3, lr_opex=0.18, opex_floor=0.65,
        **{k: v for k, v in kw.items() if k != "n_tiers"})
    res = {lm: L.solve_netcore(st, learning=lm, tiers=(tq, tm), **kw)
           for lm in ("none", "capacity", "production", "both")}
    cap = {k: v["components"]["capex"] for k, v in res.items()}
    opx = {k: v["components"]["operate"] for k, v in res.items()}
    assert abs(cap["production"] - cap["none"]) < 1e-6, \
        "production learning moved capex; it is supposed to touch opex only"
    assert abs(opx["both"] - opx["production"]) < 1e-6, \
        "capacity learning moved Channel B's opex; the channels interfere"


def test_netcore_tier_activation_is_monotone(nc):
    """Cumulative production cannot decrease, so a node cannot fall back a tier.

    If it does, a big-M is the wrong sign or the lag map is wrong -- and the
    objective would still look plausible.
    """
    st, curve = nc["st"], nc["curve"]
    (tq, tm), _o, _p = L.calibrate_tiers(st, n_tiers=3, lr_opex=0.18,
                                         opex_floor=0.65, capex_curve=curve,
                                         lag_years=3, allow_dispose=True)
    m = L.build_netcore(st, learning="production", tiers=(tq, tm),
                        capex_curve=curve, n_tiers=3, lag_years=3)
    m.optimize()
    assert m.SolCount > 0 and m._z is not None
    for (s, rk) in m._scope:
        path = [next(j for j in range(3) if m._z[s, rk, p, j].X > 0.5)
                for p in st.P]
        assert path == sorted(path), f"{s}/{rk} went backwards through the tiers"


def test_netcore_cumulative_production_is_undiscounted(nc):
    """A knowledge stock counts units made, not their present value.

    Discounting it would be a category error, and every other sum in the model
    IS discounted, so it is an easy one to make.
    """
    import inspect
    src = inspect.getsource(L.build_netcore)
    block = src[src.index("cum_prod"):src.index("cum_prod") + 800]
    body = src[src.index("cumprod[s, rk, p]"):src.index("name=\"cum_prod\"")]
    assert "LEN[q]" in body, "cumulative production is not weighted by period length"
    assert "OMEGA" not in body, \
        "cumulative production is discounted; a knowledge stock must not be"


# --------------------------------------------------------------------------
# Part 4f: interdiction


@pytest.fixture(scope="module")
def idnet():
    inst = L.load_interdiction_instance(ROOT / "data" / "raw")
    return L.build_flow_network(inst)


def test_super_source_and_sink_are_not_attackable(idnet):
    """They stand for a reserve base and a demand aggregate, not for links.

    Leave them attackable and the attacker cuts the three source arcs; the
    problem becomes trivial and the notebook has nothing to say.
    """
    for a in idnet.attackable:
        assert a[0] != "SRC" and a[1] != "SNK"
    assert len(idnet.attackable) == len(idnet.arcs) - 2 * len(idnet.inst.regions)


def test_attacker_dual_reproduces_the_primal_it_replaces(idnet):
    """The whole method rests on max-flow == min-cut.

    A wrong dual does not crash - it returns numbers that look like throughput.
    The only check is to hand its chosen attack to the operator's own LP.
    """
    for budget in (0, 1, 2, 3, 4):
        val, attack = L.attacker_best_response(idnet, budget)
        direct, _ = L.max_flow(idnet, interdicted=attack)
        assert abs(val - direct) < 1e-6, (
            f"budget {budget}: min-cut says {val:.4f}, the operator achieves "
            f"{direct:.4f} under that exact attack")
        assert len(attack) <= budget


def test_more_attacker_budget_never_helps_the_operator(idnet):
    vals = [L.attacker_best_response(idnet, b)[0] for b in range(0, 5)]
    assert all(vals[i] >= vals[i + 1] - 1e-9 for i in range(len(vals) - 1)), \
        f"throughput rose with a bigger attacker budget: {vals}"


def test_bri_reproduces_enumeration(idnet):
    """The value must match. The fortification need not - ties are real here."""
    for bdef in (1, 2):
        ev, _ef, _ = L.defender_enumerate(idnet, bdef, 3)
        r = L.best_response_intersection(idnet, bdef, 3)
        assert abs(ev - r["value"]) < 1e-6
        assert all(h["UB"] >= h["LB"] - 1e-9 for h in r["hist"]), \
            "an upper bound fell below a lower bound"


def test_restricting_defender_candidates_can_lose_throughput(idnet):
    """Part 4f section 9's finding, pinned from both sides.

    The restricted set can never beat the full one, and on this instance it
    must actually lose something - otherwise the notebook's central negative
    result has gone and its prose needs rewriting.
    """
    seen = set()
    for b in range(1, 6):
        _, atk = L.attacker_best_response(idnet, b)
        seen |= set(atk)
    restricted = sorted(seen)
    lost_somewhere = False
    for bdef in (1, 2):
        full, _, _ = L.defender_enumerate(idnet, bdef, 3)
        rest, _, _ = L.defender_enumerate(idnet, bdef, 3, candidates=restricted)
        assert rest <= full + 1e-9, "the restricted set beat the full set"
        if rest < full - 1e-6:
            lost_somewhere = True
    assert lost_somewhere, (
        "restricting the candidates cost nothing on this instance; Part 4f "
        "section 9 says it does")


# --------------------------------------------------------------------------
# Part 5: the integrated core


@pytest.fixture(scope="module")
def p5():
    return L.load_integrated_instance(ROOT / "data" / "raw")


def test_integrated_instance_separates_chain_from_loop(p5):
    assert p5.recycle_stage not in p5.chain
    assert p5.stages == p5.chain + (p5.recycle_stage,)
    assert all(0 < y <= 1 for y in p5.yield_.values())


def test_period_weights_tile_the_horizon(p5):
    """A weight that does not tile means years counted twice or not at all,
    and the objective would still look reasonable."""
    plan = ((6, 1), (4, 3), (3, 5))
    lens, starts, H = L.periods_from_plan(plan)
    rho = 0.05
    omega = {p: sum((1 + rho) ** -(starts[p] + k) for k in range(lens[p]))
             for p in range(len(lens))}
    assert abs(sum(omega.values()) - sum((1 + rho) ** -t for t in range(H))) < 1e-9


def test_recycling_cannot_precede_the_pack_lifetime(p5):
    """Nothing can be recycled before anything has been scrapped."""
    m = L.integrated.build(p5, pack_life=10, mipgap=1e-3)
    m.optimize()
    assert m.SolCount > 0
    for row in L.recycled_share(m):
        if row["year"] < 10:
            assert row["recycled"] < 1e-6, (
                f"recycled material in year {row['year']}, before any pack "
                f"could have been scrapped")


def test_closing_the_loop_cannot_cost_more(p5):
    """Dual feedstock adds an option without removing an obligation.

    If this ever fails, the `rec_sink` constraint has gone missing and recycled
    material is silently vanishing - which reports a CHEAPER answer, not an
    error.
    """
    on = L.integrated.build(p5, allow_dual_feedstock=True, mipgap=1e-4)
    on.optimize()
    off = L.integrated.build(p5, allow_dual_feedstock=False, mipgap=1e-4)
    off.optimize()
    assert on.ObjVal <= off.ObjVal + 1e-6


def test_the_collapse_invariant_holds(p5):
    """Two identical free-trading regions must equal one region, doubled.

    Asserted on the LP relaxation, where it is exact. The MILP difference is
    integer lumpiness, which is real, and is returned as a diagnostic.
    """
    r = L.collapse_test(p5)
    assert r["passed"], f"the collapse invariant failed at {r['rel_lp']:.2e}"
    assert r["rel_lp"] < 1e-9
    assert r["lp_multi"] > 1.0, "the relaxation solved to ~0; it was not copied"


def test_recycling_bound_is_an_inequality():
    """Scrap BOUNDS what recycling can process; it is not a quota.

    As an equality the model would be forced to recycle everything it ever
    sold, in every period. Checked in the source because the distinction is
    invisible in any solved objective.
    """
    import inspect
    src = inspect.getsource(L.integrated.build)
    block = src[src.index("def pack_period"):]
    block = block[:block.index("m.addConstrs((f.sum(chain[-1]")]
    assert "<=" in block and "recovery *" in block, \
        "the recycling availability constraint is no longer an inequality"


def test_every_stochastic_entry_point_accepts_a_mipgap():
    """These functions difference expectations 0.01% apart against each other.

    `build` defaults to a 0.005 MIP gap, which is an order of magnitude LARGER
    than the quantities being measured, so a function that cannot be told the
    gap cannot be made to measure them. Each one below silently used 0.005
    until Part 2 was written against it.
    """
    import inspect
    for name in ("subproblem", "progressive_hedging", "evaluate_stage1",
                 "wait_and_see", "mean_value_stage1", "strategy_stage1",
                 "ph_three_case", "three_case_comparison", "extensive_form"):
        sig = inspect.signature(getattr(L, name))
        assert "mipgap" in sig.parameters, (
            f"{name} takes no mipgap, so it cannot be measured consistently "
            f"with the quantities it is differenced against")
        default = sig.parameters["mipgap"].default
        assert default == 1e-6, (
            f"{name} defaults to mipgap={default}; every stochastic entry "
            f"point must share one tight default or two of them will be "
            f"compared at different precisions")


def test_ph_three_case_solves_and_scores_at_the_same_gap(stoch):
    """A plan found at one gap and scored at another is not a measurement.

    `ph_three_case` accepted a `mipgap`, used it for the scoring solves, and
    dropped it before the progressive-hedging call that produces the plan being
    scored. This asserts the argument actually reaches the subproblems.
    """
    import inspect
    src = inspect.getsource(L.ph_three_case)
    call = src[src.index("progressive_hedging("):]
    call = call[:call.index(")")]
    assert "mipgap" in call, (
        "ph_three_case does not pass its mipgap down to progressive_hedging, "
        "so SP's plan is found at a different precision from the one it is "
        "then scored and differenced at")


def test_block_asynchrony_is_an_approximation_not_a_free_saving(stoch):
    """Skipping subproblems changes the answer, and the gap must be able to see it.

    At `build`'s 0.005 default every block fraction returned an identical cost
    and it looked like a free 63% saving. It was the gap, not the algorithm.
    """
    costs = {}
    for bf in (1.0, 0.34):
        ph = L.progressive_hedging(stoch["st"], stoch["scens"], stoch["iy"],
                                   stoch["s1"], rho=300, iters=20, block_frac=bf)
        costs[bf] = L.evaluate_stage1(stoch["st"], stoch["scens"], stoch["iy"],
                                      stoch["s1"], ph["z"])
    assert costs[1.0] != costs[0.34], (
        "solving a third of the subproblems gave exactly the same cost as "
        "solving all of them; that is a MIP gap wider than the effect, not a "
        "free saving")


def test_ph_penalty_stays_linear(stoch):
    """The x^2 = x trick: subproblems must remain MILPs, never MIQPs."""
    sub = L.subproblem(stoch["st"], stoch["scens"][0][2], stoch["iy"], stoch["s1"])
    sub.update()
    assert sub.NumQNZs == 0, (
        "a subproblem picked up quadratic terms; the binary linearisation is the "
        "only reason these stay inside a restricted licence"
    )
