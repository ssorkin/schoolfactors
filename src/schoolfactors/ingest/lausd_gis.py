"""LAUSD GIS ingestion: ArcGIS snapshots → attribute parquet families.

Geometry stays in the raw GeoJSON files (analysis reads it directly); parquet carries
attributes only, one family per table so `ingest/db.py` auto-creates clean per-table
views (lausd_mp25_raw, lausd_codes_raw, ...). All values are nullable strings, matching
the CDE ingest convention.

Derived columns worth noting:
- lausd_mp25: `split_suffix` (trailing letter on P_KEY for polygons split by another
  level's boundary) and `p_e/p_m/p_h` (the three 5-digit segments re-parsed from P_KEY,
  kept alongside E_KEY/M_KEY/H_KEY so `sf check` can prove they always agree).
- lausd_codes: the three per-level Codes tables union under a `level` column (E/M/H)
  with `key5` renamed from {E,M,H}KEY_5S, and `cds` = 19 + 64733 + zero-padded 7-digit
  school code (full CDS, matching the rest of the store).
- lausd_capacity: OPCAP_<year>/ENROLLMENT_<year> columns unpivoted to long
  (cds, year, opcap, enrollment).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import polars as pl

from schoolfactors.paths import PARQUET_DIR, RAW_DIR

RAW = RAW_DIR / "lausd_gis"
LAUSD_CD_PREFIX = "1964733"  # county 19 + district 64733


def _to_str(v) -> str | None:
    if v is None:
        return None
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    s = str(v).strip()
    return s or None


def _rows_to_df(rows: list[dict]) -> pl.DataFrame:
    cols: dict[str, list] = {}
    for row in rows:
        for k in row:
            cols.setdefault(k, [])
    for row in rows:
        for k, values in cols.items():
            values.append(_to_str(row.get(k)))
    return pl.DataFrame(cols, schema={k: pl.Utf8 for k in cols})


def _esri_attributes(path: Path) -> pl.DataFrame:
    doc = json.loads(path.read_text())
    return _rows_to_df([f["attributes"] for f in doc["features"]])


def _geojson_properties(path: Path, with_coords: bool = False) -> pl.DataFrame:
    doc = json.loads(path.read_text())
    rows = []
    for f in doc["features"]:
        row = dict(f.get("properties") or {})
        if with_coords and f.get("geometry", {}).get("type") == "Point":
            lng, lat = f["geometry"]["coordinates"][:2]
            row["lng"], row["lat"] = lng, lat
        rows.append(row)
    return _rows_to_df(rows)


def _snake(df: pl.DataFrame) -> pl.DataFrame:
    # Esri layers carry both Shape_Area and Shape__Area; collapsing underscores would
    # collide, so later duplicates get a numeric suffix.
    mapping: dict[str, str] = {}
    seen: set[str] = set()
    for c in df.columns:
        name = re.sub(r"_+", "_", re.sub(r"[^\w]+", "_", c.strip())).strip("_").lower()
        base, i = name, 2
        while name in seen:
            name = f"{base}_{i}"
            i += 1
        seen.add(name)
        mapping[c] = name
    return df.rename(mapping)


def _write(family: str, source: str, df: pl.DataFrame) -> None:
    df = df.with_columns(pl.lit(source).alias("source_file"))
    out = PARQUET_DIR / family / f"file={Path(source).stem}"
    out.mkdir(parents=True, exist_ok=True)
    df.write_parquet(out / "data.parquet")
    print(f"  {family}/{source}: {len(df):,} rows, {len(df.columns)} cols")


def _full_cds(col: str) -> pl.Expr:
    """19 + 64733 + zero-padded 7-digit school code, null-safe."""
    code = pl.col(col).str.strip_chars()
    return (
        pl.when(code.str.len_chars() > 0)
        .then(pl.lit(LAUSD_CD_PREFIX) + code.str.zfill(7))
        .otherwise(None)
        .alias("cds")
    )


def ingest_mp25() -> None:
    path = RAW / "mp25_polygons.geojson"
    if not path.exists():
        return
    df = _snake(_geojson_properties(path))
    df = df.with_columns(
        pl.col("p_key").str.extract(r"([a-z])$", 1).alias("split_suffix"),
        pl.col("p_key").str.slice(0, 5).alias("p_e"),
        pl.col("p_key").str.slice(5, 5).alias("p_m"),
        pl.col("p_key").str.slice(10, 5).alias("p_h"),
    )
    _write("lausd_mp25", path.name, df)


def ingest_codes() -> None:
    frames = []
    for fname, key_col, level in (
        ("atte1112_codes.json", "EKEY_5S", "E"),
        ("attm1112_codes.json", "MKEY_5S", "M"),
        ("atth1112_codes.json", "HKEY_5S", "H"),
    ):
        path = RAW / fname
        if not path.exists():
            continue
        df = _esri_attributes(path).rename({key_col: "key5"})
        df = _snake(df).with_columns(
            pl.lit(level).alias("level"),
            pl.lit(fname).alias("codes_file"),
        )
        frames.append(df)
    if not frames:
        return
    df = pl.concat(frames, how="diagonal").with_columns(_full_cds("cds").alias("cds14"))
    _write("lausd_codes", "att1112_codes.json", df)


def ingest_abinfo() -> None:
    path = RAW / "attendance_boundary_info.json"
    if not path.exists():
        return
    df = _snake(_esri_attributes(path))
    df = df.with_columns(_full_cds("cds").alias("cds14"))
    _write("lausd_abinfo", path.name, df)


def ingest_points() -> None:
    path = RAW / "school_points.geojson"
    if not path.exists():
        return
    df = _snake(_geojson_properties(path, with_coords=True))
    _write("lausd_points", path.name, df)


def ingest_locx() -> None:
    path = RAW / "locx_2023_24.json"
    if not path.exists():
        return
    df = _snake(_esri_attributes(path))
    _write("lausd_locx", path.name, df)


def ingest_capacity() -> None:
    path = RAW / "sites_capacity_enrollment.json"
    if not path.exists():
        return
    wide = _snake(_esri_attributes(path))
    years = sorted(
        {m.group(1) for c in wide.columns if (m := re.fullmatch(r"opcap_(\d{4})", c))}
    )
    id_cols = ["cdscode", "ccc", "mpd_name", "mpd_type", "map_type", "cos", "latitude",
               "longitude"]
    id_cols = [c for c in id_cols if c in wide.columns]
    frames = []
    for y in years:
        cols = [*id_cols]
        frame = wide.select(
            *cols,
            pl.lit(y).alias("year"),
            pl.col(f"opcap_{y}").alias("opcap"),
            pl.col(f"enrollment_{y}").alias("enrollment"),
        )
        frames.append(frame)
    if not frames:
        return
    _write("lausd_capacity", path.name, pl.concat(frames))


def ingest_blocks() -> None:
    path = RAW / "la_blocks_2020.json"
    if not path.exists():
        return
    df = _snake(_esri_attributes(path))
    _write("la_blocks", path.name, df)


def ingest_all() -> None:
    ingest_mp25()
    ingest_codes()
    ingest_abinfo()
    ingest_points()
    ingest_locx()
    ingest_capacity()
    ingest_blocks()
