"""Statewide district enrollment import/export accounting (rolling ACS windows).

Generalizes the LAUSD reconciliation (analysis/lausd_export.py, documented in
analysis/residual_reconciliation.md) to every California school district, per ACS
5-year vintage 2009-2024. Full model documentation: analysis/enrollment_flow_model.md.

Sign convention everywhere: POSITIVE = net importer.

The accounting, per vintage v:
- Residence side: B14003 resident children 5-17 by enrollment status per district
  area (unified / elementary / secondary summary levels; each partitions the state),
  pre-2010 population-control correction applied fractionally to windows ending
  2009-2013 (county factor as per-district proxy — a documented bias term).
- Seats side: per-school census-day enrollment, mean over the five springs
  overlapping the window (v-3 .. v+1), sited into district areas by school location
  (enrollment_geo), split at each area's grade cut. Schools flagged virtual, plus
  non-classroom statewide-draw charters (NC_RATIO authorizer criterion), form a
  REMOTE import-only pool allocated over each program's legal county footprint
  (authorizer county + adjacent counties) in proportion to resident population;
  unsited seats stay in their administrative county's adjustment.
- Universe calibration: m = (state CDE - state ACS public) / state CDE converts CDE
  seat counts into resident-children units (~5.5%, trendless).
- net_import(d) = seats_phys(d)*(1-m) - (resident_pub(d) - virt_alloc(d)).

All flows are NET accounting residuals — apparent, not observed transfers (there is
no public student-level origin/destination data). No pairwise flow allocation is
performed; counterparty context on the site is the neighboring areas' own residuals.
"""

from __future__ import annotations

import math

import duckdb
import polars as pl

from schoolfactors.analysis import enrollment_geo
from schoolfactors.paths import DUCKDB_PATH, PARQUET_DIR

ANALYSIS_DIR = PARQUET_DIR / "analysis"
RESIDENCE_PARQUET = ANALYSIS_DIR / "enrollment_residence.parquet"
SEATS_PARQUET = ANALYSIS_DIR / "enrollment_school_seats.parquet"
FLOWS_PARQUET = ANALYSIS_DIR / "enrollment_district_flows.parquet"
CALIB_PARQUET = ANALYSIS_DIR / "enrollment_calibration.parquet"
ACS1_PARQUET = ANALYSIS_DIR / "enrollment_acs1_overlay.parquet"
REMOTE_AUTH_PARQUET = ANALYSIS_DIR / "enrollment_remote_authorizers.parquet"
REMOTE_PROGRAMS_PARQUET = ANALYSIS_DIR / "enrollment_remote_programs.parquet"
REMOTE_XCTY_PARQUET = ANALYSIS_DIR / "enrollment_remote_county_matrix.parquet"

# Remote-sector classification (virtual & non-classroom statewide-draw seats).
# CDE's directory virtual flag (F/V) misses non-classroom-based/homeschool
# charters (it measures online-ness, not classroom-ness), so it is complemented
# by an arithmetic criterion: a GEOGRAPHIC authorizer district whose
# administered brick-and-mortar charter enrollment exceeds NC_RATIO x its own
# resident public-school children cannot be supplying that enrollment locally —
# the excess is remote by construction, not by assumption. COE/non-geographic
# authorizers are exempt (no resident base to compare; their charters stay
# physical). The classified set is written to REMOTE_AUTH_PARQUET per vintage
# and audited in the DQ report.
NC_RATIO = 1.5
NC_MIN_SEATS = 50.0

AGES = ("5 to 9 years", "10 to 14 years", "15 to 17 years")
AGE_KEYS = {"5 to 9 years": "5_9", "10 to 14 years": "10_14", "15 to 17 years": "15_17"}
CATS = {
    "Enrolled in public school": "pub",
    "Enrolled in private school": "priv",
    "Not enrolled in school": "noten",
}
# ACS MOE sentinel: the estimate is controlled (no sampling error).
CONTROLLED = -555555555.0
GRADE_COLS = [f"g{i}" for i in range(1, 13)]


def _views(con: duckdb.DuckDBPyConnection) -> set[str]:
    return {r[0] for r in con.execute("SHOW TABLES").fetchall()}


# ---------------------------------------------------------------------------
# Step 1: residence (B14003, all geographies/surveys/vintages, with MOEs)


def _classify_label(variable: str, label: str | None) -> tuple[str, str, str] | None:
    """(kind 'E'|'M', cat, age_key) for the 18 sex x status x age cells, else None."""
    if not label or variable[-1] not in ("E", "M"):
        return None
    parts = [p.rstrip(":") for p in label.split("!!")]
    # ['Estimate'|'Margin of Error', 'Total', sex, status, age]
    if len(parts) != 5 or parts[2] not in ("Male", "Female") or parts[4] not in AGES:
        return None
    cat = CATS.get(parts[3])
    if cat is None:
        return None
    return variable[-1], cat, AGE_KEYS[parts[4]]


def residence_table(con: duckdb.DuckDBPyConnection) -> pl.DataFrame:
    """One row per (survey, geo_type, geoid, vintage): resident children 5-17 by
    enrollment status, public split by age band, with 90% MOEs (root-sum-square;
    controlled estimates carry zero margin). Estimates stay null when absent —
    never coerced to zero."""
    rows = con.execute(
        """
        SELECT survey, geo_type, geoid, TRY_CAST(vintage AS INT) AS vintage,
               variable, label, TRY_CAST(value AS DOUBLE) AS v
        FROM census_acs_raw
        WHERE table_id = 'B14003'
          AND geo_type IN ('sd_unified', 'sd_elementary', 'sd_secondary',
                           'county', 'state')
        """
    ).pl()
    classes = pl.DataFrame(
        [
            {"survey": s, "vintage": vin, "variable": var, "kind": kca[0],
             "cat": kca[1], "age": kca[2]}
            for s, vin, var, lbl in rows.select(
                "survey", "vintage", "variable", "label"
            ).unique().iter_rows()
            if (kca := _classify_label(var, lbl)) is not None
        ]
    )
    j = rows.join(classes, on=["survey", "vintage", "variable"], how="inner")
    est = (
        j.filter((pl.col("kind") == "E") & (pl.col("v") >= 0))
        .group_by("survey", "geo_type", "geoid", "vintage", "cat", "age")
        .agg(pl.col("v").sum().alias("est"), pl.len().alias("n_vars"))
        # Both sex variables must be present for a cell to count; a partial sum
        # would masquerade as a smaller population.
        .with_columns(pl.when(pl.col("n_vars") == 2).then(pl.col("est")).alias("est"))
        .drop("n_vars")
    )
    moe = (
        j.filter(pl.col("kind") == "M")
        .with_columns(
            pl.when(pl.col("v") == CONTROLLED)
            .then(0.0)
            .when(pl.col("v") >= 0)
            .then(pl.col("v"))
            .alias("mv")
        )
        .group_by("survey", "geo_type", "geoid", "vintage", "cat", "age")
        .agg((pl.col("mv") ** 2).sum().alias("m2"))
    )
    cells = est.join(moe, on=["survey", "geo_type", "geoid", "vintage", "cat", "age"],
                     how="left")

    # Expected complete-cell counts after the sex collapse: 3 age cells per
    # status category, 1 cell per single band.
    specs = {
        "pub": ("pub", None, 3),
        "priv": ("priv", None, 3),
        "noten": ("noten", None, 3),
        "pub_5_9": ("pub", "5_9", 1),
        "pub_10_14": ("pub", "10_14", 1),
        "pub_15_17": ("pub", "15_17", 1),
    }

    def agg(name: str, cat: str, age: str | None) -> list[pl.Expr]:
        cond = pl.col("cat") == cat
        if age:
            cond = cond & (pl.col("age") == age)
        return [
            pl.col("est").filter(cond).sum().alias(name),
            pl.col("est").filter(cond).count().alias(f"n_{name}"),
            pl.col("m2").filter(cond).sum().sqrt().alias(f"moe_{name}"),
        ]

    out = cells.group_by("survey", "geo_type", "geoid", "vintage").agg(
        *[e for name, (cat, age, _) in specs.items() for e in agg(name, cat, age)],
        pl.col("est").sum().alias("total"),
        pl.col("est").count().alias("n_total"),
    )
    # A geography with missing cells (unpublished/suppressed) must read as null,
    # never as a partial sum masquerading as a smaller population.
    out = out.with_columns(
        *[
            pl.when(pl.col(f"n_{name}") == n_cells)
            .then(pl.col(name))
            .alias(name)
            for name, (_, _, n_cells) in specs.items()
        ],
        pl.when(pl.col("n_total") == 9).then(pl.col("total")).alias("total"),
    ).drop([f"n_{name}" for name in specs] + ["n_total"])
    return out.sort("survey", "geo_type", "vintage", "geoid")


# ---------------------------------------------------------------------------
# Step 2-3: pre-2010 population-control correction (all counties)


def control_factors(con: duckdb.DuckDBPyConnection) -> dict[tuple[str, int], float]:
    """{(county_fips | 'CA', survey_year 2005-2009): factor} — intercensal
    (2010-census-consistent) children 5-17 over the same-year vintage postcensal
    5-17, per county. Generalizes lausd_export._acs1_control_factors; ages 15-17
    in the intercensal 5-year bins are approximated as 3/5 of 15-19."""
    if "popest_raw" not in _views(con):
        return {}
    inter: dict[tuple[str, int], float] = {}
    for jy, cty, grp, v in con.execute(
        """
        SELECT july_year, county, agegrp, TRY_CAST(value AS DOUBLE)
        FROM popest_raw
        WHERE series = 'intercensal' AND agegrp IN ('2', '3', '4')
        """
    ).fetchall():
        if v is None:
            continue
        w = 0.6 if grp == "4" else 1.0
        for key in (cty, "CA"):
            inter[key, int(jy)] = inter.get((key, int(jy)), 0.0) + v * w
    post: dict[tuple[str, int], float] = {}
    for series, jy, cty, v in con.execute(
        """
        SELECT series, july_year, county, sum(TRY_CAST(value AS DOUBLE))
        FROM popest_raw
        WHERE series LIKE 'vintage%' AND measure IN ('age513_tot', 'age1417_tot')
        GROUP BY 1, 2, 3
        """
    ).fetchall():
        y = int(series.removeprefix("vintage"))
        if v is None or int(jy) != y:
            continue
        for key in (cty, "CA"):
            post[key, y] = post.get((key, y), 0.0) + v
    return {k: inter[k] / post[k] for k in post if k in inter and post[k]}


def _window_factor(
    factors: dict[tuple[str, int], float], fips: str, survey: str, vintage: int
) -> float:
    """Correction multiplier for one observation: full for acs1 2005-2009, the mean
    of per-year factors (1.0 for years >= 2010) for acs5 windows ending 2009-2013."""

    def f(year: int) -> float:
        if year >= 2010:
            return 1.0
        return factors.get((fips, year)) or factors.get(("CA", year)) or 1.0

    if survey == "acs1":
        return f(vintage)
    years = range(vintage - 4, vintage + 1)
    return sum(f(y) for y in years) / 5


def district_crosswalk(con: duckdb.DuckDBPyConnection) -> pl.DataFrame:
    """[geoid, dcds (7-digit district prefix), county_code, county_fips] from the
    CDE directory NCES LEAID, majority mapping per geoid (census_poverty pattern)."""
    xw = con.execute(
        """
        SELECT lpad(trim(ncesdist), 7, '0') AS geoid,
               substr(cds, 1, 7) AS dcds,
               substr(cds, 1, 2) AS county_code,
               count(*) AS n_rows
        FROM directory_raw
        WHERE ncesdist IS NOT NULL AND trim(ncesdist) <> ''
        GROUP BY 1, 2, 3
        """
    ).pl()
    xw = xw.sort("n_rows", descending=True).unique(
        subset=["geoid"], keep="first", maintain_order=True
    )
    return xw.with_columns(
        (pl.col("county_code").cast(pl.Int32) * 2 - 1)
        .cast(pl.Utf8)
        .str.zfill(3)
        .alias("county_fips")
    ).drop("n_rows")


def apply_control_correction(
    residence: pl.DataFrame,
    factors: dict[tuple[str, int], float],
    xwalk: pl.DataFrame,
) -> pl.DataFrame:
    """Multiply estimates and MOEs by the (fractional) control factor; record it."""
    fips_map = dict(xwalk.select("geoid", "county_fips").iter_rows())

    def fips_for(geo_type: str, geoid: str) -> str:
        if geo_type == "county":
            return geoid[-3:]
        if geo_type == "state":
            return "CA"
        return fips_map.get(geoid, "CA")

    fac = pl.Series(
        "factor",
        [
            _window_factor(factors, fips_for(gt, g), s, v)
            for s, gt, g, v in residence.select(
                "survey", "geo_type", "geoid", "vintage"
            ).iter_rows()
        ],
    )
    scaled = [
        c
        for c in residence.columns
        if c.startswith(("pub", "priv", "noten", "moe_")) or c == "total"
    ]
    return residence.with_columns(fac).with_columns(
        [(pl.col(c) * pl.col("factor")).alias(c) for c in scaled]
    )


# ---------------------------------------------------------------------------
# Step 4: per-school census-day seats with grade detail, class, and siting


def seats_table(con: duckdb.DuckDBPyConnection) -> pl.DataFrame:
    """One row per (cds, spring): census-day enrollment with per-grade counts,
    school class, and sited area geoids. Historical rows are race x gender grain
    and school-level only; current-format rows are taken at school grain. NPS and
    district-office pseudo-codes missing from the directory are sited through the
    district-prefix crosswalk so their (small) seat counts stay in the right area."""
    kn = "coalesce(TRY_CAST(gr_kn AS DOUBLE), 0)"
    hist_cols = ", ".join(
        f"sum(coalesce(TRY_CAST(gr_{i} AS DOUBLE), 0)) AS g{i}" for i in range(1, 13)
    )
    new_cols = ", ".join(
        f"sum(coalesce(TRY_CAST(gr_{i:02d} AS DOUBLE), 0)) AS g{i}" for i in range(1, 13)
    )
    seats = con.execute(
        f"""
        SELECT cds, TRY_CAST(substr(academic_year, 1, 4) AS INT) + 1 AS spring,
               sum(TRY_CAST(enr_total AS DOUBLE))
                 - sum(coalesce(TRY_CAST(adult AS DOUBLE), 0)) AS total,
               sum({kn}) AS kn, {hist_cols},
               sum(coalesce(TRY_CAST(ungr_elm AS DOUBLE), 0)) AS ungr_elm,
               sum(coalesce(TRY_CAST(ungr_sec AS DOUBLE), 0)) AS ungr_sec
        FROM enrollment_hist_raw
        WHERE (enr_type = 'C' OR enr_type IS NULL) AND length(academic_year) = 7
          AND TRY_CAST(substr(academic_year, 1, 4) AS INT) + 1 >= 2005
        GROUP BY 1, 2
        UNION ALL
        SELECT cds, TRY_CAST(substr(academicyear, 1, 4) AS INT) + 1,
               sum(TRY_CAST(total_enr AS DOUBLE)),
               sum(coalesce(TRY_CAST(gr_tk AS DOUBLE), 0) + {kn}), {new_cols},
               0, 0
        FROM enrollment_raw
        WHERE aggregatelevel = 'S' AND reportingcategory = 'TA'
        GROUP BY 1, 2
        """
    ).pl()

    # Brick-and-mortar charters split by funding model (lausd_export convention):
    # locally funded = "affiliated" (operates like a district school), anything
    # else = independent/directly funded.
    classes = con.execute(
        """
        SELECT cds,
               CASE
                 WHEN max(CASE WHEN trim(charter) = 'Y'
                               AND trim(virtual) IN ('F', 'V') THEN 1 ELSE 0 END) = 1
                   THEN 'charter_virtual'
                 WHEN max(CASE WHEN trim(charter) = 'Y'
                               AND fundingtype ILIKE '%locally%' THEN 1 ELSE 0 END) = 1
                   THEN 'charter_aff'
                 WHEN max(CASE WHEN trim(charter) = 'Y' THEN 1 ELSE 0 END) = 1
                   THEN 'charter_bm'
                 ELSE 'district_run'
               END AS class
        FROM directory_raw
        WHERE substr(cds, 8, 7) <> '0000000'
        GROUP BY cds
        """
    ).pl()
    siting = pl.read_parquet(enrollment_geo.SITING_PARQUET).select(
        "cds", "unified_geoid", "elem_geoid", "sec_geoid", "sited"
    )
    out = (
        seats.join(classes, on="cds", how="left")
        .join(siting, on="cds", how="left")
        .with_columns(
            pl.col("class").fill_null("district_run"),
            pl.col("cds").str.slice(0, 2).alias("county_code"),
        )
    )

    # Fallback siting for enrollment rows with no directory school record (NPS
    # pseudo-codes, district offices): the district prefix's own area.
    xw = district_crosswalk(con)
    u_ids = set(enrollment_geo.load_district_geometries("unified")[0])
    e_ids = set(enrollment_geo.load_district_geometries("elementary")[0])
    s_ids = set(enrollment_geo.load_district_geometries("secondary")[0])
    prefix_geoid = dict(xw.select("dcds", "geoid").iter_rows())

    def prefix_site(cds: str) -> tuple[str | None, str | None, str | None, str | None]:
        g = prefix_geoid.get(cds[:7])
        if g in u_ids:
            return g, None, None, "crosswalk"
        if g in e_ids:
            return None, g, None, "crosswalk"
        if g in s_ids:
            return None, None, g, "crosswalk"
        return None, None, None, None

    unsited = out.filter(pl.col("sited").is_null())["cds"].unique()
    fixes = {c: prefix_site(c) for c in unsited}
    fix_df = pl.DataFrame(
        {
            "cds": list(fixes),
            "fx_u": [f[0] for f in fixes.values()],
            "fx_e": [f[1] for f in fixes.values()],
            "fx_s": [f[2] for f in fixes.values()],
            "fx_sited": [f[3] for f in fixes.values()],
        }
    )
    out = (
        out.join(fix_df, on="cds", how="left")
        .with_columns(
            pl.coalesce("unified_geoid", "fx_u").alias("unified_geoid"),
            pl.coalesce("elem_geoid", "fx_e").alias("elem_geoid"),
            pl.coalesce("sec_geoid", "fx_s").alias("sec_geoid"),
            pl.coalesce("sited", "fx_sited").alias("sited"),
        )
        .drop("fx_u", "fx_e", "fx_s", "fx_sited")
    )

    # District-run and affiliated (locally funded) charter schools belong to
    # their OWN district's area: their attendance is administrative, and
    # point-in-polygon mis-sites boundary-adjacent campuses (e.g. La Canada High
    # stands on the Pasadena side of the TIGER line but serves La Canada).
    # Location stays the evidence where there is no attendance area: independent
    # charters keep host-area siting, and schools of non-geographic districts
    # (COE, SBE) keep host-area siting too.
    cuts = pl.read_parquet(enrollment_geo.CUTS_PARQUET)
    elem_sec = dict(
        cuts.filter(pl.col("level") == "elementary").select("geoid", "sec_geoid").iter_rows()
    )
    # Virtual charters are included so "virtual programs based here" reports by
    # AUTHORIZER (their office coordinates are meaningless); they remain
    # excluded from the physical accounting either way.
    admin_rows = []
    admin_targets = (
        out.filter(pl.col("class").is_in(["district_run", "charter_aff", "charter_virtual"]))
        .select("cds", "elem_geoid")
        .unique(subset=["cds"])
    )
    for cds, cur_e in admin_targets.iter_rows():
        g = prefix_geoid.get(cds[:7])
        if g in u_ids:
            admin_rows.append({"cds": cds, "a_u": g, "a_e": None, "a_s": None})
        elif g in e_ids:
            admin_rows.append({"cds": cds, "a_u": None, "a_e": g, "a_s": elem_sec.get(g)})
        elif g in s_ids:
            admin_rows.append({"cds": cds, "a_u": None, "a_e": cur_e, "a_s": g})
    if admin_rows:
        adf = pl.DataFrame(admin_rows).with_columns(pl.lit(True).alias("a_on"))
        out = (
            out.join(adf, on="cds", how="left")
            .with_columns(
                pl.when(pl.col("a_on")).then(pl.col("a_u"))
                .otherwise(pl.col("unified_geoid")).alias("unified_geoid"),
                pl.when(pl.col("a_on")).then(pl.col("a_e"))
                .otherwise(pl.col("elem_geoid")).alias("elem_geoid"),
                pl.when(pl.col("a_on")).then(pl.col("a_s"))
                .otherwise(pl.col("sec_geoid")).alias("sec_geoid"),
                pl.when(pl.col("a_on")).then(pl.lit("admin"))
                .otherwise(pl.col("sited")).alias("sited"),
            )
            .drop("a_u", "a_e", "a_s", "a_on")
        )
    return out


def _split_seats(seats: pl.DataFrame, cuts: pl.DataFrame) -> pl.DataFrame:
    """Add lower/upper grade-band columns per school row, at the sited area's cut.

    Lower = TK/K through grade cut-1 (+ ungraded elementary), upper = cut through 12
    (+ ungraded secondary); any residual vs the reported total (rare) is prorated.
    Unified-sited schools are never split (their whole total goes to the unified
    node), so their cut defaults harmlessly."""
    elem_cut = dict(
        cuts.filter(pl.col("level") == "elementary").select("geoid", "cut").iter_rows()
    )
    sec_cut = dict(
        cuts.filter(pl.col("level") == "secondary").select("geoid", "cut").iter_rows()
    )
    cut = pl.Series(
        "cut",
        [
            elem_cut.get(e) or sec_cut.get(s) or enrollment_geo.DEFAULT_CUT
            for e, s in seats.select("elem_geoid", "sec_geoid").iter_rows()
        ],
    )
    df = seats.with_columns(cut)
    lower = pl.col("kn") + pl.col("ungr_elm")
    upper = pl.col("ungr_sec")
    for i in range(1, 13):
        lower = lower + pl.when(pl.col("cut") > i).then(pl.col(f"g{i}")).otherwise(0.0)
        upper = upper + pl.when(pl.col("cut") <= i).then(pl.col(f"g{i}")).otherwise(0.0)
    df = df.with_columns(lower.alias("lower"), upper.alias("upper"))
    resid = (pl.col("total") - pl.col("lower") - pl.col("upper")).clip(lower_bound=0)
    graded = pl.col("lower") + pl.col("upper")
    return df.with_columns(
        (
            pl.col("lower")
            + pl.when(graded > 0).then(resid * pl.col("lower") / graded).otherwise(resid)
        ).alias("lower"),
        (
            pl.col("upper") + pl.when(graded > 0).then(resid * pl.col("upper") / graded).otherwise(0.0)
        ).alias("upper"),
    )


# ---------------------------------------------------------------------------
# Steps 5-6: calibration and per-area accounting


def _cde_state_series(con: duckdb.DuckDBPyConnection) -> dict[int, int]:
    from schoolfactors.analysis.lausd_export import _cde_census_day

    return _cde_census_day(con, "TRUE", "aggregatelevel = 'T'", since_spring=2005)


def _age_weight(cut: int) -> float:
    """Share of the 10-14 age band belonging to the LOWER grades for a given cut:
    lower covers ages 5 .. cut+4, so ages 10..cut+4 of the five-year band."""
    return max(0.0, min(1.0, (cut - 5) / 5))


def _balanced_attribution(
    rows: dict[str, float],
    footprints: dict[str, set[str]],
    seed_base: dict[str, float],
    ceiling: dict[str, float],
    iters: int = 200,
) -> tuple[dict[str, float], dict[tuple[str, str], float]]:
    """Capacity-constrained IPF over the legal footprint graph.

    Distributes each authorizer county's remote seats (``rows``, already in
    resident units) over its footprint counties. Both margins are MEASURED:
    row totals are administrative enrollment; column capacity is each county's
    resident-vs-local-seat gap (``ceiling``, clipped at 0). Seeded by
    population share (``seed_base``), then alternately scales columns DOWN
    where attribution exceeds the measured gap and renormalizes rows to their
    exact totals — converging toward the max-entropy solution consistent with
    margins and support. Counties absent from ``ceiling`` are unconstrained.
    A row whose entire footprint is capped to zero falls back to its seed
    (documented ceiling violation) so the pool always sums exactly.

    Returns (per-county attribution, (authorizer, county) matrix)."""
    x: dict[tuple[str, str], float] = {}
    seeds: dict[str, list[tuple[str, float]]] = {}
    for a, r in rows.items():
        if not r:
            continue
        fp = [c for c in footprints.get(a, {a}) if seed_base.get(c)]
        tot = sum(seed_base[c] for c in fp)
        if not tot:
            fp = [c for c in seed_base if seed_base[c]]
            tot = sum(seed_base.values())
            if not tot:
                continue
        seeds[a] = [(c, seed_base[c] / tot) for c in fp]
        for c, w in seeds[a]:
            x[a, c] = r * w
    for _ in range(iters):
        col: dict[str, float] = {}
        for (a, c), v in x.items():
            col[c] = col.get(c, 0.0) + v
        capped = False
        for c, t in col.items():
            cap = ceiling.get(c)
            if cap is not None and t > cap:
                f = cap / t if t else 0.0
                for k in [k for k in x if k[1] == c]:
                    x[k] *= f
                capped = True
        rowsum: dict[str, float] = {}
        for (a, c), v in x.items():
            rowsum[a] = rowsum.get(a, 0.0) + v
        drift = False
        for a, r in rows.items():
            rs = rowsum.get(a, 0.0)
            if not r or a not in seeds:
                continue
            if rs <= r * 1e-9:
                for c, w in seeds[a]:  # footprint fully capped — reseed
                    x[a, c] = r * w
                drift = True
            elif abs(rs - r) > r * 1e-9:
                f = r / rs
                for c, _w in seeds[a]:
                    if (a, c) in x:
                        x[a, c] *= f
                drift = True
        if not capped and not drift:
            break
    out: dict[str, float] = {}
    for (a, c), v in x.items():
        out[c] = out.get(c, 0.0) + v
    return out, x


def build_all(con: duckdb.DuckDBPyConnection | None = None) -> None:
    own = con is None
    if own:
        con = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    try:
        views = _views(con)
        needed = {"census_acs_raw", "enrollment_hist_raw", "enrollment_raw",
                  "directory_raw"}
        if not needed <= views or not enrollment_geo.tiger_available():
            print("  enrollment flows: census/CDE/tiger inputs missing — skipped")
            return

        print("  building statewide enrollment flows …")
        geo = {lvl: enrollment_geo.load_district_geometries(lvl)
               for lvl in enrollment_geo.LEVELS}
        cuts = enrollment_geo.area_grade_cuts(geo)
        enrollment_geo.site_schools(con, geo)
        enrollment_geo.district_adjacency(geo)

        residence = residence_table(con)
        xwalk = district_crosswalk(con)
        factors = control_factors(con)
        residence = apply_control_correction(residence, factors, xwalk)
        ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
        residence.write_parquet(RESIDENCE_PARQUET)

        seats = _split_seats(seats_table(con), cuts)
        seats.write_parquet(SEATS_PARQUET)

        state_cde = _cde_state_series(con)
        acs5 = residence.filter(pl.col("survey") == "acs5")
        vintages = sorted(
            acs5.filter(pl.col("geo_type") == "county")["vintage"].unique().to_list()
        )

        # Administrative county per district node (for the per-county pool): the
        # node's CDE district prefix; nodes without a crosswalk (NCES pseudo
        # secondary districts) take the majority county of their sited schools.
        geoid_dcds = dict(xwalk.select("geoid", "dcds").iter_rows())
        maj_county: dict[tuple[str, str], tuple[str, float]] = {}
        for col, lk in (("unified_geoid", "u"), ("elem_geoid", "e"), ("sec_geoid", "h")):
            d = (
                seats.filter(pl.col(col).is_not_null())
                .group_by(col, "county_code")
                .agg(pl.col("total").sum().alias("s"))
            )
            for g, cc, s in d.iter_rows():
                if s and ((lk, g) not in maj_county or s > maj_county[lk, g][1]):
                    maj_county[lk, g] = (cc, s)
        node_county: dict[tuple[str, str], str | None] = {}
        for lk, lvl in (("u", "unified"), ("e", "elementary"), ("h", "secondary")):
            for g in geo[lvl][0]:
                dcds = geoid_dcds.get(g)
                node_county[lk, g] = dcds[:2] if dcds else (
                    maj_county[lk, g][0] if (lk, g) in maj_county else None
                )

        # District prefix -> its own area node (for the authorizer-base test
        # and for reporting remote programs on their authorizer's page).
        dcds_nodes: dict[str, tuple[str, str]] = {}
        for lk, lvl in (("u", "unified"), ("e", "elementary"), ("h", "secondary")):
            for g in geo[lvl][0]:
                d = geoid_dcds.get(g)
                if d and d not in dcds_nodes:
                    dcds_nodes[d] = (lk, g)

        # County adjacency, for the legal enrollment footprint of remote
        # programs: two counties are adjacent when any of their district areas
        # share a border in either display band. Derived from TIGER polygons,
        # so water-only county adjacencies are absent (documented limitation).
        geoid_county: dict[str, str | None] = {}
        for (lk, g), cc in node_county.items():
            geoid_county.setdefault(g, cc)
        county_adj: dict[str, set[str]] = {}
        for a, b in (
            pl.read_parquet(enrollment_geo.ADJACENCY_PARQUET)
            .select("geoid", "neighbor")
            .unique()
            .iter_rows()
        ):
            ca, cb = geoid_county.get(a), geoid_county.get(b)
            if ca and cb:
                county_adj.setdefault(ca, {ca}).add(cb)
                county_adj.setdefault(cb, {cb}).add(ca)

        remote_auth_rows: list[dict] = []
        remote_prog_rows: list[dict] = []
        remote_xcty_rows: list[dict] = []

        sec_cut = dict(
            cuts.filter(pl.col("level") == "secondary").select("geoid", "cut").iter_rows()
        )
        elem_cut = dict(
            cuts.filter(pl.col("level") == "elementary").select("geoid", "cut").iter_rows()
        )

        flow_rows: list[dict] = []
        calib_rows: list[dict] = []
        for v in vintages:
            springs = [s for s in range(v - 3, v + 2) if s in state_cde]
            n_springs = len(springs)
            if n_springs < 3:
                continue
            cde5 = sum(state_cde[s] for s in springs) / n_springs

            res_v = acs5.filter(pl.col("vintage") == v)
            state_pub = res_v.filter(pl.col("geo_type") == "county")["pub"].sum()
            if not state_pub or not cde5:
                continue
            m = (cde5 - state_pub) / cde5

            sv = (
                seats.filter(pl.col("spring").is_in(springs))
                .group_by(
                    "cds", "class", "unified_geoid", "elem_geoid", "sec_geoid", "sited",
                    "county_code",
                )
                .agg(
                    (pl.col("total").sum() / n_springs).alias("total"),
                    (pl.col("lower").sum() / n_springs).alias("lower"),
                    (pl.col("upper").sum() / n_springs).alias("upper"),
                )
            )
            # (Seat aggregation happens after the remote-sector split below —
            # the non-classroom criterion needs this vintage's resident bases.)
            res_map: dict[tuple[str, str], dict] = {
                (gt, g): row
                for gt, g, row in zip(
                    res_v["geo_type"], res_v["geoid"], res_v.to_dicts()
                )
            }

            def resident_base(
                level: str, geoid: str, res_map: dict = res_map
            ) -> tuple[float | None, float | None, dict | None]:
                """(resident_pub for this node's grade span, its MOE, full row)."""
                gt = {"u": "sd_unified", "e": "sd_elementary", "h": "sd_secondary"}[level]
                row = res_map.get((gt, geoid))
                if row is None or row["pub"] is None:
                    return None, None, row
                if level == "u":
                    return row["pub"], row["moe_pub"], row
                cut = (elem_cut if level == "e" else sec_cut).get(
                    geoid, enrollment_geo.DEFAULT_CUT
                )
                w = _age_weight(cut)
                if any(row[c] is None for c in ("pub_5_9", "pub_10_14", "pub_15_17")):
                    return None, None, row
                if level == "e":
                    base = row["pub_5_9"] + w * row["pub_10_14"]
                    moe = math.sqrt(
                        (row["moe_pub_5_9"] or 0) ** 2
                        + (w * (row["moe_pub_10_14"] or 0)) ** 2
                    )
                else:
                    base = (1 - w) * row["pub_10_14"] + row["pub_15_17"]
                    moe = math.sqrt(
                        ((1 - w) * (row["moe_pub_10_14"] or 0)) ** 2
                        + (row["moe_pub_15_17"] or 0) ** 2
                    )
                return base, moe, row

            # District node set = current geometry; ACS rows keyed by as-of-vintage
            # geoid, so reorganized districts show null residents in old vintages.
            nodes: list[tuple[str, str]] = (
                [("u", g) for g in geo["unified"][0]]
                + [("e", g) for g in geo["elementary"][0]]
                + [("h", g) for g in geo["secondary"][0]]
            )
            bases = {}
            for level, g in nodes:
                bases[level, g] = resident_base(level, g)

            # --- remote sector: flagged-virtual plus non-classroom ----------
            # statewide-draw charters (NC_RATIO criterion, see module top):
            # a geographic authorizer whose administered charter_bm seats
            # exceed NC_RATIO x its own resident base cannot be serving local
            # children — the excess is arithmetic. COE and other
            # non-geographic authorizers are exempt (no base to compare).
            cbm_auth = dict(
                sv.filter(pl.col("class") == "charter_bm")
                .with_columns(pl.col("cds").str.slice(0, 7).alias("dcds"))
                .group_by("dcds")
                .agg(pl.col("total").sum().alias("s"))
                .iter_rows()
            )
            nc_auth: list[str] = []
            for dcds, s in cbm_auth.items():
                node = dcds_nodes.get(dcds)
                if s < NC_MIN_SEATS or node is None:
                    continue
                b = bases.get(node, (None,))[0]
                if b and s > NC_RATIO * b:
                    nc_auth.append(dcds)
                    remote_auth_rows.append(
                        {"vintage": v, "dcds": dcds, "cbm_seats": s,
                         "res_base": b, "ratio": s / b}
                    )
            sv = sv.with_columns(
                (
                    (pl.col("class") == "charter_virtual")
                    | (
                        (pl.col("class") == "charter_bm")
                        & pl.col("cds").str.slice(0, 7).is_in(nc_auth)
                    )
                ).alias("remote")
            )
            remote_sv = sv.filter(pl.col("remote"))
            phys = sv.filter(~pl.col("remote"))
            pool_virtual = remote_sv.filter(pl.col("class") == "charter_virtual")["total"].sum()
            pool_nc = remote_sv.filter(pl.col("class") == "charter_bm")["total"].sum()
            pool_unsited = (
                phys.filter(pl.col("sited").is_null())["total"].sum()
                + phys.filter(
                    pl.col("sited").is_not_null()
                    & pl.col("unified_geoid").is_null()
                    & pl.col("sec_geoid").is_null()
                )["upper"].sum()
                + phys.filter(
                    pl.col("sited").is_not_null()
                    & pl.col("unified_geoid").is_null()
                    & pl.col("elem_geoid").is_null()
                )["lower"].sum()
            )
            for cds_, cls_, cc_, tot_ in remote_sv.select(
                "cds", "class", "county_code", "total"
            ).iter_rows():
                remote_prog_rows.append(
                    {"vintage": v, "cds": cds_, "county": cc_, "seats": tot_,
                     "kind": "virtual" if cls_ == "charter_virtual" else "nonclassroom"}
                )

            def seat_agg(
                geo_col: str, value: pl.Expr, phys: pl.DataFrame = phys
            ) -> dict[str, dict[str, float]]:
                d = (
                    phys.filter(pl.col(geo_col).is_not_null())
                    .group_by(geo_col, "class")
                    .agg(value.sum().alias("s"))
                )
                out: dict[str, dict[str, float]] = {}
                for g, cls, s in d.iter_rows():
                    out.setdefault(g, {})[cls] = s
                return out

            seats_u = seat_agg("unified_geoid", pl.col("total"))
            seats_e = seat_agg("elem_geoid", pl.col("lower"))
            seats_h = seat_agg("sec_geoid", pl.col("upper"))
            # Band split of unified areas' seats, for the K-8 / 9-12 residual
            # diagnostic (elementary/secondary areas are single-band already).
            seats_u_lo = seat_agg("unified_geoid", pl.col("lower"))
            seats_u_up = seat_agg("unified_geoid", pl.col("upper"))
            # Remote programs BASED in each area, grouped by AUTHORIZER (cds
            # prefix, whose county sets the legal footprint) — observed seats,
            # excluded from the local physical accounting but reported so
            # authorizers' operations are visible on their pages.
            remote_by_auth = dict(
                remote_sv.with_columns(pl.col("cds").str.slice(0, 7).alias("dcds"))
                .group_by("dcds")
                .agg(pl.col("total").sum().alias("s"))
                .iter_rows()
            )
            virt_by_level: dict[str, dict[str, dict[str, float]]] = {"u": {}, "e": {}, "h": {}}
            for dcds, s in remote_by_auth.items():
                node = dcds_nodes.get(dcds)
                if node:
                    virt_by_level[node[0]].setdefault(node[1], {})["remote"] = s
            remote_c: dict[str, float] = dict(
                remote_sv.group_by("county_code")
                .agg(pl.col("total").sum().alias("s"))
                .iter_rows()
            )
            seats_c: dict[str, dict[str, float]] = {}
            for g, cls, s in (
                phys.group_by("county_code", "class")
                .agg(pl.col("total").sum().alias("s"))
                .iter_rows()
            ):
                seats_c.setdefault(g, {})[cls] = s

            # Footprint allocation of the remote pool, AGE-MATCHED: each remote
            # program's K-8 seats spread over K-8-age residents and its 9-12
            # seats over high-school-age residents of its authorizer's county
            # PLUS adjacent counties — the Ed Code contiguous-county enrollment
            # limit for nonclassroom-based programs. Law-constrained geography,
            # allocated (not measured) within it; the small ungraded remainder
            # (total - lower - upper) is spread age-neutrally so the allocation
            # sums exactly to the pool and state closure is preserved.
            county_rows = res_v.filter(pl.col("geo_type") == "county").to_dicts()
            w_c = _age_weight(enrollment_geo.DEFAULT_CUT)
            cty_pub: dict[str, float] = {}
            cty_lo: dict[str, float] = {}
            cty_up: dict[str, float] = {}
            for r in county_rows:
                code = f"{(int(r['geoid'][-3:]) + 1) // 2:02d}"
                if r["pub"]:
                    cty_pub[code] = r["pub"]
                    if all(
                        r[k] is not None for k in ("pub_5_9", "pub_10_14", "pub_15_17")
                    ):
                        cty_lo[code] = r["pub_5_9"] + w_c * r["pub_10_14"]
                        cty_up[code] = (1 - w_c) * r["pub_10_14"] + r["pub_15_17"]

            # Band calibration (diagnostic, not used in the accounting): the
            # upper-band universe gap is larger than the total m because
            # 18-year-old seniors sit in CDE grade counts but outside the ACS
            # 5-17 resident base.
            state_seats_lo = sv["lower"].sum()
            state_seats_up = sv["upper"].sum()
            m_lo = 1 - sum(cty_lo.values()) / state_seats_lo if state_seats_lo else None
            m_up = 1 - sum(cty_up.values()) / state_seats_up if state_seats_up else None

            def _spread(
                seats: float, fp: set[str], base_map: dict[str, float],
                out: dict[str, float], m: float = m,
            ) -> None:
                if not seats:
                    return
                fpb = sum(base_map.get(c, 0.0) for c in fp)
                if not fpb:
                    fp, fpb = set(base_map), sum(base_map.values())
                if not fpb:
                    return
                for c in fp:
                    b = base_map.get(c, 0.0)
                    if b:
                        out[c] = out.get(c, 0.0) + seats * (1 - m) * b / fpb

            # Balanced attribution (capacity-constrained IPF): both margins are
            # measured — each authorizer county's remote seats (administrative
            # records) and each county's resident-vs-local-seat gap (the
            # ceiling: a county cannot supply more remote students than its
            # total measured gap). Within those margins and the legal
            # footprint, the split is the population-seeded max-entropy
            # balance, per grade band. What a county's ceiling refuses stays
            # in its measured "counted in other counties" residual.
            seats_c_lo: dict[str, float] = {}
            seats_c_up: dict[str, float] = {}
            for gcc, slo_, sup_ in (
                phys.group_by("county_code")
                .agg(pl.col("lower").sum().alias("lo"), pl.col("upper").sum().alias("up"))
                .iter_rows()
            ):
                seats_c_lo[gcc] = slo_
                seats_c_up[gcc] = sup_
            ceil_lo = {
                c: max(b - seats_c_lo.get(c, 0.0) * (1 - (m_lo if m_lo is not None else m)), 0.0)
                for c, b in cty_lo.items()
            }
            ceil_up = {
                c: max(b - seats_c_up.get(c, 0.0) * (1 - (m_up if m_up is not None else m)), 0.0)
                for c, b in cty_up.items()
            }
            rows_lo: dict[str, float] = {}
            rows_up: dict[str, float] = {}
            rows_x: dict[str, float] = {}
            for authc, slo, sup, stot in (
                remote_sv.group_by("county_code")
                .agg(
                    pl.col("lower").sum().alias("slo"),
                    pl.col("upper").sum().alias("sup"),
                    pl.col("total").sum().alias("stot"),
                )
                .iter_rows()
            ):
                rows_lo[authc] = slo * (1 - m)
                rows_up[authc] = sup * (1 - m)
                rows_x[authc] = (stot - slo - sup) * (1 - m)
            remote_alloc_lo, x_lo = _balanced_attribution(
                rows_lo, county_adj, cty_lo, ceil_lo
            )
            remote_alloc_up, x_up = _balanced_attribution(
                rows_up, county_adj, cty_up, ceil_up
            )
            remote_alloc_x: dict[str, float] = {}
            for authc, r in rows_x.items():
                _spread(r, county_adj.get(authc, {authc}), cty_pub, remote_alloc_x, m=0.0)
            remote_alloc: dict[str, float] = {}
            for d_ in (remote_alloc_lo, remote_alloc_up, remote_alloc_x):
                for c, s in d_.items():
                    remote_alloc[c] = remote_alloc.get(c, 0.0) + s
            for (a_, c_), v_ in x_lo.items():
                remote_xcty_rows.append(
                    {"vintage": v, "auth": a_, "dest": c_, "band": "lo", "est": v_}
                )
            for (a_, c_), v_ in x_up.items():
                remote_xcty_rows.append(
                    {"vintage": v, "auth": a_, "dest": c_, "band": "up", "est": v_}
                )

            # Two-part allocation:
            #   virt_alloc: the district's share of its county's footprint
            #     allocation of the remote pool (virtual + non-classroom),
            #     spread within the county by resident population;
            #   ooc_alloc: each county's remaining administrative adjustment
            #     (signed), sized so that PHYSICAL seats and physical
            #     resident-students net out EXACTLY within every county
            #     (it also absorbs the small unsited-seat pool).
            # District nets are therefore pure within-county physical
            # redistribution; cross-county and remote administrative flows show
            # at the county level, where they are measured rather than assumed.
            seats_by_level = {"u": seats_u, "e": seats_e, "h": seats_h}

            county_base: dict[str | None, float] = {}
            county_seats: dict[str | None, float] = {}
            county_blo: dict[str | None, float] = {}
            county_bup: dict[str | None, float] = {}
            county_glo: dict[str | None, float] = {}
            county_gup: dict[str | None, float] = {}
            node_bands: dict[tuple[str, str], tuple[float | None, float | None]] = {}
            node_bseats: dict[tuple[str, str], tuple[float, float]] = {}
            node_gaps: dict[tuple[str, str], tuple[float, float]] = {}
            for level, g in nodes:
                base, _moe, row = bases[level, g]
                if base is None:
                    continue
                cc = node_county.get((level, g))
                sm = seats_by_level[level].get(g, {})
                s_all = (sm.get("district_run", 0.0) + sm.get("charter_aff", 0.0)
                         + sm.get("charter_bm", 0.0))
                county_base[cc] = county_base.get(cc, 0.0) + base
                county_seats[cc] = county_seats.get(cc, 0.0) + s_all * (1 - m)
                if level == "u":
                    if row and all(
                        row.get(k) is not None
                        for k in ("pub_5_9", "pub_10_14", "pub_15_17")
                    ):
                        blo = row["pub_5_9"] + w_c * row["pub_10_14"]
                        bup = (1 - w_c) * row["pub_10_14"] + row["pub_15_17"]
                    else:
                        blo = bup = None
                elif level == "e":
                    blo, bup = base, None
                else:
                    blo, bup = None, base
                node_bands[level, g] = (blo, bup)
                if blo:
                    county_blo[cc] = county_blo.get(cc, 0.0) + blo
                if bup:
                    county_bup[cc] = county_bup.get(cc, 0.0) + bup
                # Band seats and positive measured band gaps per node — the
                # weights (and caps) for passing the county's balanced remote
                # attribution down to districts: remote use is attributed
                # where unexplained outflow is observed, never beyond it.
                if level == "u":
                    ns_lo = sum(
                        seats_u_lo.get(g, {}).get(k, 0.0)
                        for k in ("district_run", "charter_aff", "charter_bm")
                    )
                    ns_up = sum(
                        seats_u_up.get(g, {}).get(k, 0.0)
                        for k in ("district_run", "charter_aff", "charter_bm")
                    )
                elif level == "e":
                    ns_lo, ns_up = s_all, 0.0
                else:
                    ns_lo, ns_up = 0.0, s_all
                node_bseats[level, g] = (ns_lo, ns_up)
                g_lo = (
                    max(blo - ns_lo * (1 - (m_lo if m_lo is not None else m)), 0.0)
                    if blo is not None else 0.0
                )
                g_up = (
                    max(bup - ns_up * (1 - (m_up if m_up is not None else m)), 0.0)
                    if bup is not None else 0.0
                )
                node_gaps[level, g] = (g_lo, g_up)
                if g_lo:
                    county_glo[cc] = county_glo.get(cc, 0.0) + g_lo
                if g_up:
                    county_gup[cc] = county_gup.get(cc, 0.0) + g_up

            closure = 0.0
            covered = 0
            for level, g in nodes:
                base, moe, row = bases[level, g]
                sm = seats_by_level[level].get(g, {})
                s_dr = sm.get("district_run", 0.0)
                s_caff = sm.get("charter_aff", 0.0)
                s_cbm = sm.get("charter_bm", 0.0)
                seats_adj = (s_dr + s_caff + s_cbm) * (1 - m)
                cc = node_county.get((level, g))
                blo, bup = node_bands.get((level, g), (None, None))
                ns_lo, ns_up = node_bseats.get((level, g), (0.0, 0.0))
                s_lo = ns_lo if level != "h" else None
                s_up = ns_up if level != "e" else None
                ral_lo = ral_up = None
                if base is None or not county_base.get(cc):
                    net = rate = virt_est = ooc = None
                else:
                    pool_cc = county_base[cc] - county_seats[cc]
                    # District pass-back of the county's balanced remote
                    # attribution: weighted by each district's own measured
                    # band gap (residents minus band-calibrated local seats,
                    # clipped at zero) — remote use is attributed where
                    # unexplained outflow is observed, and a district with no
                    # gap receives none. Nodes without age/gap data fall back
                    # to population share. The remaining county pool (net
                    # in-person redistribution + unsited) still spreads by
                    # population, so districts sum exactly to the county.
                    g_lo, g_up = node_gaps.get((level, g), (0.0, 0.0))
                    if county_glo.get(cc):
                        ral_lo = remote_alloc_lo.get(cc, 0.0) * g_lo / county_glo[cc]
                    elif blo and county_blo.get(cc):
                        ral_lo = remote_alloc_lo.get(cc, 0.0) * blo / county_blo[cc]
                    if county_gup.get(cc):
                        ral_up = remote_alloc_up.get(cc, 0.0) * g_up / county_gup[cc]
                    elif bup and county_bup.get(cc):
                        ral_up = remote_alloc_up.get(cc, 0.0) * bup / county_bup[cc]
                    if ral_lo is None and ral_up is None:
                        virt_est = remote_alloc.get(cc, 0.0) * base / county_base[cc]
                    else:
                        virt_est = (
                            (ral_lo or 0.0) + (ral_up or 0.0)
                            + remote_alloc_x.get(cc, 0.0) * base / county_base[cc]
                        )
                    total_alloc = virt_est + (
                        (pool_cc - remote_alloc.get(cc, 0.0)) * base / county_base[cc]
                    )
                    ooc = total_alloc - virt_est
                    net = seats_adj - (base - total_alloc)
                    rate = net / base if base else None
                    closure += net
                    covered += 1
                flow_rows.append(
                    {
                        "level": level,
                        "geoid": g,
                        "county": cc,
                        "vintage": v,
                        "n_springs": n_springs,
                        "res_pub": base,
                        "res_moe": moe,
                        "res_priv": row.get("priv") if row else None,
                        "res_noten": row.get("noten") if row else None,
                        "res_total": row.get("total") if row else None,
                        "factor": row.get("factor") if row else None,
                        "seats_dr": s_dr,
                        "seats_caff": s_caff,
                        "seats_cbm": s_cbm,
                        "seats_virt": virt_by_level[level]
                        .get(g, {})
                        .get("remote", 0.0),
                        "seats_adj": seats_adj,
                        "virt_alloc": virt_est,
                        "ooc_alloc": ooc,
                        "net": net,
                        "net_rate": rate,
                        "res_lo": blo,
                        "res_up": bup,
                        "seats_lo": s_lo,
                        "seats_up": s_up,
                        "ralloc_lo": ral_lo,
                        "ralloc_up": ral_up,
                    }
                )

            # County nodes: administrative county (cds prefix) vs county residence.
            # Only the REMOTE pool is allocated here (footprint-weighted) —
            # unsited physical seats already sit in their administrative
            # county's seat totals (seats_c groups by CDS prefix, which every
            # school has), so re-allocating them would double-count and county
            # nets would sum to +pool_unsited*(1-m) statewide instead of zero.
            # A county's net is thus its measured cross-county administrative
            # flow, and county nets close exactly at the state level (the
            # footprint allocation sums to the full remote pool).
            for r in county_rows:
                fips = r["geoid"][-3:]
                code = f"{(int(fips) + 1) // 2:02d}"
                seat_map = seats_c.get(code, {})
                s_dr = seat_map.get("district_run", 0.0)
                s_caff = seat_map.get("charter_aff", 0.0)
                s_cbm = seat_map.get("charter_bm", 0.0)
                base = r["pub"]
                valloc = remote_alloc.get(code, 0.0) if base else None
                seats_adj = (s_dr + s_caff + s_cbm) * (1 - m)
                net = seats_adj - (base - valloc) if base is not None and valloc is not None else None
                flow_rows.append(
                    {
                        "level": "c",
                        "geoid": code,
                        "county": code,
                        "vintage": v,
                        "n_springs": n_springs,
                        "res_pub": base,
                        "res_moe": r["moe_pub"],
                        "res_priv": r["priv"],
                        "res_noten": r["noten"],
                        "res_total": r["total"],
                        "factor": r["factor"],
                        "seats_dr": s_dr,
                        "seats_caff": s_caff,
                        "seats_cbm": s_cbm,
                        "seats_virt": remote_c.get(code, 0.0),
                        "seats_adj": seats_adj,
                        "virt_alloc": valloc,
                        "ooc_alloc": None,
                        "net": net,
                        "net_rate": net / base if net is not None and base else None,
                        "res_lo": cty_lo.get(code),
                        "res_up": cty_up.get(code),
                        "seats_lo": seats_c_lo.get(code),
                        "seats_up": seats_c_up.get(code),
                        "ralloc_lo": remote_alloc_lo.get(code),
                        "ralloc_up": remote_alloc_up.get(code),
                    }
                )

            calib_rows.append(
                {
                    "vintage": v,
                    "n_springs": n_springs,
                    "state_cde": cde5,
                    "state_acs_pub": state_pub,
                    "m": m,
                    "m_lo": m_lo,
                    "m_up": m_up,
                    "pool_virtual": pool_virtual,
                    "pool_nc": pool_nc,
                    "n_nc_authorizers": len(nc_auth),
                    "pool_unsited": pool_unsited,
                    "closure": closure,
                    "closure_share": closure / cde5,
                    "nodes_covered": covered,
                    "nodes_total": len(nodes),
                }
            )
            print(
                f"    vintage {v}: m={m:.3%}, virtual={pool_virtual:,.0f}, "
                f"non-classroom={pool_nc:,.0f} ({len(nc_auth)} authorizers), "
                f"unsited={pool_unsited:,.0f}, "
                f"closure={closure / cde5:+.4%} over {covered}/{len(nodes)} areas"
            )

        pl.DataFrame(flow_rows).write_parquet(FLOWS_PARQUET)
        pl.DataFrame(calib_rows).write_parquet(CALIB_PARQUET)
        pl.DataFrame(remote_auth_rows).write_parquet(REMOTE_AUTH_PARQUET)
        pl.DataFrame(remote_prog_rows).write_parquet(REMOTE_PROGRAMS_PARQUET)
        pl.DataFrame(remote_xcty_rows).write_parquet(REMOTE_XCTY_PARQUET)

        acs1_overlay(residence, seats)
        print(f"  enrollment flows: {len(flow_rows):,} area-vintage rows, "
              f"{len(calib_rows)} vintages")
    finally:
        if own:
            con.close()


# ---------------------------------------------------------------------------
# Step 7: annual ACS 1-year overlay (large unified districts, counties, state)


def acs1_overlay(residence: pl.DataFrame, seats: pl.DataFrame) -> pl.DataFrame:
    """[level, geoid, year, pub, pub_moe, cde_straddle]: the annual series where
    published, against the straddle mean (springs y, y+1) of the same sited
    physical-seat concept used by the 5-year accounting."""
    acs1 = residence.filter(pl.col("survey") == "acs1")
    phys = seats.filter(pl.col("class") != "charter_virtual")

    def straddle(series: dict[int, float], y: int) -> float | None:
        vals = [series[s] for s in (y, y + 1) if s in series]
        return sum(vals) / len(vals) if vals else None

    by_u: dict[str, dict[int, float]] = {}
    for g, s, t in (
        phys.filter(pl.col("unified_geoid").is_not_null())
        .group_by("unified_geoid", "spring")
        .agg(pl.col("total").sum())
        .iter_rows()
    ):
        by_u.setdefault(g, {})[s] = t
    by_c: dict[str, dict[int, float]] = {}
    for g, s, t in phys.group_by("county_code", "spring").agg(
        pl.col("total").sum()
    ).iter_rows():
        by_c.setdefault(g, {})[s] = t
    state: dict[int, float] = {}
    for s, t in phys.group_by("spring").agg(pl.col("total").sum()).iter_rows():
        state[s] = t

    rows = []
    for r in acs1.to_dicts():
        y = r["vintage"]
        if r["geo_type"] == "sd_unified":
            level, gid = "u", r["geoid"]
            cde = straddle(by_u.get(gid, {}), y)
        elif r["geo_type"] == "county":
            fips = r["geoid"][-3:]
            level, gid = "c", f"{(int(fips) + 1) // 2:02d}"
            cde = straddle(by_c.get(gid, {}), y)
        else:
            level, gid = "s", "CA"
            cde = straddle(state, y)
        rows.append(
            {
                "level": level,
                "geoid": gid,
                "year": y,
                "pub": r["pub"],
                "pub_moe": r["moe_pub"],
                "factor": r["factor"],
                "cde_straddle": cde,
            }
        )
    df = pl.DataFrame(rows).sort("level", "geoid", "year")
    df.write_parquet(ACS1_PARQUET)
    return df


if __name__ == "__main__":
    build_all()
