"""Build the DuckDB database over the Parquet store.

All type casting and the mandatory de-duplication filters live here, in one place:
- CAASPP: analysis views are school-level (type_id 7/9/10) or district-level (6).
- CDE long files: filter charter_school='All' and dass='All' where those columns
  exist, otherwise aggregate rows are triple/nine-counted.
"""

from __future__ import annotations

import duckdb

from schoolfactors.paths import DUCKDB_PATH, PARQUET_DIR


def build() -> None:
    con = duckdb.connect(str(DUCKDB_PATH))
    pq = str(PARQUET_DIR)

    def view_over(name: str, glob: str) -> bool:
        matches = list(PARQUET_DIR.glob(glob.removeprefix(f"{pq}/").replace("**", "*")))
        if not (PARQUET_DIR / glob.split("/")[0]).exists():
            return False
        con.execute(
            f"CREATE OR REPLACE VIEW {name} AS "
            f"SELECT * FROM read_parquet('{pq}/{glob}', union_by_name=true)"
        )
        return True

    made = []
    have_entities = view_over("caaspp_entities", "caaspp_entities/year=*/data.parquet")
    if have_entities:
        made.append("caaspp_entities")
    if view_over("caaspp_sb_raw", "caaspp_sb/year=*/data.parquet"):
        made.append("caaspp_sb_raw")
        if have_entities:
            # Era A/B files lack type_id: fill it from the entities table.
            con.execute("""
                CREATE OR REPLACE VIEW caaspp_sb AS
                SELECT r.* EXCLUDE (type_id),
                       COALESCE(r.type_id, e.type_id) AS type_id
                FROM caaspp_sb_raw r
                LEFT JOIN caaspp_entities e
                  ON r.cds = e.cds AND r.test_year = e.test_year
            """)
            made.append("caaspp_sb")
    if view_over("caaspp_tests", "caaspp_tests/data.parquet"):
        made.append("caaspp_tests")
    if view_over("caaspp_student_groups", "caaspp_student_groups/data.parquet"):
        made.append("caaspp_student_groups")

    for family in sorted(p.name for p in PARQUET_DIR.iterdir() if p.is_dir()):
        if family.startswith("caaspp"):
            continue
        if view_over(f"{family}_raw", f"{family}/file=*/data.parquet"):
            made.append(f"{family}_raw")

    con.close()
    print(f"  views: {', '.join(made)}")
