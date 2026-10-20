"""Fetch + cache the geography: ward polygons, drivable graph (GraphML), buildings, OSM waste points, facilities.
    python -m circwaste.geo.build [--smoke]   (smoke = first ward only)"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import wards as W
from .facilities import capacities_from_plants_csv, facilities_frame, load_facilities, within_radius


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--out", default="data/geo")
    a = ap.parse_args()
    cfg = W.load_study()
    wards = W.ward_polygons(cfg, a.smoke)
    G = W.road_graph(wards, a.smoke)
    b = W.buildings(wards, a.smoke)
    wp = W.mapped_waste_points(wards, a.smoke)
    c = wards.to_crs(32643).geometry.union_all().centroid
    import geopandas as gpd
    c = gpd.GeoSeries([c], crs=32643).to_crs(4326).iloc[0]
    facs = within_radius(load_facilities(), c.y, c.x, cfg["facility_radius_km"])
    caps = capacities_from_plants_csv(facs)
    for f in facs:
        if f.id in caps:
            f.capacity_kg_day, f.source = caps[f.id][0], f.source + " | capacity: " + caps[f.id][1]
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    facilities_frame(facs).to_csv(out / ("facilities_smoke.csv" if a.smoke else "facilities.csv"), index=False)
    facs_geo = {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"id": f.id, "kind": f.kind, "name": f.name, "capacity_kg_day": f.capacity_kg_day},
                "geometry": {"type": "Point", "coordinates": [f.lon, f.lat]}} for f in facs]}
    (out / ("facilities_smoke.geojson" if a.smoke else "facilities.geojson")).write_text(json.dumps(facs_geo))
    print(f"geo: wards={len(wards)} graph nodes={G.number_of_nodes()} edges={G.number_of_edges()} buildings={len(b)} osm_waste_points={len(wp)} "
          f"facilities_in_{cfg['facility_radius_km']}km={len(facs)} (with capacity {sum(f.capacity_kg_day is not None for f in facs)})")


if __name__ == "__main__":
    main()
