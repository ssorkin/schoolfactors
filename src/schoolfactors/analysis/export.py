"""Export prebuilt JSON for the static site.

Site data contract (v1):
    data/index.json                 — statewide search index (schools + districts)
    data/schools/{cds}.json         — per-school page payload
    data/districts/{cds}.json       — per-district page payload
    data/summary.json               — homepage stats
Everything is precomputed — the site has no API.
"""

from __future__ import annotations

import bisect
import json

import duckdb
import polars as pl

from schoolfactors.paths import DUCKDB_PATH, PARQUET_DIR, REPO_ROOT

SITE_DATA = REPO_ROOT / "site" / "static" / "data"

EFFECT_COLS = [
    "total_scores",
    "n_years",
    "last_year",
    "level_eb",
    "level_se",
    "growth_eb",
    "growth_se",
    "trend_eb",
    "trend_se",
    "move_eb",
    "move_se",
    "move_reliability",
    "level_adj_eb",
    "level_adj_lcb",
    "growth_adj_eb",
    "growth_adj_lcb",
    "level_reliability",
    "growth_reliability",
    "share_econ_dis",
    "share_el",
]


def _names() -> pl.DataFrame:
    """Latest known name per entity (falling back through years for closed schools).

    CAASPP files list direct-funded charters as their own LEA, so their school
    rows carry the charter's name in district_name ("KIPP Promesa Prep", not
    "Los Angeles Unified"). Every rollup on the site folds charters into their
    CDS-prefix district, so school rows take that district's name here too —
    otherwise district: facet searches silently exclude ~1,000 direct-funded
    charters (known_issues/caaspp-charter-lea-district-name.yaml). Schools
    whose prefix district never appears in CAASPP keep the LEA name.
    """
    con = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    df = con.execute("""
        WITH latest AS (
            SELECT cds, school_name, district_name, county_name, type_id
            FROM (
                SELECT cds, school_name, district_name, county_name, type_id,
                       row_number() OVER (PARTITION BY cds ORDER BY test_year DESC) AS rn
                FROM caaspp_entities
            ) WHERE rn = 1
        )
        SELECT e.cds, e.school_name,
               coalesce(d.district_name, e.district_name) AS district_name,
               e.county_name, e.type_id
        FROM latest e
        LEFT JOIN latest d ON d.cds = substr(e.cds, 1, 7) || '0000000'
    """).pl()
    con.close()
    return df


def _effect_payload(row: dict) -> dict:
    return {k: row.get(k) for k in EFFECT_COLS if row.get(k) is not None}


def _gamma_table(path, effects: pl.DataFrame, covariates: list[str]) -> dict[str, float]:
    """Level-adjustment coefficients for one entity kind, keyed by term.

    Falls back to refitting when the analysis predates the saved table: the fit
    is deterministic on the saved inputs, so it reproduces the saved residuals.
    """
    from schoolfactors.analysis.model import adjust

    if path.exists():
        t = pl.read_parquet(path)
        return {
            k: g
            for k, g in zip(t["term"].to_list(), t["gamma_level"].to_list())
            if g is not None
        }
    print(f"  {path.name} not found; refitting level adjustment for its coefficients")
    _, coef, _ = adjust(
        effects.drop([c for c in effects.columns if c.endswith("_adj") or "_adj_" in c]),
        "level",
        covariates,
    )
    return dict(zip(coef["term"].to_list(), coef["gamma_level"].to_list()))


def _adj_calc(row: dict, gam: dict[str, float], xbar: dict[str, float]) -> dict | None:
    """Term-by-term demographic adjustment of the raw level, for the entity page's
    "show the calculation" panel.

    Starts from the unshrunken OLS level (the adjustment regresses that, not the
    shrunken display value). level - intercept - sum(share x coefficient) is the
    residual; the residual is shrunk by reliability, and the lower bound of the
    95% band around the shrunken residual is what the percentile ranks.

    Each term is also expressed relative to the mean covariate value of the
    entities in the fit (xbar): baseline = intercept + sum(coef x mean) is the
    expected level of an entity with the average mix, and each contribution
    coef x (x - mean) says how this entity's mix moves it from there. The two
    forms are the same equation; the centered one reads without a bare
    intercept.
    """
    lvl = row.get("level")
    resid = row.get("level_adj")
    if lvl is None or resid is None or not gam or "intercept" not in gam:
        return None
    terms = []
    expected = gam["intercept"]
    baseline = gam["intercept"]
    for k, g in gam.items():
        if k == "intercept":
            continue
        x = row.get(k)
        if x is None:
            return None
        expected += x * g
        baseline += xbar[k] * g
        terms.append(
            {
                "k": k,
                "x": round(x, 4),
                "m": round(xbar[k], 4),
                "g": round(g, 4),
                "c": round(x * g, 4),
                "d": round((x - xbar[k]) * g, 4),
            }
        )
    if abs(lvl - expected - resid) > 1e-6:
        raise ValueError(f"adjustment does not reproduce residual for {row.get('cds')}")
    out = {
        "level": round(lvl, 4),
        "level_se": round(row["level_var"] ** 0.5, 4),
        "intercept": round(gam["intercept"], 4),
        "baseline": round(baseline, 4),
        "terms": terms,
        "expected": round(expected, 4),
        "resid": round(resid, 4),
        "lambda": round(row["level_adj_reliability"], 4),
        "resid_eb": round(row["level_adj_eb"], 4),
        "lcb": round(row["level_adj_lcb"], 4),
    }
    if row.get("tested_total") is not None:
        out["tested"] = int(row["tested_total"])
    return out


def _round_row(d: dict) -> dict:
    return {k: (round(v, 3) if isinstance(v, float) else v) for k, v in d.items()}


def _rows(part: dict, cds: str) -> list[dict]:
    df = part.get((cds,))
    return df.to_dicts() if df is not None else []


SPARK_YEARS = [2015, 2016, 2017, 2018, 2019, 2022, 2023, 2024, 2025]

# Enrollment sparkline axis: unlike test scores, census enrollment exists for
# every year including 2020 and 2021, and extends to the current school year.
ENR_YEARS = list(range(2015, 2027))

# Student groups that get a "Best for" table (data/groups/{id}.json).
BESTFOR_GROUPS = [128, 31, 160, 8, 74, 76, 77, 78, 80, 144, 52, 240, 90]

# Groups compared against their statewide rate in the entity-page summary.
SUMMARY_GROUPS = [31, 160, 128, 74, 76, 78, 80]

# School type classes (mirroring the site's map legend in maptypes.js): the
# partition used by the peer scatter AND the lookalike matching — demographics
# cannot distinguish a continuation school from a traditional school serving
# identical students, so cross-type comparisons are invalid.
# "Hard" alternative programs select on student circumstance (credit
# recovery, court placement) — median similar-schools percentile 34 in their
# own pool. EdOps ALTSOC ("alternative school of choice", e.g. LAUSD pilot
# schools) is the opposite: upward self-selection like magnets (median
# percentile 80, 64% top-quartile), so it forms its own "choice" class and
# stays in the general percentile pool.
ALT_FLAGS_HARD = {"continuation", "community-day", "community", "court", "special-ed"}


def school_type(flags: list | None) -> str:
    fl = flags or []
    if "selective" in fl:
        return "selective"
    if "magnet" in fl:
        return "magnet"
    if "charter" in fl:
        return "charter"
    if ALT_FLAGS_HARD & set(fl):
        return "alternative"
    if "alt-choice" in fl:
        return "choice"
    return "standard"

# Groups benchmarked against SIMILAR entities (same kind, model-predicted level
# within a band) — the comparison that explains extreme adjusted placements.
# Includes All Students (Met+ AND Exceeded: a shortfall can live entirely in
# the top band) and the advantage-marked groups whose statewide averages are
# the wrong bar in advantaged communities.
VS_SIMILAR_GROUPS = [1, 31, 111, 93, 94]


def _latest_rates(rows: list[dict]) -> dict | None:
    """Latest-year combined Met+/Exceeded for one group's rows (count-weighted)."""
    by_year: dict[int, list] = {}
    for r in rows:
        if r["pct_met_and_above"] is None:
            continue
        by_year.setdefault(r["test_year"], []).append(
            (r["pct_met_and_above"], r["pct_exceeded"], r["n"])
        )
    if not by_year:
        return None
    vals = by_year[max(by_year)]
    n = sum(v[2] for v in vals)
    if not n:
        return None
    met = sum(v[0] * v[2] for v in vals) / n
    excs = [(v[1], v[2]) for v in vals if v[1] is not None]
    exc = sum(a * b for a, b in excs) / sum(b for _, b in excs) if excs else None
    return {"met": met, "exc": exc, "n": n}


def _group_stats(rows: list[dict]) -> dict:
    """Latest per-subject pass rates, count-weighted spark, and last data year
    for one student group's grade-13 rows."""
    by_year: dict[int, list] = {}
    latest: dict[str, tuple] = {}
    for r in rows:
        if r["pct_met_and_above"] is None:
            continue
        by_year.setdefault(r["test_year"], []).append((r["pct_met_and_above"], r["n"]))
        subj = "ela" if r["test_id"] == 1 else "math"
        if subj not in latest or r["test_year"] > latest[subj][0]:
            latest[subj] = (r["test_year"], r["pct_met_and_above"], r["n"])
    spark = []
    for y in SPARK_YEARS:
        vals = by_year.get(y)
        if vals:
            den = sum(n for _, n in vals)
            spark.append(round(sum(p * n for p, n in vals) / den) if den else None)
        else:
            spark.append(None)
    last_year = max(by_year) if by_year else None
    combined_latest = None
    n_latest = None
    if last_year is not None:
        vals = by_year[last_year]
        den = sum(n for _, n in vals)
        if den:
            combined_latest = round(sum(p * n for p, n in vals) / den, 1)
            n_latest = den
    return {
        "spark": spark,
        "last_year": last_year,
        "pass_ela": round(latest["ela"][1]) if "ela" in latest else None,
        "pass_math": round(latest["math"][1]) if "math" in latest else None,
        "combined_latest": combined_latest,
        "n_latest": n_latest,
    }


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
    from schoolfactors.analysis.model import ADJUST_COVARIATES, COUNTY_COVARIATES

    # Mean covariate values over the adjustment sample, per kind: the reference
    # mix the entity page's calculation panel centers its contributions on.
    def _xbar(effects: pl.DataFrame, covariates: list[str]) -> dict[str, float]:
        est = effects.filter(
            pl.col("level").is_not_null()
            & pl.col("level_adj").is_not_null()
            & pl.all_horizontal([pl.col(c).is_not_null() for c in covariates])
        )
        return {c: float(est[c].mean()) for c in covariates}

    xbar_by_kind = {
        "school": _xbar(schools, ADJUST_COVARIATES),
        "district": _xbar(districts, ADJUST_COVARIATES),
        "county": _xbar(counties, COUNTY_COVARIATES),
    }
    gammas_by_kind = {
        "school": gammas,
        "district": _gamma_table(
            PARQUET_DIR / "analysis" / "adjustment_coefficients_district.parquet",
            districts,
            ADJUST_COVARIATES,
        ),
        "county": _gamma_table(
            PARQUET_DIR / "analysis" / "adjustment_coefficients_county.parquet",
            counties,
            COUNTY_COVARIATES,
        ),
    }
    names = _names()

    sigma = estimate_sigma(school_rows(SCHOOL_TYPES))
    state = state_means()

    # Statewide Met+ per student group and year (grade-13 rollup, both subjects,
    # count-weighted): the page summary compares each entity's groups against
    # the same group statewide — a raw comparison, labeled as such.
    con_state = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    state_group_rate: dict[tuple[int, int], float] = {}
    for gid, yr, num, den in con_state.execute(f"""
        SELECT student_group_id, test_year,
               sum(pct_met_and_above * students_with_scores),
               sum(students_with_scores)
        FROM caaspp_sb_raw
        WHERE cds = '00000000000000' AND grade = 13 AND test_id IN (1, 2)
          AND student_group_id IN ({", ".join(map(str, SUMMARY_GROUPS))})
          AND pct_met_and_above IS NOT NULL AND test_year <> 2021
        GROUP BY 1, 2
    """).fetchall():
        if den:
            state_group_rate[(gid, yr)] = num / den
    # State Met+ by year x grade x subject: the band-language reference for the
    # cohort examples on entity pages ("58% met standards in grade 3, state 47%").
    state_met = {
        (r[0], r[1], r[2]): r[3]
        for r in con_state.execute("""
            SELECT test_year, grade, test_id, pct_met_and_above
            FROM caaspp_sb_raw
            WHERE cds = '00000000000000' AND student_group_id = 1
              AND grade BETWEEN 3 AND 11 AND test_id IN (1, 2)
              AND pct_met_and_above IS NOT NULL
        """).fetchall()
    }

    # Participation: tested / enrolled for All Students at grade 13, both
    # subjects summed. Keyed by (cds, year) so each index row reports the same
    # year as its Met+ columns; low values flag entities (notably virtual
    # charters) whose Met+ rates describe only a subset of students.
    tested_map: dict[tuple[str, int], int] = {}
    for cds_, yr, tested, enrolled in con_state.execute("""
        SELECT cds, test_year, sum(students_tested), sum(students_enrolled)
        FROM caaspp_sb
        WHERE grade = 13 AND test_id IN (1, 2) AND student_group_id = 1
          AND students_tested IS NOT NULL AND students_enrolled IS NOT NULL
        GROUP BY 1, 2
    """).fetchall():
        if enrolled:
            tested_map[(cds_, yr)] = round(100 * tested / enrolled)
    con_state.close()

    # School level (elementary/middle/high) from the directory, for table facets.
    con_dir = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    eil_map = dict(
        con_dir.execute(
            "SELECT cds, any_value(eilcode) FROM directory_raw WHERE eilcode IS NOT NULL GROUP BY cds"
        ).fetchall()
    )

    # Physical address (school pages). The directory's street/city are the
    # campus location, which for remotely-authorized charters can sit in a
    # different county than the CDS says — showing it makes that legible.
    addr_map = {}
    for cds_, street, city_, zip_ in con_dir.execute("""
        SELECT cds, any_value(street), any_value(city), any_value(zip)
        FROM directory_raw
        WHERE street IS NOT NULL AND city IS NOT NULL
        GROUP BY cds
    """).fetchall():
        zip5 = (zip_ or "")[:5]
        addr_map[cds_] = f"{street}, {city_}, CA {zip5}".strip() if zip5 else f"{street}, {city_}"

    # Admission/type flags. CDE knows magnet/charter/EdOps; it has NO field for
    # exam-based admission (verified: Whitney (Gretchen) High and Oxford Academy
    # are Magnet=N/EdOps=Traditional), so selective schools come from the
    # community-curated, cited list in curated/selective_admissions.yaml.
    import yaml

    from schoolfactors.paths import REPO_ROOT as _ROOT

    EDOPS_FLAG = {
        "ALTSOC": "alt-choice",
        "CON": "continuation",
        "COMMDAY": "community-day",
        "COMM": "community",
        "JUV": "court",
        "SPEC": "special-ed",
    }
    flags_map: dict[str, list[str]] = {}
    for cds_, magnet, charter, edops, virt in con_dir.execute(
        "SELECT cds, any_value(magnet), any_value(charter), any_value(edopscode), "
        "any_value(trim(virtual)) FROM directory_raw GROUP BY cds"
    ).fetchall():
        fl = []
        if magnet == "Y":
            fl.append("magnet")
        if charter == "Y":
            fl.append("charter")
        # CDE directory Virtual flag: F = exclusively virtual, V = primarily
        # virtual. Scores at these schools describe students who may live far
        # from the school's (or authorizer's) location, so the flag travels
        # with the name like the admission flags do.
        if virt in ("F", "V"):
            fl.append("virtual")
        if edops in EDOPS_FLAG:
            fl.append(EDOPS_FLAG[edops])
        if fl:
            flags_map[cds_] = fl
    curated_path = _ROOT / "curated" / "selective_admissions.yaml"
    if curated_path.exists():
        for entry in yaml.safe_load(curated_path.read_text()):
            flags_map.setdefault(entry["cds"], [])
            if "selective" not in flags_map[entry["cds"]]:
                flags_map[entry["cds"]].insert(0, "selective")
    school_type_map = {c: school_type(fl) for c, fl in flags_map.items()}

    # Similar Student inputs: within-school student-level composition effects
    # (analysis/similar_student.py). simstu = level_eb - stud_eff ranks, for a
    # fixed student profile, the conditional expectation at each entity — the
    # parent decision question. Profile-invariant under the additive model.
    from schoolfactors.analysis.similar_student import student_effects

    print("estimating similar-student composition effects …")
    stud_eff_map, _stud_deltas = student_effects()
    print(f"  student effects for {len(stud_eff_map):,} entities")


    # Districts that authorize fully/primarily-virtual charters: school count
    # and enrollment at the latest census-day year, plus the district's own
    # associated total for a share. Surfaced as a notice on district pages —
    # such a district's numbers describe students who may live far outside it.
    virt_auth: dict[str, dict] = {}
    try:
        latest_ay = con_dir.execute(
            "SELECT max(academicyear) FROM enrollment_raw"
        ).fetchone()[0]
        rows_va = con_dir.execute(
            "WITH virt AS (SELECT cds FROM directory_raw WHERE trim(charter) = 'Y' AND trim(virtual) IN ('F', 'V') GROUP BY cds), cur AS (SELECT cds, sum(TRY_CAST(total_enr AS DOUBLE)) AS v FROM enrollment_raw WHERE aggregatelevel = 'S' AND reportingcategory = 'TA' AND academicyear = ? GROUP BY cds) SELECT substr(virt.cds, 1, 7), count(*) FILTER (WHERE coalesce(cur.v, 0) > 0), sum(coalesce(cur.v, 0)) FROM virt LEFT JOIN cur ON virt.cds = cur.cds GROUP BY 1", [latest_ay]
        ).fetchall()
        dist_tot = dict(con_dir.execute(
            "SELECT substr(cds, 1, 7), sum(TRY_CAST(total_enr AS DOUBLE)) FROM enrollment_raw WHERE aggregatelevel = 'S' AND reportingcategory = 'TA' AND academicyear = ? GROUP BY 1", [latest_ay]
        ).fetchall())
        for d7, n_va, enr_va in rows_va:
            if n_va and enr_va:
                tot = dist_tot.get(d7)
                virt_auth[d7] = {
                    "year": latest_ay,
                    "n": int(n_va),
                    "enr": int(enr_va),
                    "share": round(enr_va / tot, 3) if tot else None,
                }
    except Exception as exc:  # noqa: BLE001 - the notice is optional
        print(f"  virtual-authorizer map skipped: {exc}")

    # Out-of-sample percentile history: for each cutoff year, rank entities the
    # way the live percentile does (lower bound of the 95% band, reliability
    # >= 0.70, data current through the cutoff, and — for schools — alternative
    # programs pooled separately) — but on a model refit from data through that
    # cutoff only. Each result is labeled with the NEXT test year: the chip an
    # entity page shows for 2024 is the percentile a reader entering 2024 would
    # have seen, computed before 2024's scores existed. The current all-data
    # percentile (adj_pct) is the "now" chip; no history row duplicates it.
    def pct_history(
        stem: str, cls_of, src: str = "level_adj_lcb"
    ) -> dict[str, list[list[int]]]:
        from itertools import pairwise

        out: dict[str, list[list[int]]] = {}
        hist_path = PARQUET_DIR / "analysis" / f"{stem}_history.parquet"
        if not hist_path.exists():
            return out
        hist = pl.read_parquet(hist_path)
        if src not in hist.columns:  # older history parquet without the column
            return out
        hist_years = sorted(hist["as_of_year"].unique().to_list())
        for cut, nxt in pairwise(hist_years):
            sub = hist.filter(
                (pl.col("as_of_year") == cut)
                & (pl.col("last_year") == cut)
                & pl.col(src).is_not_null()
                & (pl.col("level_reliability") >= 0.7)
            )
            by_cls: dict[str, list[tuple[str, float]]] = {}
            for cds_, lcb in sub.select("cds", src).rows():
                by_cls.setdefault(cls_of(cds_), []).append((cds_, lcb))
            for members in by_cls.values():
                pool = sorted(lcb for _, lcb in members)
                if len(pool) < 20:
                    continue
                for cds_, lcb in members:
                    lo = bisect.bisect_left(pool, lcb)
                    hi = bisect.bisect_right(pool, lcb)
                    pct = min(99, max(1, round(100 * (lo + hi) / 2 / len(pool))))
                    out.setdefault(cds_, []).append([nxt, pct])
        return out

    pct_hist_by_kind = {
        "schools": pct_history(
            "school_effects",
            lambda c: (
                "alternative"
                if school_type_map.get(c, "standard") == "alternative"
                else "general"
            ),
        ),
        "districts": pct_history("district_effects", lambda c: ""),
        "counties": pct_history("county_effects", lambda c: ""),
    }
    # Expected Student chips: same out-of-sample cutoffs, ranking the
    # demographic prediction instead of the residual band.
    stu_hist_by_kind = {
        "schools": pct_history(
            "school_effects",
            lambda c: (
                "alternative"
                if school_type_map.get(c, "standard") == "alternative"
                else "general"
            ),
            src="level_pred",
        ),
        "districts": pct_history("district_effects", lambda c: "", src="level_pred"),
        "counties": pct_history("county_effects", lambda c: "", src="level_pred"),
    }
    for kind_, m in pct_hist_by_kind.items():
        print(f"  percentile history: {len(m):,} {kind_} "
              f"({sum(len(v) for v in m.values()):,} chips; "
              f"{sum(len(v) for v in stu_hist_by_kind[kind_].values()):,} expected)")

    from schoolfactors.analysis.neighbors import build_neighbors

    print("  computing nearby/lookalike neighbors …")
    neighbors = build_neighbors(schools, school_type_map)
    # Current census-day enrollment (latest CDE cdenroll year). School rows carry
    # their own charter flag; district/county totals need the ALL rollup.
    # County rows in the new-format census files carry no cds (only countycode);
    # rebuild their 14-char key so county pages get enrollment too.
    census_map = dict(
        con_dir.execute("""
            SELECT COALESCE(cds, countycode || '000000000000'),
                   max(TRY_CAST(total_enr AS INT))
            FROM enrollment_raw
            WHERE reportingcategory = 'TA'
              AND academicyear = (SELECT max(academicyear) FROM enrollment_raw)
              AND (aggregatelevel = 'S' OR charter = 'ALL')
              AND aggregatelevel IN ('S', 'D', 'C')
            GROUP BY 1
        """).fetchall()
    )
    # Full-population FRPM share (all enrolled students, latest FRPM year) — the
    # census view of economic disadvantage, not the tested-population share.
    frpm_school = con_dir.execute("""
        SELECT cds,
               TRY_CAST(frpm_count_k_12 AS DOUBLE) AS c,
               TRY_CAST(enrollment_k_12 AS DOUBLE) AS e
        FROM frpm_raw
        WHERE academic_year = (SELECT max(academic_year) FROM frpm_raw)
          AND school_code IS NOT NULL AND school_code <> '0000000'
          AND TRY_CAST(enrollment_k_12 AS DOUBLE) > 0
    """).fetchall()
    # FRPM census by year (spring-labeled), rolled up to district/county like
    # the other rollups. The intake-shift warning cross-checks the tested
    # population's SED shift against this: when school-wide FRPM barely moved,
    # a tested-share shift mostly reflects who tests, not who enrolls.
    frpm_hist_pool: dict[str, dict[int, list]] = {}
    for scds, ay_, c, e in con_dir.execute("""
        SELECT cds, academic_year,
               TRY_CAST(frpm_count_k_12 AS DOUBLE), TRY_CAST(enrollment_k_12 AS DOUBLE)
        FROM frpm_raw
        WHERE school_code IS NOT NULL AND school_code <> '0000000'
          AND TRY_CAST(enrollment_k_12 AS DOUBLE) > 0 AND length(academic_year) = 9
    """).fetchall():
        if c is None or e is None:
            continue
        year = int(ay_[:4]) + 1
        for key in (scds, scds[:7] + "0000000", scds[:2] + "000000000000"):
            agg = frpm_hist_pool.setdefault(key, {}).setdefault(year, [0.0, 0.0])
            agg[0] += c
            agg[1] += e
    frpm_hist_map = {
        k: {y: round(c / e, 3) for y, (c, e) in by_year.items() if e > 0}
        for k, by_year in frpm_hist_pool.items()
    }
    # ESSA per-pupil expenditure, every published year (essappeXXYYdata →
    # spring 20YY). Total = school + allocated central, federal + state/local.
    ppe_rows_all = con_dir.execute("""
        SELECT file, cds, lea_cds_code,
               COALESCE(TRY_CAST(school_expenditures_federal AS DOUBLE), 0)
             + COALESCE(TRY_CAST(school_expenditures_state_local AS DOUBLE), 0)
             + COALESCE(TRY_CAST(central_expenditures_federal AS DOUBLE), 0)
             + COALESCE(TRY_CAST(central_expenditures_state_local AS DOUBLE), 0) AS pp,
               TRY_CAST(student_membership AS DOUBLE) AS mem
        FROM ppe_raw
        WHERE TRY_CAST(school_expenditures_state_local AS DOUBLE) IS NOT NULL
          AND length(cds) = 14
    """).fetchall()
    # Coordinates for the map view. CDE directory lat/long, bounded to
    # California so placeholder zeros/typos don't land points in the Gulf of
    # Guinea; entities sharing a cds across files get the average.
    latlon_rows = con_dir.execute("""
        SELECT cds,
               round(avg(TRY_CAST(latitude AS DOUBLE)), 5),
               round(avg(TRY_CAST(longitude AS DOUBLE)), 5)
        FROM directory_raw
        WHERE TRY_CAST(latitude AS DOUBLE) BETWEEN 32.0 AND 42.5
          AND TRY_CAST(longitude AS DOUBLE) BETWEEN -125.0 AND -113.5
          AND cds IS NOT NULL AND length(cds) = 14
        GROUP BY cds
    """).fetchall()
    # Census enrollment history for the table sparkline: CDE's historical
    # enrollment-by-school files through 2022-23 (enr_type 'C', the census-day
    # combined count — statewide total matches CDE's published 5,852,544 for
    # 2022-23) stitched to the new-format census files from 2023-24 on
    # (school-level seam is continuous). Includes 2019-20 through 2021-22:
    # enrollment was collected in the COVID years even though testing wasn't.
    # Years are labeled by spring (2014-15 → 2015) to match test_year.
    # District/county series roll up ALL rows by CDS prefix — including
    # school-code-0000000 district-office programs and charters — matching how
    # every other rollup on the site folds charters into their CDS district.
    enr_hist: dict[str, dict[int, int]] = {}
    for cds_, ay_, n_ in con_dir.execute("""
        SELECT cds, academic_year, sum(TRY_CAST(enr_total AS BIGINT))
        FROM enrollment_hist_raw
        WHERE enr_type = 'C' AND academic_year >= '2014-15'
          AND length(academic_year) = 7 AND length(cds) = 14
        GROUP BY 1, 2
    """).fetchall():
        if not n_:
            continue
        year = int(ay_[:4]) + 1
        # dict.fromkeys dedupes: a district-office row (school code 0000000)
        # IS its own district key and must count once, not twice.
        for key in dict.fromkeys(
            (cds_, cds_[:7] + "0000000", cds_[:2] + "000000000000")
        ):
            d = enr_hist.setdefault(key, {})
            d[year] = d.get(year, 0) + int(n_)
    for cds_, ay_, n_ in con_dir.execute("""
        SELECT COALESCE(cds, countycode || '000000000000'),
               academicyear, max(TRY_CAST(total_enr AS INT))
        FROM enrollment_raw
        WHERE reportingcategory = 'TA' AND (aggregatelevel = 'S' OR charter = 'ALL')
          AND aggregatelevel IN ('S', 'D', 'C')
        GROUP BY 1, 2
    """).fetchall():
        if n_:
            enr_hist.setdefault(cds_, {})[int(ay_[:4]) + 1] = int(n_)
    con_dir.close()
    frpm_pop: dict[str, list] = {}
    for scds, c, e in frpm_school:
        if c is None or e is None:
            continue
        for key in (scds, scds[:7] + "0000000", scds[:2] + "000000000000"):
            agg = frpm_pop.setdefault(key, [0.0, 0.0])
            agg[0] += c
            agg[1] += e
    frpm_pop_share = {
        k: round(c / e, 3) for k, (c, e) in frpm_pop.items() if e > 0
    }
    # District/county rows missing their own directory coordinates fall back
    # to the unweighted centroid of their schools.
    latlon_map = {r[0]: (r[1], r[2]) for r in latlon_rows}
    cent: dict[str, list[float]] = {}
    for scds, (lat, lon) in list(latlon_map.items()):
        if scds.endswith("0000000"):
            continue
        for key in (scds[:7] + "0000000", scds[:2] + "000000000000"):
            agg = cent.setdefault(key, [0.0, 0.0, 0])
            agg[0] += lat
            agg[1] += lon
            agg[2] += 1
    for key, (la, lo, n) in cent.items():
        if key not in latlon_map and n:
            latlon_map[key] = (round(la / n, 5), round(lo / n, 5))

    # Normalize PPE totals-reporters (known issue ppe-totals-reporting): ~5% of
    # LEAs filed total dollars in the per-pupil columns. The convention is
    # consistent within an LEA (per year), so an LEA whose median reported value
    # exceeds $100k/pupil is treated as a totals-reporter and its rows are
    # divided by membership. Symmetrically (known issue
    # ppe-implausibly-low-filings), an LEA whose median is under $5k/pupil —
    # below the LCFF base grant alone — filed broken data (e.g. Mt. Diablo
    # Unified 2024-25 omitted state/local dollars entirely) and every one of its
    # rows is unusable, including any that individually pass the floor.
    # Post-normalization values outside [$5k, $500k] are dropped as unusable:
    # below the LCFF base grant is impossible, but tiny SpEd/court/community-day
    # programs legitimately run $150k-$400k per pupil, so the ceiling only cuts
    # the physically absurd. Each published year is normalized independently
    # (a filing convention can change between years), producing a per-entity
    # spending history plus the latest-year value used in the table.
    ppe_hist: dict[str, dict[int, int]] = {}
    for file_ in sorted({r[0] for r in ppe_rows_all}):
        year = 2000 + int(file_[9:11])  # essappe1819data → spring 2019
        rows_y = [r for r in ppe_rows_all if r[0] == file_]
        ppe_by_lea: dict[str, list[float]] = {}
        for _, _, lea, pp, _ in rows_y:
            if pp > 0:
                ppe_by_lea.setdefault(lea, []).append(pp)
        ppe_totals_leas = {
            lea for lea, v in ppe_by_lea.items() if sorted(v)[len(v) // 2] > 100_000
        }
        ppe_broken_leas = {
            lea for lea, v in ppe_by_lea.items() if sorted(v)[len(v) // 2] < 5_000
        }
        ppe_pool: dict[str, list] = {}
        for _, scds, lea, pp, mem in rows_y:
            if pp <= 0 or lea in ppe_broken_leas:
                continue
            # The student_membership column only exists in recent ESSA files
            # (2023-24+); census enrollment for the same school-year stands in
            # for it elsewhere — without this, district/county rollups silently
            # started in 2024 despite per-pupil figures existing back to 2019.
            weight = mem or enr_hist.get(scds, {}).get(year)
            if lea in ppe_totals_leas:
                if not weight:
                    continue
                pp = pp / weight
            if not 5_000 <= pp <= 500_000:
                continue
            ppe_hist.setdefault(scds, {})[year] = round(pp)
            # District/county figures: reconstruct dollars (pp × membership,
            # or census enrollment when membership wasn't published), sum,
            # re-divide — never average per-pupil ratios. Charter schools
            # fold into their CDS-prefix district, matching CAASPP rollups.
            if weight:
                for key in (scds[:7] + "0000000", scds[:2] + "000000000000"):
                    agg = ppe_pool.setdefault(key, [0.0, 0.0])
                    agg[0] += pp * weight
                    agg[1] += weight
        # Coverage gate: after dropping unusable rows, a district/county
        # aggregate may describe only a sliver of the entity (Mt. Diablo
        # Unified's own schools are all dropped, leaving just co-located
        # charters). Publish the rollup only when usable reports cover >= 70%
        # of that year's census enrollment.
        for key, (dollars, students) in ppe_pool.items():
            census = enr_hist.get(key, {}).get(year)
            if students > 0 and (census is None or students >= 0.7 * census):
                ppe_hist.setdefault(key, {})[year] = round(dollars / students)
    PPE_YEARS = sorted({y for d in ppe_hist.values() for y in d})
    latest_ppe_year = max(PPE_YEARS) if PPE_YEARS else None
    ppe_map: dict[str, int] = {
        k: d[latest_ppe_year] for k, d in ppe_hist.items() if latest_ppe_year in d
    }
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
    vs_pool: dict[str, list] = {}
    index: list[dict] = []
    district_pages: set[str] = set()
    county_pages: set[str] = set()
    group_tables: dict[int, list[dict]] = {}

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
            # Group stats: All Students feeds the index row and the page
            # summary; curated groups feed the Student-groups tables.
            sub_rows = _rows(subgroups_by, cds)
            g1 = _group_stats([r for r in sub_rows if r["student_group_id"] == 1])
            # Stash predicted level + group rates for the vs-similar benchmark
            # (pooled in a post-pass once every entity of the kind is known).
            _row_full = eff_by_cds.get(cds, {})
            _pred_level = _row_full.get("level")
            _pred_resid = _row_full.get("level_adj")
            if _pred_level is not None and _pred_resid is not None:
                vs_pool.setdefault(kind, []).append(
                    {
                        "cds": cds,
                        "pred": _pred_level - _pred_resid,
                        "rates": {
                            g: _latest_rates(
                                [r for r in sub_rows if r["student_group_id"] == g]
                            )
                            for g in VS_SIMILAR_GROUPS
                        },
                    }
                )
            # Each group's latest combined Met+ vs the same group statewide,
            # current-year data only, gated on >= 30 scores (source suppression
            # already hides n < 11; 30 keeps single-classroom noise out of the
            # summary sentence).
            gvs = []
            for gid in SUMMARY_GROUPS:
                gs = _group_stats([r for r in sub_rows if r["student_group_id"] == gid])
                ref = state_group_rate.get((gid, gs["last_year"]))
                if (
                    gs["combined_latest"] is None
                    or ref is None
                    or (gs["n_latest"] or 0) < 30
                    or gs["last_year"] != g1["last_year"]
                ):
                    continue
                gvs.append({"g": gid, "d": round(gs["combined_latest"] - ref, 1)})
            payload = {
                "cds": cds,
                "kind": kind[:-1] if kind != "counties" else "county",
                "name": display_name,
                "pass_ela": g1["pass_ela"],
                "pass_math": g1["pass_math"],
                "pass_year": g1["last_year"],
                "enrollment": census_map.get(cds),
                "enr": (
                    [enr_hist[cds].get(y) for y in ENR_YEARS] if cds in enr_hist else None
                ),
                "ppe": ppe_map.get(cds),
                "ppe_years": PPE_YEARS,
                "ppe_hist": (
                    [ppe_hist[cds].get(y) for y in PPE_YEARS] if cds in ppe_hist else None
                ),
                "frpm_hist": frpm_hist_map.get(cds),
                "group_vs_state": gvs,
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
                        "state_pct_met": state_met.get(
                            (r["test_year"], r["grade"], r["test_id"])
                        ),
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
                    for r in sub_rows
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
            if cds in pct_hist_by_kind[kind]:
                payload["pct_hist"] = pct_hist_by_kind[kind][cds]
            if cds in stu_hist_by_kind[kind]:
                payload["stu_hist"] = stu_hist_by_kind[kind][cds]
            if kind == "schools":
                payload["address"] = addr_map.get(cds)
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
                if cds[:7] in virt_auth:
                    payload["virtual_auth"] = virt_auth[cds[:7]]
            else:
                payload["district_has_page"] = payload["district_cds"] in district_pages
                payload["county_has_page"] = payload["county_cds"] in county_pages
            calc = _adj_calc(
                eff_by_cds.get(cds, {}),
                gammas_by_kind[payload["kind"]],
                xbar_by_kind[payload["kind"]],
            )
            if calc is not None:
                payload["adj_calc"] = calc
            (SITE_DATA / kind / f"{cds}.json").write_text(json.dumps(payload))
            written[kind] += 1
            eff = payload["effects"]
            full_eff = eff_by_cds.get(cds, {})

            # Per-subject levels via the fitted subject gap (math - ela):
            # ela = level - gap/2, math = level + gap/2, for raw and adjusted alike.
            def _split(level, full_eff=full_eff):
                gap = full_eff.get("subj_gap")
                if level is None:
                    return None, None
                if gap is None:
                    return round(level, 2), round(level, 2)
                return round(level - gap / 2, 2), round(level + gap / 2, 2)

            raw_ela, raw_math = _split(eff.get("level_eb"))
            adj_ela, adj_math = _split(eff.get("level_adj_eb"))

            spark = g1["spark"]
            last_year = g1["last_year"]

            for gid in BESTFOR_GROUPS:
                gs = _group_stats(
                    [r for r in sub_rows if r["student_group_id"] == gid]
                )
                if gs["last_year"] is None:
                    continue
                gap = (
                    round(gs["combined_latest"] - g1["combined_latest"], 1)
                    if gs["combined_latest"] is not None
                    and g1["combined_latest"] is not None
                    and gs["last_year"] == g1["last_year"]
                    else None
                )
                group_tables.setdefault(gid, []).append(
                    {
                        "cds": cds,
                        "kind": payload["kind"],
                        "name": payload["name"],
                        "district": nrow["district_name"],
                        "county": nrow["county_name"],
                        "eil": eil_map.get(cds) if kind == "schools" else None,
                        "flags": flags_map.get(cds) if kind == "schools" else None,
                        "pass_ela": gs["pass_ela"],
                        "pass_math": gs["pass_math"],
                        "n": gs["n_latest"],
                        "gap": gap,
                        "spark": gs["spark"],
                        "last_year": gs["last_year"],
                        "enrollment": census_map.get(cds),
                        "econ": frpm_pop_share.get(cds),
                    }
                )

            index.append(
                {
                    "cds": cds,
                    "kind": payload["kind"],
                    "name": payload["name"],
                    "district": nrow["district_name"],
                    "district_cds": payload["district_cds"],
                    "county": nrow["county_name"],
                    "county_cds": payload["county_cds"],
                    "eil": eil_map.get(cds) if kind == "schools" else None,
                    "flags": flags_map.get(cds) if kind == "schools" else None,
                    "level_eb": eff.get("level_eb"),
                    "level_adj_eb": eff.get("level_adj_eb"),
                    "adj_lcb": eff.get("level_adj_lcb"),
                    "raw_ela": raw_ela,
                    "raw_math": raw_math,
                    "adj_ela": adj_ela,
                    "adj_math": adj_math,
                    "pass_ela": g1["pass_ela"],
                    "pass_math": g1["pass_math"],
                    "tested": tested_map.get((cds, last_year)),
                    "last_year": last_year,
                    "growth_adj_eb": eff.get("growth_adj_eb"),
                    "growth_lcb": eff.get("growth_adj_lcb"),
                    # Within-cohort movement (growth + trend): the slope a
                    # class actually experiences vs the state as it moves up.
                    "growth_eb": eff.get("move_eb"),
                    "trend_eb": eff.get("trend_eb"),
                    # Stripped before writing — used only for percentile/peer gating.
                    "_lrel": eff.get("level_reliability"),
                    "_grel": eff.get("growth_reliability"),
                    "_gse": eff.get("move_se"),
                    "_mrel": eff.get("move_reliability"),
                    "_trel": full_eff.get("trend_reliability"),
                    "_ly": eff.get("last_year"),
                    # Similar Student level: the demographic prediction from
                    # the adjustment regression (level minus residual, OLS —
                    # deterministic given composition). Its percentile says
                    # where students with this entity's demographic profile
                    # would be expected to score statewide; prediction +
                    # residual = observed level, so the three percentiles
                    # (similar-student, raw, similar-schools) decompose.
                    # Similar Student: fitted level minus the WITHIN-school
                    # student-composition effect, ranked at its shrunken-band
                    # lower bound like the other percentiles.
                    "_simstu": (
                        round(
                            eff["level_eb"] - stud_eff_map[cds]
                            - 1.96
                            * ((eff.get("level_reliability") or 1) ** 0.5)
                            * (full_eff.get("level_se") or 0),
                            3,
                        )
                        if eff.get("level_eb") is not None and cds in stud_eff_map
                        else None
                    ),
                    "_ssl": (
                        round(full_eff["level"] - full_eff["level_adj"], 3)
                        if full_eff.get("level") is not None
                        and full_eff.get("level_adj") is not None
                        else None
                    ),
                    # Full-population FRPM share (all enrolled students). No
                    # fallback to the tested-SED share: the two definitions
                    # disagree by ±5pp at ~30% of high schools (see known issue
                    # sed-vs-frpm-measure-divergence), so a "% FRPM" column must
                    # not silently mix them — missing stays missing.
                    "econ": frpm_pop_share.get(cds),
                    "ppe": ppe_map.get(cds),
                    "enrollment": census_map.get(cds),
                    "total_scores": eff.get("total_scores"),
                    "ll": latlon_map.get(cds),
                    "spark": spark,
                    "enr": (
                        [enr_hist[cds].get(y) for y in ENR_YEARS]
                        if cds in enr_hist
                        else None
                    ),
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
            "adj_lcb": e["adj_lcb"],
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
    # LCFF vs basic-aid funding status per district (from the LCFF summary
    # files' latest certification) — displayed alongside spending.
    from schoolfactors.analysis.lausd_export import lcff_funding_flags

    con_lcff = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    funding_flags = lcff_funding_flags(con_lcff)
    con_lcff.close()

    for dcds in district_pages:
        path = SITE_DATA / "districts" / f"{dcds}.json"
        d = json.loads(path.read_text())
        d["schools"] = sorted(by_district.get(dcds, []), key=lambda s: s["name"] or "")
        if dcds in funding_flags:
            d["lcff_status"] = funding_flags[dcds]
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

    (SITE_DATA / "groups").mkdir(exist_ok=True)
    for gid, rows in group_tables.items():
        (SITE_DATA / "groups" / f"{gid}.json").write_text(json.dumps(rows))
    print(f"  best-for tables: {len(group_tables)} groups "
          f"({sum(len(v) for v in group_tables.values()):,} rows)")

    # Percentile presentation of the adjusted estimates (in the spirit of the
    # Urban Institute's demographically adjusted rankings): midrank percentile
    # among entities of the same kind, computed on the LOWER bound of the 95%
    # band around the shrunken residual — an unconfident high estimate ranks
    # below a confident slightly-lower one. Gated on reliability >= 0.70
    # (SEDA's rule — an estimate that is mostly noise gets no percentile) and
    # on having modeled data in the statewide latest year: the level is
    # recency-weighted, so for a school whose data stopped years ago it
    # describes a school that may no longer exist in that form. The underlying
    # student-SD values stay in the payloads; this is display only.
    #
    # School percentile pools additionally split alternative programs
    # (continuation, community day, court, special-ed) from the general pool:
    # they land in the bottom decile 68% of the time on student selection
    # rather than performance — occupying the basement of a shared ranking and
    # getting meaningless ranks themselves. Selective (exam-admission) schools
    # stay in the general pool, badged: their percentile is expected to sit at
    # the top on admissions alone, so a selective school NOT near the top is
    # itself informative — and with only a handful of curated entries, a
    # separate pool would fall below the 20-school minimum and show nothing.
    # Magnet and charter schools also stay: they serve general-education
    # populations and the covariates carry their composition.
    def pool_class(e: dict) -> str:
        if e["kind"] != "school":
            return ""
        t = school_type_map.get(e["cds"], "standard")
        return "alternative" if t == "alternative" else "general"

    HIST_LO, HIST_W, HIST_N = -1.6, 0.1, 32
    POOL_LABEL = {
        ("school", "general"): "schools (general programs)",
        ("school", "alternative"): "alternative schools",
        ("district", ""): "districts",
        ("county", ""): "counties",
    }
    latest_by_kind: dict[str, int | None] = {}
    for kind_ in ("school", "district", "county"):
        latest = max(
            (e["_ly"] for e in index if e["kind"] == kind_ and e.get("_ly")),
            default=None,
        )
        latest_by_kind[kind_] = latest
        classes = sorted({pool_class(e) for e in index if e["kind"] == kind_})
        for cls in classes:
            for src, rel_key, out in (
                ("adj_lcb", "_lrel", "adj_pct"),
                ("growth_lcb", "_grel", "growth_pct"),
                # Similar Student %ile: expected-outcome ranking for a fixed
                # student profile (peer composition credited to the school).
                ("_ssl", "_lrel", "stu_pct"),
                # Similar Student %ile: conditional expectation for a fixed
                # student profile — the parent decision ranking.
                ("_simstu", "_lrel", "simstu_pct"),
            ):
                def eligible(
                    e, kind_=kind_, cls=cls, src=src, rel_key=rel_key, latest=latest
                ):
                    return (
                        e["kind"] == kind_
                        and pool_class(e) == cls
                        and e.get(src) is not None
                        and (e.get(rel_key) or 0) >= 0.7
                        and e.get("_ly") == latest
                    )

                pool = sorted(e[src] for e in index if eligible(e))
                if len(pool) < 20:
                    continue
                # The Similar Schools pool itself (histogram of ranked lower
                # bounds) travels with each member, so its page can show
                # where the entity's value sits among the values it was
                # ranked against.
                if src == "adj_lcb":
                    bins = [0] * HIST_N
                    for v in pool:
                        bins[min(HIST_N - 1, max(0, int((v - HIST_LO) / HIST_W)))] += 1
                    pool_hist = {
                        "lo": HIST_LO,
                        "w": HIST_W,
                        "bins": bins,
                        "n": len(pool),
                        "label": POOL_LABEL[(kind_, cls)],
                    }
                for e in index:
                    if eligible(e):
                        lo = bisect.bisect_left(pool, e[src])
                        hi = bisect.bisect_right(pool, e[src])
                        e[out] = min(
                            99, max(1, round(100 * (lo + hi) / 2 / len(pool)))
                        )
                        if src == "adj_lcb":
                            e["_pool"] = {**pool_hist, "below": lo, "tied": hi - lo}

    # Cohort trajectory verdict — the display form of growth. A percentile of
    # growth amplifies near-zero differences (tau is only 0.066 SD/grade) into
    # grades, and reads "holding at a high level" as mediocrity. Instead:
    # gaining/holding/slipping vs the STATE (raw growth), called only when the
    # 95% posterior band clears zero AND the point estimate exceeds a 0.02
    # SD/grade practical floor; gated like the percentiles (reliability >= 0.70,
    # current-year data). Posterior sd = sqrt(reliability) * se — shrinkage
    # already removed noise, so the raw se would double-count it.
    for e in index:
        eb = e.get("growth_eb")
        se = e.get("_gse")
        rel = e.get("_mrel") or 0
        if (
            eb is None
            or se is None
            or rel < 0.7
            or e.get("_ly") != latest_by_kind.get(e["kind"])
        ):
            e["growth_cat"] = None
            continue
        half = 1.96 * (rel**0.5) * se
        if eb - half > 0 and eb >= 0.02:
            e["growth_cat"] = "gaining"
        elif eb + half < 0 and eb <= -0.02:
            e["growth_cat"] = "slipping"
        else:
            e["growth_cat"] = "holding"

    # Absolute yearly improvement for the peer scatter. Cohort growth cannot be
    # made absolute — scores are standardized within year x grade, so the
    # state's own within-cohort motion is zero by construction. Trend can:
    # standardize the state's means against a FIXED (pooled-across-years)
    # benchmark per grade x subject and fit a year slope; adding that to each
    # entity's state-relative trend yields improvement per year in absolute
    # terms, and the state itself gets a dot at (0, state_slope).
    import numpy as np

    st = state.join(sigma, on=["test_year", "grade", "test_id"], how="inner")
    st = st.with_columns(
        (
            (pl.col("state_mean") - pl.col("state_mean").mean().over(["grade", "test_id"]))
            / pl.col("sigma")
        ).alias("z_fixed")
    )
    state_slope = float(
        np.polyfit(st["test_year"].to_numpy(), st["z_fixed"].to_numpy(), 1)[0]
    )
    print(f"  state absolute trend: {state_slope:+.4f} SDs/year")

    # Absolute cohort movement: scores normalized against the fixed
    # on-grade-level ("Standard Met") threshold rather than the state mean, so
    # a cohort's slope across grades is meaningful in absolute terms and the
    # state itself has one — the average California cohort's drift vs
    # standards. Per-entity value = state-relative growth + this state slope.
    cuts = sigma.group_by(["grade", "test_id"]).agg(pl.col("cut").median().alias("cut_med"))
    stc = (
        state.join(sigma, on=["test_year", "grade", "test_id"], how="inner")
        .join(cuts, on=["grade", "test_id"], how="inner")
        .with_columns(
            ((pl.col("state_mean") - pl.col("cut_med")) / pl.col("sigma")).alias("z_std"),
            (pl.col("test_year") + 12 - pl.col("grade")).alias("grad_year"),
        )
        .with_columns(
            (pl.col("grade") - pl.col("grade").mean().over(["grad_year", "test_id"])).alias("gd"),
            (pl.col("z_std") - pl.col("z_std").mean().over(["grad_year", "test_id"])).alias("zd"),
        )
    )
    state_cohort_slope = float(
        (stc["gd"] * stc["zd"]).sum() / (stc["gd"] ** 2).sum()
    )
    print(f"  state cohort movement vs standards: {state_cohort_slope:+.4f} SDs/grade")

    # Trend passes the same gates as the percentiles (reliability >= 0.70,
    # current-year data). It backs the y-axis of the peer scatter.
    def trend_ok(e: dict) -> bool:
        return (
            e.get("trend_eb") is not None
            and (e.get("_trel") or 0) >= 0.7
            and e.get("_ly") == latest_by_kind.get(e["kind"])
        )

    # Peer histograms for the page summary card: adjusted level among entities
    # of the same kind — for schools, additionally the same level and type
    # (selective/magnet/charter/alternative/standard, mirroring the map legend
    # in site maptypes.js) — in student SDs. Fixed common bins keep every
    # histogram comparable; outliers clamp into the end bins.
    EIL_WORD = {"ELEM": "elementary", "INTMIDJR": "middle", "HS": "high",
                "ELEMHIGH": "K-12"}

    def peer_key(e: dict) -> tuple:
        if e["kind"] == "school":
            return ("school", EIL_WORD.get(e.get("eil"), "other"), school_type(e.get("flags")))
        return (e["kind"],)

    def peer_label(key: tuple) -> str:
        if key[0] == "school":
            lvl, typ = key[1], key[2]
            lvl_part = f"{lvl} schools" if lvl != "other" else "schools"
            if typ == "standard":
                return lvl_part
            if typ == "choice":
                return f"{lvl_part} of choice"
            return f"{typ} {lvl_part}"
        return "districts" if key[0] == "district" else "counties"

    peer_bins: dict[tuple, list[int]] = {}
    for e in index:
        v = e.get("level_adj_eb")
        if v is None:
            continue
        b = min(HIST_N - 1, max(0, int((v - HIST_LO) / HIST_W)))
        peer_bins.setdefault(peer_key(e), [0] * HIST_N)[b] += 1
    adj_by_cds = {e["cds"]: e.get("level_adj_eb") for e in index}
    trend_by_cds = {e["cds"]: e.get("trend_eb") for e in index}
    growth_by_cds = {e["cds"]: e.get("growth_eb") for e in index}

    # Peer scatter files (data/peers/{key}.json): every peer whose level gate
    # passed and that has at least one gated y-measure, as [cds, name,
    # adjusted level, absolute cohort movement/yr | null,
    # absolute improvement/yr | null, [lat, lon] | null]. Cohort movement
    # (vs the fixed Standard Met threshold) carries the trajectory-verdict
    # gates; yearly improvement carries trend_ok. Coordinates let the page
    # narrow the cloud to nearby schools client-side. Shared per peer group,
    # so the clouds are cached across pages instead of inlined into 11k
    # prerendered documents.
    def peer_file_key(e: dict) -> str:
        k = peer_key(e)
        return "-".join(k) if k[0] == "school" else k[0]

    peers_dir = SITE_DATA / "peers"
    peers_dir.mkdir(exist_ok=True)
    peer_rows: dict[str, list] = {}
    for e in index:
        t_ok = trend_ok(e)
        g_ok = e.get("growth_cat") is not None and e.get("growth_eb") is not None
        if e.get("adj_pct") is None or not (t_ok or g_ok):
            continue
        peer_rows.setdefault(peer_file_key(e), []).append(
            [
                e["cds"],
                e["name"],
                e["level_adj_eb"],
                round(e["growth_eb"] + state_cohort_slope, 4) if g_ok else None,
                round(e["trend_eb"] + state_slope, 4) if t_ok else None,
                e.get("ll"),
            ]
        )
    for k, prows in peer_rows.items():
        (peers_dir / f"{k}.json").write_text(json.dumps(prows))
    print(f"  peer scatter files: {len(peer_rows)} groups "
          f"({sum(len(v) for v in peer_rows.values()):,} points)")

    # vs-similar benchmark: each entity's groups pooled against its band of
    # similar entities (same kind, model-predicted level within ±0.15 SD;
    # widened to the nearest 15 when sparse). Statewide group averages are the
    # wrong bar in strongly (dis)advantaged communities — this is the
    # comparison that actually explains an extreme adjusted placement, and it
    # includes Exceeded because a shortfall can live entirely in the top band.
    vs_by_cds: dict[str, dict] = {}
    for pool in vs_pool.values():
        pool.sort(key=lambda r: r["pred"])
        preds = np.array([r["pred"] for r in pool])
        cums = {}
        for g in VS_SIMILAR_GROUPS:
            metn = np.zeros(len(pool))
            nn = np.zeros(len(pool))
            excn = np.zeros(len(pool))
            en = np.zeros(len(pool))
            for k, r in enumerate(pool):
                pr = r["rates"].get(g)
                if pr:
                    metn[k] = pr["met"] * pr["n"]
                    nn[k] = pr["n"]
                    if pr["exc"] is not None:
                        excn[k] = pr["exc"] * pr["n"]
                        en[k] = pr["n"]
            cums[g] = tuple(
                np.concatenate(([0.0], np.cumsum(a))) for a in (metn, nn, excn, en)
            )
        for i, r in enumerate(pool):
            lo = int(np.searchsorted(preds, r["pred"] - 0.15, "left"))
            hi = int(np.searchsorted(preds, r["pred"] + 0.15, "right"))
            n_band = hi - lo - 1
            use_window = n_band >= 15
            if not use_window:
                order = [int(k) for k in np.argsort(np.abs(preds - r["pred"])) if k != i][:15]
            rows_out = []
            for g in VS_SIMILAR_GROUPS:
                own = r["rates"].get(g)
                if not own or own["n"] < 30:
                    continue
                if use_window:
                    cm, cn, ce, cen = cums[g]
                    ms = cm[hi] - cm[lo] - own["met"] * own["n"]
                    mn = cn[hi] - cn[lo] - own["n"]
                    es = ce[hi] - ce[lo]
                    en_ = cen[hi] - cen[lo]
                    if own["exc"] is not None:
                        es -= own["exc"] * own["n"]
                        en_ -= own["n"]
                else:
                    ms = mn = es = en_ = 0.0
                    for k in order:
                        pr = pool[k]["rates"].get(g)
                        if not pr:
                            continue
                        ms += pr["met"] * pr["n"]
                        mn += pr["n"]
                        if pr["exc"] is not None:
                            es += pr["exc"] * pr["n"]
                            en_ += pr["n"]
                if mn < 300:
                    continue
                rows_out.append(
                    {
                        "g": g,
                        "met": round(own["met"], 1),
                        "p_met": round(ms / mn, 1),
                        "exc": round(own["exc"], 1) if own["exc"] is not None else None,
                        "p_exc": round(es / en_, 1) if en_ else None,
                    }
                )
            if rows_out:
                vs_by_cds[r["cds"]] = {
                    "n": n_band if use_window else len(order),
                    "rows": rows_out,
                }

    # Percentiles and peer histograms are computed cross-entity above, so they
    # land in the page payloads here: the entity-page summary card reads them.
    kind_dir = {"school": "schools", "district": "districts", "county": "counties"}
    for e in index:
        updates = {
            k: e[k]
            for k in ("adj_pct", "growth_pct", "growth_cat", "stu_pct", "simstu_pct")
            if e.get(k) is not None
        }
        key = peer_key(e)
        if e.get("level_adj_eb") is not None and key in peer_bins:
            bins = peer_bins[key]
            updates["peer_hist"] = {
                "lo": HIST_LO,
                "w": HIST_W,
                "bins": bins,
                "label": peer_label(key),
                "n": sum(bins),
            }
            if e["kind"] == "school":
                refs = (("district_ref", e["district_cds"]), ("county_ref", e["county_cds"]))
            elif e["kind"] == "district":
                refs = (("county_ref", e["county_cds"]),)
            else:
                refs = ()
            for rk, rc in refs:
                rv = adj_by_cds.get(rc)
                if rv is not None:
                    updates[rk] = rv
                    rt = trend_by_cds.get(rc)
                    if rt is not None:
                        updates[rk + "_trend_abs"] = round(rt + state_slope, 4)
                    rg = growth_by_cds.get(rc)
                    if rg is not None:
                        updates[rk + "_growth_abs"] = round(rg + state_cohort_slope, 4)
            updates["peer_key"] = peer_file_key(e)
            updates["state_trend"] = round(state_slope, 4)
            updates["state_growth"] = round(state_cohort_slope, 4)
            if e.get("ll"):
                updates["ll"] = e["ll"]
            if trend_ok(e):
                updates["trend_abs"] = round(e["trend_eb"] + state_slope, 4)
            if e.get("growth_cat") is not None and e.get("growth_eb") is not None:
                updates["growth_abs"] = round(e["growth_eb"] + state_cohort_slope, 4)
        if e["cds"] in vs_by_cds:
            updates["vs_similar"] = vs_by_cds[e["cds"]]
        if e.get("_pool") is not None:
            updates["adj_pool"] = e["_pool"]
        if not updates:
            continue
        path = SITE_DATA / kind_dir[e["kind"]] / f"{e['cds']}.json"
        d = json.loads(path.read_text())
        d.update(updates)
        path.write_text(json.dumps(d))

    for e in index:
        e.pop("_lrel", None)
        e.pop("_grel", None)
        e.pop("_gse", None)
        e.pop("_mrel", None)
        e.pop("_trel", None)
        e.pop("_ly", None)
        e.pop("_ssl", None)
        e.pop("_simstu", None)
        e.pop("_pool", None)

    (SITE_DATA / "index.json").write_text(json.dumps(index))
    print(f"  wrote {written['schools']:,} school pages, {written['districts']:,} district pages")
    print(f"  index.json: {len(index):,} entries")

    summary = {
        "n_schools_modeled": len(schools),
        "n_districts_modeled": len(districts),
        "n_counties_modeled": len(counties),
        "years": [2015, 2016, 2017, 2018, 2019, 2022, 2023, 2024, 2025],
        "corr_raw_level_econ": -0.74,
        "corr_adjusted_level_econ": -0.003,
        "falsification_growth_vs_level": -0.012,
    }
    (SITE_DATA / "summary.json").write_text(json.dumps(summary, indent=1))
    print("  summary.json written")

    from schoolfactors.analysis.og_images import generate_og_images

    n_og = generate_og_images(index, REPO_ROOT / "site" / "static" / "og")
    print(f"  og share images: {n_og:,} written")

    # District data-story exports (reads index.json + district payload written above).
    from schoolfactors.analysis.lausd_export import export_lausd

    print("exporting /lausd data story …")
    export_lausd()

    # Statewide enrollment import/export exports (reads index.json + the
    # enrollment_flows parquets; stamps `enroll` on entity payloads above).
    from schoolfactors.analysis.enrollment_export import export_enrollment

    print("exporting /enrollment data …")
    export_enrollment()
