"""District FRPM vs census child poverty (ACS B17024).

FRPM (185% of the federal poverty line, reported by districts) and ACS B17024
(residents by ratio of income to poverty) measure "the same" population two ways, and
they diverge systematically: PPIC found the median district reports ~1.8x as many FRPM
students as the Census Bureau counts school-age residents under 185% of poverty
(https://www.ppic.org/ — direct certification, categorical eligibility, and enrollment
vs residence all push FRPM above the census count). We compute both statewide so the
divergence is visible, checkable, and comparable district by district.

Universes differ slightly and deliberately: FRPM counts *enrolled* students ages 5-17
(`frpm_count_ages_5_17`), the census counts *resident* children 6-17 (ages "6 to 11" +
"12 to 17" in B17024). That residents-vs-attendance gap is the object of study, not a
bug. Variables are selected from B17024 by label, never by hardcoded `_0NN` IDs.

Join key: CDE directory `ncesdist` (7-digit NCES LEAID, e.g. 0622710 for LAUSD) equals
the digits after "US" in the ACS school-district GEO_ID.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import polars as pl

from schoolfactors.paths import DUCKDB_PATH, PARQUET_DIR

OUT_PARQUET = PARQUET_DIR / "analysis" / "census_frpm_district.parquet"

SCHOOL_AGES = ("6 to 11 years", "12 to 17 years")
# The seven income-to-poverty bins strictly below 1.85 (the reduced-price meal line).
P185_BINS = (
    "Under .50",
    ".50 to .74",
    ".75 to .99",
    "1.00 to 1.24",
    "1.25 to 1.49",
    "1.50 to 1.74",
    "1.75 to 1.84",
)


def p185_variables(labels: dict[str, str]) -> tuple[list[str], list[str]]:
    """Select B17024 estimate variables by label: (poverty-bin numerators, age totals).

    Labels look like ``Estimate!!Total:!!6 to 11 years:!!1.75 to 1.84``; the age-group
    totals are ``Estimate!!Total:!!6 to 11 years:``.
    """
    num, den = [], []
    for var, label in labels.items():
        if not var.endswith("E") or not label:
            continue
        parts = [p.rstrip(":") for p in label.split("!!")]
        if len(parts) == 3 and parts[2] in SCHOOL_AGES:
            den.append(var)
        elif len(parts) == 4 and parts[2] in SCHOOL_AGES and parts[3] in P185_BINS:
            num.append(var)
    return sorted(num), sorted(den)


def _labels(con: duckdb.DuckDBPyConnection, vintage: str) -> dict[str, str]:
    rows = con.execute(
        "SELECT DISTINCT variable, label FROM census_acs_raw "
        "WHERE table_id = 'B17024' AND vintage = ?",
        [vintage],
    ).fetchall()
    return {v: lbl for v, lbl in rows if lbl}


def build_district_table(con: duckdb.DuckDBPyConnection | None = None) -> pl.DataFrame | None:
    """One row per CA district: census P185 residents vs FRPM counts, latest data.

    Returns None (with a message) when the census store isn't populated yet.
    """
    own = con is None
    if own:
        con = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    try:
        views = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if "census_acs_raw" not in views:
            print("  census_acs_raw view missing — run `sf acquire --dataset census` + ingest")
            return None
        vintage = con.execute(
            "SELECT max(vintage) FROM census_acs_raw WHERE table_id = 'B17024'"
        ).fetchone()[0]
        if vintage is None:
            print("  no B17024 rows in census_acs_raw")
            return None
        num, den = p185_variables(_labels(con, vintage))
        if len(num) != len(P185_BINS) * len(SCHOOL_AGES) or len(den) != len(SCHOOL_AGES):
            raise ValueError(
                f"B17024 label selection drifted: {len(num)} numerator / {len(den)} "
                f"denominator variables (expected {len(P185_BINS) * len(SCHOOL_AGES)} / "
                f"{len(SCHOOL_AGES)}); inspect the groups metadata snapshot"
            )

        # Census side: sum bin counts, then divide — never average percentages.
        # ACS sentinel values are large negatives; only non-negative values count.
        census = con.execute(
            """
            SELECT geoid,
                   any_value(geo_name) AS census_name,
                   replace(geo_type, 'sd_', '') AS dtype,
                   sum(CASE WHEN list_contains(?::VARCHAR[], variable) THEN v END)
                       AS p185_count,
                   sum(CASE WHEN list_contains(?::VARCHAR[], variable) THEN v END)
                       AS child_pop
            FROM (
                SELECT *, TRY_CAST(value AS DOUBLE) AS v
                FROM census_acs_raw
                WHERE table_id = 'B17024' AND vintage = ? AND geo_type LIKE 'sd_%'
            )
            WHERE v IS NULL OR v >= 0
            GROUP BY geoid, geo_type
            """,
            [num, den, vintage],
        ).pl()

        # NCES LEAID crosswalk from the CDE directory (district grain).
        xwalk = con.execute(
            """
            SELECT substr(cds, 1, 7) || '0000000' AS cds,
                   lpad(trim(ncesdist), 7, '0') AS geoid,
                   count(*) AS n_rows
            FROM directory_raw
            WHERE ncesdist IS NOT NULL AND trim(ncesdist) <> ''
            GROUP BY 1, 2
            """
        ).pl()
        dupes = xwalk.group_by("cds").len().filter(pl.col("len") > 1)
        if len(dupes):
            # Keep the majority mapping per district; directory rows occasionally
            # disagree for reorganized districts.
            xwalk = (
                xwalk.sort("n_rows", descending=True)
                .unique(subset=["cds"], keep="first", maintain_order=True)
            )
        xwalk = xwalk.drop("n_rows")

        # FRPM side: latest year, school rows only, sum counts by district prefix.
        # Only geographic districts: county offices of education, State Board-
        # authorized charters, and state special schools have no census school-
        # district geography, so they are out of the comparison universe entirely.
        frpm = con.execute(
            """
            WITH latest AS (SELECT max(academic_year) AS y FROM frpm_raw)
            SELECT substr(cds, 1, 7) || '0000000' AS cds,
                   any_value(district_name) AS name,
                   any_value(district_type) AS district_type,
                   any_value(academic_year) AS frpm_year,
                   sum(TRY_CAST(frpm_count_ages_5_17 AS DOUBLE)) AS frpm_count,
                   sum(TRY_CAST(enrollment_ages_5_17 AS DOUBLE)) AS enr_5_17
            FROM frpm_raw, latest
            WHERE academic_year = latest.y AND school_code <> '0000000'
              AND district_type IN ('Elementary School District',
                                    'High School District',
                                    'Unified School District')
            GROUP BY 1
            """
        ).pl()

        df = (
            frpm.join(xwalk, on="cds", how="left")
            .join(census, on="geoid", how="left")
            .with_columns(
                pl.lit(vintage).alias("acs_vintage"),
                (pl.col("frpm_count") / pl.col("enr_5_17")).alias("frpm"),
                (pl.col("p185_count") / pl.col("child_pop")).alias("p185"),
            )
            .with_columns(
                # PPIC's benchmark metric: the district's FRPM RATE over the census
                # P185 RATE (median ~1.8x statewide). Rates, not raw counts — enrolled
                # students are fewer than resident children (private school,
                # inter-district enrollment), so count ratios run mechanically lower.
                (pl.col("frpm") / pl.col("p185")).alias("ratio"),
            )
            .sort("cds")
        )
        OUT_PARQUET.parent.mkdir(parents=True, exist_ok=True)
        df.write_parquet(OUT_PARQUET)

        matched = df.filter(pl.col("p185_count").is_not_null())
        med = matched.filter(
            pl.col("ratio").is_not_null() & pl.col("ratio").is_finite()
        )["ratio"].median()
        print(
            f"  census B17024 ({vintage}) vs FRPM: {len(matched):,}/{len(df):,} districts "
            f"matched, median FRPM/P185 rate ratio = {med:.2f}x (PPIC benchmark ~1.8x)"
        )
        return df
    finally:
        if own:
            con.close()


def make_figure(df: pl.DataFrame) -> Path:
    """Statewide scatter: census P185 share vs FRPM share, one dot per district."""
    import matplotlib.pyplot as plt
    import numpy as np

    from schoolfactors.analysis.figures import BLUE, FIG_DIR, INK2, ORANGE

    d = df.filter(
        pl.col("frpm").is_not_null()
        & pl.col("p185").is_not_null()
        & (pl.col("enr_5_17") > 0)
    )
    x = d["p185"].to_numpy() * 100
    y = d["frpm"].to_numpy() * 100
    size = np.clip(np.sqrt(d["enr_5_17"].to_numpy()) / 6, 3, 80)
    med = d.filter(pl.col("ratio").is_not_null())["ratio"].median()

    fig, ax = plt.subplots(figsize=(6.4, 6.0))
    ax.scatter(x, y, s=size, alpha=0.35, color=BLUE, edgecolors="none", rasterized=True)
    lim = [0, 100]
    ax.plot(lim, lim, color=ORANGE, lw=1.2, label="equal shares (y = x)")
    lausd = d.filter(pl.col("cds") == "19647330000000")
    if len(lausd):
        ax.scatter(
            lausd["p185"].to_numpy() * 100, lausd["frpm"].to_numpy() * 100,
            s=90, color=ORANGE, edgecolors="white", zorder=5, label="LAUSD",
        )
    ax.set_xlim(*lim)
    ax.set_ylim(*lim)
    ax.set_xlabel("Resident children 6–17 under 185% of poverty (ACS B17024)")
    ax.set_ylabel("Students 5–17 FRPM-eligible (CDE)")
    ax.set_title(
        "Districts report more FRPM students than the census counts poor residents\n"
        f"median district ratio {med:.2f}x — measurement differences, not error",
        fontsize=10.5,
        color=INK2,
    )
    ax.legend(frameon=False, fontsize=9)
    fig.tight_layout()
    out = FIG_DIR / "census_frpm_scatter.png"
    fig.savefig(out, dpi=180)
    plt.close(fig)
    return out
