# SchoolFactors — project conventions

Open-source repository + analysis of California public-education data. Plan of record:
pipeline (acquire → ingest → quality → analysis) in Python, static SvelteKit site.

## Commands

- `uv sync` — install; `uv run sf --help` — pipeline CLI (`acquire`, `ingest`, `check`, `analyze`, `export`)
- `uv run pytest` — tests; `uv run ruff check src tests` — lint

## Hard rules (data integrity)

- **Never hardcode source-file URLs with version suffixes.** CDE/CAASPP silently repost
  files as `-v2`/`_v2`/`v3`. Downloaders scrape landing pages (or probe versions) and
  record what they got in `manifests/`.
- **Never sum across CAASPP student groups** (they overlap) and always filter CDE files
  on `AggregateLevel`, `Charter School == 'All'`, `DASS == 'All'` before aggregating —
  otherwise totals inflate up to 9×.
- **CDS key** = zero-padded County(2) + District(5) + School(7), everywhere. School code
  `0000000` = district row; district `00000` = county row.
- **Suppressed values** (`*`, blank, `NA`, n<11) are data: parse numerics as nullable and
  carry suppression flags; never coerce to 0.
- **Mean scale score, not percent-proficient**, is the primary achievement metric.
- Data problems are documented in `known_issues/` and surfaced in the DQ report —
  never silently patched. Cleaning steps are explicit, named transforms.
- `data/` is gitignored; provenance lives in `manifests/` (URL, version, sha256, dates).

## Style

- Python 3.12+, ruff (line length 100), typer CLI, polars for ingest, DuckDB for joins.
- Site copy always says "correlated with"/"schools serving similar students" — never
  causal language, never bare ranks.
