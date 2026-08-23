"""Data-quality checks over the ingested store.

Each check returns a list of Finding rows. Findings are published in DATA_QUALITY.md —
never silently patched. The subgroup-sum check is the framework's acceptance test: it
must independently rediscover the known 2015 English-fluency anomaly (subgroup 6 ≠ 7+8)
that CDE acknowledged but never fixed.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import duckdb

from schoolfactors.paths import DUCKDB_PATH


@dataclass
class Finding:
    check: str
    severity: str  # info | warning | anomaly
    year: int | None
    entity: str | None
    message: str
    details: dict = field(default_factory=dict)


def _con() -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(DUCKDB_PATH), read_only=True)


def check_row_counts() -> list[Finding]:
    """Report per-year fact rows and flag year-over-year swings beyond format changes."""
    con = _con()
    rows = con.execute(
        "SELECT test_year, count(*) AS n, any_value(era) AS era "
        "FROM caaspp_sb_raw GROUP BY 1 ORDER BY 1"
    ).fetchall()
    con.close()
    findings = [
        Finding("row_counts", "info", y, None, f"{n:,} rows (era {era})") for y, n, era in rows
    ]
    years = [y for y, _, _ in rows]
    for missing in (2020,):
        if missing not in years:
            findings.append(
                Finding(
                    "row_counts",
                    "info",
                    missing,
                    None,
                    "no file exists (COVID-19 testing cancellation) — trends must bridge "
                    "this gap explicitly",
                )
            )
    return findings


# Parent subgroup -> child subgroups whose enrollments should sum to the parent.
# Only relationships that are true partitions in the CAASPP group taxonomy are used.
# Note: group 6 is "fluent English proficient AND English only" — verified empirically
# that 6 = 7 (IFEP) + 8 (RFEP) + 180 (EO) holds exactly for 2016+ enrollment and for
# tested counts in all years.
SUBGROUP_SUMS = {
    "fluency 6 = 7 + 8 + 180 (IFEP + RFEP + English-only)": (6, (7, 8, 180)),
}
# Whole-population partitions: children should sum to All Students (group 1).
POPULATION_PARTITIONS = {
    "economic status (31 + 111 = all students)": (1, (31, 111)),
    "gender (male 3 + female 4 = all students)": (1, (3, 4)),
    "disability (128 + 99 = all students)": (1, (128, 99)),
}


def check_subgroup_sums(tolerance: float = 0.02, min_n: int = 30) -> list[Finding]:
    """District-level: parent-group enrollment should equal the sum of its children.

    Suppression (n<11) removes small child groups, so we only test rows where all
    parts are present, and allow `tolerance` relative slack before flagging.
    Aggregated to one finding per (year, relationship) with example districts.
    """
    con = _con()
    findings: list[Finding] = []

    def run(label: str, parent_id: int, kids: tuple[int, ...]) -> None:
        ids = ", ".join(str(k) for k in (parent_id, *kids))
        kid_cols = ",\n".join(
            f"max(CASE WHEN student_group_id = {k} THEN enrolled END) AS k{i}"
            for i, k in enumerate(kids)
        )
        kid_sum = " + ".join(f"k{i}" for i in range(len(kids)))
        kid_not_null = " AND ".join(f"k{i} IS NOT NULL" for i in range(len(kids)))
        q = f"""
        WITH base AS (
            SELECT r.test_year, r.cds, any_value(e.district_name) AS district_name,
                   r.student_group_id, any_value(r.students_enrolled) AS enrolled
            FROM caaspp_sb_raw r
            JOIN caaspp_entities e ON r.cds = e.cds AND r.test_year = e.test_year
            WHERE r.school_code = '0000000' AND r.district_code <> '00000'
              AND r.grade = 13 AND r.test_id = 1
              AND r.student_group_id IN ({ids})
              AND r.students_enrolled IS NOT NULL
            GROUP BY r.test_year, r.cds, r.student_group_id
        ),
        wide AS (
            SELECT test_year, cds, any_value(district_name) AS district_name,
                   max(CASE WHEN student_group_id = {parent_id} THEN enrolled END) AS parent,
                   {kid_cols}
            FROM base GROUP BY 1, 2
        )
        SELECT test_year, cds, district_name, parent, {kid_sum} AS kid_sum
        FROM wide
        WHERE parent IS NOT NULL AND {kid_not_null}
          AND parent >= {min_n}
          AND abs(parent - ({kid_sum})) > {tolerance} * parent
        ORDER BY test_year, abs(parent - ({kid_sum})) DESC
        """
        rows = con.execute(q).fetchall()
        by_year: dict[int, list] = {}
        for year, cds, dname, parent, ksum in rows:
            by_year.setdefault(year, []).append((cds, dname, parent, ksum))
        for year, items in by_year.items():
            examples = [
                f"{dname or cds[2:7]} (cds {cds[:7]}…): parent={p:,} vs children {ks:,}"
                for cds, dname, p, ks in items[:5]
            ]
            findings.append(
                Finding(
                    "subgroup_sums",
                    "anomaly",
                    year,
                    None,
                    f"{label}: {len(items)} district(s) violate the identity by more than "
                    f"{tolerance:.0%}",
                    details={"examples": examples, "violations": len(items)},
                )
            )

    for label, (parent_id, kids) in (SUBGROUP_SUMS | POPULATION_PARTITIONS).items():
        run(label, parent_id, kids)

    con.close()
    return findings


def check_subgroup_enrollment_variation() -> list[Finding]:
    """Detect years where subgroup enrollment is constant across groups (2015 problem).

    In 2015 the enrollment field held the entity-level all-subject eligible count for
    every subgroup row, so enrolled(subgroup) == enrolled(All Students) everywhere.
    This check measures, per year, the share of districts where enrollment is identical
    across a set of groups that must differ in any real population.
    """
    con = _con()
    rows = con.execute("""
        WITH wide AS (
            SELECT test_year, cds,
                   max(CASE WHEN student_group_id = 1 THEN students_enrolled END) AS all_students,
                   max(CASE WHEN student_group_id = 3 THEN students_enrolled END) AS male,
                   max(CASE WHEN student_group_id = 31 THEN students_enrolled END) AS econ_dis
            FROM caaspp_sb_raw
            WHERE school_code = '0000000' AND district_code <> '00000'
              AND grade = 13 AND test_id = 1 AND students_enrolled >= 30
            GROUP BY 1, 2
        )
        SELECT test_year,
               count(*) AS n,
               round(100.0 * sum(CASE WHEN all_students = male AND all_students = econ_dis
                                      THEN 1 ELSE 0 END) / count(*), 1) AS pct_constant
        FROM wide
        WHERE all_students IS NOT NULL AND male IS NOT NULL AND econ_dis IS NOT NULL
        GROUP BY 1 ORDER BY 1
    """).fetchall()
    con.close()
    out = []
    for year, n, pct in rows:
        if pct > 50:
            out.append(
                Finding(
                    "enrollment_definition",
                    "anomaly",
                    year,
                    None,
                    f"{pct}% of {n:,} districts report IDENTICAL enrollment for All Students, "
                    "Male, and Socioeconomically-Disadvantaged rows — the enrollment field "
                    "carries entity-level counts, not subgroup counts (known 2015 definition "
                    "issue, id caaspp-2015-enrollment-definition)",
                )
            )
        else:
            out.append(
                Finding(
                    "enrollment_definition",
                    "info",
                    year,
                    None,
                    f"subgroup enrollment varies normally ({pct}% of {n:,} districts constant)",
                )
            )
    return out


def check_entity_continuity() -> list[Finding]:
    """Schools reporting in year Y and Y+2 but absent in Y+1 (excluding the 2020 gap)."""
    con = _con()
    rows = con.execute("""
        WITH school_years AS (
            SELECT DISTINCT cds, test_year
            FROM caaspp_sb_raw
            WHERE school_code <> '0000000' AND student_group_id = 1
        ),
        pairs AS (
            SELECT a.cds, a.test_year AS y0, a.test_year + 2 AS y2
            FROM school_years a
            JOIN school_years b ON a.cds = b.cds AND b.test_year = a.test_year + 2
            LEFT JOIN school_years m ON a.cds = m.cds AND m.test_year = a.test_year + 1
            WHERE m.cds IS NULL AND a.test_year + 1 NOT IN (2020, 2021)
        )
        SELECT y0 + 1 AS missing_year, count(*) FROM pairs GROUP BY 1 ORDER BY 1
    """).fetchall()
    con.close()
    return [
        Finding(
            "entity_continuity",
            "warning",
            year,
            None,
            f"{n} schools report in {year - 1} and {year + 1} but not {year} "
            "(closures/reopenings, code changes, or reporting gaps)",
        )
        for year, n in rows
    ]


def check_suppression_rates() -> list[Finding]:
    """Fraction of school-level All-Students rows with suppressed scores, per year."""
    con = _con()
    rows = con.execute("""
        SELECT test_year,
               count(*) AS n,
               round(100.0 * sum(CASE WHEN mean_scale_score IS NULL THEN 1 ELSE 0 END)
                     / count(*), 1) AS pct_suppressed
        FROM caaspp_sb_raw
        WHERE school_code <> '0000000' AND student_group_id = 1 AND grade = 13 AND test_id = 1
        GROUP BY 1 ORDER BY 1
    """).fetchall()
    con.close()
    out = []
    for year, n, pct in rows:
        sev = "warning" if pct > 20 else "info"
        out.append(
            Finding(
                "suppression",
                sev,
                year,
                None,
                f"{pct}% of {n:,} school-level All-Students ELA rows have suppressed scores",
            )
        )
    return out


def check_participation() -> list[Finding]:
    """Statewide tested/enrolled ratio — flags 2021's participation collapse."""
    con = _con()
    rows = con.execute("""
        SELECT test_year,
               round(100.0 * sum(students_tested) / nullif(sum(students_enrolled), 0), 1)
        FROM caaspp_sb_raw
        WHERE cds = '00000000000000' AND student_group_id = 1 AND grade <> 13 AND test_id = 1
        GROUP BY 1 ORDER BY 1
    """).fetchall()
    con.close()
    out = []
    for year, pct in rows:
        if pct is None:
            continue
        sev = "anomaly" if pct < 90 else "info"
        note = " — participation collapse; do not use for trends" if pct < 90 else ""
        out.append(
            Finding("participation", sev, year, None, f"statewide ELA participation {pct}%{note}")
        )
    return out


def check_census_frpm_alignment() -> list[Finding]:
    """District FRPM rate vs census P185 rate (B17024) — the PPIC benchmark.

    PPIC found the median CA district's FRPM rate is ~1.8x the census rate of
    school-age residents under 185% of poverty (direct certification, categorical
    eligibility, and who actually enrolls all push FRPM above the census measure).
    `ratio` is the RATE ratio — FRPM share of enrolled over P185 share of residents —
    not a count ratio (enrolled students are fewer than resident children, so count
    ratios run mechanically lower; observed ~1.4 median vs ~1.87 for rates on ACS
    2023 x FRPM 2025-26). A median far from 1.8x, or poor NCES-join coverage, means
    the census pipeline (bin selection, crosswalk, or rollup) is broken. Bands are
    loose on purpose: our ACS vintage and FRPM year differ from PPIC's study.
    """
    from schoolfactors.analysis.census_poverty import OUT_PARQUET

    if not OUT_PARQUET.exists():
        return [
            Finding(
                "census_frpm",
                "info",
                None,
                None,
                "census-vs-FRPM table not built yet — run `sf acquire --dataset census`, "
                "`sf ingest --dataset census`, then `sf analyze`",
            )
        ]
    import polars as pl

    df = pl.read_parquet(OUT_PARQUET)
    n = len(df)
    matched = df.filter(df["p185_count"].is_not_null() & (df["p185_count"] > 0))
    coverage = len(matched) / n if n else 0.0
    ratios = matched.filter(pl.col("ratio").is_not_null() & pl.col("ratio").is_finite())
    med = float(ratios["ratio"].median()) if len(ratios) else float("nan")
    vintage = df["acs_vintage"][0] if n else "?"
    year = df["frpm_year"].drop_nulls()[0] if n else "?"

    findings = [
        Finding(
            "census_frpm",
            "info",
            None,
            None,
            f"ACS {vintage} B17024 vs FRPM {year}: {len(matched):,}/{n:,} districts "
            f"matched ({coverage:.0%}), median FRPM/P185 rate ratio {med:.2f}x "
            "(PPIC benchmark ~1.8x)",
            details={"median_ratio": round(med, 3), "coverage": round(coverage, 3)},
        )
    ]
    if coverage < 0.90:
        findings.append(
            Finding(
                "census_frpm",
                "anomaly",
                None,
                None,
                f"only {coverage:.0%} of districts matched to an ACS school-district row "
                "via ncesdist — crosswalk regression",
            )
        )
    if not (1.0 <= med <= 3.0):
        findings.append(
            Finding(
                "census_frpm",
                "anomaly",
                None,
                None,
                f"median FRPM/P185 ratio {med:.2f}x is outside [1.0, 3.0] — bin selection "
                "or rollup is likely wrong (PPIC benchmark ~1.8x)",
            )
        )
    elif not (1.4 <= med <= 2.3):
        findings.append(
            Finding(
                "census_frpm",
                "warning",
                None,
                None,
                f"median FRPM/P185 ratio {med:.2f}x drifted outside [1.4, 2.3] "
                "(PPIC benchmark ~1.8x) — check vintage/year pairing",
            )
        )
    return findings


def check_lausd_resolution() -> list[Finding]:
    """MP25 attendance-area keys must resolve to real LAUSD schools.

    Validates: every polygon's P_KEY equals its E/M/H key segments; every distinct key
    resolves through the Codes tables or the Attendance Boundary Info fallback (known
    exception: E 11017, see known_issues/lausd_key_resolution.yaml); every resolved CDS
    exists in the CDE directory under district 1964733.
    """
    con = _con()
    views = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    if not {"lausd_mp25_raw", "lausd_codes_raw", "lausd_abinfo_raw"} <= views:
        con.close()
        return [
            Finding(
                "lausd_resolution",
                "info",
                None,
                None,
                "LAUSD GIS store not ingested yet — run `sf acquire --dataset lausd_gis` "
                "then `sf ingest --dataset lausd_gis`",
            )
        ]
    import polars as pl

    from schoolfactors.analysis.lausd import resolve_keys

    findings: list[Finding] = []
    n_poly, n_mismatch = con.execute(
        """
        SELECT count(*),
               count(*) FILTER (p_e <> lpad(e_key, 5, '0') OR p_m <> lpad(m_key, 5, '0')
                                OR p_h <> lpad(h_key, 5, '0'))
        FROM lausd_mp25_raw
        """
    ).fetchone()
    findings.append(
        Finding(
            "lausd_resolution",
            "anomaly" if n_mismatch else "info",
            None,
            "LAUSD",
            f"{n_poly:,} MP25 polygons; {n_mismatch} P_KEY/segment mismatches",
        )
    )

    resolved = resolve_keys(con)
    keys = resolved.select("level", "key5").unique()
    unresolved = resolved.filter(pl.col("cds").is_null()).select("level", "key5")
    sev = "info" if len(unresolved) <= 1 else "anomaly"
    findings.append(
        Finding(
            "lausd_resolution",
            sev,
            None,
            "LAUSD",
            f"{len(keys) - len(unresolved)}/{len(keys)} distinct E/M/H keys resolved to "
            f"schools; unresolved: {unresolved.to_dicts() or 'none'}",
        )
    )

    dir_cds = {
        r[0]
        for r in con.execute(
            "SELECT DISTINCT cds FROM directory_raw WHERE cds LIKE '1964733%'"
        ).fetchall()
    }
    resolved_cds = set(resolved.filter(pl.col("cds").is_not_null())["cds"].to_list())
    bad = sorted(resolved_cds - dir_cds)
    not_lausd = sorted(c for c in resolved_cds if not c.startswith("1964733"))
    if bad or not_lausd:
        findings.append(
            Finding(
                "lausd_resolution",
                "anomaly",
                None,
                "LAUSD",
                f"resolved CDS not in CDE directory: {bad[:10]}; "
                f"outside district 1964733: {not_lausd[:10]}",
            )
        )
    else:
        findings.append(
            Finding(
                "lausd_resolution",
                "info",
                None,
                "LAUSD",
                f"all {len(resolved_cds)} resolved CDS codes exist in the CDE directory "
                "under district 1964733",
            )
        )
    con.close()
    return findings


def check_enrollment_closure() -> list[Finding]:
    """Statewide enrollment-flow accounting closes. Two invariants: (1) physical
    seats and physical resident-students net out PER COUNTY — every county's
    district nets sum to ~zero, exactly by construction of the county pool
    allocation, so a violation means a bookkeeping bug; (2) the statewide sum is
    likewise ~zero. Coverage is reported per vintage (reorganized districts have
    no current polygon in early windows)."""
    from schoolfactors.paths import PARQUET_DIR

    calib_path = PARQUET_DIR / "analysis" / "enrollment_calibration.parquet"
    flows_path = PARQUET_DIR / "analysis" / "enrollment_district_flows.parquet"
    if not calib_path.exists() or not flows_path.exists():
        return [Finding("enrollment_closure", "info", None, None,
                        "enrollment flows not built yet — run `sf analyze`")]
    import polars as pl

    calib = pl.read_parquet(calib_path).sort("vintage")
    flows = pl.read_parquet(flows_path)
    findings = []

    # Invariant 1: per-county netting of the district-level physical accounting.
    county_sums = (
        flows.filter((pl.col("level") != "c") & pl.col("net").is_not_null())
        .group_by("vintage", "county")
        .agg(pl.col("net").sum().alias("net_sum"), pl.col("res_pub").sum().alias("res"))
    )
    worst = county_sums.with_columns(
        (pl.col("net_sum").abs() / pl.col("res").clip(lower_bound=1)).alias("share")
    ).sort("share", descending=True)
    bad = worst.filter(pl.col("net_sum").abs() > 1.0)
    if len(bad):
        for r in bad.head(5).to_dicts():
            findings.append(
                Finding("enrollment_closure", "anomaly", int(r["vintage"]),
                        r["county"],
                        f"county {r['county']}: district nets sum to "
                        f"{r['net_sum']:+,.0f} (must be ~0 by construction)")
            )
    else:
        findings.append(
            Finding("enrollment_closure", "info", None, None,
                    "per-county netting exact: every county's district nets sum to "
                    f"<1 student across all {calib.height} vintages")
        )

    # Invariant 1b: the COUNTY rows' nets sum to ~zero statewide — the state is
    # a closed system, so measured cross-county flows must cancel. This is the
    # invariant the unsited-pool double-count violated (county nets summed to
    # +pool_unsited*(1-m) before the fix), so it gets its own check.
    c_sums = (
        flows.filter((pl.col("level") == "c") & pl.col("net").is_not_null())
        .group_by("vintage")
        .agg(pl.col("net").sum().alias("net_sum"))
        .sort("vintage")
    )
    bad_c = c_sums.filter(pl.col("net_sum").abs() > 1.0)
    if len(bad_c):
        for r in bad_c.to_dicts():
            findings.append(
                Finding("enrollment_closure", "anomaly", int(r["vintage"]), None,
                        f"county nets sum to {r['net_sum']:+,.0f} statewide "
                        "(must be ~0: cross-county flows cancel in a closed state)")
            )
    else:
        findings.append(
            Finding("enrollment_closure", "info", None, None,
                    "county-level netting exact: county nets sum to <1 student "
                    f"statewide across all {c_sums.height} vintages")
        )

    # Invariant 2: statewide closure + coverage.
    for r in calib.to_dicts():
        v = int(r["vintage"])
        tol = 0.005
        share = r["closure_share"]
        cov = r["nodes_covered"] / r["nodes_total"]
        sev = "anomaly" if abs(share) > tol else "info"
        findings.append(
            Finding(
                "enrollment_closure", sev, v, None,
                f"closure {share:+.3%} of state enrollment (tolerance ±{tol:.1%}), "
                f"m={r['m']:.2%}, {r['nodes_covered']}/{r['nodes_total']} areas covered",
            )
        )
        if v >= 2014 and cov < 0.95:
            findings.append(
                Finding("enrollment_closure", "warning", v, None,
                        f"only {cov:.1%} of district areas have ACS residence data")
            )
    return findings


def check_enrollment_remote_classification() -> list[Finding]:
    """Audit the non-classroom statewide-draw classification (the NC_RATIO
    authorizer criterion in enrollment_flows): report, per latest vintage, how
    many authorizers are classified, the pooled seats, and the top entries by
    ratio — so the arithmetic cut is inspectable, and a sudden change in the
    classified set (a big district flipping in or out) is visible in the DQ
    diff rather than silently reshaping county flows."""
    from schoolfactors.paths import PARQUET_DIR

    path = PARQUET_DIR / "analysis" / "enrollment_remote_authorizers.parquet"
    if not path.exists():
        return [Finding("enrollment_remote", "info", None, None,
                        "remote-authorizer classification not built yet — run `sf analyze`")]
    import polars as pl

    from schoolfactors.analysis.enrollment_flows import NC_MIN_SEATS, NC_RATIO

    ra = pl.read_parquet(path)
    findings = []
    if not ra.height:
        return [Finding("enrollment_remote", "warning", None, None,
                        "remote-authorizer table is empty — criterion matched nothing")]
    v = int(ra["vintage"].max())
    cur = ra.filter(pl.col("vintage") == v).sort("cbm_seats", descending=True)
    findings.append(
        Finding("enrollment_remote", "info", v, None,
                f"{cur.height} geographic authorizers classified non-classroom "
                f"(criterion: charter seats > {NC_RATIO}x resident base, "
                f">= {NC_MIN_SEATS:.0f} seats); pooled seats "
                f"{cur['cbm_seats'].sum():,.0f}")
    )
    for r in cur.head(8).to_dicts():
        findings.append(
            Finding("enrollment_remote", "info", v, r["dcds"],
                    f"authorizer {r['dcds']}: {r['cbm_seats']:,.0f} charter seats vs "
                    f"{r['res_base']:,.0f} resident children (ratio {r['ratio']:.1f})")
        )
    # Borderline entries (within 20% of the cut, either side) deserve eyes.
    prior = ra.filter(pl.col("vintage") == v - 1)["dcds"].to_list()
    churn = set(prior) ^ set(cur["dcds"].to_list())
    if prior and churn:
        findings.append(
            Finding("enrollment_remote", "warning", v, None,
                    f"classification churn vs prior vintage: {sorted(churn)} — "
                    "check whether a borderline authorizer crossed the ratio cut")
        )
    return findings


def check_enrollment_siting() -> list[Finding]:
    """Every school's seats must land in a district area (or be counted in the
    import-only pool knowingly): report enrollment share by siting method and the
    NCES crosswalk gaps in both directions (feeds known_issues/nces-crosswalk-gaps)."""
    from schoolfactors.paths import PARQUET_DIR

    seats_path = PARQUET_DIR / "analysis" / "enrollment_school_seats.parquet"
    if not seats_path.exists():
        return [Finding("enrollment_siting", "info", None, None,
                        "enrollment flows not built yet — run `sf analyze`")]
    import polars as pl

    seats = pl.read_parquet(seats_path)
    latest = int(seats["spring"].max())
    d = (
        seats.filter(pl.col("spring") == latest)
        .group_by("sited")
        .agg(pl.col("total").sum().alias("enr"))
    )
    total = d["enr"].sum()
    findings = []
    unsited_share = 0.0
    for r in d.sort("sited").to_dicts():
        share = r["enr"] / total if total else 0.0
        label = r["sited"] or "UNSITED (import-only pool)"
        if r["sited"] is None:
            unsited_share = share
        findings.append(
            Finding("enrollment_siting", "info", latest, None,
                    f"{label}: {r['enr']:,.0f} students ({share:.2%})")
        )
    if unsited_share > 0.01:
        findings.append(
            Finding("enrollment_siting", "warning", latest, None,
                    f"unsited enrollment {unsited_share:.2%} exceeds 1% — "
                    "the import-only pool allocation is carrying real schools")
        )

    con = _con()
    try:
        views = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if "directory_raw" in views:
            from schoolfactors.analysis import enrollment_geo
            from schoolfactors.analysis.enrollment_flows import district_crosswalk

            if enrollment_geo.tiger_available():
                xw = district_crosswalk(con)
                mapped = set(xw["geoid"].to_list())
                geom = {
                    g
                    for lvl in enrollment_geo.LEVELS
                    for g in enrollment_geo.load_district_geometries(lvl)[0]
                }
                # NCES pseudo secondary districts (GEOID 0699xxx) have no CDE LEA
                # by construction — territory whose high grades a unified district
                # serves. Only real-district gaps count against the crosswalk.
                no_cds = sorted(g for g in geom - mapped if not g.startswith("0699"))
                geographic = {
                    r[0]
                    for r in con.execute(
                        "SELECT DISTINCT lpad(trim(ncesdist), 7, '0') FROM directory_raw "
                        "WHERE doc IN ('52', '54', '56') AND ncesdist IS NOT NULL "
                        "AND trim(ncesdist) <> ''"
                    ).fetchall()
                }
                no_geom = sorted(geographic - geom)
                findings.append(
                    Finding(
                        "enrollment_siting", "warning" if len(no_cds) > 40 else "info",
                        None, None,
                        f"crosswalk gaps: {len(no_cds)} current polygons with no CDE "
                        f"district, {len(no_geom)} CDE geographic districts with no "
                        f"current polygon (reorganizations; see known_issues)",
                    )
                )
    finally:
        con.close()
    return findings


def check_enrollment_lausd_regression() -> list[Finding]:
    """The statewide model must reproduce the shipped LAUSD page's resident series:
    acs5 resident public children for the LAUSD area, vintages 2014+ (earlier
    windows differ by the fractional controls correction the LAUSD page does not
    apply to 5-year data), within max(1%, the ACS margin). Net import is NOT
    compared: the LAUSD page allocates the virtual/out-of-county pool from the
    county ledger while the statewide model allocates a statewide pool — a
    documented method difference."""
    import json

    import polars as pl

    from schoolfactors.paths import PARQUET_DIR, REPO_ROOT

    flows_path = PARQUET_DIR / "analysis" / "enrollment_district_flows.parquet"
    page_path = REPO_ROOT / "site" / "static" / "data" / "lausd" / "enrollment.json"
    if not flows_path.exists() or not page_path.exists():
        return [Finding("enrollment_lausd_regression", "info", None, None,
                        "flows or LAUSD page data not built yet")]
    flows = pl.read_parquet(flows_path).filter(
        (pl.col("geoid") == "0622710") & (pl.col("vintage") >= 2014)
    )
    page = json.loads(page_path.read_text())
    acs5_pub = {
        int(y): pub
        for y, _total, survey, pub in page["narrative"]["resident_517"]
        if survey == "acs5" and pub
    }
    findings = []
    for r in flows.sort("vintage").to_dicts():
        v = int(r["vintage"])
        if v not in acs5_pub or r["res_pub"] is None:
            continue
        delta = r["res_pub"] - acs5_pub[v]
        tol = max(0.01 * acs5_pub[v], r["res_moe"] or 0)
        sev = "anomaly" if abs(delta) > tol else "info"
        findings.append(
            Finding(
                "enrollment_lausd_regression", sev, v, "LAUSD",
                f"resident public {r['res_pub']:,.0f} vs LAUSD page "
                f"{acs5_pub[v]:,.0f} ({delta:+,.0f}; tolerance ±{tol:,.0f})",
            )
        )
    if not findings:
        findings.append(Finding("enrollment_lausd_regression", "warning", None, None,
                                "no overlapping vintages to compare"))
    return findings


def check_enrollment_doc_validation() -> list[Finding]:
    """Validate the enrollment flow model against OBSERVED transfers: the District
    of Choice program publishes district-pair transfer counts (CALPADS). DOC is a
    subset of inter-district movement (~8k students/yr, ~50 districts), so this is
    directional validation, not reconciliation: (1) do observed transfers actually
    prefer nearby districts (the model's siting premise); (2) do model nets agree
    in sign with observed DOC nets where DOC volume is material. A hard floor test
    would be invalid — a DOC importer can simultaneously export more via regular
    permits."""
    import math

    import polars as pl

    from schoolfactors.paths import PARQUET_DIR

    flows_path = PARQUET_DIR / "analysis" / "enrollment_district_flows.parquet"
    adj_path = PARQUET_DIR / "analysis" / "enrollment_adjacency.parquet"
    con = _con()
    try:
        views = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if "doc_raw" not in views or not flows_path.exists() or not adj_path.exists():
            return [Finding("enrollment_doc_validation", "info", None, None,
                            "district-of-choice data or flows not built yet")]
        latest = con.execute(
            "SELECT max(source_file) FROM doc_raw WHERE source_file LIKE 'dortransfer%'"
        ).fetchone()[0]
        pairs = con.execute(
            """
            SELECT doc_cdcode, dor_cdcode, TRY_CAST(total_transfer_in AS INT) AS n
            FROM doc_raw
            WHERE source_file = ? AND doc_cdcode IS NOT NULL
              AND doc_cdcode <> dor_cdcode
            """,
            [latest],
        ).fetchall()
        yy = int(latest.replace("dortransfer", "").replace(".txt", ""))
        doc_year = 2000 + yy + 1  # file 22 = school year 2022-23, spring 2023
        into = dict(con.execute(
            "SELECT cdcode, TRY_CAST(total_transfers_in AS INT) FROM doc_raw "
            "WHERE source_file LIKE 'doctransfersinto%' AND source_file LIKE ? "
            "AND cdcode IS NOT NULL",
            [f"%{yy}.txt"],
        ).fetchall())
        out_col = con.execute(
            "SELECT column_name FROM (DESCRIBE doc_raw) WHERE column_name LIKE "
            "'total_transfers_out%' LIMIT 1"
        ).fetchone()
        outs = dict(con.execute(
            f"SELECT cdcode, TRY_CAST({out_col[0]} AS INT) FROM doc_raw "
            "WHERE source_file LIKE 'doctransfersout%' AND source_file LIKE ? "
            "AND cdcode IS NOT NULL",
            [f"%{yy}.txt"],
        ).fetchall()) if out_col else {}
        xw = dict(con.execute(
            "SELECT substr(cds, 1, 7), lpad(trim(any_value(ncesdist)), 7, '0') "
            "FROM directory_raw WHERE ncesdist IS NOT NULL AND trim(ncesdist) <> '' "
            "GROUP BY 1"
        ).fetchall())
    finally:
        con.close()

    adj = pl.read_parquet(adj_path)
    adj_set = set(zip(adj["geoid"].to_list(), adj["neighbor"].to_list()))
    w_adj = w_tot = 0
    for doc_cd, dor_cd, n in pairs:
        gd, gr = xw.get(doc_cd.zfill(7)), xw.get(dor_cd.zfill(7))
        if not gd or not gr or not n:
            continue
        w_tot += n
        if (gd, gr) in adj_set or (gr, gd) in adj_set:
            w_adj += n
    findings = []
    if w_tot:
        share = w_adj / w_tot
        findings.append(
            Finding(
                "enrollment_doc_validation",
                "warning" if share < 0.4 else "info", doc_year, None,
                f"observed DOC transfers: {w_tot:,} students in matched pairs, "
                f"{share:.0%} between ADJACENT districts — supports the nearby-"
                f"draw premise" if share >= 0.4 else
                f"only {share:.0%} of observed DOC transfers are between adjacent "
                f"districts — the nearby-draw premise deserves scrutiny",
            )
        )

    flows = pl.read_parquet(flows_path)
    live = flows.filter((pl.col("level") != "c") & pl.col("net").is_not_null())
    last_v = int(live["vintage"].max())
    model = {r["geoid"]: r for r in live.filter(pl.col("vintage") == last_v).to_dicts()}
    n_ok = n_all = 0
    biggest = None
    for cd, t_in in into.items():
        if not t_in or t_in <= 20:
            continue
        g = xw.get(cd.zfill(7))
        r = model.get(g)
        if not r:
            continue
        doc_net = t_in - (outs.get(cd) or 0)
        ok = (doc_net > 0) == (r["net"] > 0) or abs(r["net"]) < (r["res_moe"] or 0)
        n_all += 1
        n_ok += ok
        if biggest is None or t_in > biggest[1]:
            biggest = (cd, t_in, doc_net, r["net"])
    if n_all:
        rate = n_ok / n_all
        findings.append(
            Finding(
                "enrollment_doc_validation",
                "warning" if rate < 0.6 else "info", doc_year, None,
                f"model-vs-observed sign agreement: {n_ok}/{n_all} DOC districts "
                f"(>20 transfers) match the model's net direction (or sit within "
                f"the model's margin); disagreements are expected where DOC is a "
                f"small share of a district's total movement",
            )
        )
    if biggest and not math.isnan(biggest[3]):
        findings.append(
            Finding(
                "enrollment_doc_validation", "info", doc_year, biggest[0],
                f"largest DOC importer: observed net +{biggest[2]:,} transfers vs "
                f"model net {biggest[3]:+,.0f} (model includes permits and charter "
                f"draw beyond the DOC program)",
            )
        )
    return findings


ALL_CHECKS = [
    check_row_counts,
    check_participation,
    check_suppression_rates,
    check_subgroup_enrollment_variation,
    check_subgroup_sums,
    check_entity_continuity,
    check_census_frpm_alignment,
    check_lausd_resolution,
    check_enrollment_closure,
    check_enrollment_remote_classification,
    check_enrollment_siting,
    check_enrollment_lausd_regression,
    check_enrollment_doc_validation,
]
