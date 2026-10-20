"""Study area for the closed loop: collection points, depot, travel-time / distance matrices on the road graph, and the facilities the
flow model uses. Matrices come from circwaste.geo.matrix (cached to parquet keyed by a hash of the inputs).

Matrix index 0 is the depot, index i+1 is points.iloc[i]. Facilities lie outside the study graph, so their legs use haversine x detour /
speed (docs/DECISIONS.md D7); each facility's leg is measured from the depot.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import osmnx as ox
import pandas as pd

from circwaste.config import load_assumptions, val
from circwaste.geo import wards as W
from circwaste.geo.facilities import haversine_km
from circwaste.geo.matrix import od_matrices


@dataclass
class Study:
    points: pd.DataFrame        # point_id, ward, node, lat, lon, weight_area_m2 (index = matrix index - 1)
    depot: dict                 # node, lat, lon
    time_s: np.ndarray          # (n+1, n+1) travel time, depot first
    dist_m: np.ndarray          # (n+1, n+1) distance along the fastest path
    facilities: pd.DataFrame    # selected facilities with capacity_kg_day (inf = unbounded), dist_km, time_s from the depot
    wards: object               # GeoDataFrame of ward polygons


def depot_node(G, wards) -> dict:
    c = wards.geometry.union_all().centroid
    node = int(ox.distance.nearest_nodes(G, c.x, c.y))
    return {"node": node, "lat": float(G.nodes[node]["y"]), "lon": float(G.nodes[node]["x"])}


def snap_to_main_network(G, pts: pd.DataFrame) -> pd.DataFrame:
    """Points on road fragments outside the largest strongly connected component are unreachable by trucks: move them to the nearest node
    of that component (their sim catchment weights are unchanged)."""
    import networkx as nx

    main = max(nx.strongly_connected_components(G), key=len)
    out = pts.copy()
    bad = ~out.node.astype(int).isin(main)
    if bad.any():
        ids = np.array(sorted(main))
        xy = np.array([[G.nodes[n]["x"], G.nodes[n]["y"]] for n in ids])
        for i in out.index[bad]:
            out.loc[i, "node"] = int(ids[np.argmin((xy[:, 0] - out.lon[i]) ** 2 + (xy[:, 1] - out.lat[i]) ** 2)])
    out["node"] = out.node.astype(int)
    return out


def select_facilities(depot: dict, cfg: dict, path: str = "data/geo/facilities.csv") -> pd.DataFrame:
    """Nearest `facilities.max_per_kind` facilities of each kind within the study radius. Capacity = listed capacity x study_area_share, else the
    per-kind default (assumptions.yaml, TODO-SOURCE placeholders); landfill is unbounded (inf)."""
    f = pd.read_csv(path)
    radius = float(W.load_study()["facility_radius_km"])
    f["dist_air_km"] = haversine_km(depot["lat"], depot["lon"], f.lat.to_numpy(), f.lon.to_numpy())
    f = f[f.dist_air_km <= radius]
    share = float(val(cfg, "facilities.study_area_share"))
    defaults = val(cfg, "facilities.default_capacity_kg_day")
    detour, speed = float(val(cfg, "logistics.facility_detour_factor")), float(val(cfg, "logistics.facility_speed_kph"))
    keep = []
    for kind, g in f.groupby("kind"):
        keep.append(g.sort_values("dist_air_km").head(int(val(cfg, "facilities.max_per_kind"))))
    f = pd.concat(keep, ignore_index=True)

    def cap(r) -> float:
        if pd.notna(r.capacity_kg_day):
            return float(r.capacity_kg_day) * share
        d = defaults.get(r.kind)
        return float("inf") if d is None else float(d)

    f["capacity_kg_day"] = f.apply(cap, axis=1)
    f["dist_km"] = f.dist_air_km * detour
    f["time_s"] = f.dist_km / speed * 3600.0
    return f.drop(columns=["accepts", "node"], errors="ignore").reset_index(drop=True)


def load_study(root: str | Path = ".") -> Study:
    root = Path(root)
    cfg = load_assumptions(root / "configs/assumptions.yaml")
    st = W.load_study(str(root / "configs/study.yaml"))
    wards = W.ward_polygons(st)
    G = W.road_graph(wards)
    pts = snap_to_main_network(G, pd.read_parquet(root / "data/sim/points.parquet"))
    dep = depot_node(G, wards)
    T, D = od_matrices(G, [dep["node"]] + pts.node.astype(int).tolist(), tag="study")
    return Study(pts.reset_index(drop=True), dep, T, D, select_facilities(dep, cfg, str(root / "data/geo/facilities.csv")), wards)
