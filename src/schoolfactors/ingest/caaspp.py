"""Era-aware CAASPP research-file ingestion.

The Smarter Balanced research files went through four incompatible layouts ("eras").
We detect the era from each file's own header row (the published layout pages are
unreliable) and normalize everything to one schema. Values suppressed at the source
(n<11 → '*' or blank) stay null, with the raw token preserved via `suppressed` flags
computed at query time (null students_tested with non-null enrollment, etc.).

Unified grain: cds × test_year × test_id × student_group_id × grade.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import polars as pl

from schoolfactors.paths import PARQUET_DIR, RAW_DIR

# Unified column name -> per-era source column (None = not present in that era).
# Era A = 2015-16 comma/quoted, B = 2017-19 comma/quoted, C = 2021-23 caret,
# D = 2024-25 caret 69-field.
UNIFIED = {
    "county_code": {"A": "County Code", "B": "County Code", "C": "County Code", "D": "County Code"},
    "district_code": {
        "A": "District Code",
        "B": "District Code",
        "C": "District Code",
        "D": "District Code",
    },
    "school_code": {"A": "School Code", "B": "School Code", "C": "School Code", "D": "School Code"},
    "test_year": {"A": "Test Year", "B": "Test Year", "C": "Test Year", "D": "Test Year"},
    "student_group_id": {
        "A": "Subgroup ID",
        "B": "Subgroup ID",
        "C": "Student Group ID",
        "D": "Student Group ID",
    },
    "test_id": {"A": "Test Id", "B": "Test Id", "C": "Test ID", "D": "Test ID"},
    "grade": {"A": "Grade", "B": "Grade", "C": "Grade", "D": "Grade"},
    "students_enrolled": {
        "A": "CAASPP Reported Enrollment",
        "B": "CAASPP Reported Enrollment",
        "C": "Students Enrolled",
        "D": "Total Students Enrolled",
    },
    "students_tested": {
        "A": "Students Tested",
        "B": "Students Tested",
        "C": "Students Tested",
        "D": "Total Students Tested",
    },
    "students_with_scores": {
        "A": "Students with Scores",
        "B": "Students with Scores",
        "C": "Students with Scores",
        "D": "Total Students Tested with Scores",
    },
    "mean_scale_score": {
        "A": "Mean Scale Score",
        "B": "Mean Scale Score",
        "C": "Mean Scale Score",
        "D": "Mean Scale Score",
    },
    "pct_exceeded": {
        "A": "Percentage Standard Exceeded",
        "B": "Percentage Standard Exceeded",
        "C": "Percentage Standard Exceeded",
        "D": "Percentage Standard Exceeded",
    },
    "pct_met": {
        "A": "Percentage Standard Met",
        "B": "Percentage Standard Met",
        "C": "Percentage Standard Met",
        "D": "Percentage Standard Met",
    },
    "pct_met_and_above": {
        "A": "Percentage Standard Met and Above",
        "B": "Percentage Standard Met and Above",
        "C": "Percentage Standard Met and Above",
        "D": "Percentage Standard Met and Above",
    },
    "pct_nearly_met": {
        "A": "Percentage Standard Nearly Met",
        "B": "Percentage Standard Nearly Met",
        "C": "Percentage Standard Nearly Met",
        "D": "Percentage Standard Nearly Met",
    },
    "pct_not_met": {
        "A": "Percentage Standard Not Met",
        "B": "Percentage Standard Not Met",
        "C": "Percentage Standard Not Met",
        "D": "Percentage Standard Not Met",
    },
    "type_id": {"A": None, "B": None, "C": "Type ID", "D": "Type ID"},
    "count_met_and_above": {"A": None, "B": None, "C": None, "D": "Count Standard Met and Above"},
}

INT_COLS = [
    "test_year",
    "student_group_id",
    "test_id",
    "grade",
    "students_enrolled",
    "students_tested",
    "students_with_scores",
    "type_id",
    "count_met_and_above",
]
FLOAT_COLS = [
    "mean_scale_score",
    "pct_exceeded",
    "pct_met",
    "pct_met_and_above",
    "pct_nearly_met",
    "pct_not_met",
]


def detect_era(header_line: str) -> tuple[str, str]:
    """Return (era, delimiter) from a data file's header row."""
    if "^" in header_line:
        n = header_line.count("^") + 1
        return ("D", "^") if n > 40 else ("C", "^")
    if "Total CAASPP Enrollment" in header_line:
        return ("A", ",")
    return ("B", ",")


def _read_txt(raw: bytes, era: str, sep: str) -> pl.DataFrame:
    df = pl.read_csv(
        io.BytesIO(raw),
        separator=sep,
        quote_char='"' if sep == "," else None,
        null_values=["*", "", "N/A", "NA"],
        infer_schema_length=0,  # read everything as str; we cast explicitly
        encoding="utf8-lossy",
    )
    mapping = {}
    for unified, per_era in UNIFIED.items():
        src = per_era[era]
        if src is not None and src in df.columns:
            mapping[src] = unified
    df = df.select(list(mapping.keys())).rename(mapping)

    casts = []
    for c in INT_COLS:
        if c in df.columns:
            casts.append(pl.col(c).cast(pl.Int64, strict=False))
    for c in FLOAT_COLS:
        if c in df.columns:
            casts.append(pl.col(c).cast(pl.Float64, strict=False))
    df = df.with_columns(casts)

    # 2015-16 percentages are integers at source; keep as float, note the precision
    # difference in known_issues rather than pretending decimals exist.
    df = df.with_columns(
        pl.col("county_code").str.zfill(2),
        pl.col("district_code").str.zfill(5),
        pl.col("school_code").str.zfill(7),
    )
    df = df.with_columns(
        (pl.col("county_code") + pl.col("district_code") + pl.col("school_code")).alias("cds"),
        pl.lit(era).alias("era"),
    )
    # Ensure schema-stable output across eras
    for c in ("type_id", "count_met_and_above"):
        if c not in df.columns:
            df = df.with_columns(pl.lit(None, dtype=pl.Int64).alias(c))
    return df


def _read_entities(raw: bytes) -> pl.DataFrame:
    text = raw.decode("utf-8", "replace")
    sep = "^" if "^" in text.splitlines()[0] else ","
    df = pl.read_csv(
        io.BytesIO(raw),
        separator=sep,
        quote_char='"' if sep == "," else None,
        null_values=["*", ""],
        infer_schema_length=0,
        encoding="utf8-lossy",
    )
    ren = {
        "County Code": "county_code",
        "District Code": "district_code",
        "School Code": "school_code",
        "Test Year": "test_year",
        "Type ID": "type_id",
        "County Name": "county_name",
        "District Name": "district_name",
        "School Name": "school_name",
        "Zip Code": "zip_code",
    }
    df = df.select([c for c in ren if c in df.columns]).rename(
        {k: v for k, v in ren.items() if k in df.columns}
    )
    df = df.with_columns(
        pl.col("county_code").str.zfill(2),
        pl.col("district_code").str.zfill(5),
        pl.col("school_code").str.zfill(7),
        pl.col("test_year").cast(pl.Int64, strict=False),
    )
    if "type_id" in df.columns:
        df = df.with_columns(pl.col("type_id").cast(pl.Int64, strict=False))
    else:
        # 2015/16 delimited entities files carry no Type ID; derive what the CDS
        # structure itself encodes (school vs district vs county vs state).
        df = df.with_columns(
            pl.when(pl.col("school_code") != "0000000")
            .then(7)
            .when(pl.col("district_code") != "00000")
            .then(6)
            .when(pl.col("county_code") != "00")
            .then(5)
            .otherwise(4)
            .cast(pl.Int64)
            .alias("type_id")
        )
    for c in ("county_name", "district_name", "school_name", "zip_code"):
        if c not in df.columns:
            df = df.with_columns(pl.lit(None, dtype=pl.String).alias(c))
    return df.with_columns(
        (pl.col("county_code") + pl.col("district_code") + pl.col("school_code")).alias("cds")
    )


def ingest_year_zip(zip_path: Path) -> tuple[int, int]:
    """Ingest one sb_ca{year}_all_csv zip → parquet. Returns (year, fact rows)."""
    z = zipfile.ZipFile(zip_path)
    names = z.namelist()
    data_name = next(n for n in names if "entities" not in n.lower())
    ent_name = next((n for n in names if "entities" in n.lower()), None)

    raw = z.read(data_name)
    header = raw[:8192].decode("utf-8", "replace").splitlines()[0]
    era, sep = detect_era(header)
    df = _read_txt(raw, era, sep)
    df = df.with_columns(pl.lit(zip_path.name).alias("source_file"))

    year = int(df["test_year"][0])
    out = PARQUET_DIR / "caaspp_sb" / f"year={year}"
    out.mkdir(parents=True, exist_ok=True)
    df.write_parquet(out / "data.parquet")

    if ent_name:
        ent = _read_entities(z.read(ent_name))
        eout = PARQUET_DIR / "caaspp_entities" / f"year={year}"
        eout.mkdir(parents=True, exist_ok=True)
        ent.write_parquet(eout / "data.parquet")

    return year, len(df)


def ingest_all() -> None:
    raw_dir = RAW_DIR / "caaspp"
    zips = sorted(raw_dir.glob("sb_ca*_all_csv_v*.zip"))
    if not zips:
        print("no CAASPP zips found — run `sf acquire --dataset caaspp` first")
        return
    import re

    for zp in zips:
        m = re.match(r"sb_ca(\d{4})_", zp.name)
        if m and (PARQUET_DIR / "caaspp_sb" / f"year={m.group(1)}" / "data.parquet").exists():
            print(f"  caaspp {m.group(1)}: already ingested, skipping")
            continue
        year, rows = ingest_year_zip(zp)
        print(f"  caaspp {year}: {rows:,} rows")

    # Reference tables
    for name, table in (("Tests.zip", "tests"), ("StudentGroups.zip", "student_groups")):
        path = raw_dir / name
        if path.exists():
            z = zipfile.ZipFile(path)
            member = z.namelist()[0]
            df = pl.read_csv(
                io.BytesIO(z.read(member)),
                separator="^",
                infer_schema_length=0,
                encoding="utf8-lossy",
            )
            out = PARQUET_DIR / f"caaspp_{table}"
            out.mkdir(parents=True, exist_ok=True)
            df.write_parquet(out / "data.parquet")
            print(f"  caaspp reference {table}: {len(df)} rows")
