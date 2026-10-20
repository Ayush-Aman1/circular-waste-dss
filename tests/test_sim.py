import numpy as np
import pandas as pd
import pytest

from circwaste.config import load_assumptions
from circwaste.sim.generator import build_world, generate_history

NOISE = {"lognormal_sigma": 0.47, "ar1_log_rate": 0.15, "weekday_multipliers_mon_to_sun": [1.0, 0.97, 0.98, 0.93, 0.98, 1.04, 1.09]}


@pytest.fixture(scope="module")
def world():
    rng = np.random.default_rng(0)
    pts = pd.DataFrame({"point_id": [f"w{k % 2}_{k:03d}" for k in range(24)], "ward": [f"w{k % 2}" for k in range(24)], "node": range(24),
                        "lat": 12.9, "lon": 77.6, "weight_area_m2": rng.uniform(2000, 9000, 24)})
    return build_world(pts, load_assumptions(), NOISE)


def test_ward_mass_balance_30_days(world):
    h = generate_history(world, 0, 30)
    cfg = world.cfg
    fest = set(cfg["generation"]["festival_days"]["value"])
    fm = cfg["generation"]["festival_multiplier"]["value"]
    for w, base in world.ward_daily_kg.items():
        exp = sum(base * NOISE["weekday_multipliers_mon_to_sun"][d % 7] * (fm if d in fest else 1.0) for d in range(30))
        got = h[h.ward == w].generated_kg.sum()
        assert abs(got - exp) / exp < 0.01


def test_deterministic_and_seeds_differ(world):
    a, b, c = generate_history(world, 3, 20), generate_history(world, 3, 20), generate_history(world, 4, 20)
    pd.testing.assert_frame_equal(a, b)
    assert not np.allclose(a.generated_kg, c.generated_kg)


def test_no_negative_fill_and_overflow_recorded(world):
    h = generate_history(world, 1, 60)
    assert (h[["fill_before_collection_kg", "fill_end_kg", "collected_kg", "overflow_kg", "generated_kg"]] >= -1e-9).all().all()
    assert h.synthetic.all()
    # conservation per point: generated = collected + overflow + change in fill
    h = h.sort_values(["point_id", "day"])
    prev = h.groupby("point_id").fill_end_kg.shift(1).fillna(world.cfg["bins"]["initial_fill_fraction"]["value"] * h.capacity_kg)
    resid = h.generated_kg - (h.collected_kg + h.overflow_kg + (h.fill_end_kg - prev))
    assert resid.abs().max() < 1e-6
    assert (h.overflow_kg > 0).any()      # capacity factor 2.5 days + noise must overflow sometimes
