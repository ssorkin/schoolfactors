"""Census ACS ingestion: API JSON snapshots → long-format parquet.

The data API returns an array-of-arrays (header row + data rows) per table×geography.
We reshape to long format — one row per (geography, variable) — so every ACS table,
present and future, unions cleanly under a single `census_acs_raw` DuckDB view.
Values stay nullable strings (repo convention); ACS sentinel values (large negatives
like -666666666) and nulls are handled at analysis time.

`geoid` is the digits after "US" in GEO_ID: state+district (7 digits) for school
districts — directly comparable to `directory_raw.ncesdist` — and the 12-digit
state+county+tract+block-group code for block groups.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import polars as pl

from schoolfactors.paths import PARQUET_DIR, RAW_DIR

FAMILY = "census_acs"

# acs5_<vintage>_<table>_<geo...>.json (data) vs acs5_<vintage>_groups_<table>.json (meta)
_DATA_RE = re.compile(r"^acs5_(\d{4})_([a-z]\d{5}[a-z]?)_(sd_[a-z]+|bg_\d+)\.json$")


def _load_labels(vintage: str, table: str) -> dict[str, str]:
    path = RAW_DIR / "census" / f"acs5_{vintage}_groups_{table.lower()}.json"
    if not path.exists():
        return {}
    meta = json.loads(path.read_text())
    return {var: spec.get("label", "") for var, spec in meta.get("variables", {}).items()}


def _geoid(row: dict[str, str | None], geo_type: str) -> str | None:
    gid = row.get("GEO_ID") or ""
    if "US" in gid:
        return gid.split("US", 1)[1]
    if geo_type.startswith("sd_"):
        sd_col = next((c for c in row if c.startswith("school district")), None)
        if sd_col and row.get("state") and row.get(sd_col):
            return f"{row['state']}{row[sd_col]}"
    if geo_type.startswith("bg"):
        parts = [row.get(c) for c in ("state", "county", "tract", "block group")]
        if all(parts):
            return "".join(parts)  # type: ignore[arg-type]
    return None


def ingest_file(path: Path) -> pl.DataFrame | None:
    m = _DATA_RE.match(path.name)
    if not m:
        return None
    vintage, table_lc, geo_type = m.groups()
    table = table_lc.upper()
    labels = _load_labels(vintage, table)

    arrays = json.loads(path.read_text())
    header, data = arrays[0], arrays[1:]
    var_cols = [c for c in header if re.fullmatch(rf"{table}_\d+[EM]", c)]

    rows: list[dict] = []
    for values in data:
        row = dict(zip(header, values))
        geoid = _geoid(row, geo_type)
        name = row.get("NAME")
        for var in var_cols:
            rows.append(
                {
                    "vintage": vintage,
                    "table_id": table,
                    "geo_type": geo_type,
                    "geoid": geoid,
                    "geo_name": name,
                    "variable": var,
                    "label": labels.get(var),
                    "value": row.get(var),
                }
            )
    schema = {c: pl.Utf8 for c in rows[0]} if rows else None
    return pl.DataFrame(rows, schema=schema)


def ingest_all() -> None:
    raw_dir = RAW_DIR / "census"
    if not raw_dir.exists():
        return
    for path in sorted(raw_dir.glob("acs5_*.json")):
        df = ingest_file(path)
        if df is None:
            continue
        df = df.with_columns(pl.lit(path.name).alias("source_file"))
        out = PARQUET_DIR / FAMILY / f"file={path.stem}"
        out.mkdir(parents=True, exist_ok=True)
        df.write_parquet(out / "data.parquet")
        print(f"  {FAMILY}/{path.name}: {len(df):,} rows")
