"""Parse the OpenCity BBMP KML/CSV files into Facility rows (kind: dwcc | wet_plant | biomethanation | landfill)."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import pandas as pd

from circwaste.models import Facility

RAW = Path("data/raw/opencity")
KINDS = {
    "dwcc": ("BBMP_Dry_Waste_Collection_Centres_Map.kml", ["paper", "plastic", "glass", "metal", "textile", "rubber_leather"]),
    "wet_plant": ("BBMP_Waste_Processing_Units_Map.kml", ["organic"]),
    "biomethanation": ("Bengaluru_Bio_Methanisation_Plants_Locations.kml", ["organic"]),
    "landfill": ("BBMP_Landfill_Locations_Map.kml", ["organic", "paper", "plastic", "glass", "metal", "textile", "rubber_leather", "inert_other"]),
}
NS = {"k": "http://www.opengis.net/kml/2.2"}


def parse_kml(path: Path) -> list[dict]:
    """Placemarks with a point geometry -> name, lat, lon, description (namespace-agnostic)."""
    root = ET.parse(path).getroot()
    out = []
    for pm in root.iter():
        if not pm.tag.endswith("Placemark"):
            continue
        name = desc = coords = None
        for ch in pm.iter():
            t = ch.tag.split("}")[-1]
            if t == "SimpleData" and ch.get("name", "").endswith(("Name", "name")) and ch.get("name") not in ("WardName", "KGISWardName") and not name:
                name = (ch.text or "").strip()  # DWCCName / Waste_Processing_UnitName / Land_FillsName / BMUName
            elif t == "name" and name is None:
                name = (ch.text or "").strip()
            elif t == "description" and desc is None:
                desc = re.sub(r"<[^>]+>", " ", ch.text or "")
            elif t == "coordinates" and coords is None and ch.text:
                coords = ch.text.strip().split()[0]
        if coords:
            lon, lat = (float(x) for x in coords.split(",")[:2])
            out.append({"name": name or "", "lat": lat, "lon": lon, "description": re.sub(r"\s+", " ", desc or "").strip()})
    return out


def load_facilities() -> list[Facility]:
    facs: list[Facility] = []
    for kind, (fname, accepts) in KINDS.items():
        p = RAW / fname
        if not p.exists():
            continue
        for i, r in enumerate(parse_kml(p)):
            facs.append(Facility(id=f"{kind}_{i}", kind=kind, accepts=accepts, lat=r["lat"], lon=r["lon"], name=r["name"],
                                 capacity_kg_day=None, source=f"OpenCity BBMP SWM: {fname}"))
    return facs


def haversine_km(lat1, lon1, lat2, lon2):
    p = np.pi / 180
    a = np.sin((lat2 - lat1) * p / 2) ** 2 + np.cos(lat1 * p) * np.cos(lat2 * p) * np.sin((lon2 - lon1) * p / 2) ** 2
    return 12742 * np.arcsin(np.sqrt(a))


def within_radius(facs: list[Facility], lat: float, lon: float, radius_km: float) -> list[Facility]:
    return [f for f in facs if haversine_km(lat, lon, f.lat, f.lon) <= radius_km]


def facilities_frame(facs: list[Facility]) -> pd.DataFrame:
    return pd.DataFrame([f.model_dump() for f in facs])


def _norm(s: str) -> str:
    return re.sub(r"[^a-z]", "", s.lower())


def capacities_from_plants_csv(facs: list[Facility], csv_path: Path = RAW / "BBMP_Waste_Processing_Plants.csv") -> dict[str, tuple[float, str]]:
    """Match 'name, N TPD' rows of the OpenCity plants CSV to wet_plant facilities by fuzzy name (first word).
    Returns facility id -> (kg/day, provenance). Unmatched facilities stay None (-> TODO-SOURCE in assumptions)."""
    import difflib

    out: dict[str, tuple[float, str]] = {}
    if not csv_path.exists():
        return out
    df = pd.read_csv(csv_path, header=None, names=["name", "cap"]).dropna()
    for r in df.itertuples():
        m = re.match(r"\s*(\d+)\s*TPD", str(r.cap))
        if not m or r.name.lower().startswith(("total", "old", "new")):
            continue
        key = _norm(re.sub(r"^m/s\.?", "", r.name.lower()))[:9]
        best, score = None, 0.0
        for f in facs:
            if f.kind != "wet_plant":
                continue
            sc = difflib.SequenceMatcher(None, key, _norm(f.name)[:9]).ratio()
            if sc > score:
                best, score = f, sc
        if best is not None and score >= 0.78 and best.id not in out:
            out[best.id] = (float(m.group(1)) * 1000.0, f"OpenCity 'BBMP Waste Processing Plants' CSV row '{r.name}' ({m.group(1)} TPD); fuzzy name match {score:.2f}")
    return out
