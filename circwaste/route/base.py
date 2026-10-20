"""Router contract shared by the OR-Tools and PyVRP backends.

Instance: depot = matrix index 0, point i = matrix index i + 1 (so routes hold 0-based point indices). Costs are INR: arc cost = km x cost_per_km,
prizes are INR. OR-Tools and PyVRP need integers, so both are scaled by the same factor (SCALE = 100, i.e. paise) before solving.
Every point is optional. Objective (minimised, INR) = arc cost + fixed trip cost of used vehicles + prize of every point NOT served.
Vehicles are trip slots: a compactor making two trips a day is two vehicles with its capacity each (docs/DECISIONS.md D10).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from circwaste.models import Vehicle

SCALE = 100


@dataclass
class RouteResult:
    routes: list[list[int]]            # per used vehicle, 0-based point indices in visiting order
    vehicle_ids: list[str]             # vehicle of each route
    dropped: list[int]                 # 0-based indices of points not visited
    distance_km: list[float]           # per route, depot -> ... -> depot
    time_s: list[float]                # per route travel time
    load_kg: list[float]
    routing_cost_inr: float            # arc cost + fixed cost of used vehicles
    dropped_prize_inr: float
    objective_inr: float
    backend: str
    runtime_s: float = 0.0
    status: str = "ok"
    extra: dict = field(default_factory=dict)


def evaluate(routes: list[list[int]], vehicle_ids: list[str], prizes: np.ndarray, demands: np.ndarray, dist_m: np.ndarray, time_s: np.ndarray,
             cost_per_km: float, fixed_cost: float, backend: str, runtime_s: float = 0.0, status: str = "ok") -> RouteResult:
    """Score routes identically for every backend (so objectives are comparable)."""
    n = len(prizes)
    routes = [r for r in routes if r]
    vehicle_ids = vehicle_ids[: len(routes)]
    dkm, ts, load = [], [], []
    for r in routes:
        seq = [0] + [i + 1 for i in r] + [0]
        dkm.append(float(sum(dist_m[a, b] for a, b in zip(seq[:-1], seq[1:])) / 1000.0))
        ts.append(float(sum(time_s[a, b] for a, b in zip(seq[:-1], seq[1:]))))
        load.append(float(sum(demands[i] for i in r)))
    served = {i for r in routes for i in r}
    dropped = [i for i in range(n) if i not in served]
    rc = sum(dkm) * cost_per_km + fixed_cost * len(routes)
    dp = float(sum(prizes[i] for i in dropped))
    return RouteResult(routes, vehicle_ids, dropped, dkm, ts, load, rc, dp, rc + dp, backend, runtime_s, status)


def common_cost_per_km(vehicles: list[Vehicle]) -> float:
    avail = [v for v in vehicles if v.available]
    costs = {v.cost_per_km for v in avail}
    if len(costs) > 1:
        raise ValueError("backends assume one cost_per_km for all vehicles")
    return avail[0].cost_per_km if avail else 0.0
