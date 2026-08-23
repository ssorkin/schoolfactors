"""Statewide district geometry: point-in-polygon siting, grade cuts, adjacency."""

from __future__ import annotations

import duckdb
import pytest
from shapely.geometry import box

from schoolfactors.analysis import enrollment_geo as eg

# Synthetic tiling in valid CA coordinates: a unified district on the west,
# an elementary district on the east with a secondary district over it.
U = box(-120.0, 36.0, -119.0, 37.0)
E1 = box(-119.0, 36.0, -118.5, 37.0)
E2 = box(-118.5, 36.0, -118.0, 37.0)
S = box(-119.0, 36.0, -118.0, 37.0)

GEO = {
    "unified": (["U1"], [U], [{"geoid": "U1", "name": "U", "lograde": "KG",
                               "higrade": "12", "lat": 36.5, "lon": -119.5}]),
    "elementary": (
        ["E1", "E2"], [E1, E2],
        [{"geoid": "E1", "name": "E1", "lograde": "KG", "higrade": "06"},
         {"geoid": "E2", "name": "E2", "lograde": "KG", "higrade": "06"}],
    ),
    "secondary": (["S1"], [S], [{"geoid": "S1", "name": "S", "lograde": "07",
                                 "higrade": "12"}]),
}


@pytest.fixture(autouse=True)
def _tmp_parquets(tmp_path, monkeypatch):
    monkeypatch.setattr(eg, "SITING_PARQUET", tmp_path / "siting.parquet")
    monkeypatch.setattr(eg, "CUTS_PARQUET", tmp_path / "cuts.parquet")
    monkeypatch.setattr(eg, "ADJACENCY_PARQUET", tmp_path / "adjacency.parquet")


def test_area_grade_cuts_inherit_from_secondary():
    cuts = eg.area_grade_cuts(GEO)
    d = {(r["level"], r["geoid"]): r for r in cuts.to_dicts()}
    assert d[("secondary", "S1")]["cut"] == 7
    assert d[("elementary", "E1")]["cut"] == 7
    assert d[("elementary", "E1")]["sec_geoid"] == "S1"
    assert d[("elementary", "E2")]["cut"] == 7


def _directory(rows: list[tuple]) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(":memory:")
    con.execute(
        "CREATE TABLE directory_raw (cds VARCHAR, latitude VARCHAR, longitude VARCHAR, "
        "ncesdist VARCHAR)"
    )
    con.executemany("INSERT INTO directory_raw VALUES (?,?,?,?)", rows)
    return con


def test_site_schools_pip_rescue_crosswalk():
    con = _directory(
        [
            # In the unified district.
            ("01000010000001", "36.5", "-119.5", "1234567"),
            # In elementary E1 (and therefore secondary S1).
            ("02000020000002", "36.5", "-118.75", "7654321"),
            # Just outside every polygon (west of U by ~0.005 deg): rescued.
            ("03000030000003", "36.5", "-120.005", "1111111"),
            # No coordinates; ncesdist points at the unified district.
            ("04000040000004", None, None, "0000U1"),
            # No coordinates, unknown district: unsited.
            ("05000050000005", None, None, ""),
        ]
    )
    # ncesdist is lpad-ed to 7 chars: "0000U1" -> "00000U1"; make U1 match that.
    geo = {
        "unified": ((["00000U1"]), [U], GEO["unified"][2]),
        "elementary": GEO["elementary"],
        "secondary": GEO["secondary"],
    }
    sited = eg.site_schools(con, geo)
    d = {r["cds"]: r for r in sited.to_dicts()}
    assert d["01000010000001"]["unified_geoid"] == "00000U1"
    assert d["01000010000001"]["sited"] == "pip"
    assert d["02000020000002"]["elem_geoid"] == "E1"
    assert d["02000020000002"]["sec_geoid"] == "S1"
    assert d["03000030000003"]["sited"] == "nearest"
    assert d["03000030000003"]["unified_geoid"] == "00000U1"
    assert d["04000040000004"]["sited"] == "crosswalk"
    assert d["04000040000004"]["unified_geoid"] == "00000U1"
    assert d["05000050000005"]["sited"] is None


def test_adjacency_bands():
    adj = eg.district_adjacency(GEO)
    pairs = {(r["geoid"], r["neighbor"], r["band"]) for r in adj.to_dicts()}
    # k8 partition: U1 touches E1, E1 touches E2; U1 does not touch E2.
    assert ("U1", "E1", "k8") in pairs
    assert ("E1", "E2", "k8") in pairs
    assert ("U1", "E2", "k8") not in pairs
    # hs partition: U1 touches S1.
    assert ("U1", "S1", "hs") in pairs
