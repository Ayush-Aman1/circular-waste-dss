"""Collect training outputs -> artifacts/MANIFEST.json + artifacts/TRAINING_REPORT.md (tables generated from metrics files only).
    python -m circwaste.artifacts.collect [--smoke]"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import pandas as pd


def sha(paths: list[Path]) -> str:
    h = hashlib.sha256()
    for p in sorted(paths):
        h.update(p.read_bytes())
    return h.hexdigest()[:16]


def commit() -> str:
    r = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True)
    return r.stdout.strip() or "uncommitted"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    a = ap.parse_args()
    art = Path("artifacts_smoke" if a.smoke else "artifacts")
    data = Path("data_smoke" if a.smoke else "data")
    date, git = pd.Timestamp.now().strftime("%Y-%m-%d"), commit()
    items, md = [], ["# Circular Waste DSS - training report", "", "**All bin-level data in this report is SYNTHETIC simulation data** (calibrated on BBMP/CPCB/World Bank figures "
                                                           "and Edinburgh real sensor shape). Only the Edinburgh external check uses real sensor data.", "",
                     f"Generated {date} from metrics files only (git {git}).", ""]
    hist = sorted((data / "sim").glob("history_seed*.parquet"))
    dh = sha(hist) if hist else "none"
    meta_f = data / "sim" / "history_meta.json"
    if meta_f.exists():
        m = json.loads(meta_f.read_text())
        md += ["## Synthetic history", "", f"seeds={m['seeds']}, days={m['days']}, collection points={m['points']}; ward kg/day: " + json.dumps({k: round(v, 1) for k, v in m['ward_daily_kg'].items()}), "",
               "| seed | rows | mean generated kg/point-day | share of point-days with overflow (baseline 2-day schedule) |", "|---|---|---|---|"]
        md += [f"| {s['seed']} | {s['rows']} | {s['mean_generated_kg_point_day']:.2f} | {s['overflow_share_point_days']:.3f} |" for s in m["per_seed"]]
        md.append("")
        items.append({"path": str(meta_f), "kind": "synthetic history", "synthetic": True, "data_hash": dh, "git_commit": git, "date": date})
    fn = art / "sim" / "fill_noise.json"
    if fn.exists():
        p = json.loads(fn.read_text())
        md += ["## Fill-noise calibration (REAL Edinburgh sensor data)", "", f"bins={p['n_bins']}, intervals={p['n_intervals']}, lognormal sigma={p['lognormal_sigma']}, AR(1)={p['ar1_log_rate']}, "
               f"weekday multipliers (Mon..Sun)={p['weekday_multipliers_mon_to_sun']}, censored share={p['share_censored_fill_ge_99']}", "",
               "Caveats: " + "; ".join(p["caveats"]), ""]
        items.append({"path": str(fn), "kind": "calibration", "synthetic": False, "metrics": {k: p[k] for k in ("lognormal_sigma", "ar1_log_rate")}, "data_hash": dh, "git_commit": git, "date": date})
    mf = art / "forecast" / "metrics.json"
    if mf.exists():
        f = json.loads(mf.read_text())
        md += ["## Forecasting (out-of-time rolling origins on held-out synthetic seeds)", "", f"seeds={f['seeds']}, origins={f['origins']}, target: {f['target']}", "",
               "| model | n | MAE | RMSE | MASE |", "|---|---|---|---|---|"]
        md += [f"| {r['model']} | {r['n']} | {r['mae']:.3f} | {r['rmse']:.3f} | {r['mase']:.3f} |" for r in f["point_forecasts"]]
        md += ["", "| quantile model | pinball | coverage of q0.5 | q0.8 | q0.95 |", "|---|---|---|---|---|"]
        for k, v in f["quantile_forecasts"].items():
            c = v["coverage"]
            md.append(f"| {k} | {v['pinball']:.3f} | {c['q0.5']:.3f} | {c['q0.8']:.3f} | {c['q0.95']:.3f} |")
        ov = f["overflow_risk"]
        md += ["", f"### Overflow risk - event: {ov['event']}; test event rate {ov['event_rate_test']:.3f}", "", "| model | Brier raw | Brier recalibrated (isotonic, val-fit) | Brier climatology |", "|---|---|---|---|"]
        for k, v in ov["models"].items():
            md.append(f"| {k} | {v.get('brier_raw', v.get('brier', float('nan'))):.4f} | {v.get('brier_recalibrated_isotonic_val_fit', float('nan')):.4f} | {v.get('brier_climatology', float('nan')):.4f} |")
        rv = f["recovery_value"]
        md += ["", f"### Recovery value: MAE {rv['mae_inr']:.2f} INR vs mean true {rv['mean_true_inr']:.2f} INR (n={rv['n']}). {rv['note']}", ""]
        ed = f["external_edinburgh"]
        if ed.get("status") == "ok":
            md += ["### External check on REAL Edinburgh data", "", f"{ed['source']}; streets={ed['streets']}; train days {ed['train_days']}, test days {ed['test_days']}, n={ed['n_test_rows']}", "",
                   "| model | MAE | RMSE | MASE |", "|---|---|---|---|"] + [f"| {r['model']} | {r['mae']:.2f} | {r['rmse']:.2f} | {r['mase']:.3f} |" for r in ed["models"]]
            for k in ("lgbm_quantiles", "chronos2_quantiles"):
                if k in ed:
                    md.append(f"\n{k}: pinball {ed[k]['pinball']:.2f}, coverage q0.5/q0.8/q0.95 = {ed[k]['coverage']['q0.5']:.2f}/{ed[k]['coverage']['q0.8']:.2f}/{ed[k]['coverage']['q0.95']:.2f}")
            md.append("")
        items.append({"path": str(mf), "kind": "forecast metrics", "synthetic": True, "data_hash": dh, "git_commit": git, "date": date,
                      "models": [str(x) for x in (art / "forecast").glob("*.joblib")]})
    src = data / "SOURCES.csv"
    if src.exists():
        s = pd.read_csv(src)
        md += ["## Data sources (data/SOURCES.csv)", "", "| name | licence | retrieved |", "|---|---|---|"] + [f"| {r['name']} | {r['licence']} | {r['retrieved_at']} |" for _, r in s.iterrows()] + [""]
    todo = Path("HUMAN_TASKS.md")
    if todo.exists():
        md += ["Open human tasks (TODO-SOURCE calibration values): see HUMAN_TASKS.md", ""]
    art.mkdir(exist_ok=True)
    (art / "MANIFEST.json").write_text(json.dumps({"generated": date, "synthetic": True, "items": items}, indent=1))
    (art / "TRAINING_REPORT.md").write_text("\n".join(md) + "\n")
    print(f"collect: {len(items)} manifest items -> {art}/")


if __name__ == "__main__":
    main()
