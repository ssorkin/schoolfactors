"""Out-of-sample history of the similar-schools ranking inputs.

For each cutoff year C, the full level pipeline (per-school WLS → EB shrinkage →
demographic adjustment) is refit on data through C only, with the covariate
averages likewise restricted — later years never leak into an earlier fit. The
export stage turns the cutoff-C fit into the Similar Schools percentile a
reader would have seen ENTERING the next test year, so each chip on a school
page is a genuine forecast: the chip labeled 2024 knew nothing about 2024's
scores, and the chip sequence shows how stable and predictive the measure is.
"""

from __future__ import annotations

from collections.abc import Callable

import polars as pl

from schoolfactors.analysis.model import MIN_YEARS, adjust, eb_shrink, fit_school_models

HISTORY_COLS = ["cds", "as_of_year", "last_year", "level_adj_lcb", "level_reliability"]


def level_history(
    panel: pl.DataFrame,
    build_cov: Callable[[int], pl.DataFrame],
    covariates: list[str] | None = None,
) -> pl.DataFrame:
    """One row per (cds, cutoff year): the adjusted-level ranking columns refit
    on data through that year only. build_cov(year) must return the covariate
    frame restricted to the same cutoff."""
    years = sorted(panel["test_year"].unique().to_list())
    frames = []
    for i, cut in enumerate(years):
        if i + 1 < MIN_YEARS:
            continue  # no school can pass the >= MIN_YEARS gate yet
        eff = fit_school_models(panel.filter(pl.col("test_year") <= cut))
        if len(eff) == 0:
            continue
        eff, _, _ = eb_shrink(eff, "level")
        eff = eff.join(build_cov(cut), on="cds", how="left")
        eff, _, _ = adjust(eff, "level", covariates)
        frames.append(
            eff.select(
                "cds",
                pl.lit(int(cut), dtype=pl.Int64).alias("as_of_year"),
                pl.col("last_year").cast(pl.Int64),
                "level_adj_lcb",
                "level_reliability",
            )
        )
    return pl.concat(frames) if frames else pl.DataFrame(schema=HISTORY_COLS)
