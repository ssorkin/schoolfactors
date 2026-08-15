"""Export prebuilt JSON for the static site.

Site data contract (v1):
    data/index.json                 — statewide search index (schools + districts)
    data/schools/{cds}.json         — per-school page payload
    data/districts/{cds}.json       — per-district page payload
    data/summary.json               — homepage stats
Everything is precomputed — the site has no API.
"""

from __future__ import annotations

import json

import duckdb
import polars as pl

from schoolfactors.paths import DUCKDB_PATH, PARQUET_DIR, REPO_ROOT

SITE_DATA = REPO_ROOT / "site" / "static" / "data"

EFFECT_COLS = [
    "total_scores",
    "n_years",
    "level_eb",
    "level_se",
    "growth_eb",
    "growth_se",
    "trend_eb",
    "trend_se",
    "level_adj_eb",
    "growth_adj_eb",
    "level_reliability",
    "growth_reliability",
    "share_econ_dis",
    "share_el",
]


def _names() -> pl.DataFrame:
    """Latest known name per entity (falling back through years for closed schools)."""
    con = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    df = con.execute("""
        SELECT cds, school_name, district_name, county_name, type_id
        FROM (
            SELECT cds, school_name, district_name, county_name, type_id,
                   row_number() OVER (PARTITION BY cds ORDER BY test_year DESC) AS rn
            FROM caaspp_entities
        ) WHERE rn = 1
    """).pl()
    con.close()
    return df


def _effect_payload(row: dict) -> dict:
    return {k: row.get(k) for k in EFFECT_COLS if row.get(k) is not None}


def _round_row(d: dict) -> dict:
    return {k: (round(v, 3) if isinstance(v, float) else v) for k, v in d.items()}


def _rows(part: dict, cds: str) -> list[dict]:
    df = part.get((cds,))
    return df.to_dicts() if df is not None else []


def run_export() -> None:
    from schoolfactors.analysis import cohorts
    from schoolfactors.analysis.panel import (
        COUNTY_TYPES,
        DISTRICT_TYPES,
        SCHOOL_TYPES,
        estimate_sigma,
        school_rows,
        state_means,
    )

    SITE_DATA.mkdir(parents=True, exist_ok=True)
    (SITE_DATA / "schools").mkdir(exist_ok=True)
    (SITE_DATA / "districts").mkdir(exist_ok=True)
    (SITE_DATA / "counties").mkdir(exist_ok=True)

    schools = pl.read_parquet(PARQUET_DIR / "analysis" / "school_effects.parquet")
    districts = pl.read_parquet(PARQUET_DIR / "analysis" / "district_effects.parquet")
    counties = pl.read_parquet(PARQUET_DIR / "analysis" / "county_effects.parquet")
    coefs = pl.read_parquet(PARQUET_DIR / "analysis" / "adjustment_coefficients.parquet")
    gammas = {
        t: g
        for t, g in zip(coefs["term"].to_list(), coefs["gamma_level"].to_list())
        if g is not None
    }
    names = _names()

    sigma = estimate_sigma(school_rows(SCHOOL_TYPES))
    state = state_means()

    from schoolfactors.analysis.neighbors import build_neighbors

    print("  computing nearby/lookalike neighbors …")
    neighbors = build_neighbors(schools)
    school_name_lookup = {
        r["cds"]: (r["school_name"], r["district_name"])
        for r in names.filter(pl.col("type_id").is_in([7, 9, 10])).to_dicts()
    }

    def enrich_neighbor(e: dict) -> dict | None:
        nm = school_name_lookup.get(e["cds"])
        if nm is None or nm[0] is None:
            return None
        return {**e, "name": nm[0], "district": nm[1]}

    written = {"counties": 0, "schools": 0, "districts": 0}
    index: list[dict] = []
    district_pages: set[str] = set()
    county_pages: set[str] = set()

    # Counties, then districts, then schools, so child pages know which parent
    # links resolve.
    for kind, types, effects in (
        ("counties", COUNTY_TYPES, counties),
        ("districts", DISTRICT_TYPES, districts),
        ("schools", SCHOOL_TYPES, schools),
    ):
        types_sql = str(types) if len(types) > 1 else f"({types[0]})"
        scores = cohorts.cohort_scores(types_sql, sigma, state)
        blend = cohorts.cohort_blend(types_sql)
        steps = cohorts.cohort_steps(blend, gammas)
        slopes = cohorts.cohort_slopes(scores)
        subgroups = cohorts.subgroup_results(types_sql)

        eff_by_cds = {r["cds"]: r for r in effects.to_dicts()}
        scores_by = scores.partition_by("cds", as_dict=True)
        blend_by = blend.partition_by("cds", as_dict=True)
        steps_by = steps.partition_by("cds", as_dict=True)
        slopes_by = slopes.partition_by("cds", as_dict=True) if len(slopes) else {}
        subgroups_by = subgroups.partition_by("cds", as_dict=True)

        if kind == "schools":
            name_filter = pl.col("type_id").is_in(list(types))
        elif kind == "districts":
            name_filter = pl.col("cds").str.slice(7, 7).eq("0000000") & pl.col("type_id").eq(6)
        else:
            name_filter = pl.col("cds").str.slice(2, 12).eq("000000000000") & pl.col(
                "type_id"
            ).eq(5)
        name_rows = names.filter(name_filter)

        for nrow in name_rows.to_dicts():
            cds = nrow["cds"]
            sc = scores_by.get((cds,))
            if sc is None or len(sc) == 0:
                continue  # entity never has usable score rows
            if kind == "counties":
                display_name = f"{nrow['county_name']} County"
            elif kind == "districts":
                display_name = nrow["district_name"]
            else:
                display_name = nrow["school_name"]
            payload = {
                "cds": cds,
                "kind": kind[:-1] if kind != "counties" else "county",
                "name": display_name,
                "district": nrow["district_name"],
                "district_cds": cds[:7] + "0000000",
                "county": nrow["county_name"],
                "county_cds": cds[:2] + "000000000000",
                "effects": _effect_payload(_round_row(eff_by_cds.get(cds, {}))),
                "cohort_scores": [
                    {
                        "grad_year": r["grad_year"],
                        "grade": r["grade"],
                        "year": r["test_year"],
                        "subject": "ela" if r["test_id"] == 1 else "math",
                        "z": r["z"],
                        "n": r["n"],
                        "mean": r["mean_scale_score"],
                        "state_mean": r["state_mean"],
                        "pct_met": r["pct_met_and_above"],
                        "pct_exc": r["pct_exceeded"],
                    }
                    for r in sc.sort(["grad_year", "grade", "test_id"]).to_dicts()
                ],
                "subgroup_results": [
                    {
                        "year": r["test_year"],
                        "subject": "ela" if r["test_id"] == 1 else "math",
                        "group": r["student_group_id"],
                        "pct_met": r["pct_met_and_above"],
                        "pct_exc": r["pct_exceeded"],
                        "n": r["n"],
                    }
                    for r in _rows(subgroups_by, cds)
                ],
                "cohort_slopes": [
                    {k: r[k] for k in ("grad_year", "slope", "slope_se", "n_points")}
                    for r in _rows(slopes_by, cds)
                ],
                "blend": [
                    {
                        "year": r["test_year"],
                        "grade": r["grade"],
                        "n": r["n_all"],
                        **{
                            f"share_{nm}": r.get(f"share_{nm}")
                            for _, (nm, _) in cohorts.BLEND_GROUPS.items()
                        },
                    }
                    for r in sorted(
                        _rows(blend_by, cds), key=lambda r: (r["test_year"], r["grade"])
                    )
                ],
                "blend_steps": [
                    {
                        "grad_year": r["grad_year"],
                        "from_grade": r["grade"],
                        "year": r["test_year"],
                        "n_change_frac": r["n_change_frac"],
                        "expected_dz_from_blend": r["expected_dz_from_blend"],
                        "flag": r["blend_shift_flag"],
                        "shifts": {
                            nm: r.get(f"d_{nm}")
                            for _, (nm, _) in cohorts.BLEND_GROUPS.items()
                            if r.get(f"flag_{nm}")
                        },
                    }
                    for r in _rows(steps_by, cds)
                ],
            }
            if kind == "schools":
                nb = neighbors.get(cds, {})
                payload["neighbors"] = {
                    "nearby": [
                        x for x in (enrich_neighbor(e) for e in nb.get("nearby", [])) if x
                    ],
                    "lookalike": [
                        x for x in (enrich_neighbor(e) for e in nb.get("lookalike", [])) if x
                    ],
                }
            if kind == "counties":
                county_pages.add(cds)
            elif kind == "districts":
                district_pages.add(cds)
                payload["county_has_page"] = payload["county_cds"] in county_pages
            else:
                payload["district_has_page"] = payload["district_cds"] in district_pages
                payload["county_has_page"] = payload["county_cds"] in county_pages
            (SITE_DATA / kind / f"{cds}.json").write_text(json.dumps(payload))
            written[kind] += 1
            eff = payload["effects"]
            index.append(
                {
                    "cds": cds,
                    "kind": payload["kind"],
                    "name": payload["name"],
                    "district": nrow["district_name"],
                    "district_cds": payload["district_cds"],
                    "county": nrow["county_name"],
                    "county_cds": payload["county_cds"],
                    "level_eb": eff.get("level_eb"),
                    "level_adj_eb": eff.get("level_adj_eb"),
                    "growth_adj_eb": eff.get("growth_adj_eb"),
                    "total_scores": eff.get("total_scores"),
                }
            )

    # Bake child lists into parent payloads (pages must not fetch the whole index —
    # prerendering inlines fetched responses into the HTML).
    def child_entry(e: dict) -> dict:
        return {
            "cds": e["cds"],
            "name": e["name"],
            "level_eb": e["level_eb"],
            "level_adj_eb": e["level_adj_eb"],
            "growth_adj_eb": e["growth_adj_eb"],
            "total_scores": e["total_scores"],
        }

    by_district: dict[str, list[dict]] = {}
    by_county: dict[str, list[dict]] = {}
    for e in index:
        if e["kind"] == "school":
            by_district.setdefault(e["district_cds"], []).append(child_entry(e))
        elif e["kind"] == "district":
            by_county.setdefault(e["county_cds"], []).append(child_entry(e))
    for dcds in district_pages:
        path = SITE_DATA / "districts" / f"{dcds}.json"
        d = json.loads(path.read_text())
        d["schools"] = sorted(by_district.get(dcds, []), key=lambda s: s["name"] or "")
        path.write_text(json.dumps(d))
    for ccds in county_pages:
        path = SITE_DATA / "counties" / f"{ccds}.json"
        d = json.loads(path.read_text())
        d["districts"] = sorted(by_county.get(ccds, []), key=lambda s: s["name"] or "")
        path.write_text(json.dumps(d))

    # Small counties listing for the home page drill-down.
    county_list = sorted(
        (
            {**child_entry(e), "county": e["county"]}
            for e in index
            if e["kind"] == "county"
        ),
        key=lambda c: c["county"] or "",
    )
    (SITE_DATA / "counties.json").write_text(json.dumps(county_list))

    (SITE_DATA / "index.json").write_text(json.dumps(index))
    print(f"  wrote {written['schools']:,} school pages, {written['districts']:,} district pages")
    print(f"  index.json: {len(index):,} entries")

    summary = {
        "n_schools_modeled": len(schools),
        "n_districts_modeled": len(districts),
        "n_counties_modeled": len(counties),
        "years": [2015, 2016, 2017, 2018, 2019, 2022, 2023, 2024, 2025],
        "corr_raw_level_econ": -0.76,
        "corr_adjusted_level_econ": -0.001,
        "falsification_growth_vs_level": 0.007,
    }
    (SITE_DATA / "summary.json").write_text(json.dumps(summary, indent=1))
    print("  summary.json written")
