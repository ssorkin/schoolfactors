"""Site data exports for /enrollment: statewide district import/export accounting.

Reads the parquets built by analysis/enrollment_flows.py and writes, under
site/static/data/enrollment/:

    index.json           compact {cols, rows} join table: one row per district area
                         (unified/elementary/secondary) and per county — drives the
                         landing choropleth, search routing, and prerender entries()
    boundaries_{u,e,h}.geojson   simplified statewide polygons, properties {"g": geoid}
                         ONLY (values join client-side from index.json by geoid, so
                         map fills and popups can never disagree with the data)
    districts/{cds}.json per-district detail: vintage series, schools, neighbors,
                         ACS1 overlay (large unified only), performance history
    counties/{cds}.json  county detail: series, member districts, ACS1 overlay
    meta.json            per-vintage calibration + closure, siting counts — the
                         methodology page's numbers source

Also stamps `enroll: 1` on the main district/county entity payloads that have an
enrollment page, so entity pages can cross-link.

Sign convention: positive = net importer. All flows are net accounting residuals,
never observed transfers; copy on the site must keep the "modeled" framing.
"""

from __future__ import annotations

import json

import duckdb
import polars as pl

from schoolfactors.analysis import enrollment_flows as ef
from schoolfactors.analysis import enrollment_geo as eg
from schoolfactors.paths import DUCKDB_PATH, PARQUET_DIR, REPO_ROOT

SITE_DATA = REPO_ROOT / "site" / "static" / "data"
ENROLL_DIR = SITE_DATA / "enrollment"

# Springs sampled for the per-school mini-sparkline (plus the latest spring).
SCHOOL_SPARK_SPRINGS = (2006, 2010, 2014, 2018, 2022)


def _r(x: float | None, nd: int = 0) -> float | int | None:
    if x is None:
        return None
    return round(x, nd) if nd else round(x)


def _county_cds(code: str) -> str:
    return code + "0" * 12


def _site_names() -> tuple[dict[str, str], dict[str, float], dict[str, str]]:
    """(name, similar-student percentile, county code) per cds from the main index."""
    index_path = SITE_DATA / "index.json"
    names: dict[str, str] = {}
    perf: dict[str, float] = {}
    county: dict[str, str] = {}
    if index_path.exists():
        for e in json.loads(index_path.read_text()):
            if e.get("kind") in ("district", "county"):
                names[e["cds"]] = e.get("name")
                county[e["cds"]] = e["cds"][:2]
                if e.get("simstu_pct") is not None:
                    perf[e["cds"]] = e["simstu_pct"]
    return names, perf, county


def _perf_history() -> dict[str, list[list]]:
    """cds -> [[as_of_year, Similar Student percentile]] — the parent-facing
    measure (conditional expectation for a fixed student profile), per cutoff
    year. Districts ranked among districts, counties among counties."""
    out: dict[str, list[list]] = {}
    for kind in ("district", "county"):
        path = PARQUET_DIR / "analysis" / f"{kind}_simstu_history.parquet"
        if not path.exists():
            continue
        hist = pl.read_parquet(path).with_columns(
            (
                pl.col("simstu").rank("average").over("as_of_year")
                / pl.col("simstu").count().over("as_of_year")
                * 100
            ).alias("pct")
        )
        for cds, y, p in hist.select("cds", "as_of_year", "pct").sort(
            "as_of_year"
        ).iter_rows():
            out.setdefault(cds, []).append([int(y), round(p, 1)])
    return out


def export_enrollment() -> None:
    if not ef.FLOWS_PARQUET.exists():
        print("  enrollment export: flows parquet missing — skipped")
        return
    con = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    try:
        flows = pl.read_parquet(ef.FLOWS_PARQUET)
        calib = pl.read_parquet(ef.CALIB_PARQUET)
        acs1 = pl.read_parquet(ef.ACS1_PARQUET)
        seats = pl.read_parquet(ef.SEATS_PARQUET)
        adjacency = pl.read_parquet(eg.ADJACENCY_PARQUET)
        cuts = pl.read_parquet(eg.CUTS_PARQUET)
        xwalk = ef.district_crosswalk(con)
        school_names = dict(
            con.execute(
                "SELECT cds, any_value(school) FROM directory_raw "
                "WHERE substr(cds, 8, 7) <> '0000000' GROUP BY cds"
            ).fetchall()
        )
    finally:
        con.close()

    geo = {lvl: eg.load_district_geometries(lvl) for lvl in eg.LEVELS}
    names, perf_now, _ = _site_names()
    perf_hist = _perf_history()
    geoid_cds = {g: d + "0000000" for g, d in xwalk.select("geoid", "dcds").iter_rows()}
    vintages = sorted(calib["vintage"].to_list())
    m_rows = [[int(v), round(m, 4)] for v, m in calib.select("vintage", "m").iter_rows()]
    m_band = {
        int(v): (lo, up)
        for v, lo, up in calib.select("vintage", "m_lo", "m_up").iter_rows()
    }

    def bandsplit(series: list[dict]) -> dict | None:
        """K-8 / 9-12 residual diagnostic for the latest live window of a
        unified area: residents minus band-calibrated local seats minus the
        age-matched remote allocation (before the county adjustment)."""
        live = [
            r for r in series
            if r["net"] is not None and r.get("res_lo") and r.get("res_up")
            and r.get("seats_lo") is not None and r.get("seats_up") is not None
        ]
        if not live:
            return None
        r = live[-1]
        ml, mu = m_band.get(int(r["vintage"]), (None, None))
        if ml is None or mu is None:
            return None
        glo = r["res_lo"] - r["seats_lo"] * (1 - ml) - (r["ralloc_lo"] or 0)
        gup = r["res_up"] - r["seats_up"] * (1 - mu) - (r["ralloc_up"] or 0)
        return {
            "v": int(r["vintage"]),
            "lo": _r(glo), "lo_pct": _r(glo / r["res_lo"], 3),
            "up": _r(gup), "up_pct": _r(gup / r["res_up"], 3),
        }

    ENROLL_DIR.mkdir(parents=True, exist_ok=True)
    (ENROLL_DIR / "districts").mkdir(exist_ok=True)
    (ENROLL_DIR / "counties").mkdir(exist_ok=True)

    # --- boundaries ------------------------------------------------------
    for key, fc in eg.export_boundaries(geo).items():
        (ENROLL_DIR / f"boundaries_{key}.geojson").write_text(json.dumps(fc))

    # --- index -----------------------------------------------------------
    flows_by_geoid: dict[tuple[str, str], list[dict]] = {}
    for row in flows.sort("vintage").to_dicts():
        flows_by_geoid.setdefault((row["level"], row["geoid"]), []).append(row)

    def latest_with_net(series: list[dict]) -> dict | None:
        live = [r for r in series if r["net"] is not None]
        return live[-1] if live else None

    def change_cols(series: list[dict], last: dict | None) -> tuple:
        """(res_chg, seats_chg) from the 2009-13 window to the latest one."""
        base = next((r for r in series if r["vintage"] == 2013 and r["res_pub"]), None)
        if not base or not last or not last["res_pub"]:
            return None, None
        seats0 = base["seats_dr"] + base["seats_caff"] + base["seats_cbm"]
        seats1 = last["seats_dr"] + last["seats_caff"] + last["seats_cbm"]
        return (
            _r(last["res_pub"] / base["res_pub"] - 1, 4),
            _r(seats1 / seats0 - 1, 4) if seats0 else None,
        )

    cut_map = dict(cuts.select("geoid", "cut").iter_rows())
    index_rows: list[list] = []
    level_key = {"unified": "u", "elementary": "e", "secondary": "h"}
    for lvl in eg.LEVELS:
        ids, _, props = geo[lvl]
        for gid, p in zip(ids, props):
            series = flows_by_geoid.get((level_key[lvl], gid), [])
            last = latest_with_net(series)
            cds = geoid_cds.get(gid)
            name = names.get(cds) or p["name"]
            spark = {r["vintage"]: r["net_rate"] for r in series}
            # Tiny districts can have an enrollment page but no standard
            # (performance) page; links must be gated or the prerender 404s.
            std = 1 if cds and (SITE_DATA / "districts" / f"{cds}.json").exists() else 0
            index_rows.append(
                [
                    gid,
                    cds,
                    name,
                    level_key[lvl],
                    cds[:2] if cds else None,
                    [_r(p["lat"], 4), _r(p["lon"], 4)],
                    _r(last["net_rate"], 4) if last else None,
                    _r(last["res_moe"] / last["res_pub"], 4)
                    if last and last["res_pub"]
                    else None,
                    _r(last["res_pub"]) if last else None,
                    _r(last["seats_dr"] + last["seats_caff"] + last["seats_cbm"]) if last else None,
                    _r(last["virt_alloc"] / last["res_pub"], 4)
                    if last and last["res_pub"] and last["virt_alloc"] is not None
                    else None,
                    _r(perf_now.get(cds), 1) if cds else None,
                    [_r(spark.get(v), 4) for v in vintages],
                    *change_cols(series, last),
                    std,
                ]
            )
    # county rows: geoid = 2-digit CDE county code; centroid = mean of members'.
    county_centroids: dict[str, list] = {}
    for row in index_rows:
        if row[4] and row[5][0] is not None:
            county_centroids.setdefault(row[4], []).append(row[5])
    for code in sorted(flows.filter(pl.col("level") == "c")["geoid"].unique().to_list()):
        series = flows_by_geoid.get(("c", code), [])
        last = latest_with_net(series)
        cds = _county_cds(code)
        pts = county_centroids.get(code, [])
        ll = (
            [_r(sum(p[0] for p in pts) / len(pts), 4),
             _r(sum(p[1] for p in pts) / len(pts), 4)]
            if pts
            else [None, None]
        )
        spark = {r["vintage"]: r["net_rate"] for r in series}
        index_rows.append(
            [
                code,
                cds,
                names.get(cds) or f"County {code}",
                "c",
                code,
                ll,
                _r(last["net_rate"], 4) if last else None,
                _r(last["res_moe"] / last["res_pub"], 4)
                if last and last["res_pub"]
                else None,
                _r(last["res_pub"]) if last else None,
                _r(last["seats_dr"] + last["seats_caff"] + last["seats_cbm"]) if last else None,
                _r(last["virt_alloc"] / last["res_pub"], 4)
                if last and last["res_pub"] and last["virt_alloc"] is not None
                else None,
                _r(perf_now.get(cds), 1),
                [_r(spark.get(v), 4) for v in vintages],
                *change_cols(series, last),
                1,
            ]
        )
    index_payload = {
        "cols": ["geoid", "cds", "name", "dtype", "county", "ll", "net_rate",
                 "net_moe", "res", "seats", "virt_share", "perf", "spark",
                 "res_chg", "seats_chg", "std"],
        "vintages": vintages,
        "rows": index_rows,
    }
    (ENROLL_DIR / "index.json").write_text(json.dumps(index_payload))
    print(f"  enrollment/index.json: {len(index_rows):,} rows")

    # --- per-school payload pieces ----------------------------------------
    latest_spring = int(seats["spring"].max())
    spark_springs = [*SCHOOL_SPARK_SPRINGS, latest_spring]
    seats_by_area: dict[tuple[str, str], set[str]] = {}
    for col, lk in (("unified_geoid", "u"), ("elem_geoid", "e"), ("sec_geoid", "h")):
        for gid, cds in (
            seats.filter(pl.col(col).is_not_null()).select(col, "cds").unique().iter_rows()
        ):
            seats_by_area.setdefault((lk, gid), set()).add(cds)
    school_class = dict(
        seats.group_by("cds").agg(pl.col("class").first()).iter_rows()
    )
    sit = pl.read_parquet(eg.SITING_PARQUET).select("cds", "lat", "lon", "sited")
    sit_map = {r["cds"]: r for r in sit.to_dicts()}
    totals_by_school: dict[str, dict[int, float]] = {}
    for cds, spring, tot in seats.select("cds", "spring", "total").iter_rows():
        totals_by_school.setdefault(cds, {})[spring] = tot

    def school_entry(cds: str) -> list | None:
        tots = totals_by_school.get(cds, {})
        if not tots:
            return None
        srow = sit_map.get(cds, {})
        latest = tots.get(latest_spring)
        cls = school_class.get(cds, "district_run")
        return [
            cds,
            school_names.get(cds),
            cls,
            _r(srow.get("lat"), 5),
            _r(srow.get("lon"), 5),
            _r(latest) if latest is not None else None,
            [_r(tots.get(s)) if tots.get(s) is not None else None for s in spark_springs],
            srow.get("sited"),
            # Closed/historical schools have no /school page; links must be gated
            # or the prerender crawler 404s.
            1 if (SITE_DATA / "schools" / f"{cds}.json").exists() else 0,
        ]

    neighbors_map: dict[str, set[str]] = {}
    for g, n, _band in adjacency.iter_rows():
        neighbors_map.setdefault(g, set()).add(n)

    acs1_map: dict[tuple[str, str], list[list]] = {}
    for r in acs1.sort("year").to_dicts():
        acs1_map.setdefault((r["level"], r["geoid"]), []).append(
            [int(r["year"]), _r(r["pub"]), _r(r["pub_moe"]),
             _r(r["cde_straddle"]) if r["cde_straddle"] is not None else None]
        )

    def series_payload(series: list[dict]) -> list[dict]:
        return [
            {
                "v": int(r["vintage"]),
                "n": int(r["n_springs"]),
                "res": {
                    "pub": _r(r["res_pub"]),
                    "priv": _r(r["res_priv"]),
                    "noten": _r(r["res_noten"]),
                    "total": _r(r["res_total"]),
                    "pub_moe": _r(r["res_moe"]),
                },
                "seats": {"dr": _r(r["seats_dr"]), "aff": _r(r["seats_caff"]),
                          "cbm": _r(r["seats_cbm"]), "virt": _r(r["seats_virt"])},
                "virt": _r(r["virt_alloc"]),
                "ooc": _r(r["ooc_alloc"]) if r.get("ooc_alloc") is not None else None,
                "net": _r(r["net"]),
                "rate": _r(r["net_rate"], 4),
                "cf": round(r["factor"], 4) if r["factor"] and r["factor"] != 1.0 else None,
            }
            for r in series
        ]

    # --- district pages ----------------------------------------------------
    n_pages = 0
    for lvl in eg.LEVELS:
        lk = level_key[lvl]
        ids, _, props = geo[lvl]
        for gid, p in zip(ids, props):
            cds = geoid_cds.get(gid)
            if not cds:
                continue
            series = flows_by_geoid.get((lk, gid), [])
            if not any(r["net"] is not None for r in series):
                continue
            schools = sorted(
                filter(None, (school_entry(c) for c in seats_by_area.get((lk, gid), set()))),
                key=lambda s: -(s[5] or 0),
            )
            payload = {
                "meta": {
                    "geoid": gid,
                    "cds": cds,
                    "name": names.get(cds) or p["name"],
                    "dtype": lk,
                    "county": cds[:2],
                    "county_name": names.get(_county_cds(cds[:2])) or f"County {cds[:2]}",
                    "cut": cut_map.get(gid),
                    "grades": [p["lograde"], p["higrade"]],
                    "std_page": 1
                    if (SITE_DATA / "districts" / f"{cds}.json").exists()
                    else 0,
                },
                "m": m_rows,
                "bandsplit": bandsplit(series) if lk == "u" else None,
                "series": series_payload(series),
                "schools": schools,
                "school_spark_springs": spark_springs,
                "neighbors": sorted(neighbors_map.get(gid, ())),
                "acs1": acs1_map.get(("u", gid), []),
                "perf": perf_hist.get(cds, []),
            }
            (ENROLL_DIR / "districts" / f"{cds}.json").write_text(json.dumps(payload))
            n_pages += 1
    print(f"  enrollment/districts: {n_pages:,} pages")

    # --- county pages -------------------------------------------------------
    # Named remote programs (virtual & non-classroom) by AUTHORIZER county —
    # the observed absorbers behind the cross-county administrative flows —
    # plus, per county, the adjacent-county programs whose legal footprint
    # includes it (the likely sinks of its "counted in other counties" band).
    remote_by_county: dict[str, list[list]] = {}
    remote_nearby: dict[str, list[list]] = {}
    if ef.REMOTE_PROGRAMS_PARQUET.exists():
        rp = pl.read_parquet(ef.REMOTE_PROGRAMS_PARQUET)
        if rp.height:
            last_rv = int(rp["vintage"].max())
            rp_last = (
                rp.filter((pl.col("vintage") == last_rv) & (pl.col("seats") >= 100))
                .sort("seats", descending=True)
                .to_dicts()
            )
            # Balanced-attribution shares: what fraction of an authorizer
            # county's remote seats the county-level balance places in each
            # footprint county (measured margins; modeled split).
            xfrac: dict[tuple[str, str], float] = {}
            if ef.REMOTE_XCTY_PARQUET.exists():
                xm = pl.read_parquet(ef.REMOTE_XCTY_PARQUET)
                if xm.height:
                    xm = xm.filter(pl.col("vintage") == last_rv)
                    xtot = dict(xm.group_by("auth").agg(pl.col("est").sum()).iter_rows())
                    for a, dst, s in (
                        xm.group_by("auth", "dest").agg(pl.col("est").sum()).iter_rows()
                    ):
                        if xtot.get(a):
                            xfrac[a, dst] = s / xtot[a]
            for r in rp_last:
                lst = remote_by_county.setdefault(r["county"], [])
                if len(lst) < 12:
                    lst.append(
                        [
                            school_names.get(r["cds"]) or r["cds"],
                            _r(r["seats"]),
                            r["kind"],
                            _r(r["seats"] * xfrac.get((r["county"], r["county"]), 0)),
                        ]
                    )
            # County adjacency mirrors the flow model's footprint derivation.
            geoid_cty = dict(
                flows.filter(pl.col("level") != "c")
                .select("geoid", "county")
                .unique()
                .iter_rows()
            )
            cadj: dict[str, set[str]] = {}
            for a, b in adjacency.select("geoid", "neighbor").unique().iter_rows():
                ca, cb = geoid_cty.get(a), geoid_cty.get(b)
                if ca and cb and ca != cb:
                    cadj.setdefault(ca, set()).add(cb)
                    cadj.setdefault(cb, set()).add(ca)
            for code, nbrs in cadj.items():
                lst = []
                for r in rp_last:
                    if r["county"] in nbrs and len(lst) < 10:
                        lst.append(
                            [
                                school_names.get(r["cds"]) or r["cds"],
                                _r(r["seats"]),
                                r["kind"],
                                names.get(_county_cds(r["county"])) or f"County {r['county']}",
                                _r(r["seats"] * xfrac.get((r["county"], code), 0)),
                            ]
                        )
                remote_nearby[code] = lst

    member_rows: dict[str, list[list]] = {}
    for row in index_rows:
        if row[3] != "c" and row[4]:
            member_rows.setdefault(row[4], []).append(
                [row[0], row[1], row[2], row[3], row[6], row[8]]
            )
    n_counties = 0
    for code in sorted({r for (lv, r) in flows_by_geoid if lv == "c"}):
        series = flows_by_geoid.get(("c", code), [])
        cds = _county_cds(code)
        payload = {
            "meta": {"geoid": code, "cds": cds, "name": names.get(cds) or f"County {code}",
                     "dtype": "c", "county": code},
            "m": m_rows,
            "series": series_payload(series),
            "members": sorted(member_rows.get(code, []), key=lambda r: -(r[5] or 0)),
            "remote": remote_by_county.get(code, []),
            "remote_nearby": remote_nearby.get(code, []),
            "acs1": acs1_map.get(("c", code), []),
            "perf": perf_hist.get(cds, []),
        }
        (ENROLL_DIR / "counties" / f"{cds}.json").write_text(json.dumps(payload))
        n_counties += 1
    print(f"  enrollment/counties: {n_counties} pages")

    # --- meta ----------------------------------------------------------------
    sited_counts = (
        pl.read_parquet(eg.SITING_PARQUET)
        .group_by("sited")
        .len()
        .to_dicts()
    )
    meta = {
        "vintages": vintages,
        "calibration": [
            {k: (_r(v_, 4) if isinstance(v_, float) else v_) for k, v_ in row.items()}
            for row in calib.sort("vintage").to_dicts()
        ],
        "siting": {str(r["sited"]): r["len"] for r in sited_counts},
        "state_acs1": acs1_map.get(("s", "CA"), []),
    }
    (ENROLL_DIR / "meta.json").write_text(json.dumps(meta))

    # --- enroll flag on main entity payloads ---------------------------------
    stamped = 0
    for kind, cds_list in (
        ("districts", [geoid_cds.get(g) for lvl in eg.LEVELS for g in geo[lvl][0]]),
        ("counties", [_county_cds(c) for (lv, c) in flows_by_geoid if lv == "c"]),
    ):
        for cds in cds_list:
            if not cds:
                continue
            path = SITE_DATA / kind / f"{cds}.json"
            enroll_path = ENROLL_DIR / kind / f"{cds}.json"
            if not path.exists() or not enroll_path.exists():
                continue
            try:
                payload = json.loads(path.read_text())
            except ValueError:
                continue
            if payload.get("enroll") != 1:
                payload["enroll"] = 1
                path.write_text(json.dumps(payload))
                stamped += 1
    print(f"  enroll flag stamped on {stamped:,} entity payloads")


if __name__ == "__main__":
    export_enrollment()
