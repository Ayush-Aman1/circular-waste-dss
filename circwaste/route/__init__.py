"""Routers: solve(prizes, demands, vehicles, dist_m, time_s, ...) -> RouteResult. Backends: ortools (default), pyvrp."""
from __future__ import annotations

from . import ortools_router, pyvrp_router
from .base import RouteResult

BACKENDS = {"ortools": ortools_router.solve, "pyvrp": pyvrp_router.solve}


def solve(backend: str, *args, **kw) -> RouteResult:
    return BACKENDS[backend](*args, **kw)


__all__ = ["BACKENDS", "RouteResult", "solve"]
