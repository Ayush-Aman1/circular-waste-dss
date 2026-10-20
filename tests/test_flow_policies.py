import numpy as np
import pandas as pd

from circwaste.config import load_assumptions
from circwaste.flow import FlowModel
from circwaste.models import MATERIALS
from circwaste.priority import DayForecast, make_policy
import yaml


def facs(cap_dwcc=1000.0):
    return pd.DataFrame([
        {"id": "w1", "kind": "wet_plant", "capacity_kg_day": 500.0, "dist_km": 3.0},
        {"id": "b1", "kind": "biomethanation", "capacity_kg_day": 200.0, "dist_km": 5.0},
        {"id": "d1", "kind": "dwcc", "capacity_kg_day": cap_dwcc, "dist_km": 1.0},
        {"id": "l1", "kind": "landfill", "capacity_kg_day": float("inf"), "dist_km": 30.0}])


def test_flow_mass_balance_and_capacity():
    cfg = load_assumptions()
    fm = FlowModel(facs(), cfg)
    rng = np.random.default_rng(0)
    for _ in range(20):
        mass = rng.uniform(0, 2000, size=len(MATERIALS))
        r = fm.day(mass)
        assert abs(mass.sum() - sum(r.recovered_kg.values()) - r.landfill_kg) < 1e-6
        for fid, cap in (("w1", 500.0), ("b1", 200.0), ("d1", 1000.0)):
            assert r.delivered_kg[fid] <= cap + 1e-9
        assert r.landfill_kg >= 0 and all(v >= 0 for v in r.recovered_kg.values())


def test_flow_capacity_bind_and_relief():
    cfg = load_assumptions()
    mass = np.zeros(len(MATERIALS))
    mass[0] = 5000.0                                   # organic only
    tight = FlowModel(facs(), cfg).day(mass)
    assert tight.over_capacity and tight.spilled_kg > 0
    roomy = FlowModel(facs(), cfg, capacity_pct={"wet_plant": 900, "biomethanation": 900}).day(mass)
    assert roomy.landfill_kg < tight.landfill_kg


def test_flow_segregation_zero_sends_all_to_landfill():
    cfg = load_assumptions()
    r = FlowModel(facs(), cfg, segregation=0.0).day(np.full(len(MATERIALS), 100.0))
    assert r.landfill_kg == 800.0 and r.recovered_value_inr == 0.0


def forecast():
    return DayForecast(["a", "b", "c"], np.array([100., 400., 50.]), np.array([500., 500., 500.]), np.array([50., 50., 50.]),
                       np.array([0.1, 0.9, 0.0]), np.array([30., 10., 200.]))


def test_policies_prize_formulas():
    cfg, pc = load_assumptions(), yaml.safe_load(open("configs/policies.yaml"))
    oc = cfg["costs"]["overflow_cost_inr"]["value"]
    f = forecast()
    thr = make_policy("threshold", pc, cfg).prizes(None, f)
    assert thr["b"] > 0 and thr["a"] == 0 and thr["c"] == 0              # predicted fill 0.9 >= 0.8 only for b
    oo = make_policy("overflow_only", pc, cfg).prizes(None, f)
    assert abs(oo["b"] - 0.9 * oc) < 1e-9 and oo["c"] == 0.0
    vo = make_policy("value_only", pc, cfg).prizes(None, f)
    assert vo == {"a": 30.0, "b": 10.0, "c": 200.0}
    ra = make_policy("recovery_aware", pc, cfg).prizes(None, f)
    assert abs(ra["c"] - 200.0) < 1e-9 and abs(ra["b"] - (0.9 * oc + 10.0)) < 1e-9
    assert make_policy("recovery_aware", pc, cfg, alpha=0.0, beta=2.0).prizes(None, f)["c"] == 400.0
