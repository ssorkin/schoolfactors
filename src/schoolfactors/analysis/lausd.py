"""LAUSD attendance-area analysis: key resolution and boundary coverage.

MP25 partitions LAUSD into ~985 polygons, each carrying the 5-digit keys of the
elementary (E_KEY), middle (M_KEY) and high (H_KEY) school serving it. Keys resolve to
schools through a tiered lookup:

1. `lausd_codes_raw` resident rows (the Att{e,m,h}1112_Codes tables) — authoritative
   but dated (SCH_YR 2016-17);
2. `lausd_abinfo_raw` resident rows (Attendance Boundary Info, POLYID prefix match) —
   covers keys created after the Codes tables were built;
3/4. the same two sources' "By Application" rows — last resort, flagged, because those
   are programs (dual-language, magnet centers) rather than resident schools.

A key can resolve to MULTIPLE resident schools legitimately (81 E keys do): paired
campuses and grade-span splits (e.g. a K-2 primary center + a 3-6 elementary share an
area). Resolution therefore returns one row per (level, key5, cds) with grade ranges;
`primary` marks the widest-grade-span resident school for single-school displays.

Schools with no attendance area (magnets, charters on private sites, options schools)
are the active LAUSD schools in the CDE directory that never appear as a resolved key.
"""

from __future__ import annotations

import duckdb
import polars as pl

from schoolfactors.paths import DUCKDB_PATH

LAUSD_DCDS = "19647330000000"
LAUSD_PREFIX = "1964733"

_LEVEL_COLS = {"E": ("e_key", 1), "M": ("m_key", 6), "H": ("h_key", 11)}


def _con() -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(DUCKDB_PATH), read_only=True)


def _has_views(con: duckdb.DuckDBPyConnection, *names: str) -> bool:
    have = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    return all(n in have for n in names)


def mp25_keys(con: duckdb.DuckDBPyConnection) -> pl.DataFrame:
    """Distinct (level, key5) across all MP25 polygons."""
    parts = [
        f"SELECT '{lvl}' AS level, {col} AS key5 FROM lausd_mp25_raw"
        for lvl, (col, _) in _LEVEL_COLS.items()
    ]
    return con.execute(
        f"SELECT DISTINCT level, key5 FROM ({' UNION ALL '.join(parts)}) ORDER BY 1, 2"
    ).pl()


def resolve_keys(con: duckdb.DuckDBPyConnection | None = None) -> pl.DataFrame:
    """One row per (level, key5, cds): every school a key resolves to.

    Columns: level, key5, cds, name, school_id, lo_grd, hi_grd, resolved_via
    (codes | abinfo | codes_by_app | abinfo_by_app), by_app, primary (bool).
    Keys resolving to nothing appear once with null cds.
    """
    own = con is None
    if own:
        con = _con()
    try:
        keys = mp25_keys(con)
        con.register("mp25_keys_tmp", keys.to_arrow())

        # Candidate rows from both sources, all tiers, POLYID prefix per level.
        abinfo_polyid = " OR ".join(
            f"(k.level = '{lvl}' AND substr(a.polyid, {off}, 5) = k.key5)"
            for lvl, (_, off) in _LEVEL_COLS.items()
        )
        cand = con.execute(
            f"""
            WITH codes AS (
                SELECT k.level, k.key5, c.cds14 AS cds, c.name, c.school_id,
                       TRY_CAST(c.lo_grd AS INT) AS lo_grd,
                       TRY_CAST(c.hi_grd AS INT) AS hi_grd,
                       trim(coalesce(c.by_app, '')) <> '' AS by_app,
                       'codes' AS source
                FROM mp25_keys_tmp k
                JOIN lausd_codes_raw c ON c.level = k.level AND c.key5 = k.key5
                WHERE c.cds14 IS NOT NULL
            ),
            abinfo AS (
                SELECT DISTINCT k.level, k.key5, a.cds14 AS cds, a.long_name AS name,
                       a.school_id,
                       TRY_CAST(a.lo_grd AS INT) AS lo_grd,
                       TRY_CAST(a.hi_grd AS INT) AS hi_grd,
                       trim(coalesce(a.by_app, '')) <> '' AS by_app,
                       'abinfo' AS source
                FROM mp25_keys_tmp k
                JOIN lausd_abinfo_raw a ON a.level = k.level AND ({abinfo_polyid})
                WHERE a.cds14 IS NOT NULL
            )
            SELECT * FROM codes UNION ALL SELECT * FROM abinfo
            """
        ).pl()

        tier = (
            pl.when(~pl.col("by_app") & (pl.col("source") == "codes")).then(1)
            .when(~pl.col("by_app") & (pl.col("source") == "abinfo")).then(2)
            .when(pl.col("by_app") & (pl.col("source") == "codes")).then(3)
            .otherwise(4)
        )
        cand = cand.with_columns(tier.alias("tier"))
        best_tier = cand.group_by("level", "key5").agg(pl.col("tier").min().alias("key_tier"))
        resolved = (
            cand.join(best_tier, on=["level", "key5"])
            .filter(pl.col("tier") == pl.col("key_tier"))
            .group_by("level", "key5", "cds")
            .agg(
                pl.col("name").first(),
                pl.col("school_id").first(),
                pl.col("lo_grd").min(),
                pl.col("hi_grd").max(),
                pl.col("by_app").first(),
                pl.col("tier").first(),
            )
            .with_columns(
                pl.col("tier")
                .replace_strict({1: "codes", 2: "abinfo", 3: "codes_by_app", 4: "abinfo_by_app"})
                .alias("resolved_via")
            )
        )
        # Widest grade span wins primary; ties break on lowest CDS for determinism.
        resolved = resolved.sort(
            ["level", "key5", (pl.col("hi_grd") - pl.col("lo_grd")).fill_null(-1), "cds"],
            descending=[False, False, True, False],
        ).with_columns(
            (pl.int_range(pl.len()).over(["level", "key5"]) == 0).alias("primary")
        )

        out = (
            keys.join(resolved.drop("tier"), on=["level", "key5"], how="left")
            .sort(["level", "key5", "cds"])
        )
        n_keys = len(keys)
        n_resolved = out.filter(pl.col("cds").is_not_null())["key5"].n_unique()
        unresolved = out.filter(pl.col("cds").is_null())
        print(
            f"  LAUSD keys: {n_resolved}/{n_keys} resolved "
            f"({len(unresolved)} unresolved: "
            f"{unresolved.select('level', 'key5').to_dicts()})"
        )
        return out
    finally:
        if own:
            con.close()


def schools_without_boundary(
    con: duckdb.DuckDBPyConnection | None = None, resolved: pl.DataFrame | None = None
) -> pl.DataFrame:
    """Active LAUSD schools in the CDE directory that have no attendance area."""
    own = con is None
    if own:
        con = _con()
    try:
        if resolved is None:
            resolved = resolve_keys(con)
        directory = con.execute(
            """
            SELECT cds, school AS name, eilcode, eilname, charter, magnet, virtual,
                   soctype, statustype, latitude, longitude
            FROM directory_raw
            WHERE cds LIKE '1964733%' AND substr(cds, 8, 7) <> '0000000'
              AND statustype = 'Active'
            QUALIFY row_number() OVER (PARTITION BY cds ORDER BY source_file DESC) = 1
            """
        ).pl()
        bounded = set(resolved.filter(pl.col("cds").is_not_null())["cds"].to_list())
        return directory.with_columns(
            pl.col("cds").is_in(sorted(bounded)).alias("has_boundary")
        ).sort("cds")
    finally:
        if own:
            con.close()


def polygon_table(
    con: duckdb.DuckDBPyConnection | None = None, resolved: pl.DataFrame | None = None
) -> pl.DataFrame:
    """One row per MP25 polygon: P_KEY, split suffix, and primary school per level."""
    own = con is None
    if own:
        con = _con()
    try:
        if resolved is None:
            resolved = resolve_keys(con)
        polys = con.execute(
            "SELECT p_key, split_suffix, e_key, m_key, h_key FROM lausd_mp25_raw"
        ).pl()
        prim = resolved.filter(pl.col("primary").fill_null(False))
        for lvl, (col, _) in _LEVEL_COLS.items():
            side = prim.filter(pl.col("level") == lvl).select(
                pl.col("key5").alias(col),
                pl.col("cds").alias(f"{lvl.lower()}_cds"),
                pl.col("name").alias(f"{lvl.lower()}_name"),
            )
            polys = polys.join(side, on=col, how="left")
        return polys.sort("p_key")
    finally:
        if own:
            con.close()
