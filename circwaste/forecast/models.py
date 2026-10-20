"""Forecasters of next-day generated mass per point: naive, seasonal naive, moving average, LightGBM (point + quantiles),
Chronos-2 zero-shot quantiles. Plus overflow probability from quantiles and metrics.

Chronos-2 API verified on the installed chronos-forecasting 2.3.2: Chronos2Pipeline.from_pretrained('amazon/chronos-2'),
.predict_quantiles(list_of_1d_tensors, prediction_length=1, quantile_levels=[...]) -> (list of (1,1,Q) tensors, mean list).
"""
from __future__ import annotations

from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

from .features import FEATURES

from .constants import QLEVELS


# ------------------------------------------------------------------ simple baselines
def naive(panel: pd.DataFrame) -> np.ndarray:
    return panel.lag1.to_numpy()


def seasonal_naive(panel: pd.DataFrame) -> np.ndarray:
    return panel.lag7.to_numpy()


def moving_average(panel: pd.DataFrame) -> np.ndarray:
    return panel.roll7_mean.to_numpy()


# ------------------------------------------------------------------ LightGBM
class LGBMForecaster:
    def __init__(self, seed: int = 0, n_estimators: int = 300):
        self.seed, self.n = seed, n_estimators
        self.point: lgb.LGBMRegressor | None = None
        self.q: dict[float, lgb.LGBMRegressor] = {}

    def _mk(self, **kw) -> lgb.LGBMRegressor:
        return lgb.LGBMRegressor(n_estimators=self.n, learning_rate=0.05, num_leaves=31, min_child_samples=30, subsample=0.8, subsample_freq=1,
                                 colsample_bytree=0.8, random_state=self.seed, verbose=-1, n_jobs=4, **kw)

    def fit(self, train: pd.DataFrame, quantiles: bool = True) -> "LGBMForecaster":
        X, y = train[FEATURES], train.y
        self.point = self._mk().fit(X, y)
        if quantiles:
            for a in QLEVELS:
                self.q[a] = self._mk(objective="quantile", alpha=a).fit(X, y)
        return self

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        return self.point.predict(df[FEATURES])

    def predict_quantiles(self, df: pd.DataFrame) -> np.ndarray:
        Q = np.column_stack([self.q[a].predict(df[FEATURES]) for a in QLEVELS])
        return np.maximum.accumulate(np.maximum(Q, 0.0), axis=1)   # non-crossing, non-negative


# ------------------------------------------------------------------ Chronos-2 (separate process)
def chronos_quantiles(hist: pd.DataFrame, test_days: list[int], seed: int, cache: Path, context: int = 90, batch: int = 256,
                      device: str = "cpu") -> pd.DataFrame:
    """Zero-shot quantiles for each (point, day in test_days) of one sim seed using only that point's earlier days. Cached to parquet.
    Runs in a subprocess: torch + LightGBM in one process segfault on macOS (duplicate OpenMP)."""
    import subprocess
    import sys

    f = cache / f"chronos2_seed{seed}_{min(test_days)}_{max(test_days)}_{len(test_days)}_c{context}.parquet"
    if f.exists():
        return pd.read_parquet(f)
    cache.mkdir(parents=True, exist_ok=True)
    hp = cache / f"hist_seed{seed}_{len(hist)}.parquet"
    hist[hist.sim_seed == seed][["sim_seed", "point_id", "day", "generated_kg"]].to_parquet(hp)
    cmd = [sys.executable, "-m", "circwaste.forecast.chronos_worker", "--hist", str(hp), "--seed", str(seed), "--days", *map(str, test_days),
           "--out", str(f), "--context", str(context), "--batch", str(batch), "--device", device]
    subprocess.run(cmd, check=True)
    return pd.read_parquet(f)


# ------------------------------------------------------------------ overflow probability
def exceed_prob(qvals: np.ndarray, thresh: np.ndarray) -> np.ndarray:
    """P(Y > thresh) from quantile values (rows) at QLEVELS via a piecewise-linear CDF anchored at F(0)=0 and a 1 % tail beyond the last quantile."""
    lv = np.array([0.0] + QLEVELS + [1.0])
    out = np.empty(len(thresh))
    for i, (q, t) in enumerate(zip(qvals, thresh)):
        xs = np.concatenate([[0.0], q, [q[-1] * 1.5 + 1e-6]])
        xs = np.maximum.accumulate(xs + np.arange(len(xs)) * 1e-9)   # strictly increasing for interp
        out[i] = 1.0 - float(np.interp(t, xs, lv))
    return np.clip(out, 0.0, 1.0)


# ------------------------------------------------------------------ metrics
def mae(y, p): return float(np.mean(np.abs(y - p)))
def rmse(y, p): return float(np.sqrt(np.mean((y - p) ** 2)))


def mase(y, p, y_naive_scale: float) -> float:
    return float(np.mean(np.abs(y - p)) / y_naive_scale)


def pinball(y: np.ndarray, Q: np.ndarray) -> float:
    return float(np.mean([np.mean(np.maximum(a * (y - Q[:, k]), (a - 1) * (y - Q[:, k]))) for k, a in enumerate(QLEVELS)]))


def coverage(y: np.ndarray, Q: np.ndarray) -> dict[str, float]:
    return {f"q{a}": float(np.mean(y <= Q[:, k])) for k, a in enumerate(QLEVELS)}


def brier(p: np.ndarray, e: np.ndarray) -> float:
    return float(np.mean((p - e) ** 2))


def reliability(p: np.ndarray, e: np.ndarray, bins: int = 10) -> pd.DataFrame:
    b = np.minimum((p * bins).astype(int), bins - 1)
    d = pd.DataFrame({"bin": b, "p": p, "e": e}).groupby("bin").agg(n=("e", "size"), mean_p=("p", "mean"), obs=("e", "mean")).reset_index()
    return d
