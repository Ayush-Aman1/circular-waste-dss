"""Collection-point placement on the road graph.

Mapped OSM waste points are used first (snapped to graph nodes); remaining points are sampled from graph nodes weighted by the
building area closest to each node, with a minimum spacing. Each point's catchment weight = total building area nearer to it than
to any other point. Deterministic for a given seed.
"""
from __future__ import annotations

import geopandas as gpd
import numpy as np
import osmnx as ox
import pandas as pd


def place_points(G, wards: gpd.GeoDataFrame, buildings: gpd.GeoDataFrame, waste_pts: gpd.GeoDataFrame, n_per_ward: int,
                 seed: int = 0, min_spacing_m: float = 100.0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    nodes = ox.graph_to_gdfs(G, edges=False)[["x", "y"]]
    nodes_m = gpd.GeoSeries(gpd.points_from_xy(nodes.x, nodes.y), index=nodes.index, crs=4326).to_crs(32643)
    nx_, ny_ = nodes_m.x.to_numpy(), nodes_m.y.to_numpy()
    node_ids = nodes.index.to_numpy()
    cent = buildings.to_crs(32643).geometry.centroid
    b_x, b_y = cent.x.to_numpy(), cent.y.to_numpy()
    b_area = buildings["area_m2"].to_numpy()
    wards_m = wards.to_crs(32643)
    rows = []
    for w in wards_m.itertuples():
        in_w_nodes = np.array([w.geometry.contains(p) for p in nodes_m.geometry])
        in_w_b = np.array([w.geometry.contains(p) for p in cent])
        cand = np.where(in_w_nodes)[0]
        if len(cand) == 0:
            continue
        # building area attributed to the nearest graph node
        wt = np.zeros(len(node_ids))
        for bx, by, ba in zip(b_x[in_w_b], b_y[in_w_b], b_area[in_w_b]):
            j = cand[np.argmin((nx_[cand] - bx) ** 2 + (ny_[cand] - by) ** 2)]
            wt[j] += ba
        chosen: list[int] = []
        # 1) mapped OSM waste points inside the ward
        if len(waste_pts):
            wp = waste_pts.to_crs(32643)
            for p in wp.geometry:
                if w.geometry.contains(p):
                    j = cand[np.argmin((nx_[cand] - p.x) ** 2 + (ny_[cand] - p.y) ** 2)]
                    if j not in chosen and len(chosen) < n_per_ward:
                        chosen.append(int(j))
        n_mapped = len(chosen)
        # 2) building-area weighted sampling with minimum spacing
        prob = wt[cand] + 1e-6
        prob = prob / prob.sum()
        order = rng.choice(cand, size=len(cand), replace=False, p=prob)
        for spacing in (min_spacing_m, min_spacing_m / 2, 0.0):
            for j in order:
                if len(chosen) >= n_per_ward:
                    break
                if j in chosen:
                    continue
                if all((nx_[j] - nx_[k]) ** 2 + (ny_[j] - ny_[k]) ** 2 >= spacing ** 2 for k in chosen):
                    chosen.append(int(j))
            if len(chosen) >= n_per_ward:
                break
        ch = np.array(chosen)
        # catchment weight: building area nearest to each chosen point
        catch = np.zeros(len(ch))
        for bx, by, ba in zip(b_x[in_w_b], b_y[in_w_b], b_area[in_w_b]):
            catch[np.argmin((nx_[ch] - bx) ** 2 + (ny_[ch] - by) ** 2)] += ba
        catch = np.where(catch > 0, catch, catch[catch > 0].min() if (catch > 0).any() else 1.0)
        for k, j in enumerate(ch):
            rows.append({"point_id": f"{w.ward}_{k:03d}", "ward": w.ward, "node": int(node_ids[j]), "lon": float(nodes.x.iloc[j]), "lat": float(nodes.y.iloc[j]),
                         "weight_area_m2": float(catch[k]), "mapped_in_osm": bool(k < n_mapped)})
    return pd.DataFrame(rows)
