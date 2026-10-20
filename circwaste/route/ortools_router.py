"""OR-Tools backend: capacitated VRP where every point is optional (AddDisjunction with penalty = integer-scaled prize), guided local search.

API checked on the installed ortools 9.15: pywrapcp.RoutingIndexManager / RoutingModel, AddDisjunction(indices, penalty),
SetFixedCostOfAllVehicles, FirstSolutionStrategy.PATH_CHEAPEST_ARC, LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH,
search_parameters.time_limit / solution_limit.
"""
from __future__ import annotations

import time

import numpy as np
from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from circwaste.models import Vehicle

from .base import SCALE, RouteResult, common_cost_per_km, evaluate


def solve(prizes: np.ndarray, demands: np.ndarray, vehicles: list[Vehicle], dist_m: np.ndarray, time_s: np.ndarray, time_limit_s: float = 3.0,
          fixed_cost: float = 0.0, solution_limit: int | None = None, **_) -> RouteResult:
    t0 = time.time()
    vs = [v for v in vehicles if v.available]
    n = len(prizes)
    cpk = common_cost_per_km(vehicles)
    if not vs or n == 0:
        return evaluate([], [], prizes, demands, dist_m, time_s, cpk, fixed_cost, "ortools", 0.0, "no_vehicles")
    arc = np.rint(dist_m / 1000.0 * cpk * SCALE).astype(np.int64)
    pen = np.rint(np.asarray(prizes) * SCALE).astype(np.int64)
    dem = np.concatenate([[0], np.ceil(np.asarray(demands)).astype(np.int64)])
    mgr = pywrapcp.RoutingIndexManager(n + 1, len(vs), 0)
    routing = pywrapcp.RoutingModel(mgr)
    cb = routing.RegisterTransitCallback(lambda i, j: int(arc[mgr.IndexToNode(i), mgr.IndexToNode(j)]))
    routing.SetArcCostEvaluatorOfAllVehicles(cb)
    routing.SetFixedCostOfAllVehicles(int(round(fixed_cost * SCALE)))
    dcb = routing.RegisterUnaryTransitCallback(lambda i: int(dem[mgr.IndexToNode(i)]))
    routing.AddDimensionWithVehicleCapacity(dcb, 0, [int(np.floor(v.capacity_kg)) for v in vs], True, "load")
    for i in range(n):
        routing.AddDisjunction([mgr.NodeToIndex(i + 1)], int(pen[i]))
    sp = pywrapcp.DefaultRoutingSearchParameters()
    sp.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    sp.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    sp.time_limit.FromMilliseconds(int(time_limit_s * 1000))
    if solution_limit:
        sp.solution_limit = int(solution_limit)
    sol = routing.SolveWithParameters(sp)
    if sol is None:
        return evaluate([], [], prizes, demands, dist_m, time_s, cpk, fixed_cost, "ortools", time.time() - t0, f"no_solution:{routing.status()}")
    routes, vids = [], []
    for k, v in enumerate(vs):
        idx, seq = routing.Start(k), []
        while not routing.IsEnd(idx):
            node = mgr.IndexToNode(idx)
            if node:
                seq.append(node - 1)
            idx = sol.Value(routing.NextVar(idx))
        if seq:
            routes.append(seq)
            vids.append(v.id)
    return evaluate(routes, vids, prizes, demands, dist_m, time_s, cpk, fixed_cost, "ortools", time.time() - t0, f"status:{routing.status()}")
