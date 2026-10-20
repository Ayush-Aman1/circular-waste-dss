import numpy as np
import pandas as pd
import pytest
import yaml

from circwaste.config import load_assumptions
from circwaste.forecast.features import build_panel
from circwaste.forecast.live import LiveForecaster
from circwaste.geo.world import load_study
from circwaste.scenario.levers import Levers, apply_levers
from circwaste.scenario.loop import make_exogenous, run_loop

CFG = load_assumptions()
LC = yaml.safe_load(open("configs/loop.yaml"))
PC = yaml.safe_load(open("configs/policies.yaml"))


@pytest.fixture(scope="module")
def study():
    return load_study()


@pytest.fixture(scope="module")
def fc():
    return LiveForecaster()


def test_live_features_match_training_panel(fc):
    h = pd.read_parquet("data/sim/history_seed4.parquet")
    full = build_panel(h)
    d = 120
    w = h[(h.day >= d - 22) & (h.day < d)]
    feat = fc.features(w, d, int(h[h.day == d].weekday.iloc[0]), int(h[h.day == d].festival.iloc[0]))
    ref = full[full.day == d].set_index("point_id").loc[feat.point_id]
    from circwaste.forecast.features import FEATURES
    np.testing.assert_allclose(feat[FEATURES].to_numpy(dtype=float), ref[FEATURES].to_numpy(dtype=float), rtol=1e-9, atol=1e-9)


@pytest.mark.parametrize("policy", ["threshold", "overflow_only", "recovery_aware", "value_only"])
def test_mass_balance_and_vehicle_capacity(study, fc, policy):
    ex = make_exogenous(study, CFG, 100, LC["warmup_days"] + 3)
    r = run_loop(policy, 100, study, CFG, LC, PC, fc, exo=ex, eval_days=3, keep_detail=True)
    assert len(r.days) == 3 and r.days.synthetic.all() and r.summary["synthetic"] is True
    assert r.days.ledger_residual_kg.abs().max() < 1e-6          # generated = in bins + collected + overflow
    assert r.days.flow_residual_kg.abs().max() < 1e-6            # collected = recovered + landfill
    cap = CFG["costs"]["vehicle"]["value"]["capacity_kg"]
    for day in r.detail:
        assert all(rt["load_kg"] <= cap + 1e-6 for rt in day["routes"])


def test_same_seed_same_exogenous_across_policies(study):
    a = make_exogenous(study, CFG, 101, 40)
    b = make_exogenous(study, CFG, 101, 40)
    np.testing.assert_array_equal(a.gen, b.gen)
    assert not np.array_equal(a.gen, make_exogenous(study, CFG, 102, 40).gen)


def test_zero_change_levers_reproduce_base_exactly(study, fc):
    assert apply_levers(CFG, Levers()) == CFG
    ex = make_exogenous(study, CFG, 100, LC["warmup_days"] + 2)
    base = run_loop("overflow_only", 100, study, CFG, LC, PC, fc, exo=ex, eval_days=2)
    zero = run_loop("overflow_only", 100, study, CFG, LC, PC, fc, levers=Levers(policy="overflow_only", segregation_rate=None), eval_days=2)
    cols = ["overflow_events", "km", "routing_cost_inr", "recovered_value_inr", "collected_kg", "landfill_kg"]
    pd.testing.assert_frame_equal(base.days[cols], zero.days[cols])


def test_levers_move_metrics_the_expected_way(study, fc):
    ex = make_exogenous(study, CFG, 100, LC["warmup_days"] + 3)
    base = run_loop("overflow_only", 100, study, CFG, LC, PC, fc, exo=ex, eval_days=3).summary
    fewer = run_loop("overflow_only", 100, study, CFG, LC, PC, fc, levers=Levers(policy="overflow_only", vehicles_unavailable=2), eval_days=3).summary
    assert fewer["overflow_events"] >= base["overflow_events"]
    roomy = run_loop("overflow_only", 100, study, CFG, LC, PC, fc, levers=Levers(policy="overflow_only", capacity_pct={"dwcc": 300, "wet_plant": 300, "biomethanation": 300}),
                     eval_days=3).summary
    assert roomy["landfill_kg"] <= base["landfill_kg"] + 1e-6
