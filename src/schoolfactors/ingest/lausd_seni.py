"""SENI ingestion: LAUSD Open Data Catalog CSVs → parquet family `lausd_seni`.

One file per allocation year (SENI_2026-2027.csv, SENIplus_2022-2023.csv, ...), each
one row per school with SENI score/rank/quintile, the dollar allocation, and every
underlying indicator. Column names shift between years (indicator vintages are baked
into headers like "EL Rate 2025-26"), so everything is kept as nullable strings with
snake_cased names and unioned by name in the DuckDB view; analysis selects the SENI
columns by pattern. `cds` (14-char) derives from the 7-digit "CDS Code" column plus
LAUSD's county-district prefix; `allocation_year` derives from the filename.

The ESSER-II 2021-22 files are a different program shape (per-level, 17 cols) and
ingest under the same family for completeness.
"""

from __future__ import annotations

import re
from pathlib import Path

import polars as pl

from schoolfactors.paths import PARQUET_DIR, RAW_DIR

FAMILY = "lausd_seni"
NULL_TOKENS = ["NA", "N/A", "", "*", "--"]
LAUSD_CD_PREFIX = "1964733"


def _snake(name: str) -> str:
    name = re.sub(r"[^\w]+", "_", name.strip())
    return re.sub(r"_+", "_", name).strip("_").lower()


def read_seni_csv(path: Path) -> pl.DataFrame:
    df = pl.read_csv(
        path,
        null_values=NULL_TOKENS,
        infer_schema_length=0,  # all strings
        encoding="utf8-lossy",  # some years carry a UTF-8 BOM
    )
    df = df.rename({c: _snake(c) for c in df.columns})
    if "cds_code" in df.columns:
        code = pl.col("cds_code").str.strip_chars()
        df = df.with_columns(
            pl.when(code.str.len_chars() > 0)
            .then(pl.lit(LAUSD_CD_PREFIX) + code.str.zfill(7))
            .otherwise(None)
            .alias("cds")
        )
    m = re.search(r"(\d{4})-(\d{4})", path.stem)
    if m:
        df = df.with_columns(pl.lit(m.group(2)).alias("allocation_year"))
    return df


def ingest_all() -> None:
    raw = RAW_DIR / FAMILY
    if not raw.exists():
        return
    for path in sorted(raw.glob("SENI*.csv")):
        try:
            df = read_seni_csv(path)
        except Exception as exc:  # noqa: BLE001 - report and continue with other years
            print(f"  FAILED {FAMILY}/{path.name}: {exc}")
            continue
        df = df.with_columns(pl.lit(path.name).alias("source_file"))
        out = PARQUET_DIR / FAMILY / f"file={path.stem}"
        out.mkdir(parents=True, exist_ok=True)
        df.write_parquet(out / "data.parquet")
        print(f"  {FAMILY}/{path.name}: {len(df):,} rows, {len(df.columns)} cols")
