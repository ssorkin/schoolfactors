"""LAUSD GIS acquisition from the district's public ArcGIS org.

services3.arcgis.com/9QBcCnjxM5EBVdGe hosts LAUSD's official cartography (maintained by
the district's GIS team): attendance-area polygons, school points, boundary layers, and
site capacity tables. We snapshot each layer as a merged GeoJSON/JSON file with a
manifest entry, so the geometry used for analysis and the site is byte-traceable.

Geometry is requested in EPSG:4326 (`outSR=4326`) at acquire time so no reprojection
dependency is ever needed downstream. The fetcher pages with resultOffset even though
every current layer fits in one page (MP25 is 985 features < 2000 maxRecordCount);
attribute-only pulls (returnGeometry=false) use the same loop for large tables like
the 2020 census blocks.

Key layers:
- MP25: the current attendance-area partition. Each polygon carries E_KEY/M_KEY/H_KEY
  (the elementary/middle/high school serving it); P_KEY is their concatenation plus an
  optional letter suffix for split polygons.
- Att{e,m,h}1112_Codes: the KEY -> school (name, LAUSD school id, 7-digit CDS school
  code) lookup tables. E_KEY is NOT a cost-center prefix — these tables are the
  authoritative map.
- Attendance Boundary Info: POLYID (P_KEY format) -> program/school rows, the fallback
  resolver for keys missing from the dated (2016-17) Codes tables.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import httpx

from schoolfactors.acquire.base import (
    ManifestEntry,
    client,
    load_manifest,
    save_manifest,
    sha256_file,
)
from schoolfactors.paths import RAW_DIR

DATASET = "lausd_gis"
ORG = "https://services3.arcgis.com/9QBcCnjxM5EBVdGe/ArcGIS/rest/services"

# (filename stem, service/layer path, format, extra query params)
LAYERS: list[tuple[str, str, str, dict]] = [
    ("mp25_polygons", "MP25/FeatureServer/0", "geojson", {}),
    ("atte1112_codes", "Boundaries_and_Sites/FeatureServer/4", "json", {}),
    ("attm1112_codes", "Boundaries_and_Sites/FeatureServer/5", "json", {}),
    ("atth1112_codes", "Boundaries_and_Sites/FeatureServer/6", "json", {}),
    ("attendance_boundary_info", "Attendance_Boundaries/FeatureServer/2", "json", {}),
    ("school_points", "School_Points/FeatureServer/0", "geojson", {}),
    ("locx_2023_24", "LOCX_file_2023_2024/FeatureServer/0", "json", {}),
    ("lausd_boundary", "LAUSD_Boundary/FeatureServer/0", "geojson", {}),
    (
        "sites_capacity_enrollment",
        "LAUSD_Sites_with_Capacity_and_Enrollment/FeatureServer/0",
        "json",
        {},
    ),
    # 2020 census blocks for LA County, attributes only: block -> population and
    # internal point, used to apportion block-group demographics onto MP25 polygons.
    (
        "la_blocks_2020",
        "tl_2025_06_tabblock2020/FeatureServer/0",
        "json",
        {
            "where": "COUNTYFP20='037'",
            "outFields": "GEOID20,POP20,HOUSING20,INTPTLAT20,INTPTLON20",
            "returnGeometry": "false",
        },
    ),
]


def _get_json(url: str, params: dict) -> dict:
    resp = client().get(url, params=params)
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, dict) and "error" in data:
        raise RuntimeError(f"ArcGIS error for {url}: {data['error']}")
    return data


def fetch_layer(
    name: str,
    layer_path: str,
    fmt: str = "geojson",
    extra: dict | None = None,
    page_size: int = 2000,
) -> Path | None:
    """Page a full layer through /query and write one merged file + manifest entry."""
    layer_url = f"{ORG}/{layer_path}"
    dest_dir = RAW_DIR / DATASET
    dest_dir.mkdir(parents=True, exist_ok=True)
    suffix = "geojson" if fmt == "geojson" else "json"
    dest = dest_dir / f"{name}.{suffix}"

    params: dict = {
        "where": "1=1",
        "outFields": "*",
        "f": fmt,
        "resultRecordCount": page_size,
        **(extra or {}),
    }
    if params.get("returnGeometry") != "false" and fmt == "geojson":
        params["outSR"] = 4326

    manifest = load_manifest(DATASET)
    entry = manifest.get(dest.name)
    if entry and dest.exists() and dest.stat().st_size == entry["size"]:
        return dest

    features: list = []
    merged: dict | None = None
    offset, pages = 0, 0
    while True:
        try:
            page = _get_json(f"{layer_url}/query", {**params, "resultOffset": offset})
        except (httpx.HTTPError, RuntimeError) as exc:
            print(f"  FAILED {name}: {exc}")
            return None
        page_features = page.get("features", [])
        if merged is None:
            merged = page
        features.extend(page_features)
        pages += 1
        offset += len(page_features)
        more = page.get("exceededTransferLimit") or page.get("properties", {}).get(
            "exceededTransferLimit"
        )
        if len(page_features) < page_size and not more:
            break
    if merged is None or not features:
        print(f"  FAILED {name}: no features returned")
        return None
    merged["features"] = features
    dest.write_text(json.dumps(merged))

    # Schema/provenance snapshot of the layer definition (fields, name, edit dates).
    try:
        meta = _get_json(layer_url, {"f": "json"})
        (dest_dir / f"{name}_meta.json").write_text(json.dumps(meta, indent=1))
    except (httpx.HTTPError, RuntimeError):
        pass

    manifest[dest.name] = ManifestEntry(
        dataset=DATASET,
        filename=dest.name,
        url=f"{layer_url}/query",
        sha256=sha256_file(dest),
        size=dest.stat().st_size,
        downloaded_at=datetime.now(UTC).isoformat(timespec="seconds"),
        note=f"{len(features)} features in {pages} page(s), f={fmt}",
    ).__dict__
    save_manifest(DATASET, manifest)
    print(f"  ok {dest.name} ({len(features):,} features, {dest.stat().st_size:,} bytes)")
    return dest


def acquire() -> None:
    for name, layer_path, fmt, extra in LAYERS:
        fetch_layer(name, layer_path, fmt=fmt, extra=extra)
