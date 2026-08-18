"""Build the school × year × grade × subject analysis panel from CAASPP.

Exclusions, each tied to a documented reason:
- 2021 (participation collapse — see DATA_QUALITY.md; statewide ELA participation 23.7%)
- suppressed rows (mean_scale_score null, n < 11 at source)
- grade 13 rollups (we model grade-specific means)

Scores are standardized within year × grade × subject against the state mean and an
empirically estimated student-level SD (see estimate_sigma), so a school at 0.0 is at
the state average for that grade/subject/year and units are student-level SDs.
"""

from __future__ import annotations

import duckdb
import numpy as np
import polars as pl
from scipy.stats import norm

from schoolfactors.paths import DUCKDB_PATH

EXCLUDED_YEARS = (2021,)
MIN_SCORES = 11


def _con() -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(DUCKDB_PATH), read_only=True)


SCHOOL_TYPES = (7, 9, 10)
DISTRICT_TYPES = (6,)
COUNTY_TYPES = (5,)


def school_rows(types: tuple[int, ...] = SCHOOL_TYPES) -> pl.DataFrame:
    con = _con()
    df = con.execute(f"""
        SELECT cds, test_year, grade, test_id,
               mean_scale_score, pct_met_and_above, students_with_scores AS n
        FROM caaspp_sb
        WHERE type_id IN {types if len(types) > 1 else f"({types[0]})"}
          AND student_group_id = 1
          AND grade BETWEEN 3 AND 11
          AND test_id IN (1, 2)
          AND mean_scale_score IS NOT NULL
          AND students_with_scores >= {MIN_SCORES}
          AND test_year NOT IN {EXCLUDED_YEARS}
    """).pl()
    con.close()
    return df


def state_means() -> pl.DataFrame:
    con = _con()
    df = con.execute(f"""
        SELECT test_year, grade, test_id, mean_scale_score AS state_mean
        FROM caaspp_sb_raw
        WHERE cds = '00000000000000' AND student_group_id = 1
          AND grade BETWEEN 3 AND 11 AND test_id IN (1, 2)
          AND test_year NOT IN {EXCLUDED_YEARS}
    """).pl()
    con.close()
    return df


def estimate_sigma(rows: pl.DataFrame) -> pl.DataFrame:
    """Estimate student-level scale-score SD per (year, grade, subject).

    Across schools, Phi^-1(pct_met_and_above) is linear in the school mean with slope
    1/sigma under a within-school-normal assumption with common SD. Validated against
    published Smarter Balanced thresholds (implied grade-4 ELA cut 2467.6 vs official
    2473; R^2 ~ 0.96).
    """
    out = []
    for (year, grade, test), grp in rows.group_by(
        ["test_year", "grade", "test_id"], maintain_order=True
    ):
        g = grp.filter(
            (pl.col("pct_met_and_above") >= 2)
            & (pl.col("pct_met_and_above") <= 98)
            & (pl.col("n") >= 30)
        )
        if len(g) < 100:
            continue
        z = norm.ppf(g["pct_met_and_above"].to_numpy() / 100)
        m = g["mean_scale_score"].to_numpy()
        slope, intercept = np.polyfit(m, z, 1)
        out.append(
            {
                "test_year": year,
                "grade": grade,
                "test_id": test,
                "sigma": float(1 / slope),
                # Implied "Standard Met" cut: the mean at which Phi^-1(met+) = 0.
                # Published cuts are fixed across years; the per-year implied
                # values scatter around them by estimation noise.
                "cut": float(-intercept / slope),
            }
        )
    return pl.DataFrame(out)


def build_panel(types: tuple[int, ...] = SCHOOL_TYPES) -> pl.DataFrame:
    rows = school_rows(types)
    # sigma is always estimated from the school-level cross-section (districts are
    # too few and too aggregated for the probit fit)
    sigma_rows = rows if types == SCHOOL_TYPES else school_rows(SCHOOL_TYPES)
    panel = rows.join(state_means(), on=["test_year", "grade", "test_id"], how="inner").join(
        estimate_sigma(sigma_rows), on=["test_year", "grade", "test_id"], how="inner"
    )
    return panel.with_columns(
        ((pl.col("mean_scale_score") - pl.col("state_mean")) / pl.col("sigma")).alias("z"),
        # Sampling variance of the school mean in z units. Within-school SD is somewhat
        # below the population SD (ICC ~0.2 => ratio ~0.9); we use 1/n and note the
        # modest conservatism in the writeup.
        (1.0 / pl.col("n")).alias("var_z"),
    )


# CAASPP-internal covariates: shares of the tested population, averaged across years
# (weighted by tested n). Group IDs per caaspp_student_groups.
COVARIATE_GROUPS = {
    "share_econ_dis": 31,
    "share_black": 74,
    "share_asian": 76,
    "share_hispanic": 78,
    "share_white": 80,
    "share_el": 160,
    "share_swd": 128,
    "share_parent_not_hs": 90,
    "share_parent_college": 93,
    "share_parent_gradschool": 94,
}


def build_covariates(
    types: tuple[int, ...] = SCHOOL_TYPES, max_year: int | None = None
) -> pl.DataFrame:
    """Tested-population shares, averaged across years. max_year restricts the
    average to years <= max_year for the out-of-sample history refits."""
    ids = ", ".join(str(v) for v in COVARIATE_GROUPS.values())
    types_sql = str(types) if len(types) > 1 else f"({types[0]})"
    year_cap = f"AND test_year <= {int(max_year)}" if max_year is not None else ""
    con = _con()
    df = con.execute(f"""
        WITH tested AS (
            SELECT cds, test_year, student_group_id, sum(students_tested) AS t
            FROM caaspp_sb
            WHERE type_id IN {types_sql} AND grade = 13 AND test_id = 1
              AND student_group_id IN (1, {ids})
              AND test_year NOT IN {EXCLUDED_YEARS} {year_cap}
            GROUP BY 1, 2, 3
        ),
        wide AS (
            SELECT cds, test_year,
                   max(CASE WHEN student_group_id = 1 THEN t END) AS t_all,
                   {
        ", ".join(
            f"max(CASE WHEN student_group_id = {gid} THEN t END) AS g{gid}"
            for gid in COVARIATE_GROUPS.values()
        )
    }
            FROM tested GROUP BY 1, 2
        )
        SELECT cds,
               sum(t_all) AS tested_total,
               {
        ", ".join(
            f"sum(coalesce(g{gid}, 0)) / sum(t_all) AS {name}"
            for name, gid in COVARIATE_GROUPS.items()
        )
    }
        FROM wide
        WHERE t_all IS NOT NULL AND t_all > 0
        GROUP BY cds
    """).pl()
    con.close()
    return df.with_columns(pl.col("tested_total").log().alias("log_tested"))
