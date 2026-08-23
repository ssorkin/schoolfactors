"""Statewide school-district polygons from TIGERweb (Census Bureau ArcGIS REST).

The TIGERweb "School" MapServer publishes the school-district boundary layers used
for ACS school-district geography. We snapshot the three California summary levels
(unified / secondary / elementary) as GeoJSON with manifest entries, matching the
ACS-2024 vintage of the district geoids we join on.

Layer IDs SHIFT ANNUALLY when a new ACS group is added to the service, so each
layer's metadata is probed first and its name asserted before any data is trusted
(see LAYERS). Geometry is requested in EPSG:4326 with geometryPrecision=6 to keep
raw sizes sane; display geometry is further simplified at export time
(analysis/enrollment_geo.py), and analysis point-in-polygon uses the raw file.

Fallback if TIGERweb becomes unavailable: the cartographic boundary archives at
https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_06_{unsd,elsd,scsd}_500k.zip
— but those are shapefiles and the repo deliberately has no shapefile reader
(shapely only), which is why the GeoJSON REST endpoint is primary.
"""

from __future__ import annotations

import httpx

from schoolfactors.acquire.lausd_gis import _get_json, fetch_layer

DATASET = "tiger"
SERVICE = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/School/MapServer"

# (filename stem, layer id, required substring of the layer name).
# IDs verified 2026-08-22 against the ACS 2024 group of the School service.
LAYERS: tuple[tuple[str, int, str], ...] = (
    ("tiger_sd_unified_acs2024", 10, "Unified"),
    ("tiger_sd_secondary_acs2024", 11, "Secondary"),
    ("tiger_sd_elementary_acs2024", 12, "Elementary"),
)

OUT_FIELDS = "GEOID,NAME,BASENAME,FUNCSTAT,LOGRADE,HIGRADE,CENTLAT,CENTLON"


def acquire() -> None:
    for name, layer_id, expect in LAYERS:
        layer_url = f"{SERVICE}/{layer_id}"
        try:
            meta = _get_json(layer_url, {"f": "json"})
        except (httpx.HTTPError, RuntimeError) as exc:
            print(f"  FAILED {name}: layer metadata unavailable: {exc}")
            continue
        layer_name = meta.get("name", "")
        if expect not in layer_name:
            print(
                f"  FAILED {name}: layer {layer_id} is {layer_name!r}, expected a "
                f"name containing {expect!r} — TIGERweb layer IDs have shifted; "
                f"update acquire/tiger.py LAYERS from {SERVICE}?f=json"
            )
            continue
        fetch_layer(
            name,
            layer_url,
            fmt="geojson",
            extra={
                "where": "STATE='06'",
                "outFields": OUT_FIELDS,
                "geometryPrecision": 6,
            },
            dataset=DATASET,
        )
