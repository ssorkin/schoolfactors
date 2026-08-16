"""Nearby and lookalike schools for each school page.

Nearby = geographic neighbors at the same school level (elementary with elementary),
from the CDE directory's lat/long. Lookalike = nearest neighbors in standardized
demographic space (economic disadvantage, race/ethnicity, EL, SWD, parent education,
size) at the same school level, statewide — the natural comparison set for "schools
serving similar students".
"""

from __future__ import annotations

import duckdb
import numpy as np
import polars as pl
from scipy.spatial import cKDTree

from schoolfactors.paths import DUCKDB_PATH

LOOKALIKE_FEATURES = [
    "share_econ_dis",
    "share_el",
    "share_swd",
    "share_black",
    "share_asian",
    "share_hispanic",
    "share_white",
    "share_parent_college",
    "log_tested",
]
N_NEIGHBORS = 6
# Lookalikes get a deeper pool so the page can show similar schools performing
# both better and worse than the subject school.
N_LOOKALIKE = 12
MAX_NEARBY_MILES = 25.0


def _directory() -> pl.DataFrame:
    con = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    df = con.execute("""
        SELECT cds, any_value(eilcode) AS eilcode,
               any_value(TRY_CAST(latitude AS DOUBLE)) AS lat,
               any_value(TRY_CAST(longitude AS DOUBLE)) AS lon
        FROM directory_raw
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
        GROUP BY cds
    """).pl()
    con.close()
    return df


def build_neighbors(effects: pl.DataFrame) -> dict[str, dict]:
    """Return {cds: {nearby: [...], lookalike: [...]}} for modeled schools."""
    cols = ["cds", "level_adj_eb", "share_econ_dis"] + [
        c
        for c in LOOKALIKE_FEATURES
        if c in effects.columns and c != "share_econ_dis"
    ]
    base = effects.select(cols).join(_directory(), on="cds", how="left")

    out: dict[str, dict] = {c: {"nearby": [], "lookalike": []} for c in base["cds"].to_list()}
    info = {
        r["cds"]: r
        for r in base.select(
            "cds", "level_adj_eb", "share_econ_dis", "eilcode", "lat", "lon"
        ).to_dicts()
    }

    def entry(cds: str, extra: dict) -> dict:
        r = info[cds]
        return {
            "cds": cds,
            "level_adj_eb": r["level_adj_eb"],
            "share_econ_dis": r["share_econ_dis"],
            **extra,
        }

    # Group by school level so elementary schools match elementary schools.
    for (eil,), grp in base.group_by(["eilcode"], maintain_order=True):
        if eil is None or len(grp) < N_NEIGHBORS + 1:
            continue

        # --- nearby (geographic) ---
        geo = grp.filter(pl.col("lat").is_not_null() & pl.col("lon").is_not_null())
        if len(geo) > N_NEIGHBORS:
            lat = np.radians(geo["lat"].to_numpy())
            lon = np.radians(geo["lon"].to_numpy())
            lat0 = lat.mean()
            R = 3958.8  # miles
            xy = np.column_stack([R * lon * np.cos(lat0), R * lat])
            tree = cKDTree(xy)
            dists, idxs = tree.query(xy, k=N_NEIGHBORS + 1)
            cds_arr = geo["cds"].to_list()
            for i, cds in enumerate(cds_arr):
                for d, j in zip(dists[i][1:], idxs[i][1:]):
                    if d <= MAX_NEARBY_MILES and j < len(cds_arr):
                        out[cds]["nearby"].append(
                            entry(cds_arr[j], {"miles": round(float(d), 1)})
                        )

        # --- lookalike (demographic) ---
        feat_cols = [c for c in LOOKALIKE_FEATURES if c in grp.columns]
        demo = grp.filter(
            pl.all_horizontal([pl.col(c).is_not_null() for c in feat_cols])
        )
        if len(demo) > N_LOOKALIKE:
            X = np.column_stack([demo[c].to_numpy() for c in feat_cols])
            mu = X.mean(axis=0)
            sd = X.std(axis=0)
            sd[sd == 0] = 1
            Xz = (X - mu) / sd
            tree = cKDTree(Xz)
            dists, idxs = tree.query(Xz, k=N_LOOKALIKE + 1)
            cds_arr = demo["cds"].to_list()
            for i, cds in enumerate(cds_arr):
                for d, j in zip(dists[i][1:], idxs[i][1:]):
                    if j < len(cds_arr):
                        out[cds]["lookalike"].append(
                            entry(cds_arr[j], {"dist": round(float(d), 2)})
                        )

    return out
