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


def _district_pages() -> set[str]:
    index_path = SITE_DATA / "index.json"
    if not index_path.exists():
        return set()
    return {
        e["cds"] for e in json.loads(index_path.read_text()) if e.get("kind") == "district"
    }


def _census_frpm() -> tuple[dict | None, pl.DataFrame | None]:
    if not CENSUS_FRPM_PARQUET.exists():
        return None, None
    df = pl.read_parquet(CENSUS_FRPM_PARQUET)
    pages = _district_pages()
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
                       TRY_CAST(substr(academic_year, 3, 2) AS INT)
                         + CASE WHEN TRY_CAST(substr(academic_year, 3, 2) AS INT) > 50
                                THEN 1900 ELSE 2000 END AS spring,
                       sum(TRY_CAST(enr_total AS BIGINT)) AS enr
                FROM enrollment_hist_raw
                WHERE enr_type = 'C' AND cds LIKE '1964733%'
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

        # Boundaries per level, with resident demographics when available.
        demo = lausd_geo.polygon_demographics(con)
        demo_by_key: dict[tuple[str, str], dict] = {}
        if demo is not None:
            seg = {"E": (0, 5), "M": (5, 10), "H": (10, 15)}
            joined = demo.to_dicts()
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
                features.append(
                    {"type": "Feature", "properties": props, "geometry": mapping(g)}
                )
            fc = lausd_geo.simplify_feature_collection(
                {"type": "FeatureCollection", "features": features}
            )
            _write(f"boundaries_{level.lower()}.geojson", fc)

        # Demographics: per-school resident stats + district census-vs-FRPM row.
        census_payload, census_df = _census_frpm()
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
        closures = _closures(con)
        for c in closures:
            c["has_page"] = c["cds"] in index_rows
        _write(
            "enrollment.json",
            {
                "district_enr": district.get("enr"),
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
                "seni": seni_summary,
                "census": district_row,
            },
        )

        # Always written so prerendered pages can fetch it strictly; meta=None means
        # the census store isn't built yet and the site renders a pending note.
        _write("census_frpm.json", census_payload or {"meta": None, "districts": []})
    finally:
        con.close()


if __name__ == "__main__":
    export_lausd()
