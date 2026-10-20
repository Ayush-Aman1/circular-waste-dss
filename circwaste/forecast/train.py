"""Train + rolling-origin backtest of the forecasters, overflow-risk calibration, recovery-value check and the external
Edinburgh check. Writes artifacts/forecast/ (metrics.json, predictions parquet, models, plots).

    python -m circwaste.forecast.train [--smoke] [--no-chronos]

Seeds: 0..2 train, 3 validation (isotonic recalibration only), 4..5 test (reported). Smoke: seed 0 only, days split in time.
Evaluation is always out of time (origin days 120/135/150/165; the model never sees days >= origin) AND on held-out seeds.
All data here is SYNTHETIC except the Edinburgh external check, which is real sensor data.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from circwaste.config import load_assumptions, val
from circwaste.models import MATERIALS

from .features import FEATURES, build_panel
from .models import (QLEVELS, LGBMForecaster, brier, chronos_quantiles, coverage, exceed_prob, mae, mase, moving_average, naive,
                     pinball, reliability, rmse, seasonal_naive)


def qcols(prefix: str) -> list[str]:
    return [f"{prefix}_q{a}" for a in QLEVELS]


def point_metrics(panel: pd.DataFrame, name: str, col: np.ndarray, scale: float) -> dict:
    ok = ~np.isnan(col)
    y = panel.y.to_numpy()[ok]
    return {"model": name, "n": int(ok.sum()), "mae": mae(y, col[ok]), "rmse": rmse(y, col[ok]), "mase": mase(y, col[ok], scale)}


def quantile_metrics(panel: pd.DataFrame, prefix: str) -> dict:
    Q = panel[qcols(prefix)].to_numpy()
    ok = ~np.isnan(Q).any(1)
    y = panel.y.to_numpy()[ok]
    return {"pinball": pinball(y, Q[ok]), "coverage": coverage(y, Q[ok])}


def run_backtest(panel: pd.DataFrame, train_seeds: list[int], eval_seeds: list[int], origins: list[int], step: int, n_est: int) -> pd.DataFrame:
    preds = []
    for o in origins:
        tr = panel[panel.sim_seed.isin(train_seeds) & (panel.day < o)]
        ev = panel[panel.sim_seed.isin(eval_seeds) & (panel.day >= o) & (panel.day < o + step)].copy()
        if tr.empty or ev.empty:
            continue
        m = LGBMForecaster(seed=0, n_estimators=n_est).fit(tr)
        ev["lgbm_mean"] = m.predict(ev)
        Q = m.predict_quantiles(ev)
        for k, c in enumerate(qcols("lgbm")):
            ev[c] = Q[:, k]
        ev["origin"] = o
        preds.append(ev)
    out = pd.concat(preds, ignore_index=True)
    out["naive"], out["snaive"], out["ma7"] = naive(out), seasonal_naive(out), moving_average(out)
    return out


def recovery_value(pred: pd.DataFrame, hist: pd.DataFrame, cfg: dict, ycol: str) -> pd.DataFrame:
    """Predicted recovery value = predicted mass x rolling-mean composition (last 14 days) x segregation x efficiency x price."""
    seg = float(val(cfg, "segregation.rate"))
    eff = np.array([val(cfg, "recovery.efficiency")[m] for m in MATERIALS])
    price = np.array([val(cfg, "recovery.price_per_kg")[m] for m in MATERIALS])
    h = hist.sort_values(["sim_seed", "point_id", "day"]).copy()
    share = h[[f"kg_{m}" for m in MATERIALS]].div(h.generated_kg, axis=0)
    share.columns = MATERIALS
    h = pd.concat([h[["sim_seed", "point_id", "day"]], share], axis=1)
    roll = h.groupby(["sim_seed", "point_id"], sort=False)[MATERIALS].transform(lambda s: s.shift(1).rolling(14).mean())
    h[[f"s_{m}" for m in MATERIALS]] = roll.to_numpy()
    p = pred.merge(h[["sim_seed", "point_id", "day"] + [f"s_{m}" for m in MATERIALS]], on=["sim_seed", "point_id", "day"], how="left")
    unit = (p[[f"s_{m}" for m in MATERIALS]].to_numpy() * seg * eff * price).sum(1)
    p["value_pred"] = p[ycol] * unit
    return p


def edinburgh_check(raw_csv: Path, cache: Path, use_chronos: bool, n_est: int) -> dict:
    """Same methods on REAL data: street-level daily collected volume (Edinburgh, OGL v3). Train first 70 % of days, test the rest."""
    if not raw_csv.exists():
        return {"status": "unavailable", "reason": f"{raw_csv} missing"}
    d = pd.read_csv(raw_csv, parse_dates=["date"])
    d = d[d.street_name.map(d.groupby("street_name").size()) >= 40]
    t0 = d.date.min()
    d["day"] = (d.date - t0).dt.days
    full = []
    for s, g in d.groupby("street_name"):
        g = g.set_index("day").reindex(range(int(d.day.max()) + 1))
        g["street_name"] = s
        g["total_vol_l3"] = g.total_vol_l3.fillna(0.0)
        g["date"] = t0 + pd.to_timedelta(g.index, unit="D")
        full.append(g.reset_index())
    d = pd.concat(full, ignore_index=True)
    hist = pd.DataFrame({"sim_seed": 0, "point_id": d.street_name, "ward": "edinburgh", "day": d.day, "weekday": d.date.dt.dayofweek, "festival": 0,
                         "generated_kg": d.total_vol_l3, "fill_end_kg": 0.0, "capacity_kg": 1.0, "kg_organic": d.total_vol_l3})
    panel = build_panel(hist)
    cut = int(panel.day.max() * 0.7)
    tr, te = panel[panel.day < cut], panel[panel.day >= cut].copy()
    m = LGBMForecaster(seed=0, n_estimators=min(n_est, 150)).fit(tr)
    te["lgbm_mean"] = m.predict(te)
    Q = m.predict_quantiles(te)
    for k, c in enumerate(qcols("lgbm")):
        te[c] = Q[:, k]
    te["naive"], te["snaive"], te["ma7"] = naive(te), seasonal_naive(te), moving_average(te)
    scale = float(np.nanmean(np.abs(tr.y - tr.lag1)))
    res = {"status": "ok", "real_data": True, "source": "Edinburgh litter-bin sensors (aggregated street-level daily volume, OGL v3)", "streets": int(d.street_name.nunique()),
           "train_days": [int(tr.day.min()), int(tr.day.max())], "test_days": [int(te.day.min()), int(te.day.max())], "n_test_rows": int(len(te)), "models": []}
    for name in ["naive", "snaive", "ma7", "lgbm_mean"]:
        res["models"].append(point_metrics(te, name, te[name].to_numpy(), scale))
    res["lgbm_quantiles"] = quantile_metrics(te, "lgbm")
    if use_chronos:
        cq = chronos_quantiles(hist, sorted(te.day.unique().tolist()), 0, cache / "edinburgh", context=60)
        te2 = te.merge(cq, on=["sim_seed", "point_id", "day"], how="left").rename(columns={f"q{a}": f"chr_q{a}" for a in QLEVELS})
        res["chronos2_quantiles"] = quantile_metrics(te2, "chr")
        res["models"].append(point_metrics(te2, "chronos2_median", te2["chr_q0.5"].to_numpy(), scale))
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--no-chronos", action="store_true")
    ap.add_argument("--data", default=None)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    data = Path(a.data or ("data_smoke/sim" if a.smoke else "data/sim"))
    out = Path(a.out or ("artifacts_smoke/forecast" if a.smoke else "artifacts/forecast"))
    (out / "plots").mkdir(parents=True, exist_ok=True)
    cfg = load_assumptions()
    hist = pd.concat([pd.read_parquet(f) for f in sorted(data.glob("history_seed*.parquet"))], ignore_index=True)
    assert hist.synthetic.all(), "history must be flagged synthetic"
    seeds = sorted(hist.sim_seed.unique().tolist())
    panel = build_panel(hist)
    if a.smoke:
        train_s, val_s, test_s, origins, step, n_est = seeds, seeds, seeds, [20, 25], 5, 40
    else:
        train_s, val_s, test_s, origins, step, n_est = seeds[:3], seeds[3:4], seeds[4:], [120, 135, 150, 165], 15, 300
    use_chronos = not a.no_chronos
    bt = run_backtest(panel, train_s, sorted(set(val_s + test_s)), origins, step, n_est)
    scale = float(np.nanmean(np.abs(panel[panel.sim_seed.isin(train_s)].y - panel[panel.sim_seed.isin(train_s)].lag1)))
    test_days = sorted(bt.day.unique().tolist())
    if use_chronos:
        cq = pd.concat([chronos_quantiles(hist, test_days, s, Path("data/cache/chronos" if not a.smoke else "data_smoke/cache/chronos"), device="cpu")
                        for s in sorted(set(val_s + test_s))], ignore_index=True)
        cq = cq.rename(columns={f"q{x}": f"chr_q{x}" for x in QLEVELS})
        bt = bt.merge(cq, on=["sim_seed", "point_id", "day"], how="left")
    is_test = bt.sim_seed.isin(test_s) if not a.smoke else bt.sim_seed.notna()
    is_val = bt.sim_seed.isin(val_s) if not a.smoke else bt.sim_seed.notna()
    te, va = bt[is_test].copy(), bt[is_val].copy()

    metrics: dict = {"synthetic": True, "seeds": {"train": train_s, "val": val_s, "test": test_s}, "origins": origins, "step_days": step, "target": "generated_kg per point-day (one day ahead)",
                     "mase_scale_note": "mean |y_t - y_{t-1}| on training seeds", "point_forecasts": [], "quantile_forecasts": {}}
    for name in ["naive", "snaive", "ma7", "lgbm_mean"]:
        metrics["point_forecasts"].append(point_metrics(te, name, te[name].to_numpy(), scale))
    metrics["point_forecasts"].append(point_metrics(te, "lgbm_q0.5", te["lgbm_q0.5"].to_numpy(), scale))
    metrics["quantile_forecasts"]["lgbm"] = quantile_metrics(te, "lgbm")
    if use_chronos:
        metrics["point_forecasts"].append(point_metrics(te, "chronos2_q0.5", te["chr_q0.5"].to_numpy(), scale))
        metrics["quantile_forecasts"]["chronos2_zero_shot"] = quantile_metrics(te, "chr")

    # ---- overflow risk: event = fill carried in + generation tomorrow exceeds capacity (skip = no visit)
    def ev(df): return ((df.prev_fill_end_kg + df.y) > df.capacity_kg).astype(float).to_numpy()
    def thr(df): return (df.capacity_kg - df.prev_fill_end_kg).to_numpy()
    ov: dict = {"event": "prev_fill_end_kg + generated_kg > capacity_kg (no visit before the end of the day)", "event_rate_test": float(ev(te).mean()), "models": {}}
    reliab = {}
    for name, prefix in [("lgbm", "lgbm")] + ([("chronos2", "chr")] if use_chronos else []):
        pt, pv = exceed_prob(te[qcols(prefix)].to_numpy(), thr(te)), exceed_prob(va[qcols(prefix)].to_numpy(), thr(va))
        entry = {"brier_raw": brier(pt, ev(te)), "brier_climatology": brier(np.full(len(te), ev(va).mean()), ev(te))}
        if len(np.unique(ev(va))) == 2:
            from sklearn.isotonic import IsotonicRegression
            iso = IsotonicRegression(y_min=0, y_max=1, out_of_bounds="clip").fit(pv, ev(va))
            pt2 = iso.predict(pt)
            entry["brier_recalibrated_isotonic_val_fit"] = brier(pt2, ev(te))
            joblib.dump(iso, out / f"isotonic_{name}.joblib")
            reliab[f"{name}_recalibrated"] = reliability(pt2, ev(te))
        reliab[f"{name}_raw"] = reliability(pt, ev(te))
        ov["models"][name] = entry
    ov["models"]["naive_indicator"] = {"brier": brier(((te.prev_fill_end_kg + te.lag1) > te.capacity_kg).astype(float).to_numpy(), ev(te))}
    metrics["overflow_risk"] = ov

    # ---- recovery value (composition forecast = 14-day rolling mean shares)
    rv = recovery_value(te, hist, cfg, "lgbm_q0.5").dropna(subset=["value_pred"])
    true_val = rv.merge(hist[["sim_seed", "point_id", "day", "recovery_value_inr"]], on=["sim_seed", "point_id", "day"])
    metrics["recovery_value"] = {"mae_inr": mae(true_val.recovery_value_inr.to_numpy(), true_val.value_pred.to_numpy()),
                                 "mean_true_inr": float(true_val.recovery_value_inr.mean()), "n": int(len(true_val)),
                                 "note": "uses TODO-SOURCE prices/efficiencies from configs/assumptions.yaml; values are placeholders until sourced"}

    # ---- save models/predictions/plots
    final = LGBMForecaster(seed=0, n_estimators=n_est).fit(panel[panel.sim_seed.isin(train_s + val_s)])
    joblib.dump(final, out / "lgbm_forecaster.joblib")
    te.to_parquet(out / "predictions_test.parquet")
    for k, r in reliab.items():
        r.to_csv(out / f"reliability_{k}.csv", index=False)
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(4.2, 4))
        ax.plot([0, 1], [0, 1], "k--", lw=.8)
        for k, r in reliab.items():
            ax.plot(r.mean_p, r.obs, "o-", ms=3, label=k)
        ax.set_xlabel("predicted P(overflow)"); ax.set_ylabel("observed frequency"); ax.legend(fontsize=7); ax.set_title("Overflow reliability (synthetic test seeds)", fontsize=8)
        fig.tight_layout(); fig.savefig(out / "plots" / "overflow_reliability.png", dpi=120); plt.close(fig)
        s0 = te[te.sim_seed == test_s[0]]
        pid = s0.point_id.iloc[0]
        g = s0[s0.point_id == pid].sort_values("day")
        fig, ax = plt.subplots(figsize=(7, 3))
        ax.plot(g.day, g.y, "k-", lw=1, label="actual (synthetic)")
        ax.plot(g.day, g.lgbm_mean, "-", label="LightGBM")
        ax.fill_between(g.day, g["lgbm_q0.1"], g["lgbm_q0.9"], alpha=.2, label="q10-q90")
        ax.set_title(f"Next-day generation, {pid}", fontsize=8); ax.legend(fontsize=7)
        fig.tight_layout(); fig.savefig(out / "plots" / "example_forecast.png", dpi=120); plt.close(fig)
    except Exception as ex:
        print("plots skipped:", ex)

    metrics["external_edinburgh"] = edinburgh_check(Path("data/raw/edinburgh/aggregated_bin_data.csv"), Path("data/cache/chronos" if not a.smoke else "data_smoke/cache/chronos"),
                                                    use_chronos, n_est)
    (out / "metrics.json").write_text(json.dumps(metrics, indent=1))
    print("forecast: wrote", out / "metrics.json")
    print(json.dumps(metrics["point_forecasts"], indent=0)[:600])


if __name__ == "__main__":
    main()
