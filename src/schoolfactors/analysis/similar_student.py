"""Similar Student percentile inputs: within-school student-level effects.

Shipped as the "Similar Student %ile" (the parent decision question): for a
fixed student profile, how the conditional expectation at this school ranks
statewide. The sibling "Expected Student %ile" (percentile of the demographic
prediction, computed in export.py) describes the population served; this
metric describes what the school-plus-peer environment delivers for students
like these. Motivating example: San Marino High 94th / La Canada High 99th /
John Marshall Senior High 82nd, matching observed outcomes for comparable
students. Conditional association, not a causal transfer effect — see the
methodology page.

The Similar Schools percentile ranks level_adj — the school's residual after
regressing levels on its tested-population composition. That is the right
ranking for "does this school outperform schools serving similar students",
but not for "how would a given student fare here": the school-level
coefficients absorb peer composition along with student background, so a
school whose students are unusually advantaged can rank low even when a fixed
student's expected outcome there is excellent.

This module estimates STUDENT-level demographic effects from within-school
subgroup contrasts and subtracts only those from the school's fitted level:

    ssl_s = level_eb_s − Σ_g x_{g,s} · δ_g

where δ_g are two-way fixed-effect estimates (cell × group; cell = school ×
year × grade × subject) over the published race × SED cross-tab groups
(Demographic IDs 200-207 SED, 220-227 not-SED) — a single genuine partition,
so the two dominant demographic axes are counted exactly once and never
double-counted. δ is centered so the statewide average student contributes
zero. Under an additive model, a student with profile x has expected outcome
γ'x + ssl_s at school s, so ranking schools by ssl ranks expected outcomes for
ANY fixed profile — "a percentile of an expected value".

Interpretation notes (also surfaced in the UI tooltip):
- Peer composition is credited TO the school by construction. This is an
  expected-outcome ranking, not a value-add ranking; the Similar Schools
  percentile remains the value-add view.
- Composition beyond race × SED (parent education, EL, disability) stays with
  the school. Adding those dimensions separately would double-count overlap
  with race × SED, so the correction is deliberately conservative.
- Within-school subgroup gaps can reflect within-school tracking as well as
  student background; δ is a descriptive, not causal, decomposition.

Validated against the motivating example (2026-08): San Marino High moves
39th → 94th, La Cañada High 86th → 99th, John Marshall Senior High 87th →
82nd — matching the observed pattern that a fixed student's outcomes at the
first two are similar and higher.
"""

from __future__ import annotations

import duckdb
import numpy as np
import polars as pl

from schoolfactors.analysis.panel import (
    EXCLUDED_YEARS,
    estimate_sigma,
    school_rows,
    state_means,
)
from schoolfactors.paths import DUCKDB_PATH

# Published race x SED cross-tab (Demographic ID Num): 200-207 = SED by
# race/ethnicity, 220-227 = not-SED by race/ethnicity.
CROSS_GROUPS = list(range(200, 208)) + list(range(220, 228))

# Entity levels the shares are computed for: county (5), district (6),
# school (7, 9, 10). Deltas are always estimated from school-level cells.
SHARE_TYPES = (5, 6, 7, 9, 10)
SCHOOL_TYPES = (7, 9, 10)


def student_effects(
    max_year: int | None = None,
) -> tuple[dict[str, float], dict[int, float]]:
    """Returns (stud_eff by cds for all SHARE_TYPES entities, delta by group id).

    stud_eff is the score-weighted composition effect Σ x_g · δ_g of the
    entity's tested population, in student SDs vs the state. With max_year,
    both the within-school deltas and the shares use only test years <= it —
    the era-contemporaneous version for out-of-sample comparisons.
    """
    con = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    try:
        gids = ", ".join(map(str, CROSS_GROUPS))
        rows = con.execute(
            f"""
            SELECT cds, type_id, test_year, grade, test_id,
                   student_group_id AS gid,
                   mean_scale_score AS mss, students_with_scores AS n
            FROM caaspp_sb
            WHERE type_id IN {SHARE_TYPES} AND student_group_id IN ({gids})
              AND grade BETWEEN 3 AND 11 AND test_id IN (1, 2)
              AND mean_scale_score IS NOT NULL AND students_with_scores >= 11
              AND test_year NOT IN {EXCLUDED_YEARS}
              {f"AND test_year <= {int(max_year)}" if max_year else ""}
            """
        ).pl()
        sm = state_means()
        sig = estimate_sigma(school_rows())
    finally:
        con.close()
    rows = (
        rows.join(sm, on=["test_year", "grade", "test_id"], how="inner")
        .join(sig, on=["test_year", "grade", "test_id"], how="inner")
        .with_columns(((pl.col("mss") - pl.col("state_mean")) / pl.col("sigma")).alias("z"))
    )

    school = rows.filter(pl.col("type_id").is_in(SCHOOL_TYPES)).with_columns(
        (
            pl.col("cds") + "|" + pl.col("test_year").cast(str) + "|"
            + pl.col("grade").cast(str) + "|" + pl.col("test_id").cast(str)
        ).alias("cell")
    )
    counts = school.group_by("cell").len().filter(pl.col("len") >= 2)
    school = school.join(counts.select("cell"), on="cell", how="inner")

    gidx = {g: i for i, g in enumerate(CROSS_GROUPS)}
    gi = np.array([gidx[x] for x in school["gid"].to_numpy()])
    z = school["z"].to_numpy()
    w = school["n"].to_numpy().astype(float)
    _, ci = np.unique(school["cell"].to_numpy(), return_inverse=True)
    n_cells = ci.max() + 1

    delta = np.zeros(len(CROSS_GROUPS))
    for _ in range(60):
        resid = z - delta[gi]
        ceff = np.bincount(ci, weights=w * resid, minlength=n_cells) / np.maximum(
            np.bincount(ci, weights=w, minlength=n_cells), 1e-9
        )
        resid2 = z - ceff[ci]
        delta = np.bincount(gi, weights=w * resid2, minlength=len(CROSS_GROUPS)) / (
            np.maximum(np.bincount(gi, weights=w, minlength=len(CROSS_GROUPS)), 1e-9)
        )
    weights = np.bincount(gi, weights=w, minlength=len(CROSS_GROUPS))
    delta = delta - np.average(delta, weights=weights)
    deltas = dict(zip(CROSS_GROUPS, delta))

    shares = rows.group_by(["cds", "gid"]).agg(pl.col("n").sum().alias("n"))
    stud_eff: dict[str, float] = {}
    for (cds,), df in shares.partition_by("cds", as_dict=True).items():
        byg = dict(zip(df["gid"].to_list(), df["n"].to_list()))
        tot = sum(byg.values())
        if tot > 0:
            stud_eff[cds] = float(
                sum(n / tot * deltas[g] for g, n in byg.items())
            )
    return stud_eff, deltas


def simstu_history() -> None:
    """District/county Similar-Student level history: level_eb as of each cutoff
    year minus that cutoff's student-composition effect — the parent-facing
    measure (conditional expectation for a fixed student profile), per year.
    Percentile ranking happens at export, within each entity kind.

    Writes data/parquet/analysis/{district,county}_simstu_history.parquet.
    """
    from schoolfactors.paths import PARQUET_DIR

    analysis_dir = PARQUET_DIR / "analysis"
    hists = {}
    for kind in ("district", "county"):
        path = analysis_dir / f"{kind}_effects_history.parquet"
        if path.exists():
            hists[kind] = pl.read_parquet(path).filter(pl.col("level_eb").is_not_null())
    if not hists:
        return
    years = sorted({int(y) for h in hists.values() for y in h["as_of_year"].unique()})
    eff_by_year = {y: student_effects(max_year=y)[0] for y in years}
    for kind, hist in hists.items():
        rows = [
            {"cds": cds, "as_of_year": int(y), "simstu": leb - eff_by_year[int(y)][cds]}
            for cds, y, leb in hist.select("cds", "as_of_year", "level_eb").iter_rows()
            if cds in eff_by_year[int(y)]
        ]
        out = analysis_dir / f"{kind}_simstu_history.parquet"
        pl.DataFrame(rows).write_parquet(out)
        print(f"  simstu history: {len(rows):,} {kind}xcutoff rows")
