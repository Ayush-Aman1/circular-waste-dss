"""Fit the SHAPE of daily fill increments on the real Edinburgh sensor data (Melbourne is unavailable, see BLOCKERS.md).

Edinburgh rows are bin *collection events* with the fill level (%) just before collection. For consecutive collections of the
same bin, rate = fill_before / days_since_previous_collection (% of bin per day). Relative rates r = rate / bin-mean-rate give
a scale-free increment distribution that the simulator rescales to Indian volumes.

Fitted: lognormal sigma of r, lag-1 autocorrelation of log r within a bin, weekday multipliers (mean r by weekday of the
collection that ends the interval, normalised to mean 1), share of right-censored observations (fill >= 99 %: the bin was full,
so the true rate is higher - flagged, not corrected). Caveat recorded in the output: collections are triggered by fill, which
biases intervals toward fuller bins.
Outputs: artifacts/sim/fill_noise.json, docs/calibration/fill_noise.png, data/processed/edinburgh_fill_events.csv
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

RAW = Path("data/raw/edinburgh/raw_bin_data.xlsx")


def load_events(path: Path = RAW) -> pd.DataFrame:
    d = pd.read_excel(path, sheet_name=0, skiprows=2)
    cols = {c: str(c) for c in d.columns}
    fill_col = next(c for c in cols if str(c).startswith("Fill level before collection"))
    ts_col = next(c for c in cols if str(c).startswith("Date & Time"))
    e = pd.DataFrame({"bin_id": d["Site"].astype(str), "timestamp": pd.to_datetime(d[ts_col]), "fill_pct": pd.to_numeric(d[fill_col], errors="coerce"),
                      "volume_l": pd.to_numeric(d["Volume (litres3)"], errors="coerce"), "weight_kg": pd.to_numeric(d["Weight (kg)"], errors="coerce")})
    return e.dropna(subset=["timestamp", "fill_pct"]).sort_values(["bin_id", "timestamp"]).reset_index(drop=True)


def intervals(e: pd.DataFrame, min_days: float = 0.25) -> pd.DataFrame:
    e = e.copy()
    e["prev_ts"] = e.groupby("bin_id").timestamp.shift(1)
    e["dt_days"] = (e.timestamp - e.prev_ts).dt.total_seconds() / 86400
    iv = e.dropna(subset=["dt_days"])
    iv = iv[(iv.dt_days >= min_days) & (iv.dt_days <= 14) & (iv.fill_pct > 0) & (iv.fill_pct <= 100)].copy()
    iv["rate"] = iv.fill_pct / iv.dt_days
    iv["censored"] = iv.fill_pct >= 99
    return iv


def fit(iv: pd.DataFrame, min_intervals: int = 8) -> dict:
    mu = iv.groupby("bin_id").apply(lambda g: g.fill_pct.sum() / g.dt_days.sum(), include_groups=False)
    cnt = iv.groupby("bin_id").size()
    keep = cnt[cnt >= min_intervals].index
    iv = iv[iv.bin_id.isin(keep)].copy()
    iv["rel"] = iv.rate / iv.bin_id.map(mu)
    logr = np.log(iv.rel[iv.rel > 0])
    sigma = float(logr.std(ddof=1))
    iv["logrel"] = np.log(iv.rel.clip(lower=1e-6))
    ac = []
    for _, g in iv.groupby("bin_id"):
        x = g.logrel.to_numpy()
        if len(x) >= 6 and x.std() > 0:
            ac.append(np.corrcoef(x[:-1], x[1:])[0, 1])
    wd = iv.groupby(iv.timestamp.dt.dayofweek).rel.mean()
    wd = (wd / wd.mean()).reindex(range(7)).fillna(1.0)
    return {"n_bins": int(len(keep)), "n_intervals": int(len(iv)), "lognormal_sigma": round(sigma, 4),
            "ar1_log_rate": round(float(np.nanmean(ac)), 4) if ac else 0.0,
            "weekday_multipliers_mon_to_sun": [round(float(v), 4) for v in wd], "share_censored_fill_ge_99": round(float(iv.censored.mean()), 4),
            "median_rel_rate": round(float(iv.rel.median()), 4),
            "mean_bin_rate_pct_per_day": {"median": round(float(mu.loc[keep].median()), 3), "p10": round(float(mu.loc[keep].quantile(.1)), 3), "p90": round(float(mu.loc[keep].quantile(.9)), 3)},
            "caveats": ["collections are fill-triggered (selection bias toward fuller bins)", "right-censored at 100 %",
                        "Edinburgh street litter bins in summer 2016 transferred to Indian community bins by rescaling only", "Melbourne Argyle Square dataset no longer published (BLOCKERS.md)"]}, iv


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="artifacts/sim")
    ap.add_argument("--docs", default="docs/calibration")
    a = ap.parse_args()
    e = load_events()
    Path("data/processed").mkdir(parents=True, exist_ok=True)
    e.assign(synthetic=False, source="Edinburgh Council litter-bin sensors via aileenmcd/bin_project (OGL v3)").to_csv("data/processed/edinburgh_fill_events.csv", index=False)
    params, iv = fit(intervals(e))
    params.update({"source": "Edinburgh litter-bin sensor data, OGL v3.0", "events": int(len(e)), "bins_total": int(e.bin_id.nunique()),
                   "period": [str(e.timestamp.min().date()), str(e.timestamp.max().date())], "synthetic": False})
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "fill_noise.json").write_text(json.dumps(params, indent=1))
    Path(a.docs).mkdir(parents=True, exist_ok=True)
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(1, 3, figsize=(12, 3.2))
        ax[0].hist(np.log(iv.rel.clip(lower=1e-3)), bins=40, color="#4477aa")
        ax[0].set_title(f"log relative fill rate (sigma={params['lognormal_sigma']})")
        ax[1].bar(["M", "T", "W", "T", "F", "S", "S"], params["weekday_multipliers_mon_to_sun"], color="#66aa77")
        ax[1].axhline(1, color="k", lw=.7)
        ax[1].set_title("weekday multipliers")
        ax[2].hist(iv.fill_pct, bins=25, color="#cc8844")
        ax[2].set_title("fill before collection (%)")
        fig.suptitle("Edinburgh real sensor data (calibration of fill-increment shape)", fontsize=9)
        fig.tight_layout()
        fig.savefig(Path(a.docs) / "fill_noise.png", dpi=120)
    except Exception as ex:  # plotting must not fail calibration
        print("plot skipped:", ex)
    print("calibrate:", {k: v for k, v in params.items() if k not in ("caveats",)})


if __name__ == "__main__":
    main()
