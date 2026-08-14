"""School-level performance model.

Stage 1 (per school): precision-weighted regression of standardized score on centered
year, centered grade, and subject, with level-1 variance fixed to the known sampling
variance (SEDA-style). Yields per-school OLS estimates + sampling variances for:
    level  — average standing vs the state (in student SDs), at the school's center
    growth — within-cohort grade-to-grade progression relative to the state
    trend  — change across cohorts/years relative to the state

Stage 2: empirical-Bayes shrinkage of each parameter toward the state mean, with
between-school variance tau^2 estimated by method of moments. Reliability
lambda = tau^2/(tau^2 + V) gates display (>= 0.70, SEDA's rule).

Stage 3: demographic adjustment — precision-weighted regression of the OLS estimates
(never the EB ones: shrunken outcomes bias coefficients) on school covariates;
residuals are then EB-shrunken for display.
"""

from __future__ import annotations

import numpy as np
import polars as pl

MIN_OBS = 6
MIN_YEARS = 3
PARAMS = ["level", "growth", "trend"]


def fit_school_models(panel: pl.DataFrame) -> pl.DataFrame:
    """Per-school WLS with known level-1 variances. Returns one row per school."""
    out: list[dict] = []
    for (cds,), grp in panel.group_by(["cds"], maintain_order=True):
        n_obs = len(grp)
        years = grp["test_year"].unique()
        if n_obs < MIN_OBS or len(years) < MIN_YEARS:
            continue
        y = grp["z"].to_numpy()
        w = 1.0 / grp["var_z"].to_numpy()
        yr = grp["test_year"].to_numpy().astype(float)
        gr = grp["grade"].to_numpy().astype(float)
        subj = (grp["test_id"].to_numpy() == 2).astype(float) - 0.5
        yr_c = yr - np.average(yr, weights=w)
        gr_c = gr - np.average(gr, weights=w)

        X = np.column_stack([np.ones(n_obs), yr_c, gr_c, subj])
        # Drop collinear columns (single-grade schools have no growth signal)
        keep = [0]
        if np.ptp(yr_c) > 0:
            keep.append(1)
        if np.ptp(gr_c) > 0:
            keep.append(2)
        if np.ptp(subj) > 0:
            keep.append(3)
        Xk = X[:, keep]

        XtW = Xk.T * w
        try:
            cov = np.linalg.inv(XtW @ Xk)
        except np.linalg.LinAlgError:
            continue
        beta = cov @ (XtW @ y)

        row: dict = {
            "cds": cds,
            "n_obs": n_obs,
            "n_years": len(years),
            "mid_year": float(np.average(yr, weights=w)),
            "mid_grade": float(np.average(gr, weights=w)),
            "total_scores": int(grp["n"].sum()),
        }
        names = ["level", "trend", "growth", "subj_gap"]
        for j, col in enumerate(keep):
            row[names[col]] = float(beta[j])
            row[f"{names[col]}_var"] = float(cov[j, j])
        out.append(row)
    return pl.DataFrame(out)


def eb_shrink(df: pl.DataFrame, param: str) -> pl.DataFrame:
    """Method-of-moments EB shrinkage of one parameter toward its precision-weighted mean.

    Adds: {param}_eb, {param}_se, {param}_reliability. tau^2 solves
    weighted_var(beta_hat) = tau^2 + mean(V) on the estimation sample.
    """
    est = df.filter(
        pl.col(param).is_not_null()
        & pl.col(f"{param}_var").is_not_null()
        & (pl.col(f"{param}_var") > 0)  # guard against ill-conditioned inversions
    )
    b = est[param].to_numpy()
    v = est[f"{param}_var"].to_numpy()
    w = 1.0 / (v + np.median(v))  # stabilizing first-pass weights
    mu = float(np.average(b, weights=w))
    tau2 = max(float(np.average((b - mu) ** 2, weights=w) - np.average(v, weights=w)), 1e-6)
    # One refinement pass with tau^2-informed weights
    w = 1.0 / (v + tau2)
    mu = float(np.average(b, weights=w))
    tau2 = max(float(np.average((b - mu) ** 2, weights=w) - np.average(v, weights=w)), 1e-6)

    lam = tau2 / (tau2 + est[f"{param}_var"].to_numpy())
    eb = mu + lam * (est[param].to_numpy() - mu)
    add = est.select("cds").with_columns(
        pl.Series(f"{param}_eb", eb),
        pl.Series(f"{param}_se", np.sqrt(est[f"{param}_var"].to_numpy())),
        pl.Series(f"{param}_reliability", lam),
    )
    return df.join(add, on="cds", how="left"), mu, tau2


ADJUST_COVARIATES = [
    "share_econ_dis",
    "share_black",
    "share_asian",
    "share_hispanic",
    "share_white",
    "share_el",
    "share_swd",
    "share_parent_not_hs",
    "share_parent_college",
    "share_parent_gradschool",
    "log_tested",
]


def adjust(df: pl.DataFrame, param: str, covariates: list[str] | None = None) -> pl.DataFrame:
    """Precision-weighted adjustment regression on OLS estimates; adds residual columns.

    Returns (df with {param}_adj, {param}_adj_eb), plus the fitted coefficient table.
    """
    covariates = covariates or ADJUST_COVARIATES
    est = df.filter(
        pl.col(param).is_not_null()
        & pl.col(f"{param}_var").is_not_null()
        & (pl.col(f"{param}_var") > 0)
        & pl.all_horizontal([pl.col(c).is_not_null() for c in covariates])
    )
    y = est[param].to_numpy()
    v = est[f"{param}_var"].to_numpy()
    X = np.column_stack([np.ones(len(est))] + [est[c].to_numpy() for c in covariates])

    # Estimate residual tau^2 iteratively so weights reflect total variance
    tau2 = 0.01
    for _ in range(4):
        w = 1.0 / (v + tau2)
        XtW = X.T * w
        gamma = np.linalg.solve(XtW @ X, XtW @ y)
        resid = y - X @ gamma
        tau2 = max(float(np.average(resid**2, weights=w) - np.average(v, weights=w)), 1e-6)

    lam = tau2 / (tau2 + v)
    add = est.select("cds").with_columns(
        pl.Series(f"{param}_adj", resid),
        pl.Series(f"{param}_adj_eb", lam * resid),
        pl.Series(f"{param}_adj_se", np.sqrt(v + 0 * resid)),
        pl.Series(f"{param}_adj_reliability", lam),
    )
    coef = pl.DataFrame({"term": ["intercept", *covariates], f"gamma_{param}": gamma})
    return df.join(add, on="cds", how="left"), coef, tau2
