import numpy as np
import pandas as pd

from circwaste.forecast.features import build_panel
from circwaste.forecast.models import QLEVELS, brier, exceed_prob, pinball


def _hist(days=40):
    rows = []
    for p in range(3):
        for d in range(days):
            rows.append({"sim_seed": 0, "point_id": f"p{p}", "ward": "w", "day": d, "weekday": d % 7, "festival": 0, "generated_kg": 10.0 + p + 0.1 * d,
                         "fill_end_kg": 5.0, "capacity_kg": 30.0, "kg_organic": 6.0})
    return pd.DataFrame(rows)


def test_features_use_only_the_past():
    h = _hist()
    pan = build_panel(h)
    r = pan[(pan.point_id == "p1") & (pan.day == 20)].iloc[0]
    assert r.y == h[(h.point_id == "p1") & (h.day == 20)].generated_kg.iloc[0]
    assert r.lag1 == h[(h.point_id == "p1") & (h.day == 19)].generated_kg.iloc[0]
    assert r.lag7 == h[(h.point_id == "p1") & (h.day == 13)].generated_kg.iloc[0]
    # roll7 must be the mean of days 13..19, not including day 20
    assert abs(r.roll7_mean - h[(h.point_id == "p1") & (h.day.between(13, 19))].generated_kg.mean()) < 1e-9


def test_exceed_prob_monotone_and_bounded():
    q = np.tile(np.linspace(1, 8, len(QLEVELS)), (5, 1))
    p = exceed_prob(q, np.array([0.5, 2.0, 4.0, 7.0, 50.0]))
    assert (np.diff(p) <= 1e-12).all() and (p >= 0).all() and (p <= 1).all()
    assert p[0] > 0.9 and p[-1] < 0.02


def test_metrics_sane():
    y = np.array([1.0, 2.0, 3.0])
    Q = np.tile(y[:, None], (1, len(QLEVELS)))
    assert pinball(y, Q) == 0.0
    assert brier(np.array([1.0, 0.0]), np.array([1.0, 0.0])) == 0.0
