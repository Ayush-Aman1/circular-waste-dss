"""Road polylines for routes: fastest path (travel_time) between consecutive stops on the study road graph, drawn along edge geometries.
OSM data (c) OpenStreetMap contributors (ODbL)."""
from __future__ import annotations

import networkx as nx


class RoadPaths:
    def __init__(self, G):
        self.G = G
        self.D = nx.DiGraph()
        for u, v, k, data in G.edges(keys=True, data=True):
            t = data.get("travel_time", 1e9)
            if not self.D.has_edge(u, v) or t < self.D[u][v]["t"]:
                self.D.add_edge(u, v, t=t, geom=data.get("geometry"))
        self._cache: dict[tuple[int, int], list[list[float]]] = {}

    def leg(self, a: int, b: int) -> list[list[float]]:
        """[[lon, lat], ...] along the fastest path from graph node a to node b."""
        if a == b:
            return [[self.G.nodes[a]["x"], self.G.nodes[a]["y"]]]
        if (a, b) not in self._cache:
            path = nx.shortest_path(self.D, a, b, weight="t")
            pts: list[list[float]] = []
            for u, v in zip(path[:-1], path[1:]):
                g = self.D[u][v]["geom"]
                seg = [list(c) for c in g.coords] if g is not None else [[self.G.nodes[u]["x"], self.G.nodes[u]["y"]], [self.G.nodes[v]["x"], self.G.nodes[v]["y"]]]
                pts += seg if not pts else seg[1:]
            self._cache[(a, b)] = pts
        return self._cache[(a, b)]

    def route(self, nodes: list[int]) -> list[list[float]]:
        out: list[list[float]] = []
        for a, b in zip(nodes[:-1], nodes[1:]):
            leg = self.leg(a, b)
            out += leg if not out else leg[1:]
        return out
