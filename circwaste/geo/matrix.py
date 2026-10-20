"""Travel-time (s) and distance (m) matrices between depot and points via road-graph shortest paths, cached to parquet
keyed by a hash of the inputs. Facility legs outside the study graph use haversine x detour factor / speed (assumptions.yaml)."""
from __future__ import annotations

import hashlib
from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd

CACHE = Path("data/cache")


def input_hash(nodes: list[int], graph_edges: int) -> str:
    h = hashlib.sha1(",".join(map(str, nodes)).encode() + str(graph_edges).encode())
    return h.hexdigest()[:12]


def od_matrices(G: nx.MultiDiGraph, nodes: list[int], tag: str = "main") -> tuple[np.ndarray, np.ndarray]:
    """Return (time_s, dist_m) for every ordered pair of `nodes` (graph node ids). Unreachable pairs get a large value."""
    key = input_hash(nodes, G.number_of_edges())
    f = CACHE / f"matrix_{tag}_{key}.parquet"
    n = len(nodes)
    if f.exists():
        d = pd.read_parquet(f)
        return d[[f"t{j}" for j in range(n)]].to_numpy(), d[[f"d{j}" for j in range(n)]].to_numpy()
    Gs = nx.DiGraph()
    for u, v, data in G.edges(data=True):  # keep the fastest parallel edge
        t, l = data.get("travel_time", 1e9), data.get("length", 1e9)
        if not Gs.has_edge(u, v) or t < Gs[u][v]["t"]:
            Gs.add_edge(u, v, t=t, l=l)
    T = np.full((n, n), 1e7)
    D = np.full((n, n), 1e7)
    for i, s in enumerate(nodes):
        dist_t = nx.single_source_dijkstra_path_length(Gs, s, weight="t")
        # distance along the fastest path
        paths = nx.single_source_dijkstra_path(Gs, s, weight="t")
        for j, tn in enumerate(nodes):
            if tn in dist_t:
                T[i, j] = dist_t[tn]
                p = paths[tn]
                D[i, j] = sum(Gs[a][b]["l"] for a, b in zip(p[:-1], p[1:]))
    out = pd.DataFrame({**{f"t{j}": T[:, j] for j in range(n)}, **{f"d{j}": D[:, j] for j in range(n)}})
    CACHE.mkdir(parents=True, exist_ok=True)
    out.to_parquet(f)
    return T, D


def facility_leg(lat1: float, lon1: float, lat2: float, lon2: float, detour: float, speed_kph: float) -> tuple[float, float]:
    """(time_s, dist_m) for a leg outside the study graph."""
    from circwaste.geo.facilities import haversine_km
    km = float(haversine_km(lat1, lon1, lat2, lon2)) * detour
    return km / speed_kph * 3600.0, km * 1000.0
