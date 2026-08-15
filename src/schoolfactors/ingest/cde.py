"""CDE downloadable-file ingestion.

CDE's tab-delimited files share conventions but drift across years, so ingestion is
deliberately generic: every column is read as a nullable string (suppression tokens
'*'/'N/A'/'No Data' → null), names are snake_cased, and a zero-padded 14-char `cds`
key is derived wherever county/district/school code columns exist. Type casting and
the mandatory Charter=='All' / DASS=='All' / AggregateLevel filters happen in the
DuckDB views (ingest/db.py), where they are visible and auditable in one place.
"""

from __future__ import annotations

import io
import re
from pathlib import Path

import polars as pl

from schoolfactors.paths import PARQUET_DIR, RAW_DIR

NULL_TOKENS = ["*", "", "N/A", "NA", "No Data", "--"]

# Families whose raw files are tab-delimited text
TAB_FAMILIES = [
    "directory",
    "enrollment",
    "enrollment_hist",
    "absenteeism",
    "suspension",
    "expulsion",
    "acgr",
    "cgr",
    "stability",
    "staff_exp",
    "staff_edu",
    "staff_ratio",
    "tamo",
    "el",
    "dashboard",
    "growth",
]
XLSX_FAMILIES = ["frpm", "cupc", "ppe", "currentexpense"]


def snake(name: str) -> str:
    name = re.sub(r"[^\w]+", "_", name.strip())
    name = re.sub(r"_+", "_", name).strip("_")
    return name.lower()


def _derive_cds(df: pl.DataFrame) -> pl.DataFrame:
    cols = {c.lower(): c for c in df.columns}
    for key in ("cds_code", "cdscode", "school_cds_code", "lea_cds_code"):
        if key in cols:
            return df.with_columns(pl.col(cols[key]).str.zfill(14).alias("cds"))
    county = cols.get("county_code") or cols.get("countycode")
    district = cols.get("district_code") or cols.get("districtcode")
    school = cols.get("school_code") or cols.get("schoolcode")
    if county and district and school:
        return df.with_columns(
            (
                pl.col(county).str.zfill(2)
                + pl.col(district).str.zfill(5)
                + pl.col(school).fill_null("0000000").str.zfill(7)
            ).alias("cds")
        )
    return df


def read_tab(path: Path) -> pl.DataFrame:
    raw = path.read_bytes()
    # Some CDE files (e.g. one stability year) are UTF-16; reading them as UTF-8
    # interleaves NULs into every header and value.
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff") or b"\x00" in raw[:200]:
        raw = raw.decode("utf-16").encode("utf-8")
    # A few CDE files (strat) quote numbers containing thousands separators even
    # though they are tab-delimited; polars handles the quotes, we strip commas later.
    df = pl.read_csv(
        io.BytesIO(raw),
        separator="\t",
        quote_char='"',
        null_values=NULL_TOKENS,
        infer_schema_length=0,
        encoding="utf8-lossy",
        truncate_ragged_lines=True,
    )
    df = df.rename({c: snake(c) for c in df.columns})
    return _derive_cds(df)


def read_xlsx(path: Path) -> pl.DataFrame:
    """Read the data sheet of a CDE Excel file, locating the real header row."""
    import pandas as pd

    xl = pd.ExcelFile(path)
    # Choose the sheet with the most rows whose header mentions county/district codes
    best = None
    for sheet in xl.sheet_names:
        head = xl.parse(sheet, nrows=14, header=None, dtype=str)
        header_row = None
        for i, row in head.iterrows():
            joined = " ".join(str(v) for v in row.tolist())
            if any(k in joined for k in ("County Code", "CountyCode", "CDS Code", "CDSCode")):
                header_row = i
                break
        if header_row is None:
            continue
        pdf = xl.parse(sheet, header=header_row, dtype=str)
        if best is None or len(pdf) > len(best):
            best = pdf
    if best is None:
        raise ValueError(f"no sheet with a County Code header found in {path.name}")
    best = best.replace({t: None for t in NULL_TOKENS})
    df = pl.from_pandas(best.astype("string"))
    df = df.rename({c: snake(c) for c in df.columns})
    return _derive_cds(df)


def ingest_family(family: str) -> None:
    raw_dir = RAW_DIR / family
    if not raw_dir.exists():
        return
    is_xlsx = family in XLSX_FAMILIES
    paths = sorted(p for p in raw_dir.iterdir() if p.is_file())
    for path in paths:
        try:
            if is_xlsx and path.suffix.lower() in (".xlsx", ".xls"):
                df = read_xlsx(path)
            elif not is_xlsx and path.suffix.lower() in (".txt", ".csv", ".tsv"):
                df = read_tab(path)
            else:
                continue
        except Exception as exc:  # noqa: BLE001 - report and continue
            print(f"  FAILED {family}/{path.name}: {exc}")
            continue
        df = df.with_columns(pl.lit(path.name).alias("source_file"))
        out = PARQUET_DIR / family / f"file={path.stem}"
        out.mkdir(parents=True, exist_ok=True)
        df.write_parquet(out / "data.parquet")
        print(f"  {family}/{path.name}: {len(df):,} rows, {len(df.columns)} cols")


def ingest_all() -> None:
    for family in TAB_FAMILIES + XLSX_FAMILIES:
        ingest_family(family)
