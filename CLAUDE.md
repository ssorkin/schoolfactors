# SchoolFactors — project conventions

Open-source repository + analysis of California public-education data. Plan of record:
pipeline (acquire → ingest → quality → analysis) in Python, static SvelteKit site.

## Commands

- `uv sync` — install; `uv run sf --help` — pipeline CLI (`acquire`, `ingest`, `check`, `analyze`, `export`)
- `uv run pytest` — tests; `uv run ruff check src tests` — lint
- Site: `cd site && npm run dev` / `npm run build` (static; data from `sf export`)
- Deploy (atomic): `scripts/deploy.sh [--build]` — rsync `site/build/` to dronesclub
  `/var/www/schoolfactors-releases/<ts>/`, swap symlink `/var/www/schoolfactors-current`
  via `ln -s` + `mv -T`, prune to last 3 releases. NEVER `rsync --delete` into the
  live root (mid-deploy hydration breaks).

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
- **Percentages are never averaged** — reconstruct counts (pct × n), combine, re-divide
  (see the complement computation in `analysis/cohorts.py`).
- `curated/` entries (facts CDE doesn't publish, e.g. selective admissions) require a
  per-entry `source` URL; keep claims conservative and factual.
- CDE's WAF blocks burst traffic: acquisition paces itself and aborts on block pages
  or redirect loops (`WafBlocked`); on a block, stop and retry hours later.
- `data/` is gitignored; provenance lives in `manifests/` (URL, version, sha256, dates).

## Style

- Python 3.12+, ruff (line length 100), typer CLI, polars for ingest, DuckDB for joins.
- Site copy always says "correlated with"/"schools serving similar students" — never
  causal language, never bare ranks.
