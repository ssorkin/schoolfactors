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


ALL_CHECKS = [
    check_row_counts,
    check_participation,
    check_suppression_rates,
    check_subgroup_enrollment_variation,
    check_subgroup_sums,
    check_entity_continuity,
    check_census_frpm_alignment,
    check_lausd_resolution,
]
