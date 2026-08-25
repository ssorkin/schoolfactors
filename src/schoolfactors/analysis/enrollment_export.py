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


def _school_scores() -> dict[str, float | None]:
    """Similar Student percentile per school cds from the main index."""
    index_path = SITE_DATA / "index.json"
    scores: dict[str, float | None] = {}
    if index_path.exists():
        for e in json.loads(index_path.read_text()):
            if e.get("kind") == "school":
                scores[e["cds"]] = e.get("simstu_pct")
    return scores


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


def _findings_block(
    flows: pl.DataFrame,
    calib: pl.DataFrame,
    latest_v: int | None,
    names: dict[str, str],
    nonlocal_map: dict[str, dict],
    persistence: dict | None = None,
    remote_current: list | None = None,
) -> dict | None:
    """Statewide takeaways for the landing page, computed fresh each build so the
    narrative can never drift from the data (see analysis/
    enrollment_findings_groundwork.md for the empirical grounding). All values
    are accounting observations — the site copy templated from them must keep
    the modeled-not-observed framing."""
    if latest_v is None:
        return None
    live = flows.filter((pl.col("level") != "c") & pl.col("net").is_not_null())
    d = live.filter(pl.col("vintage") == latest_v)
    if not d.height:
        return None

    within_moe = d.filter(
        pl.col("net_rate").abs() <= pl.col("res_moe") / pl.col("res_pub")
    ).height
    tot_res = d["res_pub"].sum()
    bal_res = d.filter(pl.col("net_rate").abs() <= 0.05)["res_pub"].sum()

    vints3 = [latest_v - 10, latest_v - 5, latest_v]

    # Remote sector: pool size and share of statewide enrollment per window.
    remote_series = []
    for r in calib.sort("vintage").to_dicts():
        pool = (r["pool_virtual"] or 0) + (r["pool_nc"] or 0)
        remote_series.append(
            [int(r["vintage"]), _r(pool),
             _r(pool / r["state_cde"], 4) if r["state_cde"] else None]
        )
    remote_latest: dict = {}
    if ef.REMOTE_PROGRAMS_PARQUET.exists():
        rp = pl.read_parquet(ef.REMOTE_PROGRAMS_PARQUET)
        if rp.height:
            rv = int(rp["vintage"].max())
            rl = rp.filter(pl.col("vintage") == rv)
            tot = rl["seats"].sum()
            bycty = rl.group_by("county").agg(pl.col("seats").sum()).sort(
                "seats", descending=True
            )
            remote_latest = {
                "n_programs": rl.height,
                "n_counties": bycty.height,
                "kinds": {
                    k: [_r(s), int(c)]
                    for k, s, c in rl.group_by("kind")
                    .agg(pl.col("seats").sum(), pl.len())
                    .iter_rows()
                },
                "top5_share": _r(bycty.head(5)["seats"].sum() / tot, 3) if tot else None,
                "top_counties": [
                    [names.get(_county_cds(code)) or f"County {code}", _r(s)]
                    for code, s in bycty.head(5).iter_rows()
                ],
            }

    # Counties: balance, residual decomposition, top matched pairs.
    c = flows.filter(
        (pl.col("level") == "c")
        & (pl.col("vintage") == latest_v)
        & pl.col("net").is_not_null()
    )
    gross = c["net"].abs().sum()
    flow_abs = c["net_flow"].abs().sum()
    top_pairs = []
    if ef.PHYS_FLOWS_PARQUET.exists():
        pp = pl.read_parquet(ef.PHYS_FLOWS_PARQUET)
        pp = pp.filter(pl.col("vintage") == latest_v).sort("est", descending=True)
        top_pairs = [
            [names.get(_county_cds(e)) or e, names.get(_county_cds(i)) or i, _r(est)]
            for e, i, est in pp.head(5).select("exporter", "importer", "est").iter_rows()
        ]

    # Nonlocality distribution (≥200 resident children).
    nl = sorted(
        (v for v in nonlocal_map.values() if v["res"] >= 200),
        key=lambda v: -v["ratio"],
    )
    ratios = sorted(v["ratio"] for v in nl)
    med = ratios[len(ratios) // 2] if ratios else None

    lausd = live.filter(
        (pl.col("geoid") == "0622710") & (pl.col("vintage") == latest_v)
    ).to_dicts()

    return {
        "window": [latest_v - 4, latest_v],
        "balance": {
            "n": d.height,
            "within_moe_share": _r(within_moe / d.height, 3),
            "res_within5_share": _r(bal_res / tot_res, 3) if tot_res else None,
        },
        "persistence": {
            "windows": [[v - 4, v] for v in vints3],
            **(persistence or {}),
        },
        "remote": {
            "series": remote_series,
            "current": remote_current,
            **remote_latest,
        },
        "counties": {
            "n": c.height,
            "within2": c.filter(pl.col("net_rate").abs() <= 0.02).height,
            "flow_share": _r(flow_abs / gross, 3) if gross else None,
            "pairs": top_pairs,
        },
        "nonlocal": {
            "n": len(nl),
            "median": _r(med, 2) if med is not None else None,
            "over3": sum(1 for v in nl if v["ratio"] > 3),
            "over10": sum(1 for v in nl if v["ratio"] > 10),
            "top": [
                [v["name"], v["county"], _r(v["ratio"], 1), _r(v["res"]), _r(v["admin"])]
                for v in nl[:5]
            ],
        },
        "lausd": {
            "net": _r(lausd[0]["net"]),
            "rate": _r(lausd[0]["net_rate"], 4),
        }
        if lausd
        else None,
    }


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
        # NCB-determined programs can be absent from the directory entirely
        # (successor CDS codes) — fall back to the SBE determination's name.
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if "ncb_raw" in tables:
            for cds_, nm in con.execute(
                "SELECT cds, any_value(charter_school_name) FROM ncb_raw GROUP BY cds"
            ).fetchall():
                if nm and not school_names.get(cds_):
                    school_names[cds_] = nm
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

    # County boundaries for the landing choropleth: dissolve the K-8 partition
    # (unified + elementary tile the state) by each district's ADMINISTRATIVE
    # county — the accounting unit of the model — so county borders coincide
    # exactly with the district borders they aggregate.
    from shapely.geometry import mapping as shp_mapping
    from shapely.ops import unary_union

    from schoolfactors.analysis.lausd_geo import simplify_feature_collection

    cty_of_geoid = dict(xwalk.select("geoid", "county_code").iter_rows())
    cty_geoms: dict[str, list] = {}
    for lvl in ("unified", "elementary"):
        ids, geoms, _ = geo[lvl]
        for gid, geom in zip(ids, geoms):
            code = cty_of_geoid.get(gid)
            if code:
                cty_geoms.setdefault(code, []).append(geom)
    county_fc = {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "properties": {"g": code},
             "geometry": dict(shp_mapping(unary_union(gs)))}
            for code, gs in sorted(cty_geoms.items())
        ],
    }
    county_fc = simplify_feature_collection(county_fc, epsilon=0.0015)
    (ENROLL_DIR / "boundaries_c.geojson").write_text(json.dumps(county_fc))
    print(f"  boundaries_c: {len(county_fc['features'])} counties")

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

    # --- nonlocality: administrative enrollment vs resident children ------
    # Window-matched: mean over the latest live window's springs of each CDS-
    # prefix district's total administered seats (its own schools plus every
    # charter it authorizes, wherever sited — the seats parquet already excludes
    # adult-serving charters), in resident units, over resident public children.
    # ~1 for ordinary districts; the tail measures how geographically nonlocal
    # an LEA's administrative enrollment has become.
    live_dist = flows.filter((pl.col("level") != "c") & pl.col("net").is_not_null())
    latest_v = int(live_dist["vintage"].max()) if live_dist.height else None
    m_by_v = {int(v): mm for v, mm in m_rows}
    nonlocal_map: dict[str, dict] = {}
    if latest_v is not None:
        win_admin = dict(
            seats.filter(pl.col("spring").is_in(list(range(latest_v - 4, latest_v + 1))))
            .with_columns(pl.col("cds").str.slice(0, 7).alias("dcds"))
            .group_by("dcds", "spring")
            .agg(pl.col("total").sum())
            .group_by("dcds")
            .agg(pl.col("total").mean())
            .iter_rows()
        )
        for r in live_dist.filter(pl.col("vintage") == latest_v).to_dicts():
            cds14 = geoid_cds.get(r["geoid"])
            admin_raw = win_admin.get(cds14[:7]) if cds14 else None
            if not cds14 or not r["res_pub"] or admin_raw is None:
                continue
            admin_ru = admin_raw * (1 - m_by_v[latest_v])
            nonlocal_map[cds14[:7]] = {
                "cds": cds14,
                "name": names.get(cds14),
                "county": names.get(_county_cds(cds14[:2])),
                "res": r["res_pub"],
                "admin": admin_ru,
                "ratio": admin_ru / r["res_pub"],
            }

    # Annual remote census: observed census-day enrollment at classified remote
    # programs, per spring — the classification comes from the survey window
    # ending that spring (the latest classification carries forward to newer
    # springs, so recent years are a mild lower bound: a program newly remote
    # since the last window would not yet be classified).
    remote_census: list[list] = []
    if ef.REMOTE_PROGRAMS_PARQUET.exists():
        rp_all = pl.read_parquet(ef.REMOTE_PROGRAMS_PARQUET)
        if rp_all.height:
            vmin, vmax = int(rp_all["vintage"].min()), int(rp_all["vintage"].max())
            cls_by_v: dict[int, set[str]] = {}
            for v_, cds_ in rp_all.select("vintage", "cds").iter_rows():
                cls_by_v.setdefault(int(v_), set()).add(cds_)
            for s in sorted(seats["spring"].unique().to_list()):
                cset = cls_by_v.get(min(max(int(s), vmin), vmax), set())
                sub = seats.filter(pl.col("spring") == s)
                rem = sub.filter(pl.col("cds").is_in(sorted(cset)))["total"].sum()
                tot = sub["total"].sum()
                remote_census.append(
                    [int(s), _r(rem), _r(rem / tot, 4) if tot else None]
                )

    # Persistence over three NON-overlapping windows (overlapping windows share
    # sample): +1 = significant net importer in all three, -1 = exporter in all
    # three. Restricted to districts whose margin stays within the map's
    # reliability gate (±15pp, mirroring site MOE_GATE) in every window —
    # without the gate, tiny rural districts (a handful of resident children,
    # schools serving a far wider area) dominate the importer list with
    # +500%-style rates the survey cannot support. Shipped per district so the
    # balance table can surface them.
    persist_map: dict[str, int] = {}
    n_persist_base = 0
    if latest_v is not None:
        vints3 = [latest_v - 10, latest_v - 5, latest_v]
        p3 = (
            live_dist.filter(pl.col("vintage").is_in(vints3))
            .with_columns((pl.col("res_moe") / pl.col("res_pub")).alias("moe"))
            .with_columns(
                pl.when(pl.col("net_rate") > pl.col("moe"))
                .then(1)
                .when(pl.col("net_rate") < -pl.col("moe"))
                .then(-1)
                .otherwise(0)
                .alias("sig"),
                (pl.col("moe") <= 0.15).alias("reliable"),
            )
            .group_by("geoid")
            .agg(
                pl.len().alias("nv"),
                pl.col("sig").min().alias("smin"),
                pl.col("sig").max().alias("smax"),
                pl.col("reliable").min().alias("rel"),
            )
            .filter((pl.col("nv") == len(vints3)) & pl.col("rel"))
        )
        n_persist_base = p3.height
        for g, _nv, smin, smax, _rel in p3.iter_rows():
            if smin == 1:
                persist_map[g] = 1
            elif smax == -1:
                persist_map[g] = -1

    cut_map = dict(cuts.select("geoid", "cut").iter_rows())
    # Pseudo grade-range areas are folded into their parent district's node in
    # the flow model — no index row of their own (their polygons already carry
    # the parent geoid in boundaries_h).
    pseudo_geoids: set[str] = set()
    if eg.PSEUDO_PARQUET.exists():
        pseudo_geoids = set(pl.read_parquet(eg.PSEUDO_PARQUET)["pseudo_geoid"].to_list())
    index_rows: list[list] = []
    level_key = {"unified": "u", "elementary": "e", "secondary": "h"}
    for lvl in eg.LEVELS:
        ids, _, props = geo[lvl]
        for gid, p in zip(ids, props):
            if gid in pseudo_geoids:
                continue
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
                    None,
                    None,
                    persist_map.get(gid),
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
                _r(last["net_flow"] / last["res_pub"], 4)
                if last and last["res_pub"] and last.get("net_flow") is not None
                else None,
                _r(last["net_misalign"] / last["res_pub"], 4)
                if last and last["res_pub"] and last.get("net_misalign") is not None
                else None,
                None,
            ]
        )
    index_payload = {
        "cols": ["geoid", "cds", "name", "dtype", "county", "ll", "net_rate",
                 "net_moe", "res", "seats", "virt_share", "perf", "spark",
                 "res_chg", "seats_chg", "std", "flow_rate", "mis_rate", "persist"],
        "vintages": vintages,
        "rows": index_rows,
        "findings": _findings_block(
            flows, calib, latest_v, names, nonlocal_map,
            persistence={
                "n": n_persist_base,
                "importers": sum(1 for v in persist_map.values() if v == 1),
                "exporters": sum(1 for v in persist_map.values() if v == -1),
            },
            remote_current=remote_census[-1] if remote_census else None,
        ),
    }
    (ENROLL_DIR / "index.json").write_text(json.dumps(index_payload))
    print(f"  enrollment/index.json: {len(index_rows):,} rows")

    # --- per-school payload pieces ----------------------------------------
    latest_spring = int(seats["spring"].max())
    spark_springs = [*SCHOOL_SPARK_SPRINGS, latest_spring]
    # Pseudo grade-range areas fold into their parent district's node (see
    # enrollment_geo.pseudo_parent_map): schools sited in a pseudo polygon
    # list on the parent's page.
    pseudo_node: dict[str, tuple[str, str]] = {}
    if eg.PSEUDO_PARQUET.exists():
        pseudo_node = {
            r["pseudo_geoid"]: (r["parent_level"], r["parent_geoid"])
            for r in pl.read_parquet(eg.PSEUDO_PARQUET).to_dicts()
        }
    seats_by_area: dict[tuple[str, str], set[str]] = {}
    for col, lk in (("unified_geoid", "u"), ("elem_geoid", "e"), ("sec_geoid", "h")):
        for gid, cds in (
            seats.filter(pl.col(col).is_not_null()).select(col, "cds").unique().iter_rows()
        ):
            node = pseudo_node.get(gid, (lk, gid)) if lk == "h" else (lk, gid)
            seats_by_area.setdefault(node, set()).add(cds)
    school_class = dict(
        seats.group_by("cds").agg(pl.col("class").first()).iter_rows()
    )
    # Display class for NCB / ratio-criterion remote programs: their seats sit
    # in the remote pool, not the host area's physical count, and the marker
    # should say so (the directory class alone can't — NCB-determined schools
    # may be missing from the directory entirely).
    if ef.REMOTE_PROGRAMS_PARQUET.exists():
        rp_cls = pl.read_parquet(ef.REMOTE_PROGRAMS_PARQUET)
        if rp_cls.height:
            rv_last = int(rp_cls["vintage"].max())
            for cds_, kind_ in (
                rp_cls.filter(pl.col("vintage") == rv_last).select("cds", "kind").iter_rows()
            ):
                if kind_ != "virtual" and school_class.get(cds_) != "charter_virtual":
                    school_class[cds_] = "charter_nc"
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
                "flow": _r(r["net_flow"]) if r.get("net_flow") is not None else None,
                "mis": _r(r["net_misalign"]) if r.get("net_misalign") is not None else None,
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
                    # Window-matched administrative-vs-resident ratio, shown as a
                    # stat line only when the LEA is meaningfully nonlocal.
                    "nonlocal": {
                        "ratio": _r(nonlocal_map[cds[:7]]["ratio"], 2),
                        "admin": _r(nonlocal_map[cds[:7]]["admin"]),
                        "res": _r(nonlocal_map[cds[:7]]["res"]),
                    }
                    if cds[:7] in nonlocal_map
                    and nonlocal_map[cds[:7]]["ratio"] >= 1.5
                    and nonlocal_map[cds[:7]]["res"] >= 200
                    else None,
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
    fp_surplus: dict[str, float] = {}
    school_scores = _school_scores()

    def remote_link_cols(cds: str) -> list:
        """[linkable cds or None, Similar Student %ile] — link gated on the
        school page existing (same rule as school_entry)."""
        has_page = (SITE_DATA / "schools" / f"{cds}.json").exists()
        return [cds if has_page else None, school_scores.get(cds)]

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
                            *remote_link_cols(r["cds"]),
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
            # Footprint-ledger context: each county's latest residual can hold
            # real students only up to its footprint's unabsorbed surpluses.
            cnets: dict[str, float] = {}
            for (lv, g), rows in flows_by_geoid.items():
                if lv != "c":
                    continue
                live = [r for r in rows if r["net"] is not None]
                if live:
                    cnets[g] = live[-1]["net"]
            for c in cnets:
                fp_surplus[c] = sum(
                    max(cnets.get(n, 0.0), 0.0) for n in (cadj.get(c, set()) | {c})
                )
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
                                *remote_link_cols(r["cds"]),
                            ]
                        )
                remote_nearby[code] = lst

            # --- programs.json: the statewide remote-program dataset ---------
            # One browsable table of every classified virtual / non-classroom
            # program at the latest window, with its classification basis and
            # per-window enrollment history, plus the balanced footprint split
            # per authorizer county and the district nonlocality table.
            prog_series: dict[str, dict[int, float]] = {}
            for cds_, v_, s_ in rp.select("cds", "vintage", "seats").iter_rows():
                prog_series.setdefault(cds_, {})[int(v_)] = s_
            prog_rows = []
            for r in (
                rp.filter(pl.col("vintage") == last_rv)
                .sort("seats", descending=True)
                .to_dicts()
            ):
                cds_ = r["cds"]
                ser = prog_series.get(cds_, {})
                prog_rows.append(
                    [
                        cds_,
                        school_names.get(cds_) or cds_,
                        r["kind"],
                        r["county"],
                        names.get(cds_[:7] + "0000000"),
                        _r(r["seats"]),
                        [_r(ser[v]) if v in ser else None for v in vintages],
                        len(cadj.get(r["county"], ())) + 1,
                        *remote_link_cols(cds_),
                    ]
                )
            xf_out: dict[str, list[list]] = {}
            for (a, dst), f in xfrac.items():
                if f >= 0.005:
                    xf_out.setdefault(a, []).append([dst, round(f, 3)])
            for lst in xf_out.values():
                lst.sort(key=lambda x: -x[1])
            nl_all = sorted(
                (v for v in nonlocal_map.values() if v["res"] >= 200),
                key=lambda v: -v["ratio"],
            )
            nl_ratios = sorted(v["ratio"] for v in nl_all)
            programs_payload = {
                "cols": ["cds", "name", "kind", "county", "auth_name", "seats",
                         "series", "fp_n", "link", "perf"],
                "vintages": vintages,
                "window": [last_rv - 4, last_rv],
                "county_names": {
                    code: names.get(_county_cds(code)) or f"County {code}"
                    for code in sorted(
                        {r["county"] for r in rp.to_dicts()}
                        | set(xf_out)
                        | {d for lst in xf_out.values() for d, _f in lst}
                    )
                },
                "xfrac": xf_out,
                # Annual observed remote census (spring, seats, share of state)
                # for the year-by-year chart; classification per covering window.
                "census": remote_census,
                "programs": prog_rows,
                "nonlocal": {
                    "window": [latest_v - 4, latest_v] if latest_v else None,
                    "n": len(nl_all),
                    "median": round(nl_ratios[len(nl_ratios) // 2], 2)
                    if nl_ratios
                    else None,
                    "rows": [
                        [
                            v["cds"],
                            v["name"],
                            v["county"],
                            _r(v["res"]),
                            _r(v["admin"]),
                            round(v["ratio"], 2),
                            1
                            if (ENROLL_DIR / "districts" / f"{v['cds']}.json").exists()
                            else 0,
                        ]
                        for v in nl_all[:50]
                    ],
                },
            }
            (ENROLL_DIR / "programs.json").write_text(json.dumps(programs_payload))
            print(f"  enrollment/programs.json: {len(prog_rows)} programs")

    # [geoid, cds, name, dtype, net_rate, res, simstu_pct]
    member_rows: dict[str, list[list]] = {}
    for row in index_rows:
        if row[3] != "c" and row[4]:
            member_rows.setdefault(row[4], []).append(
                [row[0], row[1], row[2], row[3], row[6], row[8], row[11]]
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
            "fp_surplus": _r(fp_surplus[code]) if code in fp_surplus else None,
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

    # --- validation ----------------------------------------------------------
    # This build's model checks, structured for the methodology page's "How we
    # check the model" section — shared helpers with quality/checks.py so the
    # page and the DQ report can never quote different numbers.
    from schoolfactors.quality.checks import (
        doc_validation_stats,
        lausd_regression_stats,
        popest_control_stats,
    )

    pair_stab: list[dict] = []
    if ef.PHYS_FLOWS_PARQUET.exists():
        ppf = pl.read_parquet(ef.PHYS_FLOWS_PARQUET)
        if ppf.height:
            last_pv = int(ppf["vintage"].max())
            latest_est = {
                (e, i): est
                for e, i, est in ppf.filter(pl.col("vintage") == last_pv)
                .select("exporter", "importer", "est")
                .iter_rows()
            }
            grp = (
                ppf.group_by("exporter", "importer")
                .agg(
                    pl.len().alias("nv"),
                    pl.col("vintage").min().alias("v0"),
                    pl.col("vintage").max().alias("v1"),
                    pl.col("est").mean().alias("avg"),
                )
                # Stability display: persistent AND material (tiny rural pairs
                # recur every window but carry a few dozen students).
                .filter(pl.col("avg") >= 200)
                .sort(["nv", "avg"], descending=True)
            )
            for e, i, nv, v0, v1, _avg in grp.head(10).iter_rows():
                pair_stab.append(
                    {
                        "exp": names.get(_county_cds(e)) or f"County {e}",
                        "imp": names.get(_county_cds(i)) or f"County {i}",
                        "n_windows": int(nv),
                        "first": int(v0),
                        "last": int(v1),
                        "latest": _r(latest_est[e, i]) if (e, i) in latest_est else None,
                    }
                )
    doc = doc_validation_stats()
    if doc:
        doc = {
            "year": doc["year"],
            "pair_students": doc["pair_students"],
            "adjacent_share": _r(doc["adjacent_share"], 3)
            if doc["adjacent_share"] is not None
            else None,
            "agree_ok": doc["agree_ok"],
            "agree_all": doc["agree_all"],
            "biggest": {
                "name": names.get(doc["biggest"]["cd"] + "0000000")
                or doc["biggest"]["cd"],
                "doc_net": doc["biggest"]["doc_net"],
                "model_net": _r(doc["biggest"]["model_net"]),
            }
            if doc["biggest"]
            else None,
        }
    popest = popest_control_stats()
    lausd = lausd_regression_stats()
    validation = {
        "closure_max_share": max(
            (abs(r["closure_share"] or 0) for r in calib.to_dicts()), default=None
        ),
        "pairs": pair_stab,
        "doc": doc,
        "popest": {
            "n": popest["n"],
            "worst_dev": _r(popest["worst_dev"], 4),
            "n_drift": len(popest["drifts"]),
        }
        if popest
        else None,
        "lausd": {
            "n": len(lausd["rows"]),
            "n_ok": sum(1 for r in lausd["rows"] if r["ok"]),
            "max_dev_share": _r(
                max((abs(r["delta"]) / r["page"] for r in lausd["rows"]), default=0), 4
            ),
        }
        if lausd and lausd["rows"]
        else None,
    }
    (ENROLL_DIR / "validation.json").write_text(json.dumps(validation))
    print("  enrollment/validation.json written")

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
