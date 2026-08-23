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
from schoolfactors.paths import DUCKDB_PATH, PARQUET_DIR, REPO_ROOT

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
          AND coalesce(survey, 'acs5') = 'acs5'
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


def _b14003_status(con, geo_type: str, geoid: str | None) -> dict[str, dict] | None:
    """B14003 children 5-17 {public, private, not_enrolled, total} per vintage.

    One geography when `geoid` is given; the statewide sum of the geo_type's
    partition when None (county files carry all 58 counties, so summing them
    is the state; each sd_* file likewise carries a Remainder-of-California row).
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
        f"""
        SELECT vintage, variable, label, sum(TRY_CAST(value AS DOUBLE)) AS v
        FROM census_acs_raw
        WHERE table_id = 'B14003' AND geo_type = ?
          AND coalesce(survey, 'acs5') = 'acs5'
          {"AND geoid = ?" if geoid else ""}
          AND (TRY_CAST(value AS DOUBLE) IS NULL OR TRY_CAST(value AS DOUBLE) >= 0)
        GROUP BY 1, 2, 3
        """,
        [geo_type, geoid] if geoid else [geo_type],
    ).fetchall()
    out: dict[str, dict] = {}
    for vintage, variable, label, v in rows:
        if not variable.endswith("E") or not label or v is None:
            continue
        parts = [p.rstrip(":") for p in label.split("!!")]
        if len(parts) != 5 or parts[2] not in ("Male", "Female") or parts[4] not in ages:
            continue
        cat = cats.get(parts[3])
        if cat is None:
            continue
        acc = out.setdefault(vintage, dict.fromkeys(cats.values(), 0.0))
        acc[cat] += v
    for acc in out.values():
        acc["total"] = round(sum(acc.values()))
        for k in cats.values():
            acc[k] = round(acc[k])
    return out or None


def _cde_census_day(
    con, hist_pred: str, new_pred: str, since_spring: int = 2007
) -> dict[int, int]:
    """Census-day enrollment by spring year, stitching the historical school-level
    files (enr_type 'C', through 2022-23) with the current-format rows. The
    historical files are school-level only, so summing them never double-counts;
    `adult` is carried separately in old eras and excluded. Current-format
    aggregate rows are taken at Charter='ALL'; school rows carry only Y/N (one
    row per school), so the charter filter applies to aggregates alone."""
    out: dict[int, int] = {}
    for year, enr in con.execute(
        f"""
        SELECT TRY_CAST(substr(academic_year, 1, 4) AS INT) + 1 AS year,
               sum(TRY_CAST(enr_total AS DOUBLE))
                 - sum(coalesce(TRY_CAST(adult AS DOUBLE), 0))
        FROM enrollment_hist_raw
        WHERE (enr_type = 'C' OR enr_type IS NULL) AND length(academic_year) = 7
          AND TRY_CAST(substr(academic_year, 1, 4) AS INT) + 1 >= {int(since_spring)}
          AND {hist_pred}
        GROUP BY 1
        """
    ).fetchall():
        if year and enr:
            out[year] = round(enr)
    for year, enr in con.execute(
        f"""
        SELECT TRY_CAST(substr(academicyear, 1, 4) AS INT) + 1 AS year,
               sum(TRY_CAST(total_enr AS DOUBLE))
        FROM enrollment_raw
        WHERE reportingcategory = 'TA'
          AND (aggregatelevel = 'S' OR charter = 'ALL') AND {new_pred}
        GROUP BY 1
        """
    ).fetchall():
        if year and enr:
            out[year] = round(enr)
    return out


def _flows(con, residence: dict[str, dict]) -> dict | None:
    """Three-level reconciliation of resident children vs census-day enrollment.

    For each ACS vintage v (5-year window ending in calendar year v) the CDE side
    is the mean census-day enrollment over the five school years overlapping the
    window (springs v-3 .. v+1). At the state level inter-district enrollment nets
    out, so the state residual (ACS public minus CDE) is pure universe mismatch —
    TK 4-year-olds and 18+ seniors in CDE but outside ages 5-17, plus survey error.
    Measured 2015-2023 it is stable (-4.8% to -6.5%, no trend), which is what makes
    the district- and county-level residuals interpretable as apparent enrollment
    across boundaries rather than measurement drift.
    """
    views = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    if "enrollment_hist_raw" not in views or "enrollment_raw" not in views:
        return None
    county = _b14003_status(con, "county", "06037")
    state = _b14003_status(con, "county", None)
    if not residence or not county or not state:
        return None
    cde = {
        "district": _cde_census_day(
            con,
            "cds LIKE '1964733%'",
            "aggregatelevel = 'D' AND countycode = '19' AND districtcode = '64733'",
        ),
        "county": _cde_census_day(
            con, "substr(cds, 1, 2) = '19'", "aggregatelevel = 'C' AND countycode = '19'"
        ),
        "state": _cde_census_day(con, "TRUE", "aggregatelevel = 'T'"),
    }
    acs = {"district": residence, "county": county, "state": state}
    levels: dict[str, list] = {}
    for level, by_vintage in acs.items():
        series = []
        for v in sorted(by_vintage):
            y = int(v)
            springs = [s for s in range(y - 3, y + 2) if s in cde[level]]
            if len(springs) < 5:
                continue
            a = by_vintage[v]
            series.append(
                [
                    y,
                    {
                        "public": a["public"],
                        "private": a["private"],
                        "not_enrolled": a["not_enrolled"],
                        "total": a["total"],
                        "cde": round(sum(cde[level][s] for s in springs) / len(springs)),
                    },
                ]
            )
        if len(series) < 2:
            return None
        levels[level] = series
    # Context series: statewide census-day enrollment at charter schools the CDE
    # directory currently flags fully/primarily virtual ('F'/'V'). The flag is
    # present-day, so early years are approximate — labeled as such on-page.
    virtual = []
    if "directory_raw" in views:
        virtual = [
            [y, int(v)]
            for y, v in con.execute(
                """
                WITH virt AS (
                    SELECT cds FROM directory_raw
                    WHERE trim(charter) = 'Y' AND trim(virtual) IN ('F', 'V')
                    GROUP BY cds
                ),
                hist AS (
                    SELECT TRY_CAST(substr(h.academic_year, 1, 4) AS INT) + 1 AS year,
                           sum(TRY_CAST(h.enr_total AS DOUBLE)) AS enr
                    FROM enrollment_hist_raw h JOIN virt USING (cds)
                    WHERE (h.enr_type = 'C' OR h.enr_type IS NULL)
                      AND length(h.academic_year) = 7
                      AND TRY_CAST(substr(h.academic_year, 1, 4) AS INT) >= 2014
                    GROUP BY 1
                ),
                cur AS (
                    SELECT TRY_CAST(substr(e.academicyear, 1, 4) AS INT) + 1 AS year,
                           sum(TRY_CAST(e.total_enr AS DOUBLE)) AS enr
                    FROM enrollment_raw e JOIN virt USING (cds)
                    WHERE e.aggregatelevel = 'S' AND e.reportingcategory = 'TA'
                    GROUP BY 1
                )
                SELECT year, enr FROM hist
                UNION ALL
                SELECT year, enr FROM cur WHERE year NOT IN (SELECT year FROM hist)
                ORDER BY year
                """
            ).fetchall()
            if y and v
        ]
    return {
        "levels": levels,
        "names": {
            "district": "LAUSD boundary",
            "county": "Los Angeles County",
            "state": "California",
        },
        "virtual": virtual,
    }


def _acs1_control_factors(con) -> dict[int, dict[str, float]]:
    """Correction factors for pre-2010 ACS 1-year levels, per survey year
    2005-2009: 2010-census-consistent intercensal children 5-17 over the
    same-year vintage postcensal 5-17 — the population controls that ACS year
    actually weighted to — for LA County ('la') and California ('ca').

    The old Census-2000-based controls overstated LA County children by up to
    ~5% (2005), which masqueraded as a county-level enrollment residual. Ages
    15-17 in the intercensal file's 5-year bins are approximated as 3/5 of the
    15-19 group (≲0.3% effect on the ratio); the vintage side is exact 5-17.
    See known_issues/acs-pre2010-population-controls-la-county.yaml.
    """
    views = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    if "popest_raw" not in views:
        return {}
    int_la: dict[int, float] = {}
    int_ca: dict[int, float] = {}
    for jy, cty, grp, v in con.execute(
        """
        SELECT july_year, county, agegrp, TRY_CAST(value AS DOUBLE)
        FROM popest_raw
        WHERE series = 'intercensal' AND agegrp IN ('2', '3', '4')
        """
    ).fetchall():
        if v is None:
            continue
        y = int(jy)
        w = 0.6 if grp == "4" else 1.0
        int_ca[y] = int_ca.get(y, 0.0) + v * w
        if cty == "037":
            int_la[y] = int_la.get(y, 0.0) + v * w
    post_la: dict[int, float] = {}
    post_ca: dict[int, float] = {}
    for series, jy, cty, v in con.execute(
        """
        SELECT series, july_year, county, sum(TRY_CAST(value AS DOUBLE))
        FROM popest_raw
        WHERE series LIKE 'vintage%'
          AND measure IN ('age513_tot', 'age1417_tot')
        GROUP BY 1, 2, 3
        """
    ).fetchall():
        y = int(series.removeprefix("vintage"))
        if v is None or int(jy) != y:  # only each vintage's own July estimate
            continue
        post_ca[y] = post_ca.get(y, 0.0) + v
        if cty == "037":
            post_la[y] = post_la.get(y, 0.0) + v
    return {
        y: {"la": int_la[y] / post_la[y], "ca": int_ca[y] / post_ca[y]}
        for y in sorted(post_la)
        if y in int_la and y in post_ca and y in int_ca
    }


def _narrative(con, flows: dict | None) -> dict | None:
    """Supplementary series for the narrative enrollment page.

    - peak + county_share_hist: CDE-only walk-back to LAUSD's 2003-04 peak
      (no ACS 5-year exists before the 2010 vintage, so pre-2010 years are
      enrollment-only: LAUSD vs rest-of-LA-county).
    - district_flows: per-unified-district residuals (ACS public 5-17 minus the
      district's census-day enrollment, 5-yr mean) for LA County — the
      importer/exporter ledger. Elementary/secondary pairs overlap in geography
      and are omitted; the county block in `flows` is complete regardless.
    - inside_charters: enrollment at non-LAUSD-authorized charter campuses whose
      directory coordinates fall inside the union of MP25 attendance polygons.
    - annual_cells: the conclusion diagram's accounting on the ACS 1-year basis,
      one row per survey year (2005-2024, no 2020): exact census-day counts for
      the LAUSD classes and in-boundary non-LAUSD charters; the remainder split
      between other districts (rest-of-county ledger) and virtual/out-of-county
      by allocating the county-wide virtual/remote pool proportionally to
      resident population (ACS margins in `est`); pre-2010 ACS levels are
      corrected to intercensal population controls (_acs1_control_factors).
    """
    views = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    if flows is None or "enrollment_hist_raw" not in views or "directory_raw" not in views:
        return None
    lausd = _cde_census_day(
        con, "cds LIKE '1964733%'",
        "aggregatelevel = 'D' AND countycode = '19' AND districtcode = '64733'",
        since_spring=1996,
    )
    county = _cde_census_day(
        con, "substr(cds, 1, 2) = '19'", "aggregatelevel = 'C' AND countycode = '19'",
        since_spring=1996,
    )
    peak_y = max(lausd, key=lambda y: lausd[y])
    share_hist = [
        [y, lausd[y], county[y] - lausd[y]]
        for y in sorted(lausd)
        if y >= 1996 and y in county
    ]

    # Per-district ACS public 5-17 (unified geography carries every LA county
    # unified district; ncesdist in the directory is the census geoid).
    ages = {"5 to 9 years", "10 to 14 years", "15 to 17 years"}
    dist_acs: dict[tuple[int, str], float] = {}
    for vin, geoid, var, lab, v in con.execute(
        """
        SELECT vintage, geoid, variable, label, TRY_CAST(value AS DOUBLE)
        FROM census_acs_raw WHERE table_id = 'B14003' AND geo_type = 'sd_unified'
          AND coalesce(survey, 'acs5') = 'acs5'
          AND (TRY_CAST(value AS DOUBLE) IS NULL OR TRY_CAST(value AS DOUBLE) >= 0)
        """
    ).fetchall():
        if not var.endswith("E") or not lab or v is None:
            continue
        p = [x.rstrip(":") for x in lab.split("!!")]
        if (len(p) == 5 and p[2] in ("Male", "Female")
                and p[3] == "Enrolled in public school" and p[4] in ages):
            dist_acs[(int(vin), geoid)] = dist_acs.get((int(vin), geoid), 0.0) + v
    vintages = sorted({v for v, _ in dist_acs})

    def mean5(series: dict[int, int], vintage: int):
        ys = [s for s in range(vintage - 3, vintage + 2) if s in series]
        return sum(series[s] for s in ys) / len(ys) if len(ys) == 5 else None

    district_flows = []
    other_uni: dict[int, int] = {}
    for dcode, nces, dname in con.execute(
        """
        SELECT substr(cds, 1, 7), any_value(ncesdist), any_value(district)
        FROM directory_raw
        WHERE substr(cds, 1, 2) = '19' AND doc = '54'
          AND ncesdist IS NOT NULL AND ncesdist <> ''
        GROUP BY 1
        """
    ).fetchall():
        ser = _cde_census_day(
            con, f"substr(cds, 1, 7) = '{dcode}'",
            f"aggregatelevel = 'D' AND countycode = '19' "
            f"AND districtcode = '{dcode[2:]}'",
        )
        if dcode != "1964733":
            for y, e in ser.items():
                other_uni[y] = other_uni.get(y, 0) + e
        resid = []
        detail = []
        latest_cde = None
        for v in vintages:
            m5 = mean5(ser, v)
            a = dist_acs.get((v, nces))
            if m5 and a is not None:
                resid.append([v, _r((a - m5) / m5)])
                detail.append([v, round(a), round(m5)])
                latest_cde = round(m5)
        if len(resid) >= 2:
            district_flows.append(
                {
                    "name": dname,
                    "dcode": dcode,
                    "cde": latest_cde,
                    "resid": resid,
                    "detail": detail,
                }
            )
    district_flows.sort(key=lambda d: d["resid"][-1][1])
    # Composition of each district's associated enrollment by school category —
    # district-run vs brick-and-mortar charter vs fully/primarily-virtual
    # charter (directory flags, present-day) — as 5-yr means at the latest
    # window. Distinguishes permit-style importers (seats in their own schools)
    # from charter-umbrella LEAs, and virtual-heavy umbrellas from classroom
    # ones (e.g. Acton-Agua Dulce's iLEAD/Compass network vs Duarte's CSArts).
    latest_win = max(vintages)
    mix_rows = con.execute(
        """
        WITH cat AS (
            SELECT cds,
                   CASE WHEN any_value(trim(charter)) = 'Y'
                             AND any_value(trim(virtual)) IN ('F', 'V') THEN 'cv'
                        WHEN any_value(trim(charter)) = 'Y' THEN 'cb'
                        ELSE 'dr' END AS c
            FROM directory_raw WHERE substr(cds, 1, 2) = '19' GROUP BY cds
        ),
        hist AS (
            SELECT substr(h.cds, 1, 7) AS d, cat.c,
                   TRY_CAST(substr(h.academic_year, 1, 4) AS INT) + 1 AS y,
                   sum(TRY_CAST(h.enr_total AS DOUBLE)) AS enr
            FROM enrollment_hist_raw h JOIN cat ON h.cds = cat.cds
            WHERE (h.enr_type = 'C' OR h.enr_type IS NULL)
              AND length(h.academic_year) = 7 AND substr(h.cds, 1, 2) = '19'
            GROUP BY 1, 2, 3
        ),
        cur AS (
            SELECT substr(e.cds, 1, 7) AS d, cat.c,
                   TRY_CAST(substr(e.academicyear, 1, 4) AS INT) + 1 AS y,
                   sum(TRY_CAST(e.total_enr AS DOUBLE)) AS enr
            FROM enrollment_raw e JOIN cat ON e.cds = cat.cds
            WHERE e.aggregatelevel = 'S' AND e.reportingcategory = 'TA'
              AND substr(e.cds, 1, 2) = '19'
            GROUP BY 1, 2, 3
        )
        SELECT d, c, y, enr FROM hist
        UNION ALL
        SELECT d, c, y, enr FROM cur WHERE y NOT IN (SELECT DISTINCT y FROM hist)
        """
    ).fetchall()
    mix_ser: dict[tuple[str, str], dict[int, float]] = {}
    for d, c, y, enr in mix_rows:
        if y and enr:
            mix_ser.setdefault((d, c), {})[y] = enr
    mix_map: dict[str, dict] = {}
    for (d, c), ser in mix_ser.items():
        # missing springs within the window are true zeros (school not open /
        # no enrollment), so average over the full window rather than requiring
        # all five years the way the residual series does
        m5 = sum(ser.get(s, 0) for s in range(latest_win - 3, latest_win + 2)) / 5
        if m5:
            mix_map.setdefault(d, {})[c] = round(m5)

    perf_map = _district_perf(con)
    for df_row in district_flows:
        dcode = df_row.pop("dcode")
        df_row["perf"] = perf_map.get(dcode)
        df_row["mix"] = mix_map.get(dcode)
        df_row["cds"] = dcode + "0000000"

    # --- county seat ledger, by authorizer group -----------------------------
    # LAUSD split into traditional+affiliated vs independent (directly funded)
    # charters via the directory's charter/funding flags (current-day flags; the
    # split is approximate in early years and cross-checked against FRPM where
    # both exist). Unmatched LAUSD schools (closed before the modern directory)
    # fold into traditional.
    cls_rows = con.execute(
        """
        WITH cls AS (
            SELECT cds,
                   CASE WHEN any_value(trim(charter)) = 'Y'
                             AND any_value(fundingtype) ILIKE '%direct%' THEN 'ind'
                        WHEN any_value(trim(charter)) = 'Y' THEN 'aff'
                        ELSE 'trad' END AS c
            FROM directory_raw WHERE cds LIKE '1964733%' GROUP BY cds
        ),
        hist AS (
            SELECT TRY_CAST(substr(h.academic_year, 1, 4) AS INT) + 1 AS y,
                   coalesce(cls.c, 'trad') AS c,
                   sum(TRY_CAST(h.enr_total AS DOUBLE)) AS enr
            FROM enrollment_hist_raw h LEFT JOIN cls ON h.cds = cls.cds
            WHERE (h.enr_type = 'C' OR h.enr_type IS NULL)
              AND length(h.academic_year) = 7 AND h.cds LIKE '1964733%'
            GROUP BY 1, 2
        ),
        cur AS (
            SELECT TRY_CAST(substr(e.academicyear, 1, 4) AS INT) + 1 AS y,
                   coalesce(cls.c, 'trad') AS c,
                   sum(TRY_CAST(e.total_enr AS DOUBLE)) AS enr
            FROM enrollment_raw e LEFT JOIN cls ON e.cds = cls.cds
            WHERE e.aggregatelevel = 'S' AND e.reportingcategory = 'TA'
              AND e.cds LIKE '1964733%'
            GROUP BY 1, 2
        )
        SELECT y, c, enr FROM hist
        UNION ALL
        SELECT y, c, enr FROM cur WHERE y NOT IN (SELECT DISTINCT y FROM hist)
        """
    ).fetchall()
    # Three-way class series (trad / affiliated / independent charters) per
    # spring year, and the trad+aff combination the county ledger uses.
    by_cls: dict[str, dict[int, int]] = {"trad": {}, "aff": {}, "ind": {}}
    for y, c, enr in cls_rows:
        if y and enr:
            by_cls[c][y] = by_cls[c].get(y, 0) + round(enr)
    years_cls = sorted(set().union(*[set(v) for v in by_cls.values()]))
    lausd_classes = [
        [y, by_cls["trad"].get(y, 0), by_cls["aff"].get(y, 0), by_cls["ind"].get(y, 0)]
        for y in years_cls
        if y >= 1996
    ]
    lausd_cls: dict[str, dict[int, int]] = {
        "trad_aff": {
            y: by_cls["trad"].get(y, 0) + by_cls["aff"].get(y, 0) for y in years_cls
        },
        "ind": by_cls["ind"],
    }

    elemhs_codes = [
        r[0] for r in con.execute(
            """
            SELECT DISTINCT substr(cds, 1, 7) FROM directory_raw
            WHERE substr(cds, 1, 2) = '19' AND doc IN ('52', '56')
            """
        ).fetchall()
    ]
    quoted = ",".join(f"'{c}'" for c in elemhs_codes)
    dcodes = ",".join(f"'{c[2:]}'" for c in elemhs_codes)
    elemhs = _cde_census_day(
        con, f"substr(cds, 1, 7) IN ({quoted})",
        f"aggregatelevel = 'D' AND countycode = '19' AND districtcode IN ({dcodes})",
    )
    ledger = []
    for v in vintages:
        row = {"y": v}
        parts = {
            "trad_aff": mean5(lausd_cls["trad_aff"], v),
            "ind": mean5(lausd_cls["ind"], v),
            "other_uni": mean5(other_uni, v),
            "elemhs": mean5(elemhs, v),
            "county": mean5(county, v),
        }
        if any(p is None for p in parts.values()):
            continue
        row.update({k: round(p) for k, p in parts.items()})
        row["remainder"] = (
            row["county"] - row["trad_aff"] - row["ind"] - row["other_uni"]
            - row["elemhs"]
        )
        ledger.append(row)

    # --- resident children 5-17 inside LAUSD, both ACS surveys ----------------
    # 1-year points (2005-2009, single-year estimates) extend the hero series
    # back before the first 5-year release; consumers must label them.
    res517: dict[tuple[int, str], list[float]] = {}
    for vin, survey, var, lab, v in con.execute(
        """
        SELECT vintage, coalesce(survey, 'acs5'), variable, label,
               TRY_CAST(value AS DOUBLE)
        FROM census_acs_raw
        WHERE table_id = 'B14003' AND geo_type = 'sd_unified' AND geoid = ?
          AND (TRY_CAST(value AS DOUBLE) IS NULL OR TRY_CAST(value AS DOUBLE) >= 0)
        """,
        [LAUSD_GEOID],
    ).fetchall():
        if not var.endswith("E") or not lab or v is None:
            continue
        p = [x.rstrip(":") for x in lab.split("!!")]
        if len(p) == 5 and p[2] in ("Male", "Female") and p[4] in ages:
            acc = res517.setdefault((int(vin), survey), [0.0, 0.0])
            acc[0] += v
            if p[3] == "Enrolled in public school":
                acc[1] += v
    # [year, total 5-17, survey, of-which-public] — one point per year,
    # preferring the 5-year estimate where both surveys exist (ACS1 now spans
    # 2005-2024, so it fills only the years the 5-year windows can't reach).
    by_year: dict[int, tuple[str, float, float]] = {}
    for (y, survey), (tot, pub) in sorted(res517.items()):
        if y not in by_year or (survey == "acs5" and by_year[y][0] == "acs1"):
            by_year[y] = (survey, tot, pub)
    resident_517 = [
        [y, round(tot), survey, round(pub)]
        for y, (survey, tot, pub) in sorted(by_year.items())
    ]

    # Per-county residual at the latest vintage: the cross-county ledger that
    # names the importer counties (CA county FIPS = 2 * CDE county code - 1).
    cty_acs: dict[tuple[int, str], float] = {}
    cty_names: dict[str, str] = {}
    for vin, geoid, gname, var, lab, v in con.execute(
        """
        SELECT vintage, geoid, geo_name, variable, label, TRY_CAST(value AS DOUBLE)
        FROM census_acs_raw WHERE table_id = 'B14003' AND geo_type = 'county'
          AND coalesce(survey, 'acs5') = 'acs5'
          AND (TRY_CAST(value AS DOUBLE) IS NULL OR TRY_CAST(value AS DOUBLE) >= 0)
        """
    ).fetchall():
        if not var.endswith("E") or not lab or v is None:
            continue
        p = [x.rstrip(":") for x in lab.split("!!")]
        if (len(p) == 5 and p[2] in ("Male", "Female")
                and p[3] == "Enrolled in public school" and p[4] in ages):
            cty_acs[(int(vin), geoid)] = cty_acs.get((int(vin), geoid), 0.0) + v
            cty_names[geoid] = (gname or "").replace(" County, California", "")
    latest_v = max((v for v, _ in cty_acs), default=None)
    # Virtual/nonclassroom charter enrollment per county (any authorizer):
    # directory-flagged F/V charter schools, census-day, 5-yr mean at the
    # latest window — the geographic-decoupling side of the county ledger.
    virt_rows = con.execute(
        """
        WITH virt AS (
            SELECT cds FROM directory_raw
            WHERE trim(charter) = 'Y' AND trim(virtual) IN ('F', 'V')
            GROUP BY cds
        ),
        hist AS (
            SELECT substr(h.cds, 1, 2) AS cc,
                   TRY_CAST(substr(h.academic_year, 1, 4) AS INT) + 1 AS y,
                   sum(TRY_CAST(h.enr_total AS DOUBLE)) AS enr
            FROM enrollment_hist_raw h JOIN virt ON h.cds = virt.cds
            WHERE (h.enr_type = 'C' OR h.enr_type IS NULL)
              AND length(h.academic_year) = 7
            GROUP BY 1, 2
        ),
        cur AS (
            SELECT substr(e.cds, 1, 2) AS cc,
                   TRY_CAST(substr(e.academicyear, 1, 4) AS INT) + 1 AS y,
                   sum(TRY_CAST(e.total_enr AS DOUBLE)) AS enr
            FROM enrollment_raw e JOIN virt ON e.cds = virt.cds
            WHERE e.aggregatelevel = 'S' AND e.reportingcategory = 'TA'
            GROUP BY 1, 2
        )
        SELECT cc, y, enr FROM hist
        UNION ALL
        SELECT cc, y, enr FROM cur WHERE y NOT IN (SELECT DISTINCT y FROM hist)
        """
    ).fetchall()
    virt_ser: dict[str, dict[int, float]] = {}
    for cc, y, enr in virt_rows:
        if y and enr:
            virt_ser.setdefault(cc, {})[y] = virt_ser.get(cc, {}).get(y, 0) + enr
    county_flows = []
    if latest_v:
        for geoid, cname in cty_names.items():
            cc = f"{(int(geoid[2:]) + 1) // 2:02d}"
            ser = _cde_census_day(
                con, f"substr(cds, 1, 2) = '{cc}'",
                f"aggregatelevel = 'C' AND countycode = '{cc}'",
            )
            m5 = mean5(ser, latest_v)
            a = cty_acs.get((latest_v, geoid))
            if m5 and a is not None:
                detail = []
                for v in vintages:
                    mv = mean5(ser, v)
                    av = cty_acs.get((v, geoid))
                    if mv and av is not None:
                        detail.append([v, round(av), round(mv)])
                vser = virt_ser.get(cc, {})
                virt5 = sum(
                    vser.get(sp, 0) for sp in range(latest_v - 3, latest_v + 2)
                ) / 5
                county_flows.append(
                    {
                        "name": cname,
                        "cde": round(m5),
                        "pct": _r((a - m5) / m5),
                        "virt": round(virt5),
                        "detail": detail,
                    }
                )
        county_flows.sort(key=lambda c: c["pct"])

    # LA County flagged-virtual charter enrollment per window (5-yr means) —
    # feeds the conclusion diagram's physical/virtual apportionment.
    la_virt_ser = virt_ser.get("19", {})
    la_virtual = [
        [v, round(sum(la_virt_ser.get(sp, 0) for sp in range(v - 3, v + 2)) / 5)]
        for v in vintages
    ]

    # Annual reconciliation on the ACS 1-year basis (2005-2024; 2020 was never
    # released). ACS calendar year y straddles school years spring-y and
    # spring-(y+1); the CDE side is the mean of those two census days. Powers
    # the annual county-import chart and the through-2024 postscript. 1-year
    # estimates are noisier than 5-year windows, and pre-2010 ACS samples were
    # smaller still — consumers label accordingly.
    acs1_cats = {
        "Enrolled in public school": "public",
        "Enrolled in private school": "private",
        "Not enrolled in school": "not_enrolled",
    }

    def _acs1_status(geo_type: str, geoid: str) -> dict[int, dict[str, float]]:
        """Per survey year: public/private/not_enrolled/total, plus public_moe —
        the published margins of the six public-school leaf cells combined
        root-sum-square (approximate: ignores control covariance)."""
        acc: dict[int, dict[str, float]] = {}
        for vin, var, lab, v in con.execute(
            """
            SELECT vintage, variable, label, TRY_CAST(value AS DOUBLE)
            FROM census_acs_raw
            WHERE table_id = 'B14003' AND survey = 'acs1'
              AND geo_type = ? AND geoid = ?
              AND (TRY_CAST(value AS DOUBLE) IS NULL OR TRY_CAST(value AS DOUBLE) >= 0)
            """,
            [geo_type, geoid],
        ).fetchall():
            if not lab or v is None:
                continue
            p = [x.rstrip(":") for x in lab.split("!!")]
            if len(p) != 5 or p[2] not in ("Male", "Female") or p[4] not in ages:
                continue
            cat = acs1_cats.get(p[3])
            if cat is None:
                continue
            a = acc.setdefault(
                int(vin), dict.fromkeys([*acs1_cats.values(), "_pub_moe_sq"], 0.0)
            )
            if var.endswith("E"):
                a[cat] += v
            elif var.endswith("M") and cat == "public":
                a["_pub_moe_sq"] += v * v
        for a in acc.values():
            a["public_moe"] = a.pop("_pub_moe_sq") ** 0.5
            a["total"] = a["public"] + a["private"] + a["not_enrolled"]
        return acc

    state1 = _acs1_status("state", "06")
    county1 = _acs1_status("county", "06037")
    lausd1 = _acs1_status("sd_unified", "0622710")

    # Pre-2010 population-control correction (explicit transform): scale each
    # affected survey year's levels — LAUSD and county by the LA factor, state
    # by the CA factor — to 2010-census-consistent intercensal controls. See
    # _acs1_control_factors and the known-issues entry it cites.
    factors = _acs1_control_factors(con)
    for fy, f in factors.items():
        for status, key in ((state1, "ca"), (county1, "la"), (lausd1, "la")):
            if fy in status:
                for k in status[fy]:
                    status[fy][k] *= f[key]
    state_cde = _cde_census_day(con, "TRUE", "aggregatelevel = 'T'", since_spring=1996)
    annual: dict[str, list] = {}
    for lvl, acc, cdeser in (
        ("state", state1, state_cde),
        ("county", county1, county),
        ("lausd", lausd1, lausd),
    ):
        series = []
        for y in sorted(acc):
            a, b = cdeser.get(y), cdeser.get(y + 1)
            if a and b:
                series.append([y, round(acc[y]["public"]), round((a + b) / 2)])
        annual[lvl] = series

    inside, inside_bm = _inside_charters(con)

    # Correct the hero chart's early single-year resident points to the same
    # intercensal controls (labeled on-page).
    for row in resident_517:
        if row[2] == "acs1" and row[0] in factors:
            f_la = factors[row[0]]["la"]
            row[1] = round(row[1] * f_la)
            row[3] = round(row[3] * f_la)

    # Annual conclusion cells: where the boundary's resident children 5-17 are
    # counted, per ACS 1-year survey year (2005-2024; no 2020). CDE-side series
    # take the straddle mean of the two census days an ACS calendar year spans;
    # LAUSD-sector seats convert to resident children with the same-year state
    # calibration; pre-2010 ACS levels carry the intercensal control correction
    # applied above. Cell structure (exact → estimated → residual):
    #   - trad/aff/ind: LAUSD-authorized census-day counts (exact CDE side)
    #   - phys_chr: non-LAUSD brick-and-mortar charters located inside the
    #     boundary (exact CDE side; virtual-flagged campuses excluded)
    #   - phys_oth: rest-of-county LEAs' net physical absorption — their
    #     adjusted seats minus flagged-virtual seats and the in-boundary
    #     charters, minus their own resident public children (exact identity:
    #     elsewhere = rest-of-county net import + county out-of-county
    #     residual, so no population-share apportionment is needed)
    #   - vr: the residual — virtual enrollment plus net counted outside the
    #     county — with an ACS margin of error alongside (est.moe_*).
    def _straddle(ser: dict[int, int], y: int, zero_missing: bool = False):
        a, b = ser.get(y), ser.get(y + 1)
        if zero_missing:
            return ((a or 0) + (b or 0)) / 2
        return (a + b) / 2 if a and b else None

    la_virt_annual = virt_ser.get("19", {})
    annual_cells = []
    for y in sorted(lausd1):
        r = lausd1[y]
        scde = _straddle(state_cde, y)
        spub = state1.get(y, {}).get("public")
        ccde = _straddle(county, y)
        cpub = county1.get(y, {}).get("public")
        dcde = _straddle(lausd, y)
        trad = _straddle(by_cls["trad"], y)
        if not all((scde, spub, ccde, cpub, dcde, trad, r.get("public"))):
            continue
        m = (scde - spub) / scde
        trad *= 1 - m
        aff = _straddle(by_cls["aff"], y, zero_missing=True) * (1 - m)
        ind = _straddle(by_cls["ind"], y, zero_missing=True) * (1 - m)
        elsewhere = max(r["public"] - trad - aff - ind, 0.0)
        phys_chr = min(
            _straddle(inside_bm, y, zero_missing=True) * (1 - m), elsewhere
        )
        rv = _straddle(la_virt_annual, y, zero_missing=True) * (1 - m)
        # Rest-of-county net physical absorption: their physical seats minus
        # their own resident public children. Negative once their children
        # outnumber their classroom seats (they too lose children to
        # virtual/out-of-county) — which is why the net alone understates the
        # boundary's permit flow.
        rest_net = (
            (ccde - dcde) * (1 - m) - rv - phys_chr - (cpub - r["public"])
        )
        # County-wide virtual + net counted outside the county, allocated
        # between boundary and rest-of-county children by resident
        # public-school population — the one allocation assumption in the
        # chart. Everything else is arithmetic: the boundary's share is the
        # virtual/remote band; the rest-of-county share frees their seats, so
        # it credits the other-district estimate.
        pool = rv + (cpub - ccde * (1 - m))
        share = r["public"] / cpub
        vr = min(max(share * pool, 0.0), elsewhere - phys_chr)
        phys_oth = elsewhere - phys_chr - vr
        moe_l = r.get("public_moe") or 0.0
        moe_c = county1[y].get("public_moe") or 0.0
        annual_cells.append(
            {
                "y": y,
                "total": round(r["total"]),
                "cells": {
                    "trad": round(trad),
                    "aff": round(aff),
                    "ind": round(ind),
                    "phys_chr": round(phys_chr),
                    "phys_oth": round(phys_oth),
                    "vr": round(vr),
                    "priv": round(r["private"]),
                    "noten": round(r["not_enrolled"]),
                },
                # Estimation detail for the two allocated cells: the
                # rest-of-county net, the rest-of-county share of the
                # virtual/remote pool that credits the other-district cell,
                # and approximate 90% ACS margins (county terms carry the
                # boundary's population share; covariance ignored).
                "est": {
                    "rest_net": round(rest_net),
                    "rest_pool": round((1 - share) * pool),
                    "moe_phys_oth": round(
                        (moe_l**2 + (share * moe_c) ** 2) ** 0.5
                    ),
                    "moe_vr": round(share * moe_c),
                },
            }
        )

    return {
        "annual": annual,
        "annual_cells": annual_cells,
        "la_virtual": la_virtual,
        "peak": {"spring": peak_y, "enr": lausd[peak_y]},
        "county_share_hist": share_hist,
        "district_flows": district_flows,
        "county_flows": {"vintage": latest_v, "rows": county_flows},
        "ledger": ledger,
        "lausd_classes": lausd_classes,
        "resident_517": resident_517,
        "inside_charters": inside,
    }


def _district_perf(con) -> dict[str, dict]:
    """Per-district performance percentiles among CA unified districts.

    raw:   mean scale score (All Students, grades 3-8 & 11, ELA+Math), converted
           to a percentile within each year x grade x test cell over 2016-2019
           (the within-county absorption era), weighted by students with scores.
    adj17/adj25: percentile of the site's demographically-adjusted level
           (level_adj_lcb, the ranking statistic) from the out-of-sample history
           refits, as of the 2017 and 2025 cutoffs.
    """
    views = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    uni = {
        r[0]
        for r in con.execute(
            "SELECT DISTINCT substr(cds, 1, 7) FROM directory_raw WHERE doc = '54'"
        ).fetchall()
    }
    out: dict[str, dict] = {}
    if "caaspp_sb" in views:
        rows = con.execute(
            """
            SELECT test_year, test_id, grade, substr(cds, 1, 7) AS d,
                   mean_scale_score, students_with_scores
            FROM caaspp_sb
            WHERE type_id = 6 AND student_group_id = 1 AND test_id IN (1, 2)
              AND grade BETWEEN 3 AND 11 AND grade <> 9 AND grade <> 10
              AND test_year BETWEEN 2016 AND 2019
              AND mean_scale_score IS NOT NULL AND students_with_scores >= 11
            """
        ).fetchall()
        cells: dict[tuple, list] = {}
        for y, t, g, d, mss, n in rows:
            if d in uni:
                cells.setdefault((y, t, g), []).append((d, float(mss), float(n)))
        acc: dict[str, list[float]] = {}
        for lst in cells.values():
            if len(lst) < 50:
                continue
            lst.sort(key=lambda r: r[1])
            m = len(lst)
            for i, (d, _, n) in enumerate(lst):
                a = acc.setdefault(d, [0.0, 0.0])
                a[0] += (i + 0.5) / m * n
                a[1] += n
        for d, (num, den) in acc.items():
            if den > 0:
                out.setdefault(d, {})["raw"] = _r(num / den)
    if "frpm_raw" in views:
        # FRPM (SED proxy) share, 2018-19 — mid-era demographic context
        for d, el, en in con.execute(
            """
            SELECT substr(cds, 1, 7), sum(TRY_CAST(frpm_count_k_12 AS DOUBLE)),
                   sum(TRY_CAST(enrollment_k_12 AS DOUBLE))
            FROM frpm_raw
            WHERE academic_year = '2018-2019' AND substr(cds, 8, 7) <> '0000000'
            GROUP BY 1
            """
        ).fetchall():
            if en and el is not None:
                out.setdefault(d, {})["sed"] = _r(el / en)
    # Similar Student percentile at district level: where districts serving
    # students like these would be expected to score — the percentile of the
    # demographic prediction (level minus residual) among CA unified districts.
    try:
        deff = pl.read_parquet(PARQUET_DIR / "analysis" / "district_effects.parquet")
        ssl_rows = []
        for r in deff.select(["cds", "level", "level_adj"]).to_dicts():
            d7 = r["cds"][:7]
            if r["level"] is not None and r["level_adj"] is not None and d7 in uni:
                ssl_rows.append((d7, r["level"] - r["level_adj"]))
        ssl_rows.sort(key=lambda t: t[1])
        mtot = len(ssl_rows)
        for i, (d7, _v) in enumerate(ssl_rows):
            out.setdefault(d7, {})["stu"] = _r((i + 0.5) / mtot)
    except Exception as exc:  # noqa: BLE001 - optional metric
        print(f"  similar-student district pct skipped: {exc}")

    # Similar Student percentile CONTEMPORANEOUS to the absorption era:
    # per-cutoff shrunken level (as of 2017, CAASPP 2015-17) minus the
    # era-restricted student-composition effect, ranked among CA unified
    # districts — the Chart 5 axis.
    try:
        from schoolfactors.analysis.similar_student import student_effects

        stud17, _d = student_effects(max_year=2017)
        h17 = pl.read_parquet(
            PARQUET_DIR / "analysis" / "district_effects_history.parquet"
        )
        if "level_eb" in h17.columns:
            h17 = h17.filter(
                (pl.col("as_of_year") == 2017) & pl.col("level_eb").is_not_null()
            )
            rows17 = []
            for r in h17.select(["cds", "level_eb"]).to_dicts():
                d7 = r["cds"][:7]
                if r["cds"] in stud17 and d7 in uni:
                    rows17.append((d7, r["level_eb"] - stud17[r["cds"]]))
            rows17.sort(key=lambda t: t[1])
            m17 = len(rows17)
            for i, (d7, _v) in enumerate(rows17):
                out.setdefault(d7, {})["simstu17"] = _r((i + 0.5) / m17)
    except Exception as exc:  # noqa: BLE001 - optional metric
        print(f"  era similar-student pct skipped: {exc}")

    hist_path = PARQUET_DIR / "analysis" / "district_effects_history.parquet"
    if hist_path.exists():
        hist = pl.read_parquet(hist_path)
        for cut, key in ((2017, "adj17"), (2025, "adj25")):
            sub = (
                hist.filter(pl.col("as_of_year") == cut)
                .with_columns(pl.col("cds").str.slice(0, 7).alias("d"))
                .filter(pl.col("d").is_in(list(uni)))
                .sort("level_adj_lcb")
            )
            m = len(sub)
            for i, d in enumerate(sub["d"].to_list()):
                out.setdefault(d, {})[key] = _r((i + 0.5) / m)
    return out


def _inside_charters(con) -> tuple[list[list[int]] | None, dict[int, int]]:
    """Census-day enrollment at non-LAUSD charters located inside the LAUSD
    boundary (union of MP25 polygons, small buffer for geocoding slop).

    Returns (export series [[year, all-inside enrollment]], brick-and-mortar-only
    series by spring year). The B&M series subtracts campuses the directory flags
    fully/primarily virtual so the annual conclusion cells never count a student
    in both the in-boundary-charter and virtual bands.
    """
    import json as _json

    if not lausd_geo.MP25_GEOJSON.exists():
        return None, {}
    from shapely.geometry import Point, shape
    from shapely.ops import unary_union
    from shapely.prepared import prep

    gj = _json.loads(lausd_geo.MP25_GEOJSON.read_text())
    boundary = prep(
        unary_union([shape(f["geometry"]) for f in gj["features"]]).buffer(0.002)
    )
    rows = con.execute(
        """
        SELECT cds, any_value(TRY_CAST(latitude AS DOUBLE)),
               any_value(TRY_CAST(longitude AS DOUBLE)),
               any_value(trim(virtual)) IN ('F', 'V') AS virt
        FROM directory_raw
        WHERE substr(cds, 1, 2) = '19' AND cds NOT LIKE '1964733%'
          AND trim(charter) = 'Y' AND substr(cds, 8, 7) <> '0000000'
        GROUP BY cds
        """
    ).fetchall()
    inside = [
        (c, virt) for c, lat, lon, virt in rows
        if lat is not None and lon is not None and boundary.contains(Point(lon, lat))
    ]
    if not inside:
        return None, {}
    quoted = ",".join(f"'{c}'" for c, _ in inside)
    series = _cde_census_day(
        con, f"cds IN ({quoted})",
        f"aggregatelevel = 'S' AND cds IN ({quoted})", since_spring=1996,
    )
    bm = dict(series)
    virt_cds = [c for c, virt in inside if virt]
    if virt_cds:
        qv = ",".join(f"'{c}'" for c in virt_cds)
        for y, v in _cde_census_day(
            con, f"cds IN ({qv})",
            f"aggregatelevel = 'S' AND cds IN ({qv})", since_spring=1996,
        ).items():
            bm[y] = max(bm.get(y, 0) - v, 0)
    return [[y, series[y]] for y in sorted(series) if y >= 2010], bm


_B03002_PATHS = {
    "his": ("Hispanic or Latino",),
    "wht": ("Not Hispanic or Latino", "White alone"),
    "blk": ("Not Hispanic or Latino", "Black or African American alone"),
    "asn": ("Not Hispanic or Latino", "Asian alone"),
}


def _resident_race_by_vintage(con) -> dict[str, dict] | None:
    """LAUSD-boundary residents (all ages) by race/ethnicity per ACS vintage."""
    views = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    if "census_acs_raw" not in views:
        return None
    rows = con.execute(
        """
        SELECT vintage, variable, label, sum(TRY_CAST(value AS DOUBLE)) AS v
        FROM census_acs_raw
        WHERE table_id = 'B03002' AND geoid = ? AND geo_type LIKE 'sd_%'
          AND (TRY_CAST(value AS DOUBLE) IS NULL OR TRY_CAST(value AS DOUBLE) >= 0)
        GROUP BY 1, 2, 3
        """,
        [LAUSD_GEOID],
    ).fetchall()
    out: dict[str, dict] = {}
    for vintage, variable, label, v in rows:
        if not variable.endswith("E") or not label or v is None:
            continue
        parts = tuple(p.rstrip(":") for p in label.split("!!"))[2:]
        acc = out.setdefault(vintage, {})
        if parts == ():
            acc["total"] = int(round(v))
        for key, path in _B03002_PATHS.items():
            if parts == path:
                acc[key] = int(round(v))
    for acc in out.values():
        if "total" in acc:
            acc["oth"] = max(
                0, acc["total"] - sum(acc.get(k, 0) for k in _B03002_PATHS)
            )
    return {v: a for v, a in out.items() if "total" in a} or None


# CDE historical enrollment race codes (files through 2022-23).
_HIST_RACE = {
    "5": "his",
    "7": "wht",
    "6": "blk",
    "2": "asn",  # Asian
    "4": "asn",  # Filipino — census counts Filipino under Asian alone
}


def _enrolled_race_hist(con) -> dict[int, dict]:
    """LAUSD-authorized enrollment by race/ethnicity per spring year.

    Historical census files (by race code, through 2022-23) stitched with the
    new-format census files (RE_* reporting categories, 2023-24+); Filipino
    folds into `asn` for census comparability, everything else into `oth`.
    """
    out: dict[int, dict] = {}
    for code, spring, enr in con.execute(
        """
        SELECT race_ethnicity,
               CASE WHEN length(academic_year) = 7
                    THEN TRY_CAST(substr(academic_year, 1, 4) AS INT) + 1
                    ELSE TRY_CAST(substr(academic_year, 3, 2) AS INT)
                      + CASE WHEN TRY_CAST(substr(academic_year, 3, 2) AS INT) > 50
                             THEN 1900 ELSE 2000 END
               END AS spring,
               sum(TRY_CAST(enr_total AS BIGINT))
        FROM enrollment_hist_raw
        WHERE (enr_type = 'C' OR enr_type IS NULL) AND cds LIKE '1964733%'
        GROUP BY 1, 2
        """
    ).fetchall():
        if spring is None or not enr:
            continue
        cat = _HIST_RACE.get((code or "").strip(), "oth")
        acc = out.setdefault(int(spring), {"his": 0, "wht": 0, "blk": 0, "asn": 0, "oth": 0})
        acc[cat] += int(enr)
    new_cat = {"RE_H": "his", "RE_W": "wht", "RE_B": "blk", "RE_A": "asn", "RE_F": "asn"}
    for cat_code, spring, enr in con.execute(
        """
        SELECT reportingcategory,
               TRY_CAST(substr(academicyear, 1, 4) AS INT) + 1 AS spring,
               sum(TRY_CAST(total_enr AS BIGINT))
        FROM enrollment_raw
        WHERE districtcode = '64733' AND aggregatelevel = 'D' AND charter = 'ALL'
          AND reportingcategory LIKE 'RE_%'
        GROUP BY 1, 2
        """
    ).fetchall():
        if spring is None or not enr:
            continue
        acc = out.setdefault(int(spring), {"his": 0, "wht": 0, "blk": 0, "asn": 0, "oth": 0})
        acc[new_cat.get(cat_code, "oth")] += int(enr)
    return out


def _parent_ed(con) -> dict[str, float]:
    """Per-school share of tested students whose parents hold a BA or higher.

    CAASPP parent-education groups (latest year, all-grades rollup, ELA):
    (college graduate + graduate school) / all reported categories, excluding
    "declined to state". Schools with <30 reported are omitted.
    """
    views = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    if "caaspp_sb" not in views:
        return {}
    rows = con.execute(
        """
        SELECT cds,
               sum(CASE WHEN student_group_id IN (93, 94) THEN students_tested END)
                   AS ba,
               sum(CASE WHEN student_group_id IN (90, 91, 92, 93, 94)
                        THEN students_tested END) AS tot
        FROM caaspp_sb
        WHERE test_year = (SELECT max(test_year) FROM caaspp_sb)
          AND cds LIKE '1964733%' AND grade = 13 AND test_id = 1
          AND type_id IN (7, 9, 10)
        GROUP BY 1
        """
    ).fetchall()
    return {
        cds: round(ba / tot, 3)
        for cds, ba, tot in rows
        if tot and tot >= 30 and ba is not None
    }


def _sed_hist(con, district: dict, children: dict) -> dict:
    """Time series for the poverty/SED measures, each with its own definition:
    FRPM (185% FPL, district-reported), CALPADS UPC (FRPM ∪ EL ∪ foster — the
    LCFF funding measure), census P185 (resident children 6-17)."""
    upc = [
        [int(y[:4]) + 1, _r(share)]
        for y, share in con.execute(
            """
            SELECT academic_year,
                   sum(TRY_CAST(calpads_unduplicated_pupil_count_upc AS DOUBLE))
                     / nullif(sum(TRY_CAST(total_enrollment AS DOUBLE)), 0)
            FROM cupc_raw
            WHERE cds LIKE '1964733%' AND school_code <> '0000000'
            GROUP BY 1 ORDER BY 1
            """
        ).fetchall()
        if share is not None
    ]
    frpm = sorted(
        [int(y), v] for y, v in (district.get("frpm_hist") or {}).items()
    )
    p185 = [[int(v), d["p185"]] for v, d in sorted(children.items()) if d.get("p185")]
    return {"frpm": frpm, "upc": upc, "p185": p185}


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
                    "simstu_pct": idx.get("simstu_pct"),
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
                    acc["et"] = acc.get("et", 0) + (d.get("edu_total") or 0)
                    acc["eb"] = acc.get("eb", 0) + (d.get("edu_ba") or 0)
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
                        # adult (25+) educational attainment: bachelor's or higher
                        "ba": _r(acc["eb"] / acc["et"]) if acc.get("et") else None,
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
        district_payload_path = SITE_DATA / "districts" / f"{LAUSD_DCDS}.json"
        district = (
            json.loads(district_payload_path.read_text())
            if district_payload_path.exists()
            else {}
        )
        resident_race_hist = _resident_race_by_vintage(con) or {}
        enrolled_race_hist = _enrolled_race_hist(con)
        _write(
            "demographics.json",
            {
                "census_pending": demo is None,
                "schools": school_demo,
                "district": district_row,
                "resident": resident,
                "enrolled": _enrolled_race(con),
                # Composition over time: resident side per ACS vintage (all ages),
                # enrolled side per spring year (LAUSD-authorized schools).
                "race_hist": {
                    "resident": [
                        [int(v), d] for v, d in sorted(resident_race_hist.items())
                    ],
                    "enrolled": [
                        [y, d] for y, d in sorted(enrolled_race_hist.items()) if y >= 1995
                    ],
                },
                # Three SED/poverty measures, each with its own definition.
                "sed_hist": _sed_hist(con, district, _census_children(con) or {}),
                # Tested students' parent education (BA+ share) per school —
                # compared on-page against each area's resident adult attainment.
                "parent_ed": _parent_ed(con),
            },
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
        # Three-level reconciliation (district / county / state) of resident
        # public-school children vs census-day enrollment — feeds the flow
        # diagrams and the residual-vs-baseline table on the enrollment page.
        flows = _flows(con, residence)
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
                "flows": flows,
                # Walk-back and per-district/importer ledgers for the narrative
                # revision of the page (see analysis/enrollment_page_narrative.md).
                "narrative": _narrative(con, flows),
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
