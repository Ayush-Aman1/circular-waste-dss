"""Data acquisition, one sub-command per source. Raw cache in data/raw/<source>/, one row per file in data/SOURCES.csv.

    python -m circwaste.data.acquire opencity|worldbank|edinburgh|melbourne|all  [--root data]

A failing source is recorded in BLOCKERS.md and the others continue (exit code 0 unless *all* fail).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import sys
import time
from pathlib import Path

import requests

UA = "circwaste-research/0.1 (academic project; contact: placeholder@example.org)"
SOURCES_HDR = ["name", "url", "retrieved_at", "licence", "sha256", "path"]


def get(url: str, *, params: dict | None = None, retries: int = 6, timeout: int = 120) -> requests.Response:
    delay = 2.0
    last: Exception | None = None
    for _ in range(retries):
        try:
            r = requests.get(url, params=params, headers={"User-Agent": UA}, timeout=timeout)
            if r.status_code in (429, 500, 502, 503, 504):
                raise requests.HTTPError(str(r.status_code))
            if r.status_code in (403, 404, 410):  # permanent: do not retry
                raise RuntimeError(f"{r.status_code} for {url}")
            r.raise_for_status()
            return r
        except RuntimeError:
            raise
        except requests.RequestException as e:
            last = e
            time.sleep(delay)
            delay = min(delay * 2, 60)
    raise RuntimeError(f"GET {url}: {last}")


def record(root: Path, name: str, url: str, licence: str, path: Path) -> None:
    f = root / "SOURCES.csv"
    new = not f.exists()
    rows = list(csv.DictReader(open(f))) if not new else []
    rows = [r for r in rows if r["path"] != str(path)]
    rows.append({"name": name, "url": url, "retrieved_at": time.strftime("%Y-%m-%d"),
                 "licence": licence, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "path": str(path)})
    with open(f, "w", newline="") as fh:
        w = csv.DictWriter(fh, SOURCES_HDR)
        w.writeheader()
        w.writerows(rows)


def save(root: Path, source: str, fname: str, content: bytes, name: str, url: str, licence: str) -> Path:
    p = root / "raw" / source / fname
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(content)
    record(root, name, url, licence, p)
    return p


def opencity(root: Path) -> None:
    """OpenCity 'BBMP Solid Waste Management Data' via the CKAN API (package_show)."""
    base = "https://data.opencity.in/api/3/action/package_show"
    pkg = get(base, params={"id": "bbmp-solid-waste-management-data"}).json()["result"]
    lic = pkg.get("license_title") or "check per file (OpenCity: maps marked Public Domain)"
    for r in pkg["resources"]:
        fname = r["name"].replace(" ", "_").replace(":", "").replace("/", "-")[:70] + "." + r["format"].lower()
        content = get(r["url"]).content
        save(root, "opencity", fname, content, f"OpenCity BBMP SWM: {r['name']}", r["url"], lic)
        print("opencity", fname, len(content))


def worldbank(root: Path) -> None:
    """World Bank What a Waste 2.0 country + city CSVs (CC BY 4.0)."""
    for kind, path in [("country", "DR0049199/country_level_data.csv")]:
        url = f"https://datacatalogfiles.worldbank.org/ddh-published/0039597/{path}"
        content = get(url, timeout=180).content
        save(root, "worldbank", f"{kind}_level_data.csv", content, f"World Bank What a Waste 2.0 ({kind})", url, "CC BY 4.0")
        print("worldbank", kind, len(content))


def edinburgh(root: Path) -> None:
    """Edinburgh litter-bin sensors (aileenmcd/bin_project raw_data; data (c) Edinburgh Council, OGL v3)."""
    url = "https://raw.githubusercontent.com/aileenmcd/bin_project/main/raw_data/raw_bin_data.xlsx"
    content = get(url, timeout=180).content
    save(root, "edinburgh", "raw_bin_data.xlsx", content, "Edinburgh litter-bin sensor data (via aileenmcd/bin_project)", url, "OGL v3.0")
    print("edinburgh", len(content))
    url2 = "https://raw.githubusercontent.com/aileenmcd/bin_project/main/cleaned_data/bin_data/aggregated_bin_data.csv"
    c2 = get(url2, timeout=180).content
    save(root, "edinburgh", "aggregated_bin_data.csv", c2, "Edinburgh street-level daily collected volume (aileenmcd/bin_project cleaned_data)", url2, "OGL v3.0")
    print("edinburgh aggregated", len(c2))


def melbourne(root: Path) -> None:
    """Melbourne Argyle Square smart bins (City of Melbourne open data; CSV export)."""
    url = "https://data.melbourne.vic.gov.au/api/v2/catalog/datasets/smart-bins-argyle-square/exports/csv?delimiter=%2C"
    content = get(url, timeout=300).content
    save(root, "melbourne", "smart_bins_argyle_square.csv", content, "Melbourne Argyle Square smart bins", url, "CC BY 4.0 (City of Melbourne open data; check portal)")
    print("melbourne", len(content))


SOURCES = {"opencity": opencity, "worldbank": worldbank, "edinburgh": edinburgh, "melbourne": melbourne}


def block(msg: str) -> None:
    key = msg.split(":")[0]
    if Path("BLOCKERS.md").exists() and any(key in ln and "acquisition" in ln for ln in Path("BLOCKERS.md").read_text().splitlines()):
        return
    with open("BLOCKERS.md", "a") as f:
        f.write(f"- {time.strftime('%F')} acquisition: {msg}\n")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("source", choices=[*SOURCES, "all"])
    ap.add_argument("--root", default="data")
    a = ap.parse_args()
    root = Path(a.root)
    names = list(SOURCES) if a.source == "all" else [a.source]
    ok = 0
    for n in names:
        try:
            SOURCES[n](root)
            ok += 1
        except Exception as e:  # noqa: BLE001  keep going, record
            print(f"{n}: FAILED {e}", file=sys.stderr)
            block(f"{n} unreachable: {str(e)[:200]}")
    if ok == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
