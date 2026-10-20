"""Precompute the grid of common what-if scenarios so the demo responds instantly.
    python -m circwaste.scenario.precompute [--workers 7] [--smoke]    (resumable: cached scenarios are skipped)"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed

from .levers import Levers
from .whatif import load_loop_cfg, run_scenario, scenario_key, load_cached

POLICIES = ["recovery_aware", "overflow_only"]
SWEEPS = {
    "generation_pct": [-20.0, -10.0, 10.0, 20.0],
    "segregation_rate": [0.3, 0.7, 0.9],
    "vehicles_unavailable": [1, 2],
    "trips_per_vehicle": [2, 4],
    "price_pct": [-30.0, 30.0],
    "festival_multiplier": [2.0],
}
CAPACITY_STOPS = [-50.0, 50.0, 100.0, 150.0, 200.0]      # applied to wet_plant, biomethanation and dwcc together


def grid() -> list[Levers]:
    out = []
    for pol in POLICIES:
        out.append(Levers(policy=pol))
        for field_, vals in SWEEPS.items():
            out += [Levers(policy=pol, **{field_: v}) for v in vals]
        out += [Levers(policy=pol, capacity_pct={k: c for k in ("wet_plant", "biomethanation", "dwcc")}) for c in CAPACITY_STOPS]
    out += [Levers(policy="threshold"), Levers(policy="value_only")]
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=3, help="seed processes per scenario")
    ap.add_argument("--parallel", type=int, default=2, help="scenarios computed at the same time")
    ap.add_argument("--smoke", action="store_true")
    a = ap.parse_args()
    lcfg = load_loop_cfg()
    todo = [lv for lv in grid() if load_cached(scenario_key(lv, lcfg["seeds"]["whatif"], lcfg["eval_days"], lcfg)) is None]
    print(f"{len(todo)} of {len(grid())} scenarios to compute", flush=True)
    todo = todo[: 2 if a.smoke else None]
    with ThreadPoolExecutor(max_workers=a.parallel) as ex:         # `parallel` scenarios at a time, each with `workers` seed processes
        futs = {ex.submit(run_scenario, lv, None, 4 if a.smoke else None, a.workers): lv for lv in todo}
        for i, f in enumerate(as_completed(futs), 1):
            lv, r = futs[f], f.result()
            print(f"[{i}/{len(todo)}] {lv.policy} {lv} -> net cost {r['summary']['mean']['net_cost_inr']:.0f}", flush=True)


if __name__ == "__main__":
    main()
