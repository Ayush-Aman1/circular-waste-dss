"""Chronos-2 zero-shot quantiles in its OWN process (torch and LightGBM segfault when sharing OpenMP in one process on macOS).
python -m circwaste.forecast.chronos_worker --hist <parquet files...> --seed S --days d1 d2 ... --out f.parquet [--context 90] [--series-col generated_kg]
API (chronos-forecasting 2.3.2): Chronos2Pipeline.from_pretrained('amazon/chronos-2'); predict_quantiles(list of 1-D tensors, prediction_length=1, quantile_levels=[...])."""
from __future__ import annotations

import argparse

import numpy as np
import pandas as pd
import torch
from chronos import Chronos2Pipeline

from .constants import QLEVELS


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hist", required=True)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--days", type=int, nargs="+", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--context", type=int, default=90)
    ap.add_argument("--batch", type=int, default=256)
    ap.add_argument("--device", default="cpu")
    a = ap.parse_args()
    hist = pd.read_parquet(a.hist)
    pipe = Chronos2Pipeline.from_pretrained("amazon/chronos-2", device_map=a.device)
    h = hist[hist.sim_seed == a.seed].sort_values(["point_id", "day"])
    series = {pid: g.generated_kg.to_numpy() for pid, g in h.groupby("point_id")}
    pids = sorted(series)
    rows = []
    for d in a.days:
        ctx = [torch.tensor(series[p][max(0, d - a.context):d], dtype=torch.float32) for p in pids]
        for i in range(0, len(ctx), a.batch):
            qs, _ = pipe.predict_quantiles(ctx[i:i + a.batch], prediction_length=1, quantile_levels=QLEVELS)
            arr = np.stack([q[0, 0].numpy() for q in qs])
            for p, row in zip(pids[i:i + a.batch], arr):
                rows.append({"sim_seed": a.seed, "point_id": p, "day": d,
                             **{f"q{x}": float(v) for x, v in zip(QLEVELS, np.maximum.accumulate(np.maximum(row, 0.0)))}})
    pd.DataFrame(rows).to_parquet(a.out)
    print("chronos worker wrote", a.out, len(rows))


if __name__ == "__main__":
    main()
