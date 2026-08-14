"""Orchestrate the first analysis: panel → per-school models → EB → adjustment.

Outputs:
    data/parquet/analysis/school_effects.parquet — one row per school with OLS, EB,
        adjusted, and reliability columns for level/growth/trend
    data/parquet/analysis/adjustment_coefficients.parquet — covariate coefficients
    printed diagnostics used by the writeup
"""

from __future__ import annotations

import numpy as np
import polars as pl

from schoolfactors.paths import PARQUET_DIR


def run_analysis() -> None:
    from schoolfactors.analysis.model import ADJUST_COVARIATES, adjust, eb_shrink, fit_school_models
    from schoolfactors.analysis.panel import build_covariates, build_panel

    print("building panel …")
    panel = build_panel()
    print(f"  {len(panel):,} school×year×grade×subject observations, "
          f"{panel['cds'].n_unique():,} schools, years {sorted(panel['test_year'].unique())}")

    print("fitting per-school models …")
    effects = fit_school_models(panel)
    print(f"  {len(effects):,} schools with enough data (≥6 obs, ≥3 years)")

    for param in ("level", "growth", "trend"):
        effects, mu, tau2 = eb_shrink(effects, param)
        rel = effects[f"{param}_reliability"]
        ok = (rel >= 0.7).sum()
        print(
            f"  {param}: mu={mu:+.3f}, tau={np.sqrt(tau2):.3f} student-SDs, "
            f"{ok:,}/{rel.is_not_null().sum():,} schools pass reliability ≥ 0.70"
        )

    print("joining covariates + demographic adjustment …")
    cov = build_covariates()
    effects = effects.join(cov, on="cds", how="left")

    coefs = []
    for param in ("level", "growth"):
        effects, coef, tau2 = adjust(effects, param)
        coefs.append(coef)
        print(f"  adjusted {param}: residual tau={np.sqrt(tau2):.3f}")
    coef_table = coefs[0].join(coefs[1], on="term", how="full", coalesce=True)

    # Diagnostics for the writeup
    d = effects.filter(
        pl.col("level").is_not_null() & pl.col("level_adj").is_not_null()
    )
    for name, col in (("raw level", "level"), ("adjusted level", "level_adj")):
        r = np.corrcoef(d[col].to_numpy(), d["share_econ_dis"].to_numpy())[0, 1]
        print(f"  corr({name}, share econ dis) = {r:+.3f}")
    g = effects.filter(pl.col("growth").is_not_null() & pl.col("growth_adj").is_not_null())
    r = np.corrcoef(g["growth_adj"].to_numpy(), g["share_econ_dis"].to_numpy())[0, 1]
    print(f"  corr(adjusted growth, share econ dis) = {r:+.3f}")
    r = np.corrcoef(g["growth_adj"].to_numpy(), g["level"].to_numpy())[0, 1]
    print(f"  falsification corr(adjusted growth, raw level) = {r:+.3f}")

    # Sensitivity: how much do rankings depend on the covariate specification?
    from scipy.stats import spearmanr

    specs = {
        "econ_only": ["share_econ_dis", "log_tested"],
        "econ_race": [
            "share_econ_dis",
            "share_black",
            "share_asian",
            "share_hispanic",
            "share_white",
            "log_tested",
        ],
        "full": ADJUST_COVARIATES,
    }
    spec_resids: dict[str, pl.DataFrame] = {}
    for name, cols in specs.items():
        adj_df, _, _ = adjust(effects.drop([c for c in effects.columns if c.endswith("_adj")
                                            or "_adj_" in c]), "level", cols)
        spec_resids[name] = adj_df.select("cds", pl.col("level_adj").alias(f"adj_{name}"))
    sens = spec_resids["econ_only"]
    for name in ("econ_race", "full"):
        sens = sens.join(spec_resids[name], on="cds", how="inner")
    stats: dict = {"sensitivity": {}}
    a = sens["adj_econ_only"].to_numpy()
    for name in ("econ_race", "full"):
        b = sens[f"adj_{name}"].to_numpy()
        rho = float(spearmanr(a, b).statistic)
        qa = np.quantile(a, 0.8)
        qb = np.quantile(b, 0.8)
        top_agree = float(np.mean((a >= qa) == (b >= qb)))
        stats["sensitivity"][f"econ_only_vs_{name}"] = {
            "spearman": round(rho, 3),
            "top_quintile_agreement": round(top_agree, 3),
        }
        print(f"  sensitivity econ_only vs {name}: spearman={rho:.3f}, "
              f"top-quintile agreement={top_agree:.1%}")

    # How many schools are actually distinguishable from expectation?
    dd = effects.filter(
        pl.col("level_adj").is_not_null() & (pl.col("level_var") > 0)
    )
    zscores = dd["level_adj"].to_numpy() / np.sqrt(dd["level_var"].to_numpy())
    distinguishable = float(np.mean(np.abs(zscores) > 1.96))
    stats["pct_distinguishable_level"] = round(100 * (distinguishable), 1)
    stats["pct_not_distinguishable_level"] = round(100 * (1 - distinguishable), 1)
    print(f"  {100 * (1 - distinguishable):.1f}% of schools not distinguishable from "
          "their demographic expectation at 95%")

    print("rendering figures …")
    from schoolfactors.analysis import figures

    for path in figures.make_all(effects):
        print(f"  wrote {path.relative_to(figures.REPO_ROOT)}")

    out = PARQUET_DIR / "analysis"
    out.mkdir(parents=True, exist_ok=True)
    effects.write_parquet(out / "school_effects.parquet")
    coef_table.write_parquet(out / "adjustment_coefficients.parquet")

    import json

    from schoolfactors.paths import REPO_ROOT

    stats_path = REPO_ROOT / "analysis" / "stats.json"
    stats_path.write_text(json.dumps(stats, indent=2) + "\n")
    print(f"wrote {out / 'school_effects.parquet'} ({len(effects):,} schools)")
