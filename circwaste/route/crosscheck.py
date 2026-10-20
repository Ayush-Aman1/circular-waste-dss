"""Cross-check the two routers on 20 random instances drawn from the study road network (guide P4).
    python -m circwaste.route.crosscheck [--n 20] [--points 25]  ->  experiments/results/router_crosscheck.csv (+ .json summary)
Instances: random subset of collection points, random demands (kg) and prizes (INR), 2-3 trip slots; both solvers are scored by the same
function (route cost + prizes of dropped points). Synthetic instances (the demands are synthetic bin contents)."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from circwaste.geo.world import load_study
from circwaste.models import Vehicle
from circwaste.route import BACKENDS


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--points", type=int, default=25)
    a = ap.parse_args()
    lc = yaml.safe_load(open("configs/loop.yaml"))["router"]
    st = load_study()
    rng = np.random.default_rng(0)
    rows = []
    for k in range(a.n):
        sub = np.sort(rng.choice(len(st.points), size=a.points, replace=False))
        sel = np.concatenate([[0], sub + 1])
        d, t = st.dist_m[np.ix_(sel, sel)], st.time_s[np.ix_(sel, sel)]
        dem = rng.uniform(100, 450, size=a.points)
        prz = rng.uniform(20, 600, size=a.points)
        veh = [Vehicle(id=f"v{j}", capacity_kg=float(rng.choice([1500, 2000, 3000])), cost_per_km=25.0) for j in range(int(rng.integers(2, 4)))]
        rs = {b: BACKENDS[b](prz, dem, veh, d, t, fixed_cost=100.0, seed=k, **lc[b]) for b in BACKENDS}
        o, p = rs["ortools"], rs["pyvrp"]
        rows.append({"instance": k, "points": a.points, "vehicles": len(veh), "ortools_objective_inr": o.objective_inr, "pyvrp_objective_inr": p.objective_inr,
                     "rel_gap": (p.objective_inr - o.objective_inr) / o.objective_inr, "ortools_s": o.runtime_s, "pyvrp_s": p.runtime_s,
                     "ortools_served": a.points - len(o.dropped), "pyvrp_served": a.points - len(p.dropped), "synthetic": True})
    df = pd.DataFrame(rows)
    out = Path("experiments/results")
    out.mkdir(parents=True, exist_ok=True)
    df.to_csv(out / "router_crosscheck.csv", index=False)
    summ = {"synthetic": True, "instances": a.n, "points_per_instance": a.points, "mean_rel_gap_pyvrp_vs_ortools": float(df.rel_gap.mean()),
            "max_abs_rel_gap": float(df.rel_gap.abs().max()), "mean_ortools_s": float(df.ortools_s.mean()), "mean_pyvrp_s": float(df.pyvrp_s.mean()),
            "router_settings": lc, "note": "rel_gap = (PyVRP objective - OR-Tools objective) / OR-Tools objective; negative = PyVRP better"}
    (out / "router_crosscheck.json").write_text(json.dumps(summ, indent=1))
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    main()
