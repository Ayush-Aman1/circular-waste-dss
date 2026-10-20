"""Ward polygons (OSM via Nominatim) and the drivable road graph with speeds and travel times (cached GraphML)."""
from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import osmnx as ox
import yaml

ox.settings.cache_folder = "data/cache/osmnx"
ox.settings.timeout = 300
CACHE = Path("data/cache")
OVERPASS = ["https://overpass-api.de/api", "https://overpass.kumi.systems/api", "https://overpass.private.coffee/api"]


def _retry(fn, attempts: int = 8):
    """Public Overpass is often at capacity: rotate endpoints with exponential backoff."""
    import time

    last = None
    for i in range(attempts):
        ox.settings.overpass_url = OVERPASS[i % len(OVERPASS)]
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            if "InsufficientResponse" in type(e).__name__:
                raise
            last = e
            time.sleep(min(15 * 2 ** (i // 2), 180))
    raise RuntimeError(f"Overpass failed after {attempts} attempts: {last}")


def load_study(path: str = "configs/study.yaml") -> dict:
    return yaml.safe_load(Path(path).read_text())


def ward_polygons(cfg: dict, smoke: bool = False) -> gpd.GeoDataFrame:
    """One row per ward: id, geometry (EPSG:4326). Cached to data/cache/wards.geojson."""
    f = CACHE / ("wards_smoke.geojson" if smoke else "wards.geojson")
    if f.exists():
        return gpd.read_file(f)
    rows = []
    for w in cfg["wards"][: 1 if smoke else None]:
        g = ox.geocode_to_gdf(w["query"])
        rows.append({"ward": w["id"], "query": w["query"], "geometry": g.geometry.iloc[0]})
    gdf = gpd.GeoDataFrame(rows, crs="EPSG:4326")
    CACHE.mkdir(parents=True, exist_ok=True)
    gdf.to_file(f, driver="GeoJSON")
    return gdf


def road_graph(wards: gpd.GeoDataFrame, smoke: bool = False):
    """Drivable graph for the union of the ward polygons (+150 m buffer), with edge speeds (kph) and travel_time (s)."""
    f = CACHE / "graph.graphml"  # smoke reuses the full cache (ward subset is applied by the caller)
    if f.exists():
        return ox.load_graphml(f)
    union = wards.to_crs(32643).geometry.union_all().buffer(150)
    poly = gpd.GeoSeries([union], crs=32643).to_crs(4326).iloc[0]
    G = _retry(lambda: ox.graph_from_polygon(poly, network_type="drive", simplify=True))
    G = ox.routing.add_edge_speeds(G)
    G = ox.routing.add_edge_travel_times(G)
    CACHE.mkdir(parents=True, exist_ok=True)
    ox.save_graphml(G, f)
    return G


def buildings(wards: gpd.GeoDataFrame, smoke: bool = False) -> gpd.GeoDataFrame:
    """Building footprints (area in m2 in column area_m2), cached as parquet."""
    f = CACHE / "buildings.parquet"  # smoke reuses the full cache (ward subset is applied by the caller)
    if f.exists():
        return gpd.read_parquet(f)
    poly = wards.geometry.union_all()
    b = _retry(lambda: ox.features_from_polygon(poly, tags={"building": True}))
    b = b[b.geometry.geom_type.isin(["Polygon", "MultiPolygon"])][["geometry"]].copy()
    b["area_m2"] = b.to_crs(32643).area
    b = b.reset_index(drop=True)
    b.to_parquet(f)
    return b


def mapped_waste_points(wards: gpd.GeoDataFrame, smoke: bool = False) -> gpd.GeoDataFrame:
    """OSM-mapped waste / recycling points (amenity=waste_basket|waste_disposal|recycling|waste_transfer_station)."""
    f = CACHE / "waste_pts.parquet"  # smoke reuses the full cache (ward subset is applied by the caller)
    if f.exists():
        return gpd.read_parquet(f)
    poly = wards.geometry.union_all()
    try:
        g = _retry(lambda: ox.features_from_polygon(poly, tags={"amenity": ["waste_basket", "waste_disposal", "recycling", "waste_transfer_station"]}))
        g = g[["geometry"]].copy()
        g["geometry"] = g.geometry.representative_point()
        g = g.reset_index(drop=True)
    except Exception:  # osmnx raises InsufficientResponseError when nothing is mapped
        g = gpd.GeoDataFrame({"geometry": []}, geometry="geometry", crs=4326)
    g.to_parquet(f)
    return g
