"""Point-day feature panel for next-day generated-mass forecasting. Row (seed, point, day t) predicts y_t = generated_kg using only
information up to day t-1 (lags, rolling stats) plus known calendar facts for day t (weekday, festival flag)."""
from __future__ import annotations

import numpy as np
import pandas as pd

LAGS = list(range(1, 8))
MIN_DAY = 14


def build_panel(hist: pd.DataFrame) -> pd.DataFrame:
    h = hist.sort_values(["sim_seed", "point_id", "day"]).reset_index(drop=True)
    g = h.groupby(["sim_seed", "point_id"], sort=False)
    out = h[["sim_seed", "point_id", "ward", "day", "weekday", "festival", "generated_kg", "fill_end_kg", "capacity_kg"]].copy()
    out = out.rename(columns={"generated_kg": "y"})
    for k in LAGS:
        out[f"lag{k}"] = g.generated_kg.shift(k)
    sh = g.generated_kg.shift(1)
    out["roll7_mean"] = sh.groupby([h.sim_seed, h.point_id], sort=False).transform(lambda s: s.rolling(7).mean())
    out["roll14_mean"] = sh.groupby([h.sim_seed, h.point_id], sort=False).transform(lambda s: s.rolling(14).mean())
    out["roll7_std"] = sh.groupby([h.sim_seed, h.point_id], sort=False).transform(lambda s: s.rolling(7).std())
    out["prev_fill_end_kg"] = g.fill_end_kg.shift(1)
    out["cap_fill_ratio"] = out.prev_fill_end_kg / out.capacity_kg
    # static: capacity, mean organic share (from history up to MIN_DAY only is overkill; use expanding share to avoid leakage)
    out["organic_share_roll14"] = (h.kg_organic / h.generated_kg).groupby([h.sim_seed, h.point_id], sort=False).transform(
        lambda s: s.shift(1).rolling(14).mean())
    out["ward_code"] = out.ward.astype("category").cat.codes
    out["wd_sin"] = np.sin(2 * np.pi * out.weekday / 7)
    out["wd_cos"] = np.cos(2 * np.pi * out.weekday / 7)
    return out[out.day >= MIN_DAY].reset_index(drop=True)


FEATURES = [f"lag{k}" for k in LAGS] + ["roll7_mean", "roll14_mean", "roll7_std", "weekday", "wd_sin", "wd_cos", "festival", "capacity_kg",
                                        "organic_share_roll14", "ward_code"]
