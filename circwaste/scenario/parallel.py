"""Run many (policy, seed, levers) loop jobs in worker processes. Each worker loads the study, assumptions and forecaster once and caches
the policy-independent synthetic world per (seed, generation levers), so policies on one seed share identical generation (paired seeds)."""
from __future__ import annotations

import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict
from typing import Callable

import yaml

from .levers import Levers

_G: dict = {}


def init_worker() -> None:
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    from circwaste.config import load_assumptions
    from circwaste.forecast.live import LiveForecaster
    from circwaste.geo.world import load_study

    _G.update(study=load_study(), cfg=load_assumptions(), lcfg=yaml.safe_load(open(os.environ.get("CIRCWASTE_LOOP_CONFIG", "configs/loop.yaml"))),
              pcfg=yaml.safe_load(open("configs/policies.yaml")), fc=LiveForecaster(), exo={})


def run_job(job: dict) -> dict:
    """job: {policy, seed, levers (dict), label?, backend?, keep_detail?, eval_days?}. Returns {summary, days (records), detail, runtime_s}."""
    from .levers import apply_levers
    from .loop import make_exogenous, run_loop

    if not _G:
        init_worker()
    lv = Levers(**job.get("levers", {}))
    lv.policy = job["policy"]
    cfg0, lc = _G["cfg"], _G["lcfg"]
    n_eval = int(job.get("eval_days") or lc["eval_days"])
    key = (job["seed"], lv.generation_pct, lv.festival_multiplier, n_eval)
    if key not in _G["exo"]:
        if len(_G["exo"]) > 6:
            _G["exo"].clear()
        _G["exo"][key] = make_exogenous(_G["study"], apply_levers(cfg0, lv), job["seed"], int(lc["warmup_days"]) + n_eval)
    r = run_loop(job["policy"], job["seed"], _G["study"], cfg0, lc, _G["pcfg"], _G["fc"], levers=lv, exo=_G["exo"][key],
                 keep_detail=bool(job.get("keep_detail")), eval_days=n_eval, backend=job.get("backend"), label=job.get("label"))
    return {"job": job, "summary": r.summary, "days": r.days.to_dict("records"), "detail": r.detail, "runtime_s": r.runtime_s}


def run_jobs(jobs: list[dict], workers: int = 6, on_done: Callable[[int, int, dict], None] | None = None) -> list[dict]:
    """Execute jobs in parallel; results are returned in the order of `jobs`."""
    out: list[dict | None] = [None] * len(jobs)
    for var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "MKL_NUM_THREADS"):
        os.environ.setdefault(var, "1")                  # one BLAS thread per worker process (set before the workers import numpy)
    if workers <= 1:
        for i, j in enumerate(jobs):
            out[i] = run_job(j)
            if on_done:
                on_done(i + 1, len(jobs), out[i])
        return out  # type: ignore[return-value]
    with ProcessPoolExecutor(max_workers=workers, initializer=init_worker) as ex:
        futs = {ex.submit(run_job, j): i for i, j in enumerate(jobs)}
        for n, f in enumerate(as_completed(futs), 1):
            out[futs[f]] = f.result()
            if on_done:
                on_done(n, len(jobs), out[futs[f]])
    return out  # type: ignore[return-value]


def lever_dict(lv: Levers) -> dict:
    return asdict(lv)
