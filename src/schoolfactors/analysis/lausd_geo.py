"""LAUSD attendance-area geometry: census crosswalk, apportionment, web geometry.

Resident demographics for each MP25 polygon come from ACS block-group tables via a
population-weighted crosswalk (the GeoCorr method):

1. Every 2020 census block in LA County is assigned to the single MP25 polygon that
   contains its internal point (blocks are small relative to attendance areas, so
   whole-block assignment error is minimal; blocks whose point falls outside every
   polygon are outside LAUSD).
2. A block group's share in a polygon = block population in the polygon / block
   population of the whole group. 2020 block GEOID[:12] is the 2020 block-group GEOID,
   which is what current ACS 5-year releases publish against.
3. Polygon estimate = Σ over block groups of share x count. Only COUNT estimates are
   apportioned (medians cannot be); shares are computed from apportioned numerator and
   denominator counts, never averaged.

Poverty uses C17002 (ratio of income to poverty, all ages — B17024 is not published at
block-group level): "under 1.85" is selected by label. Race/ethnicity uses B03002.

Web geometry: per level (E/M/H), polygons sharing a key are dissolved into one
attendance area per school, then simplified with shared-arc topology (topojson) so
adjacent areas keep coincident borders without slivers.
"""

from __future__ import annotations

import json

import duckdb
import polars as pl

from schoolfactors.paths import DUCKDB_PATH, PARQUET_DIR, RAW_DIR

MP25_GEOJSON = RAW_DIR / "lausd_gis" / "mp25_polygons.geojson"
XWALK_PARQUET = PARQUET_DIR / "analysis" / "lausd_block_crosswalk.parquet"

# ACS variables are selected by label substrings, never hardcoded _0NN IDs.
C17002_UNDER_185 = ("Under .50", ".50 to .99", "1.00 to 1.24", "1.25 to 1.49",
                    "1.50 to 1.84")
B03002_RACES = {
    "his": ("Hispanic or Latino",),  # top-level Hispanic total
    "wht": ("Not Hispanic or Latino", "White alone"),
    "blk": ("Not Hispanic or Latino", "Black or African American alone"),
    "asn": ("Not Hispanic or Latino", "Asian alone"),
}


def _con() -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(DUCKDB_PATH), read_only=True)


def load_mp25_geometries() -> tuple[list[str], list]:
    """(p_keys, shapely geometries) from the raw MP25 snapshot, WGS84."""
    from shapely.geometry import shape

    doc = json.loads(MP25_GEOJSON.read_text())
    p_keys, geoms = [], []
    for f in doc["features"]:
        p_keys.append(str(f["properties"]["P_KEY"]))
        geoms.append(shape(f["geometry"]))
    return p_keys, geoms


def build_block_crosswalk(con: duckdb.DuckDBPyConnection | None = None) -> pl.DataFrame:
    """Assign each LA County 2020 block (by internal point) to its MP25 polygon.

    Returns [geoid20, p_key, pop20]; blocks outside every polygon are excluded.
    Persisted to analysis/lausd_block_crosswalk.parquet.
    """
    import numpy as np
    from shapely import STRtree, points

    own = con is None
    if own:
        con = _con()
    try:
        blocks = con.execute(
            """
            SELECT geoid20,
                   TRY_CAST(pop20 AS BIGINT) AS pop20,
                   TRY_CAST(intptlat20 AS DOUBLE) AS lat,
                   TRY_CAST(intptlon20 AS DOUBLE) AS lon
            FROM la_blocks_raw
            WHERE geoid20 IS NOT NULL AND intptlat20 IS NOT NULL
            """
        ).pl()
    finally:
        if own:
            con.close()

    p_keys, geoms = load_mp25_geometries()
    pts = points(np.column_stack([blocks["lon"].to_numpy(), blocks["lat"].to_numpy()]))
    tree = STRtree(pts)
    poly_idx, pt_idx = tree.query(np.asarray(geoms, dtype=object), predicate="contains")

    xwalk = pl.DataFrame(
        {
            "geoid20": blocks["geoid20"].gather(pt_idx),
            "p_key": pl.Series([p_keys[i] for i in poly_idx]),
            "pop20": blocks["pop20"].gather(pt_idx).fill_null(0),
        }
    )
    # A block can only sit in one polygon of a partition; a duplicate means split or
    # overlapping source geometry and would double-count population downstream.
    dupes = xwalk.group_by("geoid20").len().filter(pl.col("len") > 1)
    if len(dupes):
        xwalk = xwalk.unique(subset=["geoid20"], keep="first", maintain_order=True)
        print(f"  WARNING: {len(dupes)} blocks matched multiple polygons; kept first")
    XWALK_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    xwalk.write_parquet(XWALK_PARQUET)
    covered = xwalk["pop20"].sum()
    print(f"  block crosswalk: {len(xwalk):,} blocks in polygons, {covered:,} residents")
    return xwalk


def bg_shares(xwalk: pl.DataFrame, county_blocks: pl.DataFrame) -> pl.DataFrame:
    """[bg_geoid, p_key, share]: block-group population share inside each polygon.

    `county_blocks` must cover the WHOLE county ([geoid20, pop20]) so the denominator
    counts population outside LAUSD too.
    """
    totals = (
        county_blocks.with_columns(pl.col("geoid20").str.slice(0, 12).alias("bg_geoid"))
        .group_by("bg_geoid")
        .agg(pl.col("pop20").cast(pl.Int64, strict=False).fill_null(0).sum().alias("bg_pop"))
    )
    inside = (
        xwalk.with_columns(pl.col("geoid20").str.slice(0, 12).alias("bg_geoid"))
        .group_by("bg_geoid", "p_key")
        .agg(pl.col("pop20").sum().alias("pop_in_poly"))
    )
    return (
        inside.join(totals, on="bg_geoid")
        .filter(pl.col("bg_pop") > 0)
        .with_columns((pl.col("pop_in_poly") / pl.col("bg_pop")).alias("share"))
        .select("bg_geoid", "p_key", "share", "pop_in_poly")
    )


def _bg_values(
    con: duckdb.DuckDBPyConnection, table: str
) -> tuple[pl.DataFrame, dict[str, str]] | None:
    """Latest-vintage block-group rows for one ACS table, plus variable labels."""
    views = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    if "census_acs_raw" not in views:
        return None
    vintage = con.execute(
        "SELECT max(vintage) FROM census_acs_raw WHERE table_id = ? "
        "AND geo_type LIKE 'bg%'",
        [table],
    ).fetchone()[0]
    if vintage is None:
        return None
    df = con.execute(
        """
        SELECT geoid AS bg_geoid, variable, label, TRY_CAST(value AS DOUBLE) AS v
        FROM census_acs_raw
        WHERE table_id = ? AND vintage = ? AND geo_type LIKE 'bg%'
          AND (TRY_CAST(value AS DOUBLE) IS NULL OR TRY_CAST(value AS DOUBLE) >= 0)
        """,
        [table, vintage],
    ).pl()
    labels = {
        r["variable"]: r["label"]
        for r in df.select("variable", "label").unique().to_dicts()
        if r["label"]
    }
    return df, labels


def _label_parts(label: str) -> list[str]:
    return [p.rstrip(":") for p in label.split("!!")]


def polygon_demographics(
    con: duckdb.DuckDBPyConnection | None = None, shares: pl.DataFrame | None = None
) -> pl.DataFrame | None:
    """Per-polygon resident demographics apportioned from ACS block groups.

    Returns [p_key, pop20, pov_universe, pov_under185, p185, race counts + shares], or
    None until block-group census data is acquired. Count estimates only, apportioned
    by population share; shares divided from apportioned counts.
    """
    own = con is None
    if own:
        con = _con()
    try:
        if shares is None:
            if not XWALK_PARQUET.exists():
                build_block_crosswalk(con)
            xwalk = pl.read_parquet(XWALK_PARQUET)
            county = con.execute("SELECT geoid20, pop20 FROM la_blocks_raw").pl()
            shares = bg_shares(xwalk, county)

        pov = _bg_values(con, "C17002")
        race = _bg_values(con, "B03002")
        if pov is None or race is None:
            print("  block-group ACS tables not in store yet — demographics skipped")
            return None

        out = (
            shares.group_by("p_key")
            .agg(pl.col("pop_in_poly").sum().alias("pop20"))
        )

        pov_df, pov_labels = pov
        pov_vars = {
            "pov_universe": [
                v for v, lbl in pov_labels.items()
                if v.endswith("E") and _label_parts(lbl) == ["Estimate", "Total"]
            ],
            "pov_under185": [
                v for v, lbl in pov_labels.items()
                if v.endswith("E")
                and len(_label_parts(lbl)) == 3
                and _label_parts(lbl)[2] in C17002_UNDER_185
            ],
        }
        if len(pov_vars["pov_under185"]) != len(C17002_UNDER_185):
            raise ValueError(
                f"C17002 label selection drifted: {pov_vars['pov_under185']}"
            )

        race_df, race_labels = race
        race_vars: dict[str, list[str]] = {
            "race_total": [
                v for v, lbl in race_labels.items()
                if v.endswith("E") and _label_parts(lbl) == ["Estimate", "Total"]
            ]
        }
        for key, path in B03002_RACES.items():
            race_vars[f"race_{key}"] = [
                v for v, lbl in race_labels.items()
                if v.endswith("E") and tuple(_label_parts(lbl)[2:]) == path
            ]
            if len(race_vars[f"race_{key}"]) != 1:
                raise ValueError(f"B03002 label selection drifted for {key}")

        for df, groups in ((pov_df, pov_vars), (race_df, race_vars)):
            joined = df.join(shares, on="bg_geoid")
            for name, variables in groups.items():
                agg = (
                    joined.filter(pl.col("variable").is_in(variables))
                    .with_columns((pl.col("v") * pl.col("share")).alias("x"))
                    .group_by("p_key")
                    .agg(pl.col("x").sum().alias(name))
                )
                out = out.join(agg, on="p_key", how="left")

        out = out.with_columns(
            (pl.col("pov_under185") / pl.col("pov_universe")).alias("p185"),
            *[
                (pl.col(f"race_{k}") / pl.col("race_total")).alias(f"share_{k}")
                for k in B03002_RACES
            ],
        ).with_columns(
            (
                1
                - pl.sum_horizontal(*[pl.col(f"share_{k}") for k in B03002_RACES])
            ).clip(0, 1).alias("share_oth")
        )
        path = PARQUET_DIR / "analysis" / "lausd_polygon_demographics.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        out.write_parquet(path)
        print(f"  polygon demographics: {len(out):,} polygons")
        return out
    finally:
        if own:
            con.close()


def dissolve_by_level(
    resolved: pl.DataFrame, level: str
) -> tuple[list[str], list, dict[str, dict]]:
    """Dissolve MP25 polygons by this level's key → (keys, geometries, key->info).

    info carries the primary school (cds, name) plus all resident schools for the key.
    """
    from shapely import coverage_union_all, union_all
    from shapely.errors import GEOSException

    p_keys, geoms = load_mp25_geometries()
    seg = {"E": (0, 5), "M": (5, 10), "H": (10, 15)}[level]
    by_key: dict[str, list] = {}
    for pk, g in zip(p_keys, geoms):
        by_key.setdefault(pk[seg[0]:seg[1]], []).append(g)

    lvl = resolved.filter(pl.col("level") == level)
    info: dict[str, dict] = {}
    for key5, rows in lvl.group_by("key5"):
        rows = rows.sort("primary", descending=True)
        schools = [
            {"cds": r["cds"], "name": r["name"]}
            for r in rows.to_dicts()
            if r["cds"] is not None
        ]
        info[key5[0]] = {
            "cds": schools[0]["cds"] if schools else None,
            "name": schools[0]["name"] if schools else None,
            "schools": schools,
        }

    keys = sorted(by_key)
    dissolved = []
    for k in keys:
        parts = by_key[k]
        if len(parts) == 1:
            dissolved.append(parts[0])
            continue
        try:
            dissolved.append(coverage_union_all(parts))
        except GEOSException:  # slivers/overlaps in source data: robust fallback
            dissolved.append(union_all(parts))
    return keys, dissolved, info


def simplify_feature_collection(fc: dict, epsilon: float = 0.0003) -> dict:
    """Shared-arc simplification of a GeoJSON FeatureCollection, coords to 5 decimals.

    toposimplify can leave a handful of self-intersecting rings; those are repaired
    with make_valid (keeping only polygonal parts) so every published feature is valid.
    """
    import shapely
    import topojson
    from shapely.geometry import mapping, shape
    from shapely.geometry.base import BaseGeometry

    topo = topojson.Topology(fc, prequantize=100_000)
    simplified = json.loads(topo.toposimplify(epsilon).to_geojson())

    def polygonal(geom: BaseGeometry) -> BaseGeometry:
        if geom.geom_type in ("Polygon", "MultiPolygon"):
            return geom
        parts = [g for g in getattr(geom, "geoms", []) if g.geom_type.endswith("Polygon")]
        return shapely.union_all(parts) if parts else geom

    def round_coords(x):
        if isinstance(x, float):
            return round(x, 5)
        if isinstance(x, (list, tuple)):
            return [round_coords(v) for v in x]
        return x

    def repaired(geom):
        if not shapely.is_valid(geom):
            geom = shapely.make_valid(geom, method="structure", keep_collapsed=False)
        return polygonal(geom)

    for f in simplified["features"]:
        # Repair first (set_precision requires valid input), then snap to the 1e-5
        # degree grid (~1 m): set_precision guarantees valid output, so the rounding
        # below cannot re-break a ring.
        geom = repaired(polygonal(shape(f["geometry"])))
        geom = repaired(shapely.set_precision(geom, 1e-5))
        f["geometry"] = dict(mapping(geom))
        f["geometry"]["coordinates"] = round_coords(f["geometry"]["coordinates"])
    return simplified
