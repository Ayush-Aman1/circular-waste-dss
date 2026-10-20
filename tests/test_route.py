import numpy as np
import pytest

from circwaste.models import Vehicle
from circwaste.route import BACKENDS


def instance(n=12, seed=0, cap=500.0, nveh=2):
    rng = np.random.default_rng(seed)
    xy = rng.uniform(0, 5000, size=(n + 1, 2))
    d = np.linalg.norm(xy[:, None] - xy[None], axis=2)      # metres
    t = d / 8.0
    vehicles = [Vehicle(id=f"v{k}", capacity_kg=cap, cost_per_km=25.0) for k in range(nveh)]
    return d, t, vehicles, rng


@pytest.mark.parametrize("backend", ["ortools", "pyvrp"])
def test_huge_prize_visited_zero_prize_far_point_dropped(backend):
    d, t, veh, rng = instance()
    n = 12
    dem = np.full(n, 100.0)
    prizes = np.full(n, 150.0)
    far = int(np.argmax(d[0, 1:]))
    big = 3 if far != 3 else 4
    prizes[big] = 1e6
    prizes[far] = 0.0
    r = BACKENDS[backend](prizes, dem, veh, d, t, time_limit_s=1.0, max_iterations=150, solution_limit=500)
    served = {i for rt in r.routes for i in rt}
    assert big in served
    assert far not in served and far in r.dropped


@pytest.mark.parametrize("backend", ["ortools", "pyvrp"])
def test_capacity_never_exceeded(backend):
    d, t, veh, rng = instance(n=14, cap=450.0, nveh=3)
    dem = rng.uniform(80, 200, size=14)
    prizes = np.full(14, 5000.0)             # everything attractive: capacity must bind
    r = BACKENDS[backend](prizes, dem, veh, d, t, time_limit_s=1.0, max_iterations=150, solution_limit=500)
    assert r.routes and all(load <= 450.0 + 1e-6 for load in r.load_kg)
    assert len(r.dropped) > 0                # total demand > fleet capacity
    assert sorted(i for rt in r.routes for i in rt + [] ) == sorted(set(i for rt in r.routes for i in rt))   # no point twice


def test_unavailable_vehicle_excluded_and_empty_fleet():
    d, t, veh, _ = instance()
    veh[0].available = False
    r = BACKENDS["ortools"](np.full(12, 800.0), np.full(12, 60.0), veh, d, t, time_limit_s=1.0, solution_limit=300)
    assert set(r.vehicle_ids) <= {"v1"}
    for v in veh:
        v.available = False
    for b in BACKENDS.values():
        assert b(np.full(12, 800.0), np.full(12, 60.0), veh, d, t).routes == []


def test_backends_agree_on_small_instances():
    """Cross-check: objectives of the two solvers (same instance, same scoring) within a stated relative tolerance."""
    gaps = []
    for s in range(5):
        d, t, veh, rng = instance(n=10, seed=s, cap=600.0)
        dem = rng.uniform(40, 160, size=10)
        prizes = rng.uniform(20, 400, size=10)
        a = BACKENDS["ortools"](prizes, dem, veh, d, t, time_limit_s=2.0, solution_limit=3000)
        b = BACKENDS["pyvrp"](prizes, dem, veh, d, t, time_limit_s=2.0, max_iterations=300)
        gaps.append(abs(a.objective_inr - b.objective_inr) / max(a.objective_inr, b.objective_inr))
    assert max(gaps) <= 0.05, gaps
