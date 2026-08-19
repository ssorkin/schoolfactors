"""Block-group -> attendance-polygon apportionment on a hand-computed fixture."""

from __future__ import annotations

import duckdb
import polars as pl
import pytest

from schoolfactors.analysis import lausd_geo

# 2 block groups, 6 blocks, 2 polygons, hand-computed expectations:
# BG1 (pop 100): 60 in P1, 20 in P2, 20 outside -> share P1=0.6, P2=0.2
# BG2 (pop 100): all 100 in P2 -> share 1.0
BLOCKS = pl.DataFrame(
    {
        "geoid20": [
            "060370001001001", "060370001001002",  # BG1 in P1
            "060370001001003",                       # BG1 in P2
            "060370001001004",                       # BG1 outside
            "060370002002001", "060370002002002",   # BG2 in P2
        ],
        "pop20": ["30", "30", "20", "20", "60", "40"],
    }
)
XWALK = pl.DataFrame(
    {
        "geoid20": [
            "060370001001001", "060370001001002", "060370001001003",
            "060370002002001", "060370002002002",
        ],
        "p_key": ["P1", "P1", "P2", "P2", "P2"],
        "pop20": [30, 30, 20, 60, 40],
    }
)

C17002_BINS = ["Under .50", ".50 to .99", "1.00 to 1.24", "1.25 to 1.49",
               "1.50 to 1.84", "1.85 to 1.99", "2.00 and over"]


def _acs_rows() -> pl.DataFrame:
    rows = []

    def add(bg, table, var, label, value):
        rows.append(
            {
                "vintage": "2023",
                "table_id": table,
                "geo_type": "bg_06037",
                "geoid": bg,
                "geo_name": bg,
                "variable": var,
                "label": label,
                "value": str(value),
            }
        )

    # C17002: BG1 universe 200, 10 per under-1.85 bin (50 poor); BG2 universe 100,
    # 16 per under bin (80 poor).
    for bg, total, per_bin in (("060370001001", 200, 10), ("060370002002", 100, 16)):
        add(bg, "C17002", "C17002_001E", "Estimate!!Total:", total)
        for i, b in enumerate(C17002_BINS):
            v = per_bin if b in lausd_geo.C17002_UNDER_185 else 0
            add(bg, "C17002", f"C17002_{i + 2:03d}E", f"Estimate!!Total:!!{b}", v)
    # B03002: totals/hispanic/white/black/asian.
    spec = {
        "060370001001": (200, 100, 50, 30, 10),
        "060370002002": (100, 80, 5, 5, 5),
    }
    for bg, (total, his, wht, blk, asn) in spec.items():
        add(bg, "B03002", "B03002_001E", "Estimate!!Total:", total)
        add(bg, "B03002", "B03002_012E", "Estimate!!Total:!!Hispanic or Latino:", his)
        for var, race, v in (
            ("B03002_003E", "White alone", wht),
            ("B03002_004E", "Black or African American alone", blk),
            ("B03002_006E", "Asian alone", asn),
        ):
            add(bg, "B03002", var,
                f"Estimate!!Total:!!Not Hispanic or Latino:!!{race}", v)
    return pl.DataFrame(rows)


def test_bg_shares():
    shares = lausd_geo.bg_shares(XWALK, BLOCKS)
    got = {(r["bg_geoid"], r["p_key"]): r["share"] for r in shares.to_dicts()}
    assert got[("060370001001", "P1")] == pytest.approx(0.6)
    assert got[("060370001001", "P2")] == pytest.approx(0.2)
    assert got[("060370002002", "P2")] == pytest.approx(1.0)
    assert ("060370001001", "outside") not in got


def test_polygon_demographics(tmp_path, monkeypatch):
    monkeypatch.setattr(lausd_geo, "PARQUET_DIR", tmp_path)
    con = duckdb.connect(":memory:")
    con.register("acs_src", _acs_rows().to_arrow())
    con.execute("CREATE TABLE census_acs_raw AS SELECT * FROM acs_src")
    shares = lausd_geo.bg_shares(XWALK, BLOCKS)

    demo = lausd_geo.polygon_demographics(con, shares)
    assert demo is not None
    p1 = demo.filter(pl.col("p_key") == "P1").to_dicts()[0]
    p2 = demo.filter(pl.col("p_key") == "P2").to_dicts()[0]
    # P1 = 0.6 x BG1: universe 120, poor 30.
    assert p1["pop20"] == 60
    assert p1["pov_universe"] == pytest.approx(120)
    assert p1["pov_under185"] == pytest.approx(30)
    assert p1["p185"] == pytest.approx(0.25)
    assert p1["share_his"] == pytest.approx(0.5)
    assert p1["share_wht"] == pytest.approx(0.25)
    assert p1["share_blk"] == pytest.approx(0.15)
    assert p1["share_asn"] == pytest.approx(0.05)
    assert p1["share_oth"] == pytest.approx(0.05)
    # P2 = 0.2 x BG1 + 1.0 x BG2: universe 140, poor 90.
    assert p2["pop20"] == 120
    assert p2["p185"] == pytest.approx(90 / 140)
    assert p2["share_his"] == pytest.approx(100 / 140)
    assert p2["share_oth"] == pytest.approx(7 / 140)


def test_simplify_round_trip_valid():
    import shapely
    from shapely.geometry import mapping, shape

    # Two adjacent squares sharing an edge; simplification must keep both valid and
    # non-empty with the shared border intact.
    fc = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"key": k},
                "geometry": mapping(shapely.box(x, 0.0, x + 0.01, 0.01)),
            }
            for k, x in (("A", 0.0), ("B", 0.01))
        ],
    }
    out = lausd_geo.simplify_feature_collection(fc, epsilon=1e-5)
    assert len(out["features"]) == 2
    for f in out["features"]:
        g = shape(f["geometry"])
        assert shapely.is_valid(g) and not g.is_empty
