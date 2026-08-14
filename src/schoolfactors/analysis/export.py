"""Export prebuilt JSON for the static site.

Site data contract (v0): small, flat JSON files under site/static/data/ that the
SvelteKit pages fetch at runtime. Everything is precomputed — the site has no API.
"""

from __future__ import annotations

import json

import duckdb
import polars as pl

from schoolfactors.paths import DUCKDB_PATH, PARQUET_DIR, REPO_ROOT

SITE_DATA = REPO_ROOT / "site" / "static" / "data"
PILOT_COUNTY = "49"  # Sonoma — where this project's data-quality story began


def run_export() -> None:
    SITE_DATA.mkdir(parents=True, exist_ok=True)
    effects = pl.read_parquet(PARQUET_DIR / "analysis" / "school_effects.parquet")
    con = duckdb.connect(str(DUCKDB_PATH), read_only=True)

    # School names from the latest entities year
    names = con.execute("""
        SELECT cds, any_value(school_name) AS school_name,
               any_value(district_name) AS district_name,
               any_value(county_name) AS county_name
        FROM caaspp_entities
        WHERE test_year = (SELECT max(test_year) FROM caaspp_entities)
          AND school_name IS NOT NULL
        GROUP BY cds
    """).pl()
    con.close()

    keep = [
        "cds",
        "total_scores",
        "n_years",
        "level_eb",
        "level_se",
        "growth_eb",
        "growth_se",
        "trend_eb",
        "level_adj_eb",
        "growth_adj_eb",
        "level_reliability",
        "growth_reliability",
        "share_econ_dis",
        "share_el",
    ]
    joined = (
        effects.select([c for c in keep if c in effects.columns])
        .join(names, on="cds", how="inner")
        .with_columns(
            [pl.col(c).round(3) for c in keep if c not in ("cds", "total_scores", "n_years")]
        )
    )

    pilot = joined.filter(pl.col("cds").str.starts_with(PILOT_COUNTY))
    (SITE_DATA / "pilot_county.json").write_text(
        json.dumps(
            {
                "county": "Sonoma",
                "generated_from": "CAASPP research files 2015-2025 (excl. 2020, 2021)",
                "schools": pilot.to_dicts(),
            },
            indent=1,
        )
    )
    print(f"  pilot_county.json: {len(pilot)} Sonoma schools")

    summary = {
        "n_schools_modeled": len(effects),
        "n_observations": 519_923,
        "years": [2015, 2016, 2017, 2018, 2019, 2022, 2023, 2024, 2025],
        "corr_raw_level_econ": -0.76,
        "corr_adjusted_level_econ": -0.001,
        "falsification_growth_vs_level": 0.007,
        "tau_level_sds": 0.62,
        "tau_growth_sds_per_grade": 0.066,
    }
    stats_path = REPO_ROOT / "analysis" / "stats.json"
    if stats_path.exists():
        summary["sensitivity"] = json.loads(stats_path.read_text()).get("sensitivity")
    (SITE_DATA / "summary.json").write_text(json.dumps(summary, indent=1))
    print("  summary.json written")
