"""PyVRP backend: the same instance as a prize-collecting VRP (clients with prize=..., required=False), hybrid genetic search.

API checked on the installed pyvrp 0.14.1: Model.add_location / add_depot / add_client(delivery=, prize=, required=) / add_vehicle_type(num_available, capacity,
start_depot, end_depot, fixed_cost, unit_distance_cost) / add_edge(frm, to, distance, duration) / solve(stop, seed, display),
pyvrp.stop.MaxIterations / MaxRuntime / MultipleCriteria; Route.schedule() yields activities (is_client(); idx = 0-based client index), Route.vehicle_type().
"""
from __future__ import annotations

import time

import numpy as np
from pyvrp import Model
from pyvrp.stop import MaxIterations, MaxRuntime, MultipleCriteria

from circwaste.models import Vehicle

from .base import SCALE, RouteResult, common_cost_per_km, evaluate


def solve(prizes: np.ndarray, demands: np.ndarray, vehicles: list[Vehicle], dist_m: np.ndarray, time_s: np.ndarray, time_limit_s: float = 5.0,
          fixed_cost: float = 0.0, max_iterations: int | None = None, seed: int = 0, **_) -> RouteResult:
    t0 = time.time()
    vs = [v for v in vehicles if v.available]
    n = len(prizes)
    cpk = common_cost_per_km(vehicles)
    if not vs or n == 0:
        return evaluate([], [], prizes, demands, dist_m, time_s, cpk, fixed_cost, "pyvrp", 0.0, "no_vehicles")
    arc = np.rint(dist_m / 1000.0 * cpk * SCALE).astype(np.int64)
    pen = np.rint(np.asarray(prizes) * SCALE).astype(np.int64)
    m = Model()
    locs = [m.add_location(float(i), 0.0) for i in range(n + 1)]
    depot = m.add_depot(locs[0])
    for i in range(n):
        m.add_client(locs[i + 1], delivery=[int(np.ceil(demands[i]))], prize=int(pen[i]), required=False)
    # group trip slots by capacity so equal slots share a vehicle type
    caps = sorted({int(np.floor(v.capacity_kg)) for v in vs})
    type_vehicles = []
    for c in caps:
        grp = [v for v in vs if int(np.floor(v.capacity_kg)) == c]
        m.add_vehicle_type(num_available=len(grp), capacity=[c], start_depot=depot, end_depot=depot, fixed_cost=int(round(fixed_cost * SCALE)), unit_distance_cost=1)
        type_vehicles.append(grp)
    for a in range(n + 1):
        for b in range(n + 1):
            if a != b:
                m.add_edge(locs[a], locs[b], distance=int(arc[a, b]), duration=int(round(time_s[a, b])))
    stops = [MaxRuntime(time_limit_s)] + ([MaxIterations(int(max_iterations))] if max_iterations else [])
    res = m.solve(stop=MultipleCriteria(stops) if len(stops) > 1 else stops[0], seed=seed, display=False)
    best = res.best
    routes, vids, used = [], [], [0] * len(type_vehicles)
    for r in best.routes():
        seq = [int(a.idx) for a in r.schedule() if a.is_client()]
        if not seq:
            continue
        t = r.vehicle_type()
        routes.append(seq)
        vids.append(type_vehicles[t][used[t]].id)
        used[t] += 1
    return evaluate(routes, vids, prizes, demands, dist_m, time_s, cpk, fixed_cost, "pyvrp", time.time() - t0,
                    "feasible" if res.is_feasible() else "infeasible")
