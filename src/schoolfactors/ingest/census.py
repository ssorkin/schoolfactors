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
_DATA_RE = re.compile(
    r"^acs(?P<survey>[15])_(\d{4})_([a-z]\d{5}[a-z]?)_(sd_[a-z]+|bg_\d+|county|state)\.json$"
)
_DEC_RE = re.compile(r"^dec(\d{4})_pl_blocks_(\d+)\.json$")
_POPEST_INT_RE = re.compile(r"^popest_co-est00int-agesex-5yr\.csv$")
_POPEST_VIN_RE = re.compile(r"^popest_cc-est(\d{4})-agesex-06\.csv$")


def ingest_popest_file(path: Path) -> pl.DataFrame | None:
    """County population-estimate controls → long rows {series, state, county,
    agegrp, july_year, measure, value}, all nullable strings.

    Intercensal file (national, 5-year age groups, 2010-census-consistent):
    California sex-total rows only; one row per (county, agegrp, July year
    2000-2010), measure 'popestimate'. AGEGRP 0 is all ages, 1..18 are 5-year
    bins starting 0-4 (so 5-17 ≈ grp 2 + grp 3 + 3/5 of grp 4 — that weighting
    is an analysis decision, not applied here).

    Vintage files (CA counties, the actual ACS weighting controls of their
    survey year): July-1 rows only — year code = july_year − 1997; codes 1-2
    are the April 2000 census count and estimates base, skipped — with exact
    5-17 as measures 'age513_tot' + 'age1417_tot'. The vintage-2005 file names
    its columns TIME/ST/CTY where later vintages use YEAR/STATE/COUNTY.
    """
    import csv as _csv

    rows: list[dict] = []
    if _POPEST_INT_RE.match(path.name):
        with path.open(encoding="latin-1") as fh:
            for r in _csv.DictReader(fh):
                if r["SUMLEV"] != "050" or r["STATE"] != "06" or r["SEX"] != "0":
                    continue
                for y in range(2000, 2011):
                    rows.append(
                        {
                            "series": "intercensal",
                            "state": r["STATE"],
                            "county": r["COUNTY"],
                            "agegrp": r["AGEGRP"],
                            "july_year": str(y),
                            "measure": "popestimate",
                            "value": r[f"POPESTIMATE{y}"],
                        }
                    )
    elif m := _POPEST_VIN_RE.match(path.name):
        vintage = m.group(1)
        with path.open(encoding="latin-1") as fh:
            for r in _csv.DictReader(fh):
                if r["SUMLEV"] != "050":
                    continue
                code = int(r.get("YEAR") or r["TIME"])
                if code < 3:  # April 2000 census count / estimates base
                    continue
                for measure in ("age513_tot", "age1417_tot"):
                    rows.append(
                        {
                            "series": f"vintage{vintage}",
                            "state": r.get("STATE") or r.get("ST"),
                            "county": r.get("COUNTY") or r.get("CTY"),
                            "agegrp": None,
                            "july_year": str(code + 1997),
                            "measure": measure,
                            "value": r[measure.upper()],
                        }
                    )
    else:
        return None
    schema = {
        c: pl.Utf8
        for c in ("series", "state", "county", "agegrp", "july_year", "measure", "value")
    }
    return pl.DataFrame(rows, schema=schema)


def ingest_dec_file(path: Path) -> pl.DataFrame | None:
    """Decennial P.L. block counts → wide rows (year, 15-digit geoid, pop, pop18)."""
    m = _DEC_RE.match(path.name)
    if not m:
        return None
    year = m.group(1)
    arrays = json.loads(path.read_text())
    header, data = arrays[0], arrays[1:]
    idx = {c: i for i, c in enumerate(header)}
    pop_col = idx.get("P001001", idx.get("P1_001N"))
    adult_col = idx.get("P003001", idx.get("P3_001N"))
    rows = [
        {
            "year": year,
            "geoid": row[idx["state"]] + row[idx["county"]] + row[idx["tract"]]
            + row[idx["block"]],
            "pop": row[pop_col],
            "pop18": row[adult_col],
        }
        for row in data
    ]
    return pl.DataFrame(rows, schema={c: pl.Utf8 for c in ("year", "geoid", "pop", "pop18")})


def _load_labels(vintage: str, table: str, survey: str = "5") -> dict[str, str]:
    path = RAW_DIR / "census" / f"acs{survey}_{vintage}_groups_{table.lower()}.json"
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
    survey, vintage, table_lc, geo_type = m.groups()
    table = table_lc.upper()
    labels = _load_labels(vintage, table, survey)

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
                    "survey": f"acs{survey}",
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
    for path in sorted(raw_dir.glob("acs[15]_*.json")):
        df = ingest_file(path)
        if df is None:
            continue
        df = df.with_columns(pl.lit(path.name).alias("source_file"))
        out = PARQUET_DIR / FAMILY / f"file={path.stem}"
        out.mkdir(parents=True, exist_ok=True)
        df.write_parquet(out / "data.parquet")
        print(f"  {FAMILY}/{path.name}: {len(df):,} rows")
    for path in sorted(raw_dir.glob("dec*_pl_blocks_*.json")):
        df = ingest_dec_file(path)
        if df is None:
            continue
        df = df.with_columns(pl.lit(path.name).alias("source_file"))
        out = PARQUET_DIR / "dec_pl" / f"file={path.stem}"
        out.mkdir(parents=True, exist_ok=True)
        df.write_parquet(out / "data.parquet")
        print(f"  dec_pl/{path.name}: {len(df):,} rows")
    for path in sorted(raw_dir.glob("popest_*.csv")):
        df = ingest_popest_file(path)
        if df is None:
            continue
        df = df.with_columns(pl.lit(path.name).alias("source_file"))
        out = PARQUET_DIR / "popest" / f"file={path.stem}"
        out.mkdir(parents=True, exist_ok=True)
        df.write_parquet(out / "data.parquet")
        print(f"  popest/{path.name}: {len(df):,} rows")
