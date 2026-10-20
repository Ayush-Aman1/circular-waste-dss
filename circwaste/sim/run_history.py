"""Place points (cached), build the world, generate multi-seed synthetic history -> data/sim/history_seed<k>.parquet.
    python -m circwaste.sim.run_history [--seeds 6] [--days 180] [--smoke]   (smoke -> data_smoke/, 1 ward subset, 1 seed, 30 days)"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from circwaste.config import load_assumptions, val
from circwaste.geo import wards as W
from circwaste.sim.generator import build_world, generate_history, load_noise
from circwaste.sim.placement import place_points


def get_points(smoke: bool, out: Path) -> pd.DataFrame:
    f = out / "points.parquet"
    if f.exists():
        return pd.read_parquet(f)
    cfg = load_assumptions()
    st = W.load_study()
    wards = W.ward_polygons(st, smoke)
    G = W.road_graph(wards, smoke)
    b = W.buildings(wards, smoke)
    wp = W.mapped_waste_points(wards, smoke)
    n = 12 if smoke else int(val(cfg, "bins.points_per_ward"))
    pts = place_points(G, wards, b, wp, n, seed=0)
    pts.to_parquet(f)
    return pts


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=6)
    ap.add_argument("--days", type=int, default=180)
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    out = Path(a.out or ("data_smoke/sim" if a.smoke else "data/sim"))
    out.mkdir(parents=True, exist_ok=True)
    seeds, days = (1, 30) if a.smoke else (a.seeds, a.days)
    cfg = load_assumptions()
    world = build_world(get_points(a.smoke, out), cfg, load_noise())
    summ = []
    for s in range(seeds):
        h = generate_history(world, s, days)
        h.to_parquet(out / f"history_seed{s}.parquet")
        summ.append({"seed": s, "rows": len(h), "mean_generated_kg_point_day": float(h.generated_kg.mean()),
                     "overflow_share_point_days": float((h.overflow_kg > 0).mean())})
    meta = {"synthetic": True, "seeds": seeds, "days": days, "points": int(len(world.points)), "ward_daily_kg": world.ward_daily_kg,
            "noise_source": "artifacts/sim/fill_noise.json (Edinburgh)", "per_seed": summ}
    (out / "history_meta.json").write_text(json.dumps(meta, indent=1))
    print("history:", json.dumps({k: meta[k] for k in ("seeds", "days", "points")}), "overflow share", [round(x["overflow_share_point_days"], 3) for x in summ])


if __name__ == "__main__":
    main()
