"""Export prebuilt JSON for the static site.

Site data contract (v1):
    data/index.json                 — statewide search index (schools + districts)
    data/schools/{cds}.json         — per-school page payload
    data/districts/{cds}.json       — per-district page payload
    data/summary.json               — homepage stats
Everything is precomputed — the site has no API.
"""

from __future__ import annotations

import bisect
import json

import duckdb
import polars as pl

from schoolfactors.paths import DUCKDB_PATH, PARQUET_DIR, REPO_ROOT

SITE_DATA = REPO_ROOT / "site" / "static" / "data"

EFFECT_COLS = [
    "total_scores",
    "n_years",
    "last_year",
    "level_eb",
    "level_se",
    "growth_eb",
    "growth_se",
    "trend_eb",
    "trend_se",
    "level_adj_eb",
    "level_adj_lcb",
    "growth_adj_eb",
    "growth_adj_lcb",
    "level_reliability",
    "growth_reliability",
    "share_econ_dis",
    "share_el",
]


def _names() -> pl.DataFrame:
    """Latest known name per entity (falling back through years for closed schools)."""
    con = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    df = con.execute("""
        SELECT cds, school_name, district_name, county_name, type_id
        FROM (
            SELECT cds, school_name, district_name, county_name, type_id,
                   row_number() OVER (PARTITION BY cds ORDER BY test_year DESC) AS rn
            FROM caaspp_entities
        ) WHERE rn = 1
    """).pl()
    con.close()
    return df


def _effect_payload(row: dict) -> dict:
    return {k: row.get(k) for k in EFFECT_COLS if row.get(k) is not None}


def _round_row(d: dict) -> dict:
    return {k: (round(v, 3) if isinstance(v, float) else v) for k, v in d.items()}


def _rows(part: dict, cds: str) -> list[dict]:
    df = part.get((cds,))
    return df.to_dicts() if df is not None else []


SPARK_YEARS = [2015, 2016, 2017, 2018, 2019, 2022, 2023, 2024, 2025]

# Enrollment sparkline axis: unlike test scores, census enrollment exists for
# every year including 2020 and 2021, and extends to the current school year.
ENR_YEARS = list(range(2015, 2027))

# Student groups that get a "Best for" table (data/groups/{id}.json).
BESTFOR_GROUPS = [128, 31, 160, 8, 74, 76, 77, 78, 80, 144, 52, 240, 90]


def _group_stats(rows: list[dict]) -> dict:
    """Latest per-subject pass rates, count-weighted spark, and last data year
    for one student group's grade-13 rows."""
    by_year: dict[int, list] = {}
    latest: dict[str, tuple] = {}
    for r in rows:
        if r["pct_met_and_above"] is None:
            continue
        by_year.setdefault(r["test_year"], []).append((r["pct_met_and_above"], r["n"]))
        subj = "ela" if r["test_id"] == 1 else "math"
        if subj not in latest or r["test_year"] > latest[subj][0]:
            latest[subj] = (r["test_year"], r["pct_met_and_above"], r["n"])
    spark = []
    for y in SPARK_YEARS:
        vals = by_year.get(y)
        if vals:
            den = sum(n for _, n in vals)
            spark.append(round(sum(p * n for p, n in vals) / den) if den else None)
        else:
            spark.append(None)
    last_year = max(by_year) if by_year else None
    combined_latest = None
    n_latest = None
    if last_year is not None:
        vals = by_year[last_year]
        den = sum(n for _, n in vals)
        if den:
            combined_latest = round(sum(p * n for p, n in vals) / den, 1)
            n_latest = den
    return {
        "spark": spark,
        "last_year": last_year,
        "pass_ela": round(latest["ela"][1]) if "ela" in latest else None,
        "pass_math": round(latest["math"][1]) if "math" in latest else None,
        "combined_latest": combined_latest,
        "n_latest": n_latest,
    }


def run_export() -> None:
    from schoolfactors.analysis import cohorts
    from schoolfactors.analysis.panel import (
        COUNTY_TYPES,
        DISTRICT_TYPES,
        SCHOOL_TYPES,
        estimate_sigma,
        school_rows,
        state_means,
    )

    SITE_DATA.mkdir(parents=True, exist_ok=True)
    (SITE_DATA / "schools").mkdir(exist_ok=True)
    (SITE_DATA / "districts").mkdir(exist_ok=True)
    (SITE_DATA / "counties").mkdir(exist_ok=True)

    schools = pl.read_parquet(PARQUET_DIR / "analysis" / "school_effects.parquet")
    districts = pl.read_parquet(PARQUET_DIR / "analysis" / "district_effects.parquet")
    counties = pl.read_parquet(PARQUET_DIR / "analysis" / "county_effects.parquet")
    coefs = pl.read_parquet(PARQUET_DIR / "analysis" / "adjustment_coefficients.parquet")
    gammas = {
        t: g
        for t, g in zip(coefs["term"].to_list(), coefs["gamma_level"].to_list())
        if g is not None
    }
    names = _names()

    sigma = estimate_sigma(school_rows(SCHOOL_TYPES))
    state = state_means()

    from schoolfactors.analysis.neighbors import build_neighbors

    print("  computing nearby/lookalike neighbors …")
    neighbors = build_neighbors(schools)

    # School level (elementary/middle/high) from the directory, for table facets.
    con_dir = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    eil_map = dict(
        con_dir.execute(
            "SELECT cds, any_value(eilcode) FROM directory_raw WHERE eilcode IS NOT NULL GROUP BY cds"
        ).fetchall()
    )

    # Admission/type flags. CDE knows magnet/charter/EdOps; it has NO field for
    # exam-based admission (verified: Whitney (Gretchen) High and Oxford Academy
    # are Magnet=N/EdOps=Traditional), so selective schools come from the
    # community-curated, cited list in curated/selective_admissions.yaml.
    import yaml

    from schoolfactors.paths import REPO_ROOT as _ROOT

    EDOPS_FLAG = {
        "ALTSOC": "alt-choice",
        "CON": "continuation",
        "COMMDAY": "community-day",
        "COMM": "community",
        "JUV": "court",
        "SPEC": "special-ed",
    }
    flags_map: dict[str, list[str]] = {}
    for cds_, magnet, charter, edops in con_dir.execute(
        "SELECT cds, any_value(magnet), any_value(charter), any_value(edopscode) "
        "FROM directory_raw GROUP BY cds"
    ).fetchall():
        fl = []
        if magnet == "Y":
            fl.append("magnet")
        if charter == "Y":
            fl.append("charter")
        if edops in EDOPS_FLAG:
            fl.append(EDOPS_FLAG[edops])
        if fl:
            flags_map[cds_] = fl
    curated_path = _ROOT / "curated" / "selective_admissions.yaml"
    if curated_path.exists():
        for entry in yaml.safe_load(curated_path.read_text()):
            flags_map.setdefault(entry["cds"], [])
            if "selective" not in flags_map[entry["cds"]]:
                flags_map[entry["cds"]].insert(0, "selective")
    # Current census-day enrollment (latest CDE cdenroll year). School rows carry
    # their own charter flag; district/county totals need the ALL rollup.
    # County rows in the new-format census files carry no cds (only countycode);
    # rebuild their 14-char key so county pages get enrollment too.
    census_map = dict(
        con_dir.execute("""
            SELECT COALESCE(cds, countycode || '000000000000'),
                   max(TRY_CAST(total_enr AS INT))
            FROM enrollment_raw
            WHERE reportingcategory = 'TA'
              AND academicyear = (SELECT max(academicyear) FROM enrollment_raw)
              AND (aggregatelevel = 'S' OR charter = 'ALL')
              AND aggregatelevel IN ('S', 'D', 'C')
            GROUP BY 1
        """).fetchall()
    )
    # Full-population FRPM share (all enrolled students, latest FRPM year) — the
    # census view of economic disadvantage, not the tested-population share.
    frpm_school = con_dir.execute("""
        SELECT cds,
               TRY_CAST(frpm_count_k_12 AS DOUBLE) AS c,
               TRY_CAST(enrollment_k_12 AS DOUBLE) AS e
        FROM frpm_raw
        WHERE academic_year = (SELECT max(academic_year) FROM frpm_raw)
          AND school_code IS NOT NULL AND school_code <> '0000000'
          AND TRY_CAST(enrollment_k_12 AS DOUBLE) > 0
    """).fetchall()
    # ESSA per-pupil expenditure, latest file (lexicographic max works for
    # essappeXXYYdata names). Total = school + allocated central, federal +
    # state/local.
    ppe_rows = con_dir.execute("""
        SELECT cds, lea_cds_code,
               COALESCE(TRY_CAST(school_expenditures_federal AS DOUBLE), 0)
             + COALESCE(TRY_CAST(school_expenditures_state_local AS DOUBLE), 0)
             + COALESCE(TRY_CAST(central_expenditures_federal AS DOUBLE), 0)
             + COALESCE(TRY_CAST(central_expenditures_state_local AS DOUBLE), 0) AS pp,
               TRY_CAST(student_membership AS DOUBLE) AS mem
        FROM ppe_raw
        WHERE file = (SELECT max(file) FROM ppe_raw)
          AND TRY_CAST(school_expenditures_state_local AS DOUBLE) IS NOT NULL
          AND length(cds) = 14
    """).fetchall()
    # Coordinates for the map view. CDE directory lat/long, bounded to
    # California so placeholder zeros/typos don't land points in the Gulf of
    # Guinea; entities sharing a cds across files get the average.
    latlon_rows = con_dir.execute("""
        SELECT cds,
               round(avg(TRY_CAST(latitude AS DOUBLE)), 5),
               round(avg(TRY_CAST(longitude AS DOUBLE)), 5)
        FROM directory_raw
        WHERE TRY_CAST(latitude AS DOUBLE) BETWEEN 32.0 AND 42.5
          AND TRY_CAST(longitude AS DOUBLE) BETWEEN -125.0 AND -113.5
          AND cds IS NOT NULL AND length(cds) = 14
        GROUP BY cds
    """).fetchall()
    # Census enrollment history for the table sparkline: CDE's historical
    # enrollment-by-school files through 2022-23 (enr_type 'C', the census-day
    # combined count — statewide total matches CDE's published 5,852,544 for
    # 2022-23) stitched to the new-format census files from 2023-24 on
    # (school-level seam is continuous). Includes 2019-20 through 2021-22:
    # enrollment was collected in the COVID years even though testing wasn't.
    # Years are labeled by spring (2014-15 → 2015) to match test_year.
    # District/county series roll up ALL rows by CDS prefix — including
    # school-code-0000000 district-office programs and charters — matching how
    # every other rollup on the site folds charters into their CDS district.
    enr_hist: dict[str, dict[int, int]] = {}
    for cds_, ay_, n_ in con_dir.execute("""
        SELECT cds, academic_year, sum(TRY_CAST(enr_total AS BIGINT))
        FROM enrollment_hist_raw
        WHERE enr_type = 'C' AND academic_year >= '2014-15'
          AND length(academic_year) = 7 AND length(cds) = 14
        GROUP BY 1, 2
    """).fetchall():
        if not n_:
            continue
        year = int(ay_[:4]) + 1
        # dict.fromkeys dedupes: a district-office row (school code 0000000)
        # IS its own district key and must count once, not twice.
        for key in dict.fromkeys(
            (cds_, cds_[:7] + "0000000", cds_[:2] + "000000000000")
        ):
            d = enr_hist.setdefault(key, {})
            d[year] = d.get(year, 0) + int(n_)
    for cds_, ay_, n_ in con_dir.execute("""
        SELECT COALESCE(cds, countycode || '000000000000'),
               academicyear, max(TRY_CAST(total_enr AS INT))
        FROM enrollment_raw
        WHERE reportingcategory = 'TA' AND (aggregatelevel = 'S' OR charter = 'ALL')
          AND aggregatelevel IN ('S', 'D', 'C')
        GROUP BY 1, 2
    """).fetchall():
        if n_:
            enr_hist.setdefault(cds_, {})[int(ay_[:4]) + 1] = int(n_)
    con_dir.close()
    frpm_pop: dict[str, list] = {}
    for scds, c, e in frpm_school:
        if c is None or e is None:
            continue
        for key in (scds, scds[:7] + "0000000", scds[:2] + "000000000000"):
            agg = frpm_pop.setdefault(key, [0.0, 0.0])
            agg[0] += c
            agg[1] += e
    frpm_pop_share = {
        k: round(c / e, 3) for k, (c, e) in frpm_pop.items() if e > 0
    }
    # District/county rows missing their own directory coordinates fall back
    # to the unweighted centroid of their schools.
    latlon_map = {r[0]: (r[1], r[2]) for r in latlon_rows}
    cent: dict[str, list[float]] = {}
    for scds, (lat, lon) in list(latlon_map.items()):
        if scds.endswith("0000000"):
            continue
        for key in (scds[:7] + "0000000", scds[:2] + "000000000000"):
            agg = cent.setdefault(key, [0.0, 0.0, 0])
            agg[0] += lat
            agg[1] += lon
            agg[2] += 1
    for key, (la, lo, n) in cent.items():
        if key not in latlon_map and n:
            latlon_map[key] = (round(la / n, 5), round(lo / n, 5))

    # Normalize PPE totals-reporters (known issue ppe-totals-reporting): ~5% of
    # LEAs filed total dollars in the per-pupil columns. The convention is
    # consistent within an LEA, so an LEA whose median reported value exceeds
    # $100k/pupil is treated as a totals-reporter and its rows are divided by
    # membership. Symmetrically (known issue ppe-implausibly-low-filings), an
    # LEA whose median is under $5k/pupil — below the LCFF base grant alone —
    # filed broken data (e.g. Mt. Diablo Unified 2024-25 omitted state/local
    # dollars entirely) and every one of its rows is unusable, including any
    # that individually pass the floor. Post-normalization values outside
    # [$5k, $500k] are dropped as unusable: below the LCFF base grant is
    # impossible, but tiny SpEd/court/community-day programs legitimately run
    # $150k-$400k per pupil, so the ceiling only cuts the physically absurd.
    ppe_by_lea: dict[str, list[float]] = {}
    for _, lea, pp, _ in ppe_rows:
        if pp > 0:
            ppe_by_lea.setdefault(lea, []).append(pp)
    ppe_totals_leas = {
        lea for lea, v in ppe_by_lea.items() if sorted(v)[len(v) // 2] > 100_000
    }
    ppe_broken_leas = {
        lea for lea, v in ppe_by_lea.items() if sorted(v)[len(v) // 2] < 5_000
    }
    ppe_map: dict[str, int] = {}
    ppe_pool: dict[str, list] = {}
    for scds, lea, pp, mem in ppe_rows:
        if pp <= 0 or lea in ppe_broken_leas:
            continue
        if lea in ppe_totals_leas:
            if not mem:
                continue
            pp = pp / mem
        if not 5_000 <= pp <= 500_000:
            continue
        ppe_map[scds] = round(pp)
        # District/county figures: reconstruct dollars (pp × membership), sum,
        # re-divide — never average per-pupil ratios. Charter schools fold into
        # their CDS-prefix district, matching the CAASPP Charter='All' rollups.
        if mem:
            for key in (scds[:7] + "0000000", scds[:2] + "000000000000"):
                agg = ppe_pool.setdefault(key, [0.0, 0.0])
                agg[0] += pp * mem
                agg[1] += mem
    # Coverage gate: after dropping unusable rows, a district/county aggregate
    # may describe only a sliver of the entity (Mt. Diablo Unified's own
    # schools are all dropped, leaving just co-located charters). Publish the
    # rollup only when usable reports cover >= 70% of census enrollment.
    for key, (dollars, students) in ppe_pool.items():
        census = census_map.get(key)
        if students > 0 and (census is None or students >= 0.7 * census):
            ppe_map[key] = round(dollars / students)
    school_name_lookup = {
        r["cds"]: (r["school_name"], r["district_name"])
        for r in names.filter(pl.col("type_id").is_in([7, 9, 10])).to_dicts()
    }

    def enrich_neighbor(e: dict) -> dict | None:
        nm = school_name_lookup.get(e["cds"])
        if nm is None or nm[0] is None:
            return None
        return {**e, "name": nm[0], "district": nm[1]}

    written = {"counties": 0, "schools": 0, "districts": 0}
    index: list[dict] = []
    district_pages: set[str] = set()
    county_pages: set[str] = set()
    group_tables: dict[int, list[dict]] = {}

    # Counties, then districts, then schools, so child pages know which parent
    # links resolve.
    for kind, types, effects in (
        ("counties", COUNTY_TYPES, counties),
        ("districts", DISTRICT_TYPES, districts),
        ("schools", SCHOOL_TYPES, schools),
    ):
        types_sql = str(types) if len(types) > 1 else f"({types[0]})"
        scores = cohorts.cohort_scores(types_sql, sigma, state)
        blend = cohorts.cohort_blend(types_sql)
        steps = cohorts.cohort_steps(blend, gammas)
        slopes = cohorts.cohort_slopes(scores)
        subgroups = cohorts.subgroup_results(types_sql)

        eff_by_cds = {r["cds"]: r for r in effects.to_dicts()}
        scores_by = scores.partition_by("cds", as_dict=True)
        blend_by = blend.partition_by("cds", as_dict=True)
        steps_by = steps.partition_by("cds", as_dict=True)
        slopes_by = slopes.partition_by("cds", as_dict=True) if len(slopes) else {}
        subgroups_by = subgroups.partition_by("cds", as_dict=True)

        if kind == "schools":
            name_filter = pl.col("type_id").is_in(list(types))
        elif kind == "districts":
            name_filter = pl.col("cds").str.slice(7, 7).eq("0000000") & pl.col("type_id").eq(6)
        else:
            name_filter = pl.col("cds").str.slice(2, 12).eq("000000000000") & pl.col(
                "type_id"
            ).eq(5)
        name_rows = names.filter(name_filter)

        for nrow in name_rows.to_dicts():
            cds = nrow["cds"]
            sc = scores_by.get((cds,))
            if sc is None or len(sc) == 0:
                continue  # entity never has usable score rows
            if kind == "counties":
                display_name = f"{nrow['county_name']} County"
            elif kind == "districts":
                display_name = nrow["district_name"]
            else:
                display_name = nrow["school_name"]
            payload = {
                "cds": cds,
                "kind": kind[:-1] if kind != "counties" else "county",
                "name": display_name,
                "district": nrow["district_name"],
                "district_cds": cds[:7] + "0000000",
                "county": nrow["county_name"],
                "county_cds": cds[:2] + "000000000000",
                "effects": _effect_payload(_round_row(eff_by_cds.get(cds, {}))),
                "cohort_scores": [
                    {
                        "grad_year": r["grad_year"],
                        "grade": r["grade"],
                        "year": r["test_year"],
                        "subject": "ela" if r["test_id"] == 1 else "math",
                        "z": r["z"],
                        "n": r["n"],
                        "mean": r["mean_scale_score"],
                        "state_mean": r["state_mean"],
                        "pct_met": r["pct_met_and_above"],
                        "pct_exc": r["pct_exceeded"],
                    }
                    for r in sc.sort(["grad_year", "grade", "test_id"]).to_dicts()
                ],
                "subgroup_results": [
                    {
                        "year": r["test_year"],
                        "subject": "ela" if r["test_id"] == 1 else "math",
                        "group": r["student_group_id"],
                        "pct_met": r["pct_met_and_above"],
                        "pct_exc": r["pct_exceeded"],
                        "n": r["n"],
                    }
                    for r in _rows(subgroups_by, cds)
                ],
                "cohort_slopes": [
                    {k: r[k] for k in ("grad_year", "slope", "slope_se", "n_points")}
                    for r in _rows(slopes_by, cds)
                ],
                "blend": [
                    {
                        "year": r["test_year"],
                        "grade": r["grade"],
                        "n": r["n_all"],
                        **{
                            f"share_{nm}": r.get(f"share_{nm}")
                            for _, (nm, _) in cohorts.BLEND_GROUPS.items()
                        },
                    }
                    for r in sorted(
                        _rows(blend_by, cds), key=lambda r: (r["test_year"], r["grade"])
                    )
                ],
                "blend_steps": [
                    {
                        "grad_year": r["grad_year"],
                        "from_grade": r["grade"],
                        "year": r["test_year"],
                        "n_change_frac": r["n_change_frac"],
                        "expected_dz_from_blend": r["expected_dz_from_blend"],
                        "flag": r["blend_shift_flag"],
                        "shifts": {
                            nm: r.get(f"d_{nm}")
                            for _, (nm, _) in cohorts.BLEND_GROUPS.items()
                            if r.get(f"flag_{nm}")
                        },
                    }
                    for r in _rows(steps_by, cds)
                ],
            }
            if kind == "schools":
                nb = neighbors.get(cds, {})
                payload["neighbors"] = {
                    "nearby": [
                        x for x in (enrich_neighbor(e) for e in nb.get("nearby", [])) if x
                    ],
                    "lookalike": [
                        x for x in (enrich_neighbor(e) for e in nb.get("lookalike", [])) if x
                    ],
                }
            if kind == "counties":
                county_pages.add(cds)
            elif kind == "districts":
                district_pages.add(cds)
                payload["county_has_page"] = payload["county_cds"] in county_pages
            else:
                payload["district_has_page"] = payload["district_cds"] in district_pages
                payload["county_has_page"] = payload["county_cds"] in county_pages
            (SITE_DATA / kind / f"{cds}.json").write_text(json.dumps(payload))
            written[kind] += 1
            eff = payload["effects"]
            full_eff = eff_by_cds.get(cds, {})

            # Per-subject levels via the fitted subject gap (math - ela):
            # ela = level - gap/2, math = level + gap/2, for raw and adjusted alike.
            def _split(level, full_eff=full_eff):
                gap = full_eff.get("subj_gap")
                if level is None:
                    return None, None
                if gap is None:
                    return round(level, 2), round(level, 2)
                return round(level - gap / 2, 2), round(level + gap / 2, 2)

            raw_ela, raw_math = _split(eff.get("level_eb"))
            adj_ela, adj_math = _split(eff.get("level_adj_eb"))

            # Group stats: All Students drives the index row; curated groups feed
            # the Best-for tables.
            sub_rows = _rows(subgroups_by, cds)
            g1 = _group_stats([r for r in sub_rows if r["student_group_id"] == 1])
            spark = g1["spark"]
            last_year = g1["last_year"]

            for gid in BESTFOR_GROUPS:
                gs = _group_stats(
                    [r for r in sub_rows if r["student_group_id"] == gid]
                )
                if gs["last_year"] is None:
                    continue
                gap = (
                    round(gs["combined_latest"] - g1["combined_latest"], 1)
                    if gs["combined_latest"] is not None
                    and g1["combined_latest"] is not None
                    and gs["last_year"] == g1["last_year"]
                    else None
                )
                group_tables.setdefault(gid, []).append(
                    {
                        "cds": cds,
                        "kind": payload["kind"],
                        "name": payload["name"],
                        "district": nrow["district_name"],
                        "county": nrow["county_name"],
                        "eil": eil_map.get(cds) if kind == "schools" else None,
                        "flags": flags_map.get(cds) if kind == "schools" else None,
                        "pass_ela": gs["pass_ela"],
                        "pass_math": gs["pass_math"],
                        "n": gs["n_latest"],
                        "gap": gap,
                        "spark": gs["spark"],
                        "last_year": gs["last_year"],
                        "enrollment": census_map.get(cds),
                        "econ": frpm_pop_share.get(cds),
                    }
                )

            index.append(
                {
                    "cds": cds,
                    "kind": payload["kind"],
                    "name": payload["name"],
                    "district": nrow["district_name"],
                    "district_cds": payload["district_cds"],
                    "county": nrow["county_name"],
                    "county_cds": payload["county_cds"],
                    "eil": eil_map.get(cds) if kind == "schools" else None,
                    "flags": flags_map.get(cds) if kind == "schools" else None,
                    "level_eb": eff.get("level_eb"),
                    "level_adj_eb": eff.get("level_adj_eb"),
                    "adj_lcb": eff.get("level_adj_lcb"),
                    "raw_ela": raw_ela,
                    "raw_math": raw_math,
                    "adj_ela": adj_ela,
                    "adj_math": adj_math,
                    "pass_ela": g1["pass_ela"],
                    "pass_math": g1["pass_math"],
                    "last_year": last_year,
                    "growth_adj_eb": eff.get("growth_adj_eb"),
                    "growth_lcb": eff.get("growth_adj_lcb"),
                    # Stripped before writing — used only for percentile gating.
                    "_lrel": eff.get("level_reliability"),
                    "_grel": eff.get("growth_reliability"),
                    "_ly": eff.get("last_year"),
                    # Full-population FRPM share (all enrolled students), falling
                    # back to the tested-population share where FRPM is missing.
                    "econ": frpm_pop_share.get(cds, eff.get("share_econ_dis")),
                    "ppe": ppe_map.get(cds),
                    "enrollment": census_map.get(cds),
                    "total_scores": eff.get("total_scores"),
                    "ll": latlon_map.get(cds),
                    "spark": spark,
                    "enr": (
                        [enr_hist[cds].get(y) for y in ENR_YEARS]
                        if cds in enr_hist
                        else None
                    ),
                }
            )

    # Bake child lists into parent payloads (pages must not fetch the whole index —
    # prerendering inlines fetched responses into the HTML).
    def child_entry(e: dict) -> dict:
        return {
            "cds": e["cds"],
            "name": e["name"],
            "level_eb": e["level_eb"],
            "level_adj_eb": e["level_adj_eb"],
            "adj_lcb": e["adj_lcb"],
            "growth_adj_eb": e["growth_adj_eb"],
            "total_scores": e["total_scores"],
        }

    by_district: dict[str, list[dict]] = {}
    by_county: dict[str, list[dict]] = {}
    for e in index:
        if e["kind"] == "school":
            by_district.setdefault(e["district_cds"], []).append(child_entry(e))
        elif e["kind"] == "district":
            by_county.setdefault(e["county_cds"], []).append(child_entry(e))
    for dcds in district_pages:
        path = SITE_DATA / "districts" / f"{dcds}.json"
        d = json.loads(path.read_text())
        d["schools"] = sorted(by_district.get(dcds, []), key=lambda s: s["name"] or "")
        path.write_text(json.dumps(d))
    for ccds in county_pages:
        path = SITE_DATA / "counties" / f"{ccds}.json"
        d = json.loads(path.read_text())
        d["districts"] = sorted(by_county.get(ccds, []), key=lambda s: s["name"] or "")
        path.write_text(json.dumps(d))

    # Small counties listing for the home page drill-down.
    county_list = sorted(
        (
            {**child_entry(e), "county": e["county"]}
            for e in index
            if e["kind"] == "county"
        ),
        key=lambda c: c["county"] or "",
    )
    (SITE_DATA / "counties.json").write_text(json.dumps(county_list))

    (SITE_DATA / "groups").mkdir(exist_ok=True)
    for gid, rows in group_tables.items():
        (SITE_DATA / "groups" / f"{gid}.json").write_text(json.dumps(rows))
    print(f"  best-for tables: {len(group_tables)} groups "
          f"({sum(len(v) for v in group_tables.values()):,} rows)")

    # Percentile presentation of the adjusted estimates (in the spirit of the
    # Urban Institute's demographically adjusted rankings): midrank percentile
    # among entities of the same kind, computed on the LOWER bound of the 95%
    # band around the shrunken residual — an unconfident high estimate ranks
    # below a confident slightly-lower one. Gated on reliability >= 0.70
    # (SEDA's rule — an estimate that is mostly noise gets no percentile) and
    # on having modeled data in the statewide latest year: the level is
    # recency-weighted, so for a school whose data stopped years ago it
    # describes a school that may no longer exist in that form. The underlying
    # student-SD values stay in the payloads; this is display only.
    for kind_ in ("school", "district", "county"):
        latest = max(
            (e["_ly"] for e in index if e["kind"] == kind_ and e.get("_ly")),
            default=None,
        )
        for src, rel_key, out in (
            ("adj_lcb", "_lrel", "adj_pct"),
            ("growth_lcb", "_grel", "growth_pct"),
        ):
            def eligible(e, kind_=kind_, src=src, rel_key=rel_key, latest=latest):
                return (
                    e["kind"] == kind_
                    and e.get(src) is not None
                    and (e.get(rel_key) or 0) >= 0.7
                    and e.get("_ly") == latest
                )

            pool = sorted(e[src] for e in index if eligible(e))
            if len(pool) < 20:
                continue
            for e in index:
                if eligible(e):
                    lo = bisect.bisect_left(pool, e[src])
                    hi = bisect.bisect_right(pool, e[src])
                    e[out] = min(99, max(1, round(100 * (lo + hi) / 2 / len(pool))))
    for e in index:
        e.pop("_lrel", None)
        e.pop("_grel", None)
        e.pop("_ly", None)

    (SITE_DATA / "index.json").write_text(json.dumps(index))
    print(f"  wrote {written['schools']:,} school pages, {written['districts']:,} district pages")
    print(f"  index.json: {len(index):,} entries")

    summary = {
        "n_schools_modeled": len(schools),
        "n_districts_modeled": len(districts),
        "n_counties_modeled": len(counties),
        "years": [2015, 2016, 2017, 2018, 2019, 2022, 2023, 2024, 2025],
        "corr_raw_level_econ": -0.74,
        "corr_adjusted_level_econ": -0.003,
        "falsification_growth_vs_level": -0.012,
    }
    (SITE_DATA / "summary.json").write_text(json.dumps(summary, indent=1))
    print("  summary.json written")
