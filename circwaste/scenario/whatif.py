"""What-if scenario engine (Tier C). run_scenario(levers, seeds) -> summary metrics (mean +- std over seeds) + per-day series + one representative
seed's per-day detail (routes, bin states, flows). Results are cached by a hash of (levers, seeds, loop settings) in experiments/whatif_cache/, and a grid of
common scenarios is precomputed (python -m circwaste.scenario.precompute) so the demo answers instantly. The engine never edits the loop: levers only
change a copy of the assumptions, the fleet, the flow capacities and the policy weights, and the same seeds are replayed (paired comparison).
ALL RESULTS ARE SYNTHETIC (field `synthetic`).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd
import yaml

from circwaste.models import MATERIALS

from .levers import Levers
from .parallel import lever_dict, run_jobs

CACHE = Path("experiments/whatif_cache")
SUMMARY_KEYS = ["overflow_events", "overflow_kg", "km", "vehicle_hours", "operating_cost_inr", "overflow_penalty_inr", "recovered_value_inr", "net_cost_inr", "generated_kg",
                "collected_kg", "recovered_kg", "landfill_kg", "recovery_rate", "landfill_diversion_rate", "facility_over_capacity_days", "recovered_kg_recycling",
                "recovered_kg_composting_biomethanation", "stops", "trips"]
SERIES_KEYS = ["generated_kg", "collected_kg", "overflow_events", "overflow_kg", "km", "routing_cost_inr", "recovered_value_inr", "landfill_kg", "stops", "trips",
               "stock_end_kg"] + [f"rec_{m}_kg" for m in MATERIALS]


def load_loop_cfg() -> dict:
    import os
    return yaml.safe_load(open(os.environ.get("CIRCWASTE_LOOP_CONFIG", "configs/loop.yaml")))


def scenario_key(lv: Levers, seeds: list[int], eval_days: int, lcfg: dict) -> str:
    return lv.key({"seeds": list(seeds), "eval_days": eval_days, "warmup_days": lcfg["warmup_days"], "router": lcfg["router"]})


def load_cached(key: str) -> dict | None:
    f = CACHE / f"{key}.json"
    return json.loads(f.read_text()) if f.exists() else None


def list_cached() -> list[dict]:
    out = []
    for f in sorted(CACHE.glob("*.json")):
        r = json.loads(f.read_text())
        out.append({"key": r["key"], "levers": r["levers"], "seeds": r["seeds"], "eval_days": r["eval_days"], "kpis": r["summary"]["mean"]})
    return out


def _round(o, nd: int = 2):
    if isinstance(o, float):
        return round(o, nd)
    if isinstance(o, dict):
        return {k: _round(v, nd) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_round(v, nd) for v in o]
    return o


def compact_detail(detail: list[dict], day0: int) -> dict:
    """Representative seed: points listed once, then per-day arrays (rounded) and routes by point id."""
    ids = detail[0]["point_ids"]
    days = []
    for d in detail:
        days.append(_round({"day": d["day"] - day0, "fill_kg": d["fill_kg"], "fill_end_kg": d["fill_end_kg"], "overflow_risk": d["overflow_risk"],
                            "recovery_value_inr": d["recovery_value_inr"], "prize_inr": d["prize_inr"], "visited": [ids[i] for i in d["visited"]],
                            "overflow": [ids[i] for i, o in enumerate(d["overflow"]) if o], "dropped_with_prize": [ids[i] for i in d["dropped_with_prize"]],
                            "routes": [{"vehicle": r["vehicle"], "points": [ids[i] for i in r["points"]], "distance_km": r["distance_km"], "load_kg": r["load_kg"]} for r in d["routes"]],
                            "flows": d["flows"]}))
    return {"point_ids": ids, "capacity_kg": _round(detail[0]["capacity_kg"]), "days": days}


def run_scenario(lv: Levers, seeds: list[int] | None = None, eval_days: int | None = None, workers: int = 3, force: bool = False,
                 progress: Callable[[int, int], None] | None = None) -> dict:
    lcfg = load_loop_cfg()
    seeds = list(seeds or lcfg["seeds"]["whatif"])
    n_eval = int(eval_days or lcfg["eval_days"])
    key = scenario_key(lv, seeds, n_eval, lcfg)
    if not force and (hit := load_cached(key)):
        hit["cached"] = True
        return hit
    jobs = [{"policy": lv.policy, "seed": s, "levers": lever_dict(lv), "keep_detail": i == 0, "eval_days": n_eval, "tags": {}} for i, s in enumerate(seeds)]
    res = run_jobs(jobs, workers=min(workers, len(jobs)), on_done=(lambda i, n, r: progress(i, n)) if progress else None)
    per_seed = pd.DataFrame([r["summary"] for r in res]).sort_values("seed")
    days = pd.DataFrame([d for r in res for d in r["days"]])
    series = days.groupby("day")[SERIES_KEYS].mean().reset_index()
    series["day"] = series.day - int(lcfg["warmup_days"])
    out = {"synthetic": True, "key": key, "cached": False, "levers": lever_dict(lv), "seeds": seeds, "eval_days": n_eval, "warmup_days": int(lcfg["warmup_days"]),
           "summary": {"mean": {k: float(per_seed[k].mean()) for k in SUMMARY_KEYS}, "std": {k: float(per_seed[k].std(ddof=1)) if len(per_seed) > 1 else 0.0 for k in SUMMARY_KEYS}},
           "per_seed": per_seed[["seed"] + SUMMARY_KEYS].to_dict("records"), "series": _round(series.to_dict("list"), 3),
           "representative_seed": seeds[0], "detail": compact_detail(res[0]["detail"], int(lcfg["warmup_days"])),
           "notice": "Synthetic simulation data: bin-level data is simulated from public statistics."}
    CACHE.mkdir(parents=True, exist_ok=True)
    (CACHE / f"{key}.json").write_text(json.dumps(out, separators=(",", ":")))
    return out
