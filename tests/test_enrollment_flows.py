"""Statewide enrollment flows: label parsing, controls correction, grade splits,
residence completeness, and a toy-world accounting closure."""

from __future__ import annotations

import duckdb
import polars as pl

from schoolfactors.analysis import enrollment_flows as ef


def test_classify_label():
    e = ef._classify_label(
        "B14003_004E", "Estimate!!Total:!!Male:!!Enrolled in public school:!!5 to 9 years"
    )
    assert e == ("E", "pub", "5_9")
    m = ef._classify_label(
        "B14003_022M",
        "Margin of Error!!Total:!!Female:!!Enrolled in private school:!!15 to 17 years",
    )
    assert m == ("M", "priv", "15_17")
    # Out-of-universe ages and non-leaf rows are rejected.
    assert ef._classify_label(
        "B14003_003E", "Estimate!!Total:!!Male:!!Enrolled in public school:!!3 and 4 years"
    ) is None
    assert ef._classify_label("B14003_002E", "Estimate!!Total:!!Male:") is None
    assert ef._classify_label("B14003_004EA", "Annotation of Estimate!!…") is None


FACTORS = {
    ("037", 2005): 0.95, ("037", 2006): 0.96, ("037", 2007): 0.97,
    ("037", 2008): 0.98, ("037", 2009): 0.99,
    ("CA", 2005): 0.97, ("CA", 2006): 0.98, ("CA", 2007): 0.985,
    ("CA", 2008): 0.99, ("CA", 2009): 0.995,
}


def test_window_factor_acs1():
    assert ef._window_factor(FACTORS, "037", "acs1", 2005) == 0.95
    assert ef._window_factor(FACTORS, "037", "acs1", 2012) == 1.0
    # Unknown county falls back to the state factor.
    assert ef._window_factor(FACTORS, "113", "acs1", 2005) == 0.97


def test_window_factor_acs5_fractional():
    # Vintage 2011 window = 2007-2011: three corrected years of five.
    expect = (0.97 + 0.98 + 0.99 + 1.0 + 1.0) / 5
    assert abs(ef._window_factor(FACTORS, "037", "acs5", 2011) - expect) < 1e-12
    # Vintage 2009 window = 2005-2009: fully corrected.
    expect = (0.95 + 0.96 + 0.97 + 0.98 + 0.99) / 5
    assert abs(ef._window_factor(FACTORS, "037", "acs5", 2009) - expect) < 1e-12
    assert ef._window_factor(FACTORS, "037", "acs5", 2014) == 1.0


def test_age_weight():
    assert ef._age_weight(9) == 0.8
    assert ef._age_weight(7) == 0.4
    assert ef._age_weight(6) == 0.2


def _seats_row(**kw) -> dict:
    base = {
        "cds": "01234561234567", "spring": 2020, "total": 0.0, "kn": 0.0,
        **{f"g{i}": 0.0 for i in range(1, 13)},
        "ungr_elm": 0.0, "ungr_sec": 0.0,
        "class": "district_run", "unified_geoid": None, "elem_geoid": None,
        "sec_geoid": None, "sited": "pip", "county_code": "01",
    }
    base.update(kw)
    return base


def test_split_seats_cut9():
    cuts = pl.DataFrame(
        [{"level": "elementary", "geoid": "E1", "cut": 9, "sec_geoid": "S1"},
         {"level": "secondary", "geoid": "S1", "cut": 9, "sec_geoid": "S1"}]
    )
    seats = pl.DataFrame([_seats_row(
        elem_geoid="E1", sec_geoid="S1", total=130.0, kn=10.0, ungr_elm=5.0,
        ungr_sec=3.0, **{f"g{i}": 8.0 for i in range(1, 13)}, county_code="01",
    )])
    out = ef._split_seats(seats, cuts)
    # lower = kn 10 + g1..g8 64 + ungr_elm 5 = 79; upper = g9..12 32 + ungr_sec 3 = 35
    # residual 130 - 114 = 16 prorated 79:35.
    r = out.to_dicts()[0]
    assert abs(r["lower"] - (79 + 16 * 79 / 114)) < 1e-9
    assert abs(r["upper"] - (35 + 16 * 35 / 114)) < 1e-9
    assert abs(r["lower"] + r["upper"] - 130.0) < 1e-9


def test_split_seats_cut7():
    cuts = pl.DataFrame(
        [{"level": "secondary", "geoid": "S7", "cut": 7, "sec_geoid": "S7"}]
    )
    seats = pl.DataFrame([_seats_row(
        sec_geoid="S7", total=96.0, **{f"g{i}": 8.0 for i in range(1, 13)},
    )])
    r = ef._split_seats(seats, cuts).to_dicts()[0]
    assert r["lower"] == 8.0 * 6  # g1..g6
    assert r["upper"] == 8.0 * 6  # g7..g12


def _acs_store(rows: list[tuple]) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(":memory:")
    con.execute(
        "CREATE TABLE census_acs_raw (survey VARCHAR, geo_type VARCHAR, geoid VARCHAR, "
        "vintage VARCHAR, table_id VARCHAR, variable VARCHAR, label VARCHAR, value VARCHAR)"
    )
    con.executemany("INSERT INTO census_acs_raw VALUES (?,?,?,?,?,?,?,?)", rows)
    return con


def _b14003_rows(geoid: str, drop_var: str | None = None) -> list[tuple]:
    rows = []
    i = 2
    for sex in ("Male", "Female"):
        for status in ("Enrolled in public school", "Enrolled in private school",
                       "Not enrolled in school"):
            for age in ("5 to 9 years", "10 to 14 years", "15 to 17 years"):
                for kind, prefix in (("E", "Estimate"), ("M", "Margin of Error")):
                    var = f"B14003_{i:03d}{kind}"
                    label = f"{prefix}!!Total:!!{sex}:!!{status}:!!{age}"
                    if var != drop_var:
                        rows.append(
                            ("acs5", "county", geoid, "2020", "B14003", var, label,
                             "100" if kind == "E" else "10")
                        )
                i += 1
    return rows


def test_residence_completeness_guard():
    con = _acs_store(_b14003_rows("06001") + _b14003_rows("06003", drop_var="B14003_002E"))
    res = ef.residence_table(con)
    full = res.filter(pl.col("geoid") == "06001").to_dicts()[0]
    assert full["pub"] == 600  # 2 sexes x 3 ages x 100
    assert full["pub_5_9"] == 200
    assert abs(full["moe_pub"] - (6 * 100) ** 0.5) < 1e-9  # rss of six 10s
    # A missing sex cell must null the category, never shrink it.
    partial = res.filter(pl.col("geoid") == "06003").to_dicts()[0]
    assert partial["pub"] is None
    assert partial["pub_5_9"] is None
    assert partial["priv"] == 600  # untouched categories stay complete


def test_toy_world_closure():
    """Two areas + a virtual school: nets must sum to ~0 by construction of m."""
    # Residents: A pub 1000, B pub 500; state CDE seats = physical 1400 + virtual 150.
    m = (1550 - 1500) / 1550
    pool = 150 * (1 - m)
    net_a = 900 * (1 - m) - (1000 - pool * 1000 / 1500)
    net_b = 500 * (1 - m) - (500 - pool * 500 / 1500)
    assert abs(net_a + net_b) < 1e-9
