"""Cohort tracking for school and district pages.

A "cohort" is the group of students expected to graduate the same year: a row at
grade g in test year t belongs to the cohort with grad_year = t + (12 - g). Following
a cohort across grades (grade 4 in 2023 vs grade 3 in 2022) approximates following
the same students — but only approximates it, because students move. So alongside
each cohort's score trajectory we track the tested population's composition
(economic disadvantage, English learners, disabilities, race/ethnicity) and flag
steps where the blend shifted by more than sampling noise explains. A score change
that coincides with a large blend shift may be compositional, not instructional,
and the page says so.

All scores are state-relative (standardized within year × grade × subject, student-SD
units), so a flat line means "moving with the state average".
"""

from __future__ import annotations

import duckdb
import numpy as np
import polars as pl

from schoolfactors.paths import DUCKDB_PATH

# Groups tracked for cohort composition, and the matching adjustment-covariate name
# (used to translate a blend shift into an expected score shift via the fitted gammas).
BLEND_GROUPS = {
    31: ("econ_dis", "share_econ_dis"),
    160: ("el", "share_el"),
    128: ("swd", "share_swd"),
    74: ("black", "share_black"),
    76: ("asian", "share_asian"),
    78: ("hispanic", "share_hispanic"),
    80: ("white", "share_white"),
}

EXCLUDED_YEARS = (2021,)
MIN_N = 11


def cohort_scores(types_sql: str, sigma: pl.DataFrame, state: pl.DataFrame) -> pl.DataFrame:
    """Per entity × subject × grade × year standardized scores with cohort labels."""
    con = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    df = con.execute(f"""
        SELECT cds, test_year, grade, test_id,
               mean_scale_score, pct_met_and_above, students_with_scores AS n
        FROM caaspp_sb
        WHERE type_id IN {types_sql}
          AND student_group_id = 1 AND grade BETWEEN 3 AND 11 AND test_id IN (1, 2)
          AND mean_scale_score IS NOT NULL AND students_with_scores >= {MIN_N}
          AND test_year NOT IN {EXCLUDED_YEARS}
    """).pl()
    con.close()
    df = df.join(state, on=["test_year", "grade", "test_id"], how="inner").join(
        sigma, on=["test_year", "grade", "test_id"], how="inner"
    )
    return df.with_columns(
        ((pl.col("mean_scale_score") - pl.col("state_mean")) / pl.col("sigma"))
        .round(3)
        .alias("z"),
        (pl.col("test_year") + 12 - pl.col("grade")).alias("grad_year"),
        pl.col("state_mean").round(1),
    ).select(
        "cds",
        "test_year",
        "grade",
        "test_id",
        "grad_year",
        "z",
        "n",
        "mean_scale_score",
        "pct_met_and_above",
        "state_mean",
    )


# Student groups shown in the "underlying data by group" table (grade-13 combined
# rows carry no mean scale score — scales differ by grade — so these use percent
# met-and-above). IDs per caaspp_student_groups.
SUBGROUP_TABLE_IDS = (
    1, 3, 4, 31, 111, 160, 8, 128, 99,
    74, 75, 76, 77, 78, 79, 80, 144,
    90, 91, 92, 93, 94, 121,
)


def subgroup_results(types_sql: str) -> pl.DataFrame:
    """Per entity × year × subject × student group: % met-and-above at grade 13."""
    ids = ", ".join(str(i) for i in SUBGROUP_TABLE_IDS)
    con = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    df = con.execute(f"""
        SELECT cds, test_year, test_id, student_group_id,
               pct_met_and_above, students_with_scores AS n
        FROM caaspp_sb
        WHERE type_id IN {types_sql} AND grade = 13 AND test_id IN (1, 2)
          AND student_group_id IN ({ids})
          AND pct_met_and_above IS NOT NULL AND students_with_scores >= {MIN_N}
          AND test_year NOT IN {EXCLUDED_YEARS}
    """).pl()
    con.close()
    return df


def cohort_blend(types_sql: str) -> pl.DataFrame:
    """Per entity × grade × year tested-population shares for the blend groups."""
    ids = ", ".join(str(g) for g in BLEND_GROUPS)
    con = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    df = con.execute(f"""
        WITH t AS (
            SELECT cds, test_year, grade, student_group_id, students_tested AS n
            FROM caaspp_sb
            WHERE type_id IN {types_sql} AND test_id = 1
              AND grade BETWEEN 3 AND 11
              AND student_group_id IN (1, {ids})
              AND students_tested IS NOT NULL
              AND test_year NOT IN {EXCLUDED_YEARS}
        )
        SELECT cds, test_year, grade,
               max(CASE WHEN student_group_id = 1 THEN n END) AS n_all,
               {
        ", ".join(
            f"max(CASE WHEN student_group_id = {gid} THEN n END) AS n_{name}"
            for gid, (name, _) in BLEND_GROUPS.items()
        )
    }
        FROM t GROUP BY 1, 2, 3
        HAVING n_all >= {MIN_N}
    """).pl()
    con.close()
    return df.with_columns(
        [
            (pl.col(f"n_{name}") / pl.col("n_all")).round(3).alias(f"share_{name}")
            for _, (name, _) in BLEND_GROUPS.items()
        ]
    ).with_columns((pl.col("test_year") + 12 - pl.col("grade")).alias("grad_year"))


def cohort_steps(
    blend: pl.DataFrame, gammas: dict[str, float]
) -> pl.DataFrame:
    """Grade-to-grade steps within each entity × cohort, with blend-shift flags.

    A share shift is flagged when it exceeds 2 binomial SEs + a 3pp floor; the
    expected score shift from the blend uses the level-adjustment coefficients.
    """
    a = blend
    b = blend.select(
        "cds",
        "grad_year",
        (pl.col("grade") - 1).alias("grade"),  # join next grade onto current
        pl.col("n_all").alias("n_all_next"),
        *[
            pl.col(f"share_{name}").alias(f"share_{name}_next")
            for _, (name, _) in BLEND_GROUPS.items()
        ],
    )
    steps = a.join(b, on=["cds", "grad_year", "grade"], how="inner")

    flag_exprs = []
    expected_dz = pl.lit(0.0)
    for _, (name, covar) in BLEND_GROUPS.items():
        s0, s1 = pl.col(f"share_{name}"), pl.col(f"share_{name}_next")
        d = s1 - s0
        se = (
            (s0 * (1 - s0) / pl.col("n_all") + s1 * (1 - s1) / pl.col("n_all_next"))
            .clip(lower_bound=0)
            .sqrt()
        )
        flag_exprs.append(
            (d.abs() > (2 * se + 0.03)).fill_null(False).alias(f"flag_{name}")
        )
        steps = steps.with_columns(d.round(3).alias(f"d_{name}"))
        gamma = gammas.get(covar)
        if gamma is not None:
            expected_dz = expected_dz + d.fill_null(0.0) * gamma

    steps = steps.with_columns(
        *flag_exprs,
        ((pl.col("n_all_next") - pl.col("n_all")) / pl.col("n_all"))
        .round(3)
        .alias("n_change_frac"),
        expected_dz.round(3).alias("expected_dz_from_blend"),
    )
    steps = steps.with_columns(
        (
            pl.any_horizontal([pl.col(f"flag_{name}") for _, (name, _) in BLEND_GROUPS.items()])
            | (pl.col("n_change_frac").abs() > 0.2)
        ).alias("blend_shift_flag")
    )
    return steps


def cohort_slopes(scores: pl.DataFrame) -> pl.DataFrame:
    """Weighted slope of z on grade per entity × cohort (subjects pooled)."""
    out = []
    for (cds, grad_year), grp in scores.group_by(["cds", "grad_year"], maintain_order=True):
        if grp["grade"].n_unique() < 2:
            continue
        g = grp["grade"].to_numpy().astype(float)
        z = grp["z"].to_numpy()
        w = grp["n"].to_numpy().astype(float)
        gc = g - np.average(g, weights=w)
        denom = float(np.sum(w * gc * gc))
        if denom <= 0:
            continue
        slope = float(np.sum(w * gc * z) / denom)
        # With Var(z_i) = 1/n_i and weights w_i = n_i, Var(slope) = 1/denom.
        se = float(np.sqrt(1.0 / denom))
        out.append(
            {
                "cds": cds,
                "grad_year": int(grad_year),
                "slope": round(slope, 3),
                "slope_se": round(se, 3),
                "n_points": len(grp),
            }
        )
    return pl.DataFrame(out)
