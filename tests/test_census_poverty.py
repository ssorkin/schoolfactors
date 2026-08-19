"""Census B17024 pipeline: label-based bin selection, ingest reshape, district join."""

from __future__ import annotations

import json

import duckdb
import polars as pl
import pytest

from schoolfactors.analysis import census_poverty
from schoolfactors.analysis.census_poverty import P185_BINS, SCHOOL_AGES, p185_variables
from schoolfactors.ingest import census as census_ingest

ALL_BINS = [
    *P185_BINS,
    "1.85 to 1.99",
    "2.00 to 2.99",
    "3.00 to 3.99",
    "4.00 to 4.99",
    "5.00 and over",
]
ALL_AGES = ["Under 6 years", *SCHOOL_AGES, "18 to 24 years", "75 years and over"]


def _labels() -> dict[str, str]:
    """Synthetic B17024-shaped labels: total, age totals, age x bin, plus M/EA noise."""
    labels = {"B17024_001E": "Estimate!!Total:"}
    i = 2
    for age in ALL_AGES:
        labels[f"B17024_{i:03d}E"] = f"Estimate!!Total:!!{age}:"
        labels[f"B17024_{i:03d}M"] = f"Margin of Error!!Total:!!{age}:"
        i += 1
        for b in ALL_BINS:
            labels[f"B17024_{i:03d}E"] = f"Estimate!!Total:!!{age}:!!{b}"
            labels[f"B17024_{i:03d}EA"] = f"Annotation of Estimate!!Total:!!{age}:!!{b}"
            i += 1
    return labels


def test_p185_variable_selection():
    num, den = p185_variables(_labels())
    assert len(num) == len(P185_BINS) * len(SCHOOL_AGES) == 14
    assert len(den) == len(SCHOOL_AGES) == 2
    labels = _labels()
    for var in num:
        age, bin_ = [p.rstrip(":") for p in labels[var].split("!!")][2:4]
        assert age in SCHOOL_AGES and bin_ in P185_BINS
    for var in den:
        assert labels[var].rstrip(":").split("!!")[-1] in SCHOOL_AGES
    # No margins, annotations, out-of-age, or over-1.85 bins slip through.
    assert all(v.endswith("E") for v in num + den)


def test_ingest_reshapes_to_long_with_geoid(tmp_path, monkeypatch):
    monkeypatch.setattr(census_ingest, "RAW_DIR", tmp_path)
    raw = tmp_path / "census"
    raw.mkdir()
    (raw / "acs5_2023_groups_b17024.json").write_text(
        json.dumps({"variables": {"B17024_001E": {"label": "Estimate!!Total:"}}})
    )
    payload = [
        ["NAME", "GEO_ID", "B17024_001E", "B17024_001M", "B17024_001EA",
         "state", "school district (unified)"],
        ["Los Angeles Unified", "9700000US0622710", "700000", "1234", None, "06", "22710"],
    ]
    path = raw / "acs5_2023_b17024_sd_unified.json"
    path.write_text(json.dumps(payload))

    df = census_ingest.ingest_file(path)
    assert df is not None
    # E and M variables kept, EA annotation dropped.
    assert sorted(df["variable"].to_list()) == ["B17024_001E", "B17024_001M"]
    row = df.filter(pl.col("variable") == "B17024_001E").to_dicts()[0]
    assert row["geoid"] == "0622710"
    assert row["geo_type"] == "sd_unified"
    assert row["vintage"] == "2023"
    assert row["label"] == "Estimate!!Total:"
    assert row["value"] == "700000"
    # Groups metadata files are not data files.
    assert census_ingest.ingest_file(raw / "acs5_2023_groups_b17024.json") is None


def test_blockgroup_geoid_from_parts():
    row = {"state": "06", "county": "037", "tract": "101110", "block group": "2"}
    assert census_ingest._geoid(row, "bg_06037") == "060371011102"


@pytest.fixture
def fixture_con(tmp_path, monkeypatch):
    """In-memory DuckDB with miniature census_acs_raw / directory_raw / frpm_raw."""
    monkeypatch.setattr(census_poverty, "OUT_PARQUET", tmp_path / "census_frpm.parquet")
    labels = _labels()
    num, den = p185_variables(labels)
    rows = []
    # District A: 13 poverty-bin vars of 10 + one ACS sentinel; age totals 300 + 260.
    for i, var in enumerate(num):
        rows.append(("0611111", var, "-666666666" if i == 0 else "10"))
    rows.append(("0611111", den[0], "300"))
    rows.append(("0611111", den[1], "260"))
    # District C exists in ACS but not in FRPM (should not break the join).
    rows.append(("0699999", den[0], "50"))
    acs = pl.DataFrame(
        {
            "vintage": ["2023"] * len(rows),
            "table_id": ["B17024"] * len(rows),
            "geo_type": ["sd_unified"] * len(rows),
            "geoid": [r[0] for r in rows],
            "geo_name": ["District A"] * len(rows),
            "variable": [r[1] for r in rows],
            "label": [labels[r[1]] for r in rows],
            "value": [r[2] for r in rows],
        }
    )
    directory = pl.DataFrame(
        {
            "cds": ["01000011234567", "01000010000000", "02000020000000"],
            "ncesdist": ["0611111", "0611111", None],
        }
    )
    frpm = pl.DataFrame(
        {
            "cds": ["01000011234567", "01000017654321", "02000021111111", "03000031111111"],
            "school_code": ["1234567", "7654321", "1111111", "1111111"],
            "district_name": ["District A", "District A", "District B", "COE C"],
            "district_type": ["Unified School District"] * 3
            + ["County Office of Education (COE)"],
            "academic_year": ["2024-2025"] * 4,
            "frpm_count_ages_5_17": ["117", "117", "40", "10"],
            "enrollment_ages_5_17": ["252", "252", "80", "20"],
        }
    )
    con = duckdb.connect(":memory:")
    for name, df in (("census_acs_raw", acs), ("directory_raw", directory), ("frpm_raw", frpm)):
        con.register(f"{name}_src", df.to_arrow())
        con.execute(f"CREATE TABLE {name} AS SELECT * FROM {name}_src")
    return con


def test_build_district_table(fixture_con):
    df = census_poverty.build_district_table(fixture_con)
    assert df is not None and census_poverty.OUT_PARQUET.exists()
    a = df.filter(pl.col("cds") == "01000010000000").to_dicts()[0]
    # Sentinel excluded: 13 x 10 = 130 poor residents of 560 children.
    assert a["p185_count"] == 130
    assert a["child_pop"] == 560
    assert a["frpm_count"] == 234
    assert a["frpm"] == pytest.approx(234 / 504)
    assert a["p185"] == pytest.approx(130 / 560)
    # PPIC-style RATE ratio: FRPM share of enrolled over P185 share of residents.
    assert a["ratio"] == pytest.approx((234 / 504) / (130 / 560))
    # District B has no ncesdist: FRPM present, census side null.
    b = df.filter(pl.col("cds") == "02000020000000").to_dicts()[0]
    assert b["frpm_count"] == 40 and b["p185_count"] is None
    # The county office of education is outside the comparison universe entirely.
    assert len(df.filter(pl.col("cds") == "03000030000000")) == 0
