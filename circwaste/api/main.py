"""FastAPI backend (guide P8). Run: uvicorn circwaste.api.main:app --port 8000   (docs at /docs).
Endpoints: GET /health, /base, /policies, /cached, /experiments, /experiments/plots/{name};
POST /scenario -> job id (the scenario key; cached scenarios return status=done at once); GET /scenario/{id}; GET /day/{scenario}/{day}.
Scenario runs are async jobs with progress. Every payload built from bin-level data has synthetic=true."""
from __future__ import annotations

import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from pathlib import Path

import pandas as pd
import yaml
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from circwaste.api.schemas import NOTICE, JobStatus, ScenarioRequest
from circwaste.config import load_assumptions, val
from circwaste.geo.world import load_study
from circwaste.scenario.levers import Levers
from circwaste.scenario.whatif import list_cached, load_cached, load_loop_cfg, run_scenario, scenario_key

RESULTS = Path("experiments/results")
WORKERS = int(os.environ.get("CIRCWASTE_WORKERS", "3"))

app = FastAPI(title="Circular Waste DSS API", version="1.0",
              description="Decision-support backend for municipal waste collection (Bengaluru case, SYNTHETIC bin-level data). " + NOTICE)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

_pool = ThreadPoolExecutor(max_workers=1)
_jobs: dict[str, JobStatus] = {}
_lock = threading.Lock()


@lru_cache(maxsize=1)
def study():
    return load_study()


@lru_cache(maxsize=1)
def roads():
    from circwaste.geo import wards as W
    from circwaste.geo.paths import RoadPaths
    return RoadPaths(W.road_graph(study().wards))


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "synthetic": True, "notice": NOTICE}


@app.get("/base")
def base() -> dict:
    """Map layers: ward polygons, collection points, facilities, depot."""
    s = study()
    cfg = load_assumptions()
    pts = s.points
    return {
        "synthetic": True, "notice": NOTICE,
        "wards": json.loads(s.wards.to_json()),
        "depot": s.depot,
        "points": [{"id": r.point_id, "ward": r.ward, "lat": r.lat, "lon": r.lon} for r in pts.itertuples()],
        "facilities": [{"id": r.id, "kind": r.kind, "name": r.name, "lat": r.lat, "lon": r.lon,
                        "capacity_kg_day": None if r.capacity_kg_day == float("inf") else float(r.capacity_kg_day), "dist_km": float(r.dist_km)}
                       for r in s.facilities.itertuples()],
        "fleet": val(cfg, "costs.vehicle") | {"trips_per_vehicle_per_day": val(cfg, "fleet.trips_per_vehicle_per_day")},
        "defaults": {"segregation_rate": val(cfg, "segregation.rate"), "festival_multiplier": val(cfg, "generation.festival_multiplier"),
                     "overflow_cost_inr": val(cfg, "costs.overflow_cost_inr")},
        "attribution": "(c) OpenStreetMap contributors (ODbL); BBMP via OpenCity; World Bank What a Waste 2.0 (CC BY 4.0); Edinburgh bin sensors (OGL v3)",
    }


@app.get("/policies")
def policies() -> dict:
    p = yaml.safe_load(open("configs/policies.yaml"))["policies"]
    lc = load_loop_cfg()
    desc = {"threshold": "Tier A: collect if predicted fill >= threshold; OR-Tools CVRP on road travel times",
            "overflow_only": "prize = alpha x P(overflow) x overflow cost (style of the 2024 integrated selection-and-routing paper, arXiv 2409.13386); PyVRP prize-collecting VRP",
            "recovery_aware": "prize = alpha x P(overflow) x overflow cost + beta x predicted recovery value (this project's contribution); PyVRP prize-collecting VRP",
            "value_only": "prize = beta x predicted recovery value; PyVRP prize-collecting VRP"}
    return {"synthetic": True, "policies": [{"name": k, "description": desc[k], "router": v.get("router"), "alpha": v.get("alpha"), "beta": v.get("beta"),
                                              "threshold_fill": v.get("threshold_fill"), "source": v.get("source")} for k, v in p.items()],
            "eval_days": lc["eval_days"], "whatif_seeds": lc["seeds"]["whatif"]}


@app.get("/cached")
def cached() -> dict:
    """Precomputed what-if scenarios (instant answers)."""
    return {"synthetic": True, "scenarios": list_cached()}


def _run(job_id: str, req: ScenarioRequest, lv: Levers) -> None:
    st = _jobs[job_id]
    st.status = "running"
    try:
        def prog(i: int, n: int) -> None:
            st.progress = i / n
        res = run_scenario(lv, req.seeds, req.eval_days, workers=WORKERS, progress=prog)
        st.result, st.progress, st.status = _light(res), 1.0, "done"
    except Exception as e:  # noqa: BLE001
        st.status, st.error = "failed", repr(e)


def _light(res: dict) -> dict:
    """Result without the per-day detail (fetched via /day)."""
    return {k: v for k, v in res.items() if k != "detail"}


@app.post("/scenario", response_model=JobStatus)
def post_scenario(req: ScenarioRequest) -> JobStatus:
    """Start (or fetch) a what-if run. The job id is the scenario key, so identical requests share one result."""
    lv = Levers(**req.levers.model_dump())
    lc = load_loop_cfg()
    seeds = req.seeds or lc["seeds"]["whatif"]
    key = scenario_key(lv, seeds, req.eval_days or lc["eval_days"], lc)
    with _lock:
        if key in _jobs and _jobs[key].status in ("queued", "running", "done"):
            return _jobs[key]
        if (hit := load_cached(key)) is not None:
            _jobs[key] = JobStatus(id=key, status="done", progress=1.0, cached=True, result=_light(hit))
            return _jobs[key]
        _jobs[key] = JobStatus(id=key, status="queued")
        _pool.submit(_run, key, req, lv)
        return _jobs[key]


@app.get("/scenario/{job_id}", response_model=JobStatus)
def get_scenario(job_id: str) -> JobStatus:
    if job_id in _jobs:
        return _jobs[job_id]
    if (hit := load_cached(job_id)) is not None:
        _jobs[job_id] = JobStatus(id=job_id, status="done", progress=1.0, cached=True, result=_light(hit))
        return _jobs[job_id]
    raise HTTPException(404, "unknown scenario id")


@app.get("/day/{scenario}/{day}")
def get_day(scenario: str, day: int) -> dict:
    """One simulated day of the scenario's representative seed: routes as GeoJSON polylines along roads, bin states, flows. `day` = 0-based day of the evaluation window."""
    res = load_cached(scenario)
    if res is None:
        raise HTTPException(404, "scenario not computed yet")
    det = res["detail"]
    if not 0 <= day < len(det["days"]):
        raise HTTPException(404, f"day must be in 0..{len(det['days']) - 1}")
    d = det["days"][day]
    s = study()
    pt = s.points.set_index("point_id")
    ids = det["point_ids"]
    node = {p: int(pt.loc[p, "node"]) for p in ids}
    rd = roads()
    feats = []
    for k, r in enumerate(d["routes"]):
        coords = rd.route([s.depot["node"]] + [node[p] for p in r["points"]] + [s.depot["node"]])
        feats.append({"type": "Feature", "geometry": {"type": "LineString", "coordinates": coords},
                      "properties": {"vehicle": r["vehicle"], "trip": k, "distance_km": r["distance_km"], "load_kg": r["load_kg"], "stops": len(r["points"])}})
    over, vis, drop = set(d["overflow"]), set(d["visited"]), set(d["dropped_with_prize"])
    bins = [{"id": p, "lat": float(pt.loc[p, "lat"]), "lon": float(pt.loc[p, "lon"]), "ward": pt.loc[p, "ward"], "fill_kg": d["fill_kg"][i], "fill_end_kg": d["fill_end_kg"][i],
             "capacity_kg": det["capacity_kg"][i], "overflow_risk": d["overflow_risk"][i], "recovery_value_inr": d["recovery_value_inr"][i], "prize_inr": d["prize_inr"][i],
             "visited": p in vis, "dropped_with_prize": p in drop, "overflowed": p in over} for i, p in enumerate(ids)]
    return {"synthetic": True, "notice": NOTICE, "scenario": scenario, "day": day, "seed": res["representative_seed"], "levers": res["levers"], "routes": {"type": "FeatureCollection", "features": feats},
            "bins": bins, "flows": d["flows"], "n_days": len(det["days"])}


@app.get("/experiments")
def experiments() -> dict:
    """Experiment result tables (experiments/results/*.csv, written by experiments/run_experiments.py)."""
    def tab(name: str) -> list[dict] | None:
        f = RESULTS / name
        return pd.read_csv(f).to_dict("records") if f.exists() else None
    meta = json.loads((RESULTS / "meta.json").read_text()) if (RESULTS / "meta.json").exists() else None
    return {"synthetic": True, "notice": NOTICE, "meta": meta, "main": tab("main_table.csv"), "paired": tab("main_paired_tests.csv"), "ablation": tab("ablation_table.csv"),
            "sensitivity": tab("sensitivity_paired.csv"),
            "plots": [p.name for p in sorted(RESULTS.glob("*.png"))],
            "router_crosscheck": json.loads((RESULTS / "router_crosscheck.json").read_text()) if (RESULTS / "router_crosscheck.json").exists() else None}


@app.get("/experiments/plots/{name}")
def plot(name: str):
    f = RESULTS / Path(name).name
    if f.suffix != ".png" or not f.exists():
        raise HTTPException(404)
    return FileResponse(f)
