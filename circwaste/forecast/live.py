"""Forecaster used inside the daily loop: the trained LightGBM point + quantile models and the validation-fitted isotonic recalibrator
(artifacts/forecast/*.joblib, written by the TRAIN phase). Chronos-2 is evaluated in the TRAIN report only: torch and LightGBM do not
share a process safely on macOS (see forecast/models.py), so the loop uses LightGBM.
"""
from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from .constants import QLEVELS
from .features import FEATURES, build_panel
from .models import exceed_prob

NEEDED = ["sim_seed", "point_id", "ward", "day", "weekday", "festival", "generated_kg", "fill_end_kg", "capacity_kg", "kg_organic"]


class LiveForecaster:
    def __init__(self, art_dir: str | Path = "artifacts/forecast"):
        art = Path(art_dir)
        self.model = joblib.load(art / "lgbm_forecaster.joblib")
        self.iso = joblib.load(art / "isotonic_lgbm.joblib")
        for m in [self.model.point, *self.model.q.values()]:
            m.set_params(n_jobs=1)

    def features(self, window: pd.DataFrame, day: int, weekday: int, festival: int) -> pd.DataFrame:
        """Feature rows for `day` from the trailing history `window` (days < day) plus a placeholder row for the day itself."""
        ph = window[window.day == window.day.max()][NEEDED].copy()
        ph["day"], ph["weekday"], ph["festival"] = day, weekday, festival
        for c in ("generated_kg", "fill_end_kg", "kg_organic"):
            ph[c] = np.nan
        panel = build_panel(pd.concat([window[NEEDED], ph], ignore_index=True))
        return panel[panel.day == day].reset_index(drop=True)

    def predict(self, feat: pd.DataFrame, fill_kg: np.ndarray, capacity_kg: np.ndarray, noise_mult: float = 1.0,
                truth_kg: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]:
        """Return (point forecast kg, recalibrated P(fill + generation > capacity)). `noise_mult` > 1 scales the point-forecast error
        (needs the true generation `truth_kg`; used only by the forecast-noise sensitivity)."""
        mean = np.maximum(self.model.predict(feat), 0.0)
        Q = self.model.predict_quantiles(feat)
        if noise_mult != 1.0 and truth_kg is not None:
            shift = (noise_mult - 1.0) * (mean - truth_kg)
            mean = np.maximum(mean + shift, 0.0)
            Q = np.maximum(Q + shift[:, None], 0.0)
        raw = exceed_prob(Q, capacity_kg - fill_kg)
        return mean, np.clip(self.iso.predict(raw), 0.0, 1.0)
