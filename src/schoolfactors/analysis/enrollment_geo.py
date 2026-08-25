"""Statewide school-district geometry: school siting, grade cuts, adjacency, web shapes.

The statewide enrollment flow model (analysis/enrollment_flow_model.md) attributes each
physical school's seats to the district AREA it sits in, regardless of authorizer. The
state is tiled two ways by the TIGER/ACS school-district summary levels:

- elementary-grades partition: unified districts + elementary districts
- high-school-grades partition: unified districts + secondary districts

Secondary districts include NCES "pseudo" districts (FUNCSTAT F, named
"Parent District (9-12)") for territory where a real district serves only a grade
range. They are real ACS observation units, but the district's seats all sit on the
parent's node, so left as standalone nodes they trade phantom flows with their own
parent (Perris UHSD showed -39%/+158% between its two polygons). pseudo_parent_map()
resolves each to its parent (exact TIGER-name match, geometric tie-break for
same-named districts); the flow model folds their residents and seats into the
parent node, adjacency and web boundaries carry the parent geoid. The only features
dropped are the "School District Not Defined" placeholder (unified layer) — its
territory is exactly the elementary/secondary tiling. ACS additionally publishes a
Remainder-of-California row (0699999) per summary level with no TIGER geometry;
closure checks use it, displays drop it.

The grade boundary between the two partitions is NOT uniformly K-8/9-12: each
secondary district's LOGRADE (9, 7, or 6) defines the cut for its territory, and the
elementary districts under it inherit that cut. Age-band bridging in
enrollment_flows.py uses the same per-area cut.
"""

from __future__ import annotations

import json
import re

import duckdb
import polars as pl

from schoolfactors.paths import DUCKDB_PATH, PARQUET_DIR, RAW_DIR

TIGER_DIR = RAW_DIR / "tiger"
SITING_PARQUET = PARQUET_DIR / "analysis" / "enrollment_school_siting.parquet"
CUTS_PARQUET = PARQUET_DIR / "analysis" / "enrollment_area_cuts.parquet"
ADJACENCY_PARQUET = PARQUET_DIR / "analysis" / "enrollment_adjacency.parquet"
PSEUDO_PARQUET = PARQUET_DIR / "analysis" / "enrollment_pseudo_areas.parquet"

# TIGER names pseudo grade-range areas "Parent District Name (9-12)".
PSEUDO_SUFFIX_RE = re.compile(r"\s*\(\d+[^)]*\)\s*$")

LEVELS = ("unified", "elementary", "secondary")
NOT_DEFINED = "School District Not Defined"
# Rescue radius for coastal-precision misses, in degrees (~2 km).
NEAREST_DEG = 0.02
DEFAULT_CUT = 9  # lowest secondary grade when no overlaying secondary district exists


def tiger_available() -> bool:
    return all((TIGER_DIR / f"tiger_sd_{lvl}_acs2024.geojson").exists() for lvl in LEVELS)


def load_district_geometries(level: str) -> tuple[list[str], list, list[dict]]:
    """(geoids, shapely geometries, properties) for one TIGER summary level, WGS84.

    Drops the "School District Not Defined" placeholder; keeps pseudo secondary
    districts (they carry ACS estimates). Properties keep name, grade range, and
    the TIGER internal-point centroid.
    """
    from shapely.geometry import shape

    doc = json.loads((TIGER_DIR / f"tiger_sd_{level}_acs2024.geojson").read_text())
    geoids, geoms, props = [], [], []
    for f in doc["features"]:
        p = f["properties"]
        if p.get("NAME") == NOT_DEFINED:
            continue
        geoids.append(str(p["GEOID"]))
        geoms.append(shape(f["geometry"]))
        props.append(
            {
                "geoid": str(p["GEOID"]),
                "name": p.get("BASENAME") or p.get("NAME"),
                "lograde": p.get("LOGRADE"),
                "higrade": p.get("HIGRADE"),
                "funcstat": p.get("FUNCSTAT"),
                "lat": float(p["CENTLAT"]) if p.get("CENTLAT") else None,
                "lon": float(p["CENTLON"]) if p.get("CENTLON") else None,
            }
        )
    return geoids, geoms, props


def pseudo_parent_map(
    geo: dict[str, tuple[list[str], list, list[dict]]] | None = None,
) -> dict[str, tuple[str, str]]:
    """pseudo secondary geoid -> (parent level 'u'|'h', parent geoid).

    FUNCSTAT-F secondary areas are Census pseudo-districts for the slice of a
    REAL district's territory where it serves only a grade range ("Perris Union
    High School District (9-12)"). They are genuine ACS observation units, but
    the district's seats all sit on the parent's node, so left separate they
    show phantom export (pseudo) / import (parent) between two polygons of the
    SAME district. The flow model folds each pseudo area's residents and seats
    into its parent node.

    Parent resolution is an EXACT name match against the same TIGER vintage
    (suffix stripped), secondary layer first, then unified — never fuzzy.
    Unmatched or ambiguous names raise: a silent mismatch would reintroduce
    phantom flows. Persisted to enrollment_pseudo_areas.parquet for exports.
    """
    geo = geo or {lvl: load_district_geometries(lvl) for lvl in LEVELS}
    s_ids, s_geoms, s_props = geo["secondary"]
    _, _, u_props = geo["unified"]
    geom_by_geoid = {}
    for lvl in LEVELS:
        for gid, gm in zip(geo[lvl][0], geo[lvl][1]):
            geom_by_geoid.setdefault(gid, gm)

    def by_name(props: list[dict], skip_f: bool) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        for p in props:
            if skip_f and p.get("funcstat") == "F":
                continue
            out.setdefault(p["name"], []).append(p["geoid"])
        return out

    sec_names = by_name(s_props, skip_f=True)
    uni_names = by_name(u_props, skip_f=False)
    pseudo_geom = {gid: gm for gid, gm in zip(s_ids, s_geoms)}
    out: dict[str, tuple[str, str]] = {}
    rows = []
    for p in s_props:
        if p.get("funcstat") != "F":
            continue
        base = PSEUDO_SUFFIX_RE.sub("", p["name"] or "")
        hits = [("h", g) for g in sec_names.get(base, [])] + [
            ("u", g) for g in uni_names.get(base, [])
        ]
        if len(hits) > 1:
            # Same-named districts exist in different counties (two Washington
            # Unifieds): the parent is the one whose territory touches the
            # pseudo polygon — a geometric fact, not a name heuristic.
            pg = pseudo_geom[p["geoid"]]
            hits = [
                (lvl_, g) for lvl_, g in hits
                if g in geom_by_geoid and geom_by_geoid[g].intersects(pg)
            ]
        if len(hits) != 1:
            raise ValueError(
                f"pseudo area {p['geoid']} '{p['name']}': expected exactly one "
                f"parent named '{base}', found {hits}"
            )
        out[p["geoid"]] = hits[0]
        rows.append(
            {"pseudo_geoid": p["geoid"], "pseudo_name": p["name"],
             "parent_level": hits[0][0], "parent_geoid": hits[0][1]}
        )
    PSEUDO_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    pl.DataFrame(rows).write_parquet(PSEUDO_PARQUET)
    return out


def _grade_int(value: str | None) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):  # 'KG', 'PK', None
        return None


def _contains_idx(geoms: list, lons, lats) -> dict[int, int]:
    """point index -> polygon index for points contained in exactly one polygon
    (first match kept on the rare boundary-sliver double hit)."""
    import numpy as np
    from shapely import STRtree, points

    pts = points(np.column_stack([lons, lats]))
    tree = STRtree(pts)
    poly_idx, pt_idx = tree.query(np.asarray(geoms, dtype=object), predicate="contains")
    out: dict[int, int] = {}
    for gi, pi in zip(poly_idx, pt_idx):
        out.setdefault(int(pi), int(gi))
    return out


def area_grade_cuts(
    geo: dict[str, tuple[list[str], list, list[dict]]] | None = None,
) -> pl.DataFrame:
    """[level, geoid, cut, sec_geoid]: lowest secondary grade per area.

    Secondary areas: cut = own LOGRADE (9/7/6; non-numeric falls back to 9).
    Elementary areas: cut inherited from the secondary polygon containing the
    elementary polygon's representative point (they nest, modulo slivers).
    Unified areas: cut = None (whole 5-17 universe, no split).
    """
    geo = geo or {lvl: load_district_geometries(lvl) for lvl in LEVELS}
    s_ids, s_geoms, s_props = geo["secondary"]
    e_ids, e_geoms, _ = geo["elementary"]

    sec_cut = {gid: _grade_int(p["lograde"]) or DEFAULT_CUT for gid, p in zip(s_ids, s_props)}
    rows = [
        {"level": "secondary", "geoid": gid, "cut": sec_cut[gid], "sec_geoid": gid}
        for gid in s_ids
    ]

    reps = [g.representative_point() for g in e_geoms]
    hit = _contains_idx(s_geoms, [p.x for p in reps], [p.y for p in reps])
    orphans = 0
    for i, gid in enumerate(e_ids):
        si = hit.get(i)
        if si is None:
            orphans += 1
        rows.append(
            {
                "level": "elementary",
                "geoid": gid,
                "cut": sec_cut[s_ids[si]] if si is not None else DEFAULT_CUT,
                "sec_geoid": s_ids[si] if si is not None else None,
            }
        )
    if orphans:
        print(f"  WARNING: {orphans} elementary areas outside every secondary polygon")

    df = pl.DataFrame(rows)
    CUTS_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(CUTS_PARQUET)
    return df


def site_schools(
    con: duckdb.DuckDBPyConnection | None = None,
    geo: dict[str, tuple[list[str], list, list[dict]]] | None = None,
) -> pl.DataFrame:
    """Assign every CDE school (past and present) to district areas by location.

    Returns [cds, lat, lon, unified_geoid, elem_geoid, sec_geoid, sited] where sited
    is 'pip' (point in polygon), 'nearest' (within NEAREST_DEG of a polygon —
    coastal/precision misses), 'crosswalk' (no usable coordinates; the school's own
    district geoid via the directory NCES crosswalk), or null (unsited: its seats
    join the statewide import-only pool). Unified assignment wins over an
    elementary-sliver double hit. Persisted to enrollment_school_siting.parquet.
    """
    import numpy as np
    from shapely import STRtree, points

    own = con is None
    if own:
        con = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    try:
        # One row per school code; closed schools keep their last-known location so
        # historical seats can be sited. Directory files occasionally disagree per
        # cds; majority/any_value is fine at this grain (coordinates, not counts).
        schools = con.execute(
            """
            SELECT cds,
                   TRY_CAST(any_value(latitude) AS DOUBLE) AS lat,
                   TRY_CAST(any_value(longitude) AS DOUBLE) AS lon,
                   lpad(trim(any_value(ncesdist)), 7, '0') AS own_geoid
            FROM directory_raw
            WHERE substr(cds, 8, 7) <> '0000000'
            GROUP BY cds
            """
        ).pl()
    finally:
        if own:
            con.close()

    geo = geo or {lvl: load_district_geometries(lvl) for lvl in LEVELS}
    u_ids, u_geoms, _ = geo["unified"]
    e_ids, e_geoms, _ = geo["elementary"]
    s_ids, s_geoms, _ = geo["secondary"]

    valid = schools.filter(
        pl.col("lat").is_between(32.0, 42.5) & pl.col("lon").is_between(-125.0, -114.0)
    )
    lons, lats = valid["lon"].to_numpy(), valid["lat"].to_numpy()
    u_hit = _contains_idx(u_geoms, lons, lats)
    e_hit = _contains_idx(e_geoms, lons, lats)
    s_hit = _contains_idx(s_geoms, lons, lats)

    # Nearest-polygon rescue for valid coordinates outside every partition polygon.
    misses = [i for i in range(len(valid)) if i not in u_hit and i not in e_hit]
    rescued: dict[int, tuple[str, int]] = {}  # point idx -> (level, polygon idx)
    if misses:
        ue_geoms = list(u_geoms) + list(e_geoms)
        tree = STRtree(ue_geoms)
        pts = points(np.column_stack([lons[misses], lats[misses]]))
        for k, pt in enumerate(pts):
            cand = tree.query(pt, predicate="dwithin", distance=NEAREST_DEG)
            if len(cand) == 0:
                continue
            j = min(cand, key=lambda c: ue_geoms[c].distance(pt))
            lvl = "unified" if j < len(u_geoms) else "elementary"
            rescued[misses[k]] = (lvl, j if lvl == "unified" else j - len(u_geoms))
        s_tree = STRtree(list(s_geoms))

    both = sum(1 for i in u_hit if i in e_hit)
    if both:
        print(f"  {both} schools in both a unified and an elementary polygon (slivers);"
              " unified kept")

    rows = []
    for i in range(len(valid)):
        unified = elem = sec = None
        sited = None
        if i in u_hit:
            unified, sited = u_ids[u_hit[i]], "pip"
        elif i in e_hit:
            elem, sited = e_ids[e_hit[i]], "pip"
            if i in s_hit:
                sec = s_ids[s_hit[i]]
        elif i in rescued:
            lvl, j = rescued[i]
            sited = "nearest"
            if lvl == "unified":
                unified = u_ids[j]
            else:
                elem = e_ids[j]
                pt = points([[lons[i], lats[i]]])[0]
                cand = s_tree.query(pt, predicate="dwithin", distance=NEAREST_DEG)
                if len(cand):
                    sec = s_ids[min(cand, key=lambda c: s_geoms[c].distance(pt))]
        rows.append({"unified_geoid": unified, "elem_geoid": elem, "sec_geoid": sec,
                     "sited": sited})
    sited_df = pl.concat([valid.select("cds", "lat", "lon", "own_geoid"),
                          pl.DataFrame(rows)], how="horizontal")

    # Schools without usable coordinates: fall back to their own district's geoid.
    u_set, e_set, s_set = set(u_ids), set(e_ids), set(s_ids)
    nocoord = schools.join(valid.select("cds"), on="cds", how="anti")
    rows = []
    for r in nocoord.to_dicts():
        g = r["own_geoid"]
        unified = g if g in u_set else None
        elem = g if g in e_set else None
        sec = g if g in s_set else None
        sited = "crosswalk" if (unified or elem or sec) else None
        rows.append({"cds": r["cds"], "lat": r["lat"], "lon": r["lon"],
                     "own_geoid": g, "unified_geoid": unified, "elem_geoid": elem,
                     "sec_geoid": sec, "sited": sited})
    if rows:
        sited_df = pl.concat([sited_df, pl.DataFrame(rows, schema=sited_df.schema)])

    SITING_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    sited_df.write_parquet(SITING_PARQUET)
    counts = sited_df.group_by("sited").len().sort("sited")
    print("  school siting:", ", ".join(
        f"{r['sited'] or 'UNSITED'}={r['len']:,}" for r in counts.to_dicts()))
    return sited_df


def district_adjacency(
    geo: dict[str, tuple[list[str], list, list[dict]]] | None = None,
) -> pl.DataFrame:
    """[geoid, neighbor, band] adjacency within each display partition.

    band 'k8' pairs within unified+elementary, band 'hs' within unified+secondary —
    a district's plausible physical counterparties are the areas it shares a border
    with in the partition where it enrolls those grades. Pseudo grade-range areas
    are folded into their parent district's node, so their borders count as the
    parent's (self-pairs from the fold are dropped).
    """
    from shapely import STRtree

    geo = geo or {lvl: load_district_geometries(lvl) for lvl in LEVELS}
    pseudo = {pg: parent for pg, (_lvl, parent) in pseudo_parent_map(geo).items()}
    rows = []
    for band, levels in (("k8", ("unified", "elementary")), ("hs", ("unified", "secondary"))):
        ids: list[str] = []
        geoms: list = []
        for lvl in levels:
            lvl_ids, lvl_geoms, _ = geo[lvl]
            ids.extend(lvl_ids)
            geoms.extend(lvl_geoms)
        tree = STRtree(geoms)
        for i, g in enumerate(geoms):
            for j in tree.query(g, predicate="intersects"):
                if int(j) != i:
                    a = pseudo.get(ids[i], ids[i])
                    b = pseudo.get(ids[int(j)], ids[int(j)])
                    if a != b:
                        rows.append({"geoid": a, "neighbor": b, "band": band})
    df = pl.DataFrame(rows).unique()
    ADJACENCY_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(ADJACENCY_PARQUET)
    print(f"  adjacency: {len(df):,} directed pairs across both bands")
    return df


def export_boundaries(
    geo: dict[str, tuple[list[str], list, list[dict]]] | None = None,
    epsilon: float = 0.0015,
) -> dict[str, dict]:
    """Simplified web FeatureCollections keyed 'u'/'e'/'h', properties = {"g": geoid}.

    Metrics are never baked into the geojson — the site joins values by geoid at
    render time so map fills and popups cannot disagree with the index. Pseudo
    grade-range polygons keep their own geometry but carry the PARENT district's
    geoid, so the whole district colors and pops up as one entity.
    """
    from shapely.geometry import mapping

    from schoolfactors.analysis.lausd_geo import simplify_feature_collection

    geo = geo or {lvl: load_district_geometries(lvl) for lvl in LEVELS}
    pseudo = {pg: parent for pg, (_lvl, parent) in pseudo_parent_map(geo).items()}
    out: dict[str, dict] = {}
    for level, key in (("unified", "u"), ("elementary", "e"), ("secondary", "h")):
        ids, geoms, _ = geo[level]
        fc = {
            "type": "FeatureCollection",
            "features": [
                {"type": "Feature", "properties": {"g": pseudo.get(gid, gid)},
                 "geometry": dict(mapping(geom))}
                for gid, geom in zip(ids, geoms)
            ],
        }
        simplified = simplify_feature_collection(fc, epsilon=epsilon)
        size = len(json.dumps(simplified))
        print(f"  boundaries_{key}: {len(ids)} features, {size / 1e6:.2f} MB simplified")
        out[key] = simplified
    return out
