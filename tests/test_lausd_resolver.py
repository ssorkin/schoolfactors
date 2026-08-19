"""LAUSD MP25 key resolution: tiering, multi-school keys, boundary coverage."""

from __future__ import annotations

import duckdb
import polars as pl
import pytest

from schoolfactors.analysis import lausd
from schoolfactors.ingest.lausd_gis import _full_cds, _snake


def _table(con, name, df: pl.DataFrame) -> None:
    df = df.cast(pl.Utf8)  # parquet-store convention: every column nullable string
    con.register(f"{name}_src", df.to_arrow())
    con.execute(f"CREATE TABLE {name} AS SELECT * FROM {name}_src")


@pytest.fixture
def con():
    con = duckdb.connect(":memory:")
    # Two polygons: one plain, one split (suffix a) sharing keys; E 10001 has TWO
    # resident schools (primary center + elementary); E 10999 resolves only via abinfo;
    # E 10777 resolves to nothing.
    _table(
        con,
        "lausd_mp25_raw",
        pl.DataFrame(
            {
                "p_key": ["100012000130001", "100012000130001a", "109992000130001",
                          "107772000130001"],
                "split_suffix": [None, "a", None, None],
                "e_key": ["10001", "10001", "10999", "10777"],
                "m_key": ["20001"] * 4,
                "h_key": ["30001"] * 4,
                "p_e": ["10001", "10001", "10999", "10777"],
                "p_m": ["20001"] * 4,
                "p_h": ["30001"] * 4,
            }
        ),
    )
    _table(
        con,
        "lausd_codes_raw",
        pl.DataFrame(
            {
                "level": ["E", "E", "E", "M", "H"],
                "key5": ["10001", "10001", "10001", "20001", "30001"],
                "name": ["Alpha El", "Alpha Primary Ctr", "Alpha DL Magnet",
                         "Beta MS", "Gamma HS"],
                "school_id": ["2001", "2002", "2003", "3001", "4001"],
                "cds14": [
                    "19647336000001", "19647330000002", "19647336000003",
                    "19647336000004", "19647336000005",
                ],
                "lo_grd": ["2", "0", "0", "6", "9"],
                "hi_grd": ["6", "1", "6", "8", "12"],
                "by_app": [None, " ", "By Application", None, None],
            }
        ),
    )
    _table(
        con,
        "lausd_abinfo_raw",
        pl.DataFrame(
            {
                "polyid": ["109992000130001"],
                "level": ["E"],
                "long_name": ["Newzone Elementary"],
                "school_id": ["2100"],
                "cds14": ["19647336000099"],
                "lo_grd": ["0"],
                "hi_grd": ["5"],
                "by_app": [None],
            }
        ),
    )
    _table(
        con,
        "directory_raw",
        pl.DataFrame(
            {
                "cds": [
                    "19647336000001", "19647330000002", "19647336000004",
                    "19647336000005", "19647336000099", "19647336000777",
                ],
                "school": ["Alpha El", "Alpha Primary Ctr", "Beta MS", "Gamma HS",
                           "Newzone El", "Charter Nowhere"],
                "eilcode": ["ELEM", "ELEM", "INTMIDJR", "HS", "ELEM", "ELEM"],
                "eilname": ["Elementary"] * 2 + ["Middle", "High School", "Elementary",
                            "Elementary"],
                "charter": ["N", "N", "N", "N", "N", "Y"],
                "magnet": ["N"] * 6,
                "virtual": ["N"] * 6,
                "soctype": ["60"] * 6,
                "statustype": ["Active"] * 6,
                "latitude": ["34.0"] * 6,
                "longitude": ["-118.3"] * 6,
                "source_file": ["pubschls.txt"] * 6,
            }
        ),
    )
    return con


def test_resolve_keys_tiers_and_multi_school(con):
    res = lausd.resolve_keys(con)
    e1 = res.filter((pl.col("level") == "E") & (pl.col("key5") == "10001"))
    # Resident tier only: the By-Application magnet row must not appear.
    assert sorted(e1["cds"].to_list()) == ["19647330000002", "19647336000001"]
    assert set(e1["resolved_via"].to_list()) == {"codes"}
    # Primary = widest grade span (Alpha El 2-6 beats Primary Ctr 0-1? no: 4 vs 1...).
    prim = e1.filter(pl.col("primary")).to_dicts()[0]
    assert prim["cds"] == "19647336000001"  # span 4 > span 1
    # abinfo fallback for the key missing from codes.
    e9 = res.filter((pl.col("level") == "E") & (pl.col("key5") == "10999")).to_dicts()[0]
    assert e9["cds"] == "19647336000099" and e9["resolved_via"] == "abinfo"
    # Unresolved key keeps a null-cds row.
    e7 = res.filter((pl.col("level") == "E") & (pl.col("key5") == "10777")).to_dicts()[0]
    assert e7["cds"] is None
    # M and H resolve.
    assert res.filter(pl.col("level") == "M")["cds"].to_list() == ["19647336000004"]
    assert res.filter(pl.col("level") == "H")["cds"].to_list() == ["19647336000005"]


def test_polygon_table_and_split_suffix(con):
    res = lausd.resolve_keys(con)
    polys = lausd.polygon_table(con, res)
    assert len(polys) == 4
    split = polys.filter(pl.col("p_key") == "100012000130001a").to_dicts()[0]
    assert split["split_suffix"] == "a"
    assert split["e_cds"] == "19647336000001"
    assert split["e_name"] == "Alpha El"
    assert split["m_cds"] == "19647336000004"
    unresolved = polys.filter(pl.col("p_key") == "107772000130001").to_dicts()[0]
    assert unresolved["e_cds"] is None and unresolved["h_cds"] == "19647336000005"


def test_schools_without_boundary(con):
    res = lausd.resolve_keys(con)
    nb = lausd.schools_without_boundary(con, res)
    by_cds = {r["cds"]: r["has_boundary"] for r in nb.to_dicts()}
    assert by_cds["19647336000001"] is True
    assert by_cds["19647336000777"] is False  # the charter with no attendance area


def test_full_cds_padding():
    df = pl.DataFrame({"cds": ["6015705", "  ", None, "124826"]})
    out = df.with_columns(_full_cds("cds"))
    assert out["cds"].to_list() == [
        "19647336015705", None, None, "19647330124826",
    ]


def test_snake_dedupes_shape_columns():
    df = pl.DataFrame({"Shape_Area": [1.0], "Shape__Area": [2.0], "P_KEY": ["x"]})
    out = _snake(df)
    assert out.columns == ["shape_area", "shape_area_2", "p_key"]
