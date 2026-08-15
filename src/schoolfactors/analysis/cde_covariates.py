"""School-level covariates from CDE administrative data.

Each is averaged across the study years per school (weighted where sensible),
aligned on the zero-padded CDS key. These join the CAASPP-derived covariates as
competing adjustment specifications — the sensitivity across specifications is a
published artifact, not a footnote.

Conventions verified against the ingested data:
- FRPM percent columns are 0-1 fractions.
- Absenteeism/stability: filter AggregateLevel='S', ReportingCategory='TA', and
  Charter/DASS='All' where present (otherwise rows triple-count).
- Staff experience: staff_type='TCH', staff_gender='ALL', school-level rows.
"""

from __future__ import annotations

import duckdb
import polars as pl

from schoolfactors.paths import DUCKDB_PATH

CDE_COVARIATES = [
    "frpm_share",
    "upc_share",
    "absent_rate",
    "stability_rate",
    "teacher_avg_years",
]


def build_cde_covariates() -> pl.DataFrame:
    con = duckdb.connect(str(DUCKDB_PATH), read_only=True)

    frpm = con.execute("""
        SELECT cds,
               avg(TRY_CAST(percent_eligible_frpm_k_12 AS DOUBLE)) AS frpm_share
        FROM frpm_raw
        WHERE school_code IS NOT NULL AND school_code <> '0000000'
        GROUP BY cds
        HAVING frpm_share IS NOT NULL
    """).pl()

    upc = con.execute("""
        SELECT cds,
               sum(TRY_CAST(calpads_unduplicated_pupil_count_upc AS DOUBLE))
                 / nullif(sum(TRY_CAST(total_enrollment AS DOUBLE)), 0) AS upc_share
        FROM cupc_raw
        WHERE school_code IS NOT NULL AND school_code <> '0000000'
        GROUP BY cds
        HAVING upc_share IS NOT NULL
    """).pl()

    absent = con.execute("""
        SELECT cds,
               avg(TRY_CAST(chronicabsenteeismrate AS DOUBLE)) / 100.0 AS absent_rate
        FROM absenteeism_raw
        WHERE COALESCE(aggregate_level, aggregatelevel) = 'S'
          AND COALESCE(reporting_category, reportingcategory) = 'TA'
          AND COALESCE(charter_school, charteryn, 'All') IN ('All', 'ALL')
        GROUP BY cds
        HAVING absent_rate IS NOT NULL
    """).pl()

    stability = con.execute("""
        -- School rows carry the school's own charter/DASS flag (no 'All' rollup at
        -- this grain), and a school-year's rate is identical across labelings, so
        -- no charter/DASS filter is needed at aggregate_level 'S'.
        SELECT cds,
               avg(TRY_CAST(stability_rate_percent AS DOUBLE)) / 100.0 AS stability_rate
        FROM stability_raw
        WHERE aggregate_level = 'S' AND reporting_category = 'TA'
        GROUP BY cds
        HAVING stability_rate IS NOT NULL
    """).pl()

    teacher = con.execute("""
        SELECT cds,
               avg(TRY_CAST(average_total_years_experience AS DOUBLE)) AS teacher_avg_years
        FROM staff_exp_raw
        WHERE aggregate_level = 'S' AND staff_type = 'TCH' AND staff_gender = 'ALL'
        GROUP BY cds
        HAVING teacher_avg_years IS NOT NULL
    """).pl()

    con.close()

    out = frpm
    for df in (upc, absent, stability, teacher):
        out = out.join(df, on="cds", how="full", coalesce=True)
    return out
