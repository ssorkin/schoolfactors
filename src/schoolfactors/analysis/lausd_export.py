"""Export the /lausd data-story files to site/static/data.

Products (all consumed by the site's /lausd routes; fractions 0-1, rounded):
- lausd/schools.json          every active LAUSD school: identity, map point, perf
                              stats (from index.json), boundary role, capacity, SENI
- lausd/boundaries_{e,m,h}.geojson  per-level attendance areas (MP25 dissolved by key,
                              topology-preserving simplification), resident demographics
                              on each feature when census block-group data is present
- lausd/demographics.json     per-school + district resident demographics
- lausd/enrollment.json       district/school enrollment series, capacity, closures
- lausd/funding.json          PPE + FRPM history, census P185, LCFF summary, SENI
- census_frpm.json            statewide district FRPM vs census P185 (all CA districts)

Runs inside `sf export` after the main site export (it reads index.json and the
district payload written there), and is independently runnable for development:
`uv run python -m schoolfactors.analysis.lausd_export`.
"""

from __future__ import annotations

import json

import duckdb
import polars as pl

from schoolfactors.analysis import lausd, lausd_geo
from schoolfactors.analysis.census_poverty import OUT_PARQUET as CENSUS_FRPM_PARQUET
from schoolfactors.analysis.lausd import LAUSD_DCDS
from schoolfactors.paths import DUCKDB_PATH, REPO_ROOT

SITE_DATA = REPO_ROOT / "site" / "static" / "data"
LAUSD_DIR = SITE_DATA / "lausd"

# Later certifications supersede earlier ones within an LCFF year.
_CERT_RANK = {"p_1": 0, "p_2": 1, "an": 2, "annual": 2, "r1": 3, "anr1": 3, "anr2": 4,
              "anr3": 5}


def _r(x, nd=3):
    """Round for JSON; non-finite (a zero-denominator ratio) becomes null."""
    import math

    if x is None:
        return None
    x = float(x)
    return round(x, nd) if math.isfinite(x) else None


def _write(name: str, payload) -> None:
    path = LAUSD_DIR / name if not name.endswith("census_frpm.json") else SITE_DATA / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))
    print(f"  wrote {path.relative_to(REPO_ROOT)} ({path.stat().st_size:,} bytes)")


def _index_rows() -> dict[str, dict]:
    index_path = SITE_DATA / "index.json"
    if not index_path.exists():
        return {}
    rows = json.loads(index_path.read_text())
    return {
        e["cds"]: e
        for e in rows
        if e.get("kind") == "school" and e.get("district_cds") == LAUSD_DCDS
    }


def _capacity(con) -> dict[str, list[list]]:
    views = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    if "lausd_capacity_raw" not in views:
        return {}
    rows = con.execute(
        """
        SELECT lpad(cdscode, 14, '0') AS cds, year,
               TRY_CAST(opcap AS DOUBLE) AS opcap,
               TRY_CAST(enrollment AS DOUBLE) AS enr
        FROM lausd_capacity_raw
        WHERE cdscode IS NOT NULL AND (opcap IS NOT NULL OR enrollment IS NOT NULL)
        ORDER BY cds, year
        """
    ).fetchall()
    out: dict[str, list[list]] = {}
    for cds, year, opcap, enr in rows:
        out.setdefault(cds, []).append(
            [int(year), None if opcap is None else round(opcap),
             None if enr is None else round(enr)]
        )
    return out


def _seni(con) -> dict[str, dict]:
    """cds -> latest-year SENI {score, rank, quintile, alloc, year}.

    Files carry their allocation year in the column names ("SENI Score 2026-27",
    "SENI Rank for 2026-27 Allocation"), so the columns are selected by pattern from
    the latest allocation year's file. `cds` is derived at ingest from the file's
    7-digit CDS Code column.
    """
    views = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    if "lausd_seni_raw" not in views:
        return {}
    latest = con.execute(
        "SELECT max(allocation_year) FROM lausd_seni_raw WHERE cds IS NOT NULL"
    ).fetchone()[0]
    if latest is None:
        return {}
    seni = con.execute(
        "SELECT * FROM lausd_seni_raw WHERE allocation_year = ? AND cds IS NOT NULL",
        [latest],
    ).pl()
    # The view unions every year's file by name, so several years' "seni_score_*"
    # columns coexist; keep only the ones that are actually populated for this year.
    seni = seni[[c for c in seni.columns if seni[c].null_count() < len(seni)]]
    import re as _re

    def col(pattern: str) -> str | None:
        return next((c for c in seni.columns if _re.fullmatch(pattern, c)), None)

    score_col = col(r"seni_score_\d{4}(_\d{2})?")
    rank_col = col(r"seni_rank_for_\d{4}(_\d{2})?_allocation")
    quint_col = col(r"seni_(\d{4}(_\d{2})?_)?quintile")
    alloc_col = col(r"seni_total_allocation_dollars?")
    enr_col = col(r"total_enrollment_\d{4}(_\d{2})?")
    out: dict[str, dict] = {}
    for row in seni.to_dicts():
        num = lambda v: None if v in (None, "") else float(str(v).replace(",", ""))
        quintile = row.get(quint_col) if quint_col else None
        if quintile:
            quintile = str(quintile).split(" ")[0]  # "1 - HIGHEST" -> "1"
        out[row["cds"]] = {
            "year": latest,
            "score": num(row.get(score_col)) if score_col else None,
            "rank": num(row.get(rank_col)) if rank_col else None,
            "quintile": quintile,
            "alloc": num(row.get(alloc_col)) if alloc_col else None,
            # SENI file's own enrollment (the allocation cohort) — used for the
            # per-pupil summary, stripped from per-school payloads.
            "enr": num(row.get(enr_col)) if enr_col else None,
        }
    return out


def _lcff(con) -> dict:
    views = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    if "lcff_raw" not in views:
        return {}
    rows = con.execute(
        """
        SELECT source_file, certification,
               TRY_CAST(lcff_base_grant_nss_allowance AS DOUBLE) AS base,
               TRY_CAST(total_lcff_supplemental_grant AS DOUBLE) AS supplemental,
               TRY_CAST(total_lcff_concentration_grant AS DOUBLE) AS concentration,
               TRY_CAST(total_lcff_entitlement AS DOUBLE) AS total,
               TRY_CAST(unduplicated_pupil_percentage AS DOUBLE) AS upp,
               TRY_CAST(total_funded_ada_or_alternative_education_grant_ada AS DOUBLE)
                   AS ada
        FROM lcff_raw WHERE cds = ?
        """,
        [LAUSD_DCDS],
    ).fetchall()
    best: dict[int, tuple] = {}
    for src, cert, *vals in rows:
        digits = "".join(c for c in src if c.isdigit())
        year = 2000 + int(digits[-2:])  # lcffsummary2425 -> spring 2025
        rank = _CERT_RANK.get(cert, -1)
        if vals[3] is None:
            continue
        if year not in best or rank > best[year][0]:
            best[year] = (rank, cert, vals)
    hist = {}
    for year in sorted(best):
        rank, cert, (base, supp, conc, total, upp, ada) = best[year]
        upp = upp / 100 if upp is not None and upp > 1.5 else upp
        hist[year] = {
            "cert": cert,
            "base": base,
            "supplemental": supp,
            "concentration": conc,
            "total": total,
            "upp": _r(upp),
            "ada": _r(ada, 0),
        }
    return hist


LAUSD_GEOID = "0622710"  # NCES LEAID / ACS school-district GEOID digits


def _census_children(con) -> dict[str, dict] | None:
    """Resident children 6-17 and their <185%-poverty share inside LAUSD's
    boundary, per ACS vintage (B17024 at the unified-district geography)."""
    views = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    if "census_acs_raw" not in views:
        return None
    from schoolfactors.analysis.census_poverty import _labels, p185_variables

    vintages = [
        r[0]
        for r in con.execute(
            "SELECT DISTINCT vintage FROM census_acs_raw "
            "WHERE table_id = 'B17024' AND geo_type LIKE 'sd_%' ORDER BY 1"
        ).fetchall()
    ]
    out: dict[str, dict] = {}
    for v in vintages:
        num, den = p185_variables(_labels(con, v))
        if not num or not den:
            continue
        p185_count, children = con.execute(
            """
            SELECT sum(CASE WHEN list_contains(?::VARCHAR[], variable) THEN val END),
                   sum(CASE WHEN list_contains(?::VARCHAR[], variable) THEN val END)
            FROM (
                SELECT variable, TRY_CAST(value AS DOUBLE) AS val
                FROM census_acs_raw
                WHERE table_id = 'B17024' AND vintage = ? AND geoid = ?
                  AND geo_type LIKE 'sd_%'
            )
            WHERE val IS NULL OR val >= 0
            """,
            [num, den, v, LAUSD_GEOID],
        ).fetchone()
        if children:
            out[v] = {
                "children": int(children),
                "p185": _r(p185_count / children),
            }
    return out or None


def _residence_enrollment(con) -> dict[str, dict] | None:
    """Resident children 5-17 inside LAUSD by enrollment status, per ACS vintage.

    B14003 at the unified-district geography: public school / private school /
    not enrolled, summed over sex and the 5-9 / 10-14 / 15-17 age bins. This is
    residence-based (ACS-ED-style: children are assigned to where they live, not
    where they attend), so it will not reconcile exactly with LEA-based counts.
    """
    views = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    if "census_acs_raw" not in views:
        return None
    ages = {"5 to 9 years", "10 to 14 years", "15 to 17 years"}
    cats = {
        "Enrolled in public school": "public",
        "Enrolled in private school": "private",
        "Not enrolled in school": "not_enrolled",
    }
    rows = con.execute(
        """
        SELECT vintage, variable, label, sum(TRY_CAST(value AS DOUBLE)) AS v
        FROM census_acs_raw
        WHERE table_id = 'B14003' AND geoid = ? AND geo_type LIKE 'sd_%'
          AND (TRY_CAST(value AS DOUBLE) IS NULL OR TRY_CAST(value AS DOUBLE) >= 0)
        GROUP BY 1, 2, 3
        """,
        [LAUSD_GEOID],
    ).fetchall()
    out: dict[str, dict] = {}
    for vintage, variable, label, v in rows:
        if not variable.endswith("E") or not label or v is None:
            continue
        # Hierarchy is Total > Sex > STATUS > AGE (status before age), e.g.
        # "Estimate!!Total!!Male!!Enrolled in public school!!5 to 9 years".
        parts = [p.rstrip(":") for p in label.split("!!")]
        if len(parts) != 5 or parts[2] not in ("Male", "Female") or parts[4] not in ages:
            continue
        cat = cats.get(parts[3])
        if cat is None:
            continue
        acc = out.setdefault(
            vintage,
            {"public": 0, "private": 0, "not_enrolled": 0,
             "by_age": {c: {"5_9": 0, "10_14": 0, "15_17": 0} for c in cats.values()}},
        )
        acc[cat] += v
        band = parts[4].replace(" to ", "_").replace(" years", "").replace(" ", "_")
        acc["by_age"][cat][band] += v
    for acc in out.values():
        acc["total"] = acc["public"] + acc["private"] + acc["not_enrolled"]
        for k in ("public", "private", "not_enrolled", "total"):
            acc[k] = int(round(acc[k]))
        acc["by_age"] = {
            c: {b: int(round(v)) for b, v in bands.items()}
            for c, bands in acc["by_age"].items()
        }
    return out or None


def _school_enrollment_by_class(con) -> dict[int, dict]:
    """LAUSD-authorized enrollment by school class per spring year (FRPM K-12).

    traditional = district-run; affiliated = locally funded charter; independent
    = directly funded charter. LEA-based: everything under the LAUSD CDS prefix,
    regardless of where the student lives.
    """
    rows = con.execute(
        """
        SELECT TRY_CAST(substr(academic_year, 1, 4) AS INT) + 1 AS year,
               CASE
                   WHEN trim(charter_school_y_n) IN ('Yes', 'Y')
                        AND charter_funding_type ILIKE '%direct%' THEN 'independent'
                   WHEN trim(charter_school_y_n) IN ('Yes', 'Y') THEN 'affiliated'
                   ELSE 'traditional'
               END AS cls,
               sum(TRY_CAST(enrollment_k_12 AS DOUBLE)) AS enr
        FROM frpm_raw
        WHERE cds LIKE '1964733%' AND school_code <> '0000000'
        GROUP BY 1, 2
        """
    ).fetchall()
    out: dict[int, dict] = {}
    for year, cls, enr in rows:
        if year and enr:
            out.setdefault(year, {})[cls] = int(round(enr))
    return out


def _district_pages() -> set[str]:
    index_path = SITE_DATA / "index.json"
    if not index_path.exists():
        return set()
    return {
        e["cds"] for e in json.loads(index_path.read_text()) if e.get("kind") == "district"
    }


def lcff_funding_flags(con) -> dict[str, dict]:
    """Per-district LCFF funding status from the latest certification on file.

    A district is "basic aid" (community funded) when its local property-tax
    revenue meets or exceeds its LCFF entitlement — it keeps the excess and
    receives no formula state aid. Everyone else is LCFF (state-aid) funded.
    Returns {district cds: {basic_aid: bool, local_share: float}}.
    """
    views = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    if "lcff_raw" not in views:
        return {}
    rows = con.execute(
        """
        WITH ranked AS (
            SELECT cds,
                   TRY_CAST(total_lcff_entitlement AS DOUBLE) AS total,
                   TRY_CAST(total_local_revenue_or_in_lieu_of_property_taxes AS DOUBLE)
                       AS local,
                   row_number() OVER (
                       PARTITION BY cds ORDER BY source_file DESC,
                       CASE certification
                           WHEN 'anr3' THEN 7 WHEN 'anr2' THEN 6 WHEN 'anr1' THEN 5
                           WHEN 'r1' THEN 4 WHEN 'annual' THEN 3 WHEN 'an' THEN 3
                           WHEN 'p_2' THEN 2 ELSE 1 END DESC
                   ) AS rn
            FROM lcff_raw
            WHERE substr(cds, 8, 7) = '0000000'
              AND total_lcff_entitlement IS NOT NULL
        )
        SELECT cds, total, local FROM ranked WHERE rn = 1
        """
    ).fetchall()
    return {
        cds: {
            "basic_aid": local is not None and total and local >= total,
            "local_share": _r(local / total) if local is not None and total else None,
        }
        for cds, total, local in rows
    }


def _census_frpm(flags: dict[str, dict] | None = None) -> tuple[dict | None, pl.DataFrame | None]:
    if not CENSUS_FRPM_PARQUET.exists():
        return None, None
    df = pl.read_parquet(CENSUS_FRPM_PARQUET)
    pages = _district_pages()
    flags = flags or {}
    matched = df.filter(
        pl.col("ratio").is_not_null() & pl.col("ratio").is_finite()
    )
    payload = {
        "meta": {
            "acs_vintage": df["acs_vintage"][0],
            "frpm_year": df["frpm_year"].drop_nulls()[0],
            "median_ratio": _r(matched["ratio"].median()),
            "n": len(df),
        },
        "districts": [
            {
                "cds": r["cds"],
                "name": r["name"],
                "dtype": r["dtype"],
                "enr_5_17": None if r["enr_5_17"] is None else int(r["enr_5_17"]),
                "frpm": _r(r["frpm"]),
                "p185": _r(r["p185"]),
                "ratio": _r(r["ratio"]),
                "has_page": r["cds"] in pages,
                "basic_aid": flags.get(r["cds"], {}).get("basic_aid", False),
            }
            for r in df.sort("cds").to_dicts()
        ],
    }
    return payload, df


def _enrolled_race(con) -> dict | None:
    """District enrollment by race/ethnicity, bucketed to match census B03002.

    CDE reporting categories: RE_H Hispanic, RE_W White, RE_B Black, RE_A Asian,
    RE_F Filipino (census counts Filipino students under Asian alone, so it folds
    into `asn` for comparability); the rest (two-or-more, AmInd/AK, Pac. Isl., not
    reported) fold into `oth`. charter='ALL' rows only — Y/N rows would double-count.
    """
    views = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    if "enrollment_raw" not in views:
        return None
    rows = con.execute(
        """
        SELECT reportingcategory, sum(TRY_CAST(total_enr AS BIGINT)) AS n,
               any_value(academicyear) AS year
        FROM enrollment_raw
        WHERE districtcode = '64733' AND aggregatelevel = 'D' AND charter = 'ALL'
          AND reportingcategory LIKE 'RE_%'
          AND academicyear = (SELECT max(academicyear) FROM enrollment_raw)
        GROUP BY 1
        """
    ).fetchall()
    if not rows:
        return None
    by_cat = {cat: n or 0 for cat, n, _ in rows}
    year = rows[0][2]
    total = sum(by_cat.values())
    if not total:
        return None
    buckets = {
        "his": by_cat.get("RE_H", 0),
        "wht": by_cat.get("RE_W", 0),
        "blk": by_cat.get("RE_B", 0),
        "asn": by_cat.get("RE_A", 0) + by_cat.get("RE_F", 0),
    }
    buckets["oth"] = total - sum(buckets.values())
    return {
        "year": year,
        "total": total,
        "race": {k: _r(v / total) for k, v in buckets.items()},
    }


def _year_of(date_str) -> int | None:
    for tok in str(date_str or "").replace("/", "-").split("-"):
        if len(tok) == 4 and tok.isdigit():
            return int(tok)
    return None


def _closures(con) -> list[dict]:
    """Closed LAUSD schools since 2015, with the last enrollment on record.

    Last enrollment stitches the historical census files (enr_type 'C', through
    2022-23) with FRPM K-12 enrollment (2017-18+), taking each school's most
    recent year.
    """
    last_enr = {
        cds: (int(spring), int(enr))
        for cds, spring, enr in con.execute(
            """
            SELECT cds, spring, enr FROM (
                SELECT cds,
                       CASE WHEN length(academic_year) = 7
                            THEN TRY_CAST(substr(academic_year, 1, 4) AS INT) + 1
                            ELSE TRY_CAST(substr(academic_year, 3, 2) AS INT)
                              + CASE WHEN TRY_CAST(substr(academic_year, 3, 2) AS INT) > 50
                                     THEN 1900 ELSE 2000 END
                       END AS spring,
                       sum(TRY_CAST(enr_total AS BIGINT)) AS enr
                FROM enrollment_hist_raw
                WHERE (enr_type = 'C' OR enr_type IS NULL) AND cds LIKE '1964733%'
                GROUP BY 1, 2
                UNION ALL
                SELECT cds, TRY_CAST(substr(academic_year, 1, 4) AS INT) + 1,
                       sum(TRY_CAST(enrollment_k_12 AS DOUBLE))
                FROM frpm_raw
                WHERE cds LIKE '1964733%' AND school_code <> '0000000'
                GROUP BY 1, 2
            )
            WHERE enr IS NOT NULL AND enr > 0
            QUALIFY row_number() OVER (PARTITION BY cds ORDER BY spring DESC) = 1
            """
        ).fetchall()
    }
    rows = con.execute(
        """
        SELECT cds, school AS name, eilname, charter, magnet, opendate, closeddate
        FROM directory_raw
        WHERE cds LIKE '1964733%' AND substr(cds, 8, 7) <> '0000000'
          AND statustype = 'Closed' AND closeddate IS NOT NULL
        QUALIFY row_number() OVER (PARTITION BY cds ORDER BY source_file DESC) = 1
        ORDER BY closeddate DESC
        """
    ).fetchall()
    out = []
    for cds, name, eilname, charter, magnet, opened, closed in rows:
        year = _year_of(closed)
        if not year or year < 2015:
            continue
        enr = last_enr.get(cds)
        out.append(
            {
                "cds": cds,
                "name": name,
                "eil": eilname,
                "year": year,
                "charter": charter == "Y",
                "magnet": magnet == "Y",
                "opened": _year_of(opened),
                "last_enr": enr[1] if enr else None,
                "last_enr_year": enr[0] if enr else None,
            }
        )
    return out


def export_lausd() -> None:
    LAUSD_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    try:
        views = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if "lausd_mp25_raw" not in views:
            print("  LAUSD GIS store missing — skipping /lausd export")
            return

        resolved = lausd.resolve_keys(con)
        roster = lausd.schools_without_boundary(con, resolved)
        index_rows = _index_rows()
        capacity = _capacity(con)
        seni = _seni(con)

        # Role and keys per school.
        with_keys = resolved.filter(pl.col("cds").is_not_null())
        keys_by_cds: dict[str, list[str]] = {}
        role_by_cds: dict[str, str] = {}
        for r in with_keys.to_dicts():
            keys_by_cds.setdefault(r["cds"], []).append(f"{r['level']}:{r['key5']}")
            role_by_cds.setdefault(r["cds"], r["level"].lower())

        eil_level = {"ELEM": "e", "INTMIDJR": "m", "HS": "h"}
        schools_payload = []
        for row in roster.to_dicts():
            cds = row["cds"]
            idx = index_rows.get(cds, {})
            schools_payload.append(
                {
                    "cds": cds,
                    "name": idx.get("name") or row["name"],
                    "ll": idx.get("ll")
                    or (
                        [float(row["latitude"]), float(row["longitude"])]
                        if row["latitude"] and row["longitude"]
                        else None
                    ),
                    "eil": row["eilcode"],
                    "level": role_by_cds.get(cds) or eil_level.get(row["eilcode"], "other"),
                    "flags": idx.get("flags")
                    or [
                        f
                        for f, on in (
                            ("charter", row["charter"] == "Y"),
                            ("magnet", row["magnet"] == "Y"),
                        )
                        if on
                    ],
                    "has_boundary": row["has_boundary"],
                    "boundary_role": role_by_cds.get(cds),
                    "keys": keys_by_cds.get(cds, []),
                    "adj_pct": idx.get("adj_pct"),
                    "level_adj_eb": idx.get("level_adj_eb"),
                    "pass_ela": idx.get("pass_ela"),
                    "pass_math": idx.get("pass_math"),
                    "econ": idx.get("econ"),
                    "enrollment": idx.get("enrollment"),
                    "enr": idx.get("enr"),
                    "capacity": capacity.get(cds),
                    # drop the SENI file's own enrollment (summary-only; the row
                    # already carries CDE enrollment)
                    "seni": (
                        {k: v for k, v in seni[cds].items() if k != "enr"}
                        if cds in seni
                        else None
                    ),
                }
            )
        _write("schools.json", schools_payload)

        # Enrollment divergence ingredients: resident under-18 change per polygon
        # (decennial 2010->2020, exact counts) and each zoned school's census
        # enrollment over the matching school years (2010-11 -> 2020-21).
        child_by_key: dict[tuple[str, str], list] = {}
        try:
            child = lausd_geo.child_change_by_area(con)
            segd = {"E": (0, 5), "M": (5, 10), "H": (10, 15)}
            for row in child.to_dicts():
                for lvl, (a, b) in segd.items():
                    acc = child_by_key.setdefault((lvl, row["p_key"][a:b]), [0, 0])
                    acc[0] += row["kids10"] or 0
                    acc[1] += row["kids20"] or 0
        except Exception as exc:  # noqa: BLE001 - divergence is optional
            print(f"  child change unavailable: {exc}")
        # Historical files use '2010-11'-style years from 2007-08 on (with the
        # census/cumulative C/P split starting 2014-15) and '8182'-style before.
        spring_enr: dict[str, dict[str, int]] = {}
        for cds, ay, enr in con.execute(
            """
            SELECT cds, academic_year, sum(TRY_CAST(enr_total AS BIGINT))
            FROM enrollment_hist_raw
            WHERE cds LIKE '1964733%'
              AND (enr_type = 'C' OR enr_type IS NULL)
              AND academic_year IN ('2010-11', '2020-21')
            GROUP BY 1, 2
            """
        ).fetchall():
            if enr:
                spring_enr.setdefault(cds, {})[ay] = int(enr)
        diverge_pairs: list[tuple[float, float]] = []  # (divergence, adj_pct), E areas

        # Boundaries per level, with resident demographics when available.
        demo = lausd_geo.polygon_demographics(con)
        demo_by_key: dict[tuple[str, str], dict] = {}
        ages_by_key: dict[tuple[str, str], dict[int, float]] = {}
        if demo is not None:
            seg = {"E": (0, 5), "M": (5, 10), "H": (10, 15)}
            joined = demo.to_dicts()
            has_ages = "age_5" in (joined[0] if joined else {})
            for lvl, (a, b) in seg.items():
                agg: dict[str, dict] = {}
                for d in joined:
                    k = d["p_key"][a:b]
                    acc = agg.setdefault(
                        k, {"pop": 0, "pu": 0.0, "p185": 0.0, "rt": 0.0,
                            **{f"r_{x}": 0.0 for x in ("his", "wht", "blk", "asn")}}
                    )
                    acc["pop"] += d["pop20"] or 0
                    acc["pu"] += d["pov_universe"] or 0
                    acc["p185"] += d["pov_under185"] or 0
                    acc["rt"] += d["race_total"] or 0
                    for x in ("his", "wht", "blk", "asn"):
                        acc[f"r_{x}"] += d[f"race_{x}"] or 0
                    if has_ages:
                        ages = ages_by_key.setdefault((lvl, k), {})
                        for age in range(5, 18):
                            ages[age] = ages.get(age, 0.0) + (d.get(f"age_{age}") or 0)
                for k, acc in agg.items():
                    race = {
                        x: _r(acc[f"r_{x}"] / acc["rt"]) if acc["rt"] else None
                        for x in ("his", "wht", "blk", "asn")
                    }
                    if acc["rt"]:
                        race["oth"] = _r(max(0.0, 1 - sum(v or 0 for v in race.values())))
                    else:
                        race["oth"] = None
                    demo_by_key[(lvl, k)] = {
                        "pop": acc["pop"],
                        "p185": _r(acc["p185"] / acc["pu"]) if acc["pu"] else None,
                        "race": race,
                    }

        from shapely.geometry import mapping

        school_demo: dict[str, dict] = {}
        for level in ("E", "M", "H"):
            keys, geoms, info = lausd_geo.dissolve_by_level(resolved, level)
            features = []
            for k, g in zip(keys, geoms):
                meta = info.get(k, {})
                props = {
                    "key": k,
                    "cds": meta.get("cds"),
                    "name": meta.get("name"),
                    "schools": meta.get("schools", []),
                }
                d = demo_by_key.get((level, k))
                if d:
                    props.update(d)
                    if meta.get("cds"):
                        school_demo[meta["cds"]] = d
                # Resident children in this area's own grade band (grade g ~
                # age g+5) — combined spans (e.g. 0-6, 6-12) get their full
                # band; degenerate spans from source quirks (lo == hi) fall
                # back to the level's standard grades.
                grades = meta.get("grades")
                if not grades or int(grades[1]) <= int(grades[0]):
                    grades = {"E": (0, 5), "M": (6, 8), "H": (9, 12)}[level]
                ages = ages_by_key.get((level, k))
                if ages:
                    a0 = 5 + max(int(grades[0]), 0)
                    a1 = 5 + min(int(grades[1]), 12)
                    props["grades"] = [int(grades[0]), int(grades[1])]
                    props["ages"] = [a0, a1]
                    props["students"] = round(
                        sum(ages.get(age, 0) for age in range(a0, a1 + 1))
                    )
                # Enrollment divergence: how much faster the zoned school shrank
                # than its neighborhood's children (percentage points). NOT a
                # capture rate — schools import/export students across zones.
                ck = child_by_key.get((level, k))
                if ck and ck[0] >= 100:
                    kid_chg = ck[1] / ck[0] - 1
                    props["kids10"], props["kids20"] = ck
                    props["kid_chg"] = _r(kid_chg)
                    se = spring_enr.get(meta.get("cds") or "", {})
                    if se.get("2010-11", 0) >= 50 and se.get("2020-21"):
                        sch_chg = se["2020-21"] / se["2010-11"] - 1
                        props["sch_chg"] = _r(sch_chg)
                        props["diverge"] = round((sch_chg - kid_chg) * 100)
                        if level == "E":
                            pct = index_rows.get(meta["cds"], {}).get("adj_pct")
                            if pct is not None:
                                diverge_pairs.append((props["diverge"], pct))
                features.append(
                    {"type": "Feature", "properties": props, "geometry": mapping(g)}
                )
            fc = lausd_geo.simplify_feature_collection(
                {"type": "FeatureCollection", "features": features}
            )
            _write(f"boundaries_{level.lower()}.geojson", fc)

        # Demographics: per-school resident stats + district census-vs-FRPM row.
        funding_flags = lcff_funding_flags(con)
        census_payload, census_df = _census_frpm(funding_flags)
        district_row = None
        if census_df is not None:
            hit = census_df.filter(pl.col("cds") == LAUSD_DCDS)
            if len(hit):
                district_row = {
                    k: _r(v) if isinstance(v, float) else v
                    for k, v in hit.to_dicts()[0].items()
                    if k in ("frpm", "p185", "ratio", "frpm_count", "p185_count",
                             "child_pop", "enr_5_17", "acs_vintage")
                }
        # District-level resident aggregate (sum of polygon counts, when present).
        resident = None
        if demo is not None:
            tot = demo.select(
                pl.col("pop20").sum(),
                pl.col("pov_universe").sum(),
                pl.col("pov_under185").sum(),
                pl.col("race_total").sum(),
                *[pl.col(f"race_{x}").sum() for x in ("his", "wht", "blk", "asn")],
            ).to_dicts()[0]
            rt = tot["race_total"] or 0
            race = {
                x: _r(tot[f"race_{x}"] / rt) if rt else None
                for x in ("his", "wht", "blk", "asn")
            }
            if rt:
                race["oth"] = _r(max(0.0, 1 - sum(v or 0 for v in race.values())))
            resident = {
                "pop": int(tot["pop20"] or 0),
                "p185": _r(tot["pov_under185"] / tot["pov_universe"])
                if tot["pov_universe"]
                else None,
                "race": race,
            }
        _write(
            "demographics.json",
            {
                "census_pending": demo is None,
                "schools": school_demo,
                "district": district_row,
                "resident": resident,
                "enrolled": _enrolled_race(con),
            },
        )

        # Enrollment story: district series (index/district payload), capacity, closures.
        district_payload_path = SITE_DATA / "districts" / f"{LAUSD_DCDS}.json"
        district = (
            json.loads(district_payload_path.read_text())
            if district_payload_path.exists()
            else {}
        )
        divergence_corr = None
        if len(diverge_pairs) >= 30:
            import numpy as np

            arr = np.array(diverge_pairs, dtype=float)
            divergence_corr = {
                "n": len(arr),
                "r_adj_pct": round(float(np.corrcoef(arr[:, 0], arr[:, 1])[0, 1]), 2),
            }
            print(
                f"  divergence vs Similar Schools %ile (E areas): "
                f"r={divergence_corr['r_adj_pct']} (n={divergence_corr['n']})"
            )

        closures = _closures(con)
        for c in closures:
            c["has_page"] = c["cds"] in index_rows
        children_by_vintage = _census_children(con) or {}
        residence = _residence_enrollment(con) or {}
        by_class = _school_enrollment_by_class(con)
        # Public-school enrollment not accounted for by LAUSD-associated schools:
        # resident public-school children (census, ages 5-17) minus LEA-based
        # enrollment (K-12, includes TK and 18+ seniors and non-resident students),
        # for the years both series cover. A residual, not a flow measure.
        public_gap = []
        for v, r in sorted(residence.items()):
            y = int(v)
            cls = by_class.get(y)
            if cls:
                total = sum(cls.values())
                public_gap.append([y, r["public"], total, r["public"] - total])
        _write(
            "enrollment.json",
            {
                "district_enr": district.get("enr"),
                # Resident children 6-17 inside the boundary, one point per ACS
                # 5-year release (overlapping windows, labeled by end year).
                "resident_children": [
                    [int(v), d["children"]] for v, d in sorted(children_by_vintage.items())
                ],
                # "Where did the students go?" — residence-based (census B14003,
                # children 5-17 by enrollment status) vs LEA-based (CDE FRPM,
                # LAUSD-authorized enrollment by school class). Different
                # universes by design; they should not reconcile exactly.
                "residence": [[int(v), d] for v, d in sorted(residence.items())],
                "by_class": [[y, d] for y, d in sorted(by_class.items())],
                "public_gap": public_gap,
                "divergence_corr": divergence_corr,
                "closures": closures,
                "capacity_years": sorted(
                    {y for rows in capacity.values() for y, _, _ in rows}
                ),
            },
        )

        seni_summary = None
        if seni:
            by_q: dict[str, dict] = {}
            for v in seni.values():
                q = v.get("quintile") or "?"
                acc = by_q.setdefault(q, {"n": 0, "alloc": 0.0, "enr": 0.0})
                acc["n"] += 1
                acc["alloc"] += v.get("alloc") or 0
                acc["enr"] += v.get("enr") or 0
            seni_summary = {
                "year": next(iter(seni.values()))["year"],
                "n": len(seni),
                "total_alloc": sum(v.get("alloc") or 0 for v in seni.values()),
                "total_enr": sum(v.get("enr") or 0 for v in seni.values()),
                "by_quintile": dict(sorted(by_q.items())),
            }
        _write(
            "funding.json",
            {
                "ppe_hist": district.get("ppe_hist"),
                "ppe_years": district.get("ppe_years"),
                "frpm_hist": district.get("frpm_hist"),
                "lcff": _lcff(con),
                "lcff_status": funding_flags.get(LAUSD_DCDS),
                "seni": seni_summary,
                "census": district_row,
            },
        )

        # Compact stats for the overview lander's cards (SSR-inlined, so small):
        # resident children 5-17 (B14003 totals) per ACS vintage, their poverty
        # share (B17024, ages 6-17), and the latest enrollment-by-class split.
        children = _census_children(con) or {}
        rvints = sorted(residence)
        latest_rv = rvints[-1] if rvints else None
        prev_rv = rvints[0] if len(rvints) > 1 else None
        latest_cls = by_class[max(by_class)] if by_class else None
        _write(
            "overview.json",
            {
                "census": {
                    "vintage": latest_rv,
                    "children": residence.get(latest_rv, {}).get("total"),
                    "children_prev": residence.get(prev_rv, {}).get("total")
                    if prev_rv
                    else None,
                    "prev_vintage": prev_rv,
                    # poverty share is B17024's 6-17 universe (labeled on-page)
                    "p185": children.get(max(children), {}).get("p185") if children else None,
                }
                if latest_rv
                else None,
                "by_class": {"year": max(by_class), **latest_cls} if latest_cls else None,
            },
        )

        # Always written so prerendered pages can fetch it strictly; meta=None means
        # the census store isn't built yet and the site renders a pending note.
        _write("census_frpm.json", census_payload or {"meta": None, "districts": []})
    finally:
        con.close()


if __name__ == "__main__":
    export_lausd()
