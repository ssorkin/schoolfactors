# SchoolFactors

An open repository of public data about public education — starting with California —
and honest statistical analysis of the factors associated with high-performing and
improving schools.

**Sunlight is the best disinfectant.** Everything here is open source: the download
scripts, the cleaning transforms, the statistical models, the data-quality findings,
and the website that presents them. Anyone can reproduce every number we publish.

Website: [schoolfactors.org](https://schoolfactors.org) — every California school,
district, and county in one sortable table, with per-school pages, cohort tracking,
demographically-adjusted comparisons, and "Best for" views by student group.

## What this project does

- **Acquires** all available [CAASPP research files](https://caaspp-elpac.ets.org/caaspp/ResearchFileListSB)
  (Smarter Balanced results, 2014–15 onward) and the California Department of Education's
  [downloadable data files](https://www.cde.ca.gov/ds/ad/downloadabledata.asp)
  (enrollment, FRPM/poverty, English learners, staffing, spending, absenteeism,
  discipline, graduation, and more) — the same sources that feed DataQuest and Ed-Data.
- **Normalizes** them into a single analytical store (Parquet + DuckDB), documenting
  every transform and every known inconsistency in the source data along the way.
- **Analyzes** which factors correlate with school performance and improvement, using
  precision-weighted multilevel models and demographic-adjustment techniques, with
  uncertainty reported honestly.
- **Publishes** the results on an interactive website that makes CAASPP data navigation
  and school/district comparison fluid.

## Principles

1. **Correlations, not causation.** School-level data cannot tell you what a school
   *causes*; it can tell you how schools compare to others serving similar students.
   Our language and visualizations reflect that everywhere.
2. **Error margins always.** Small schools have noisy estimates. We use empirical-Bayes
   shrinkage, report intervals, gate estimates on reliability, and show explicit
   "not distinguishable from average" categories rather than false-precision rankings.
3. **Data quality in the open.** Source files have real problems (definition changes,
   internal inconsistencies, suppression). We detect them, document them in a published
   data-quality report, and never silently patch them.
4. **Reproducibility.** Raw data is not committed to this repo, but `manifests/` records
   the exact source URL, version, and SHA-256 of every file we use, and the pipeline
   rebuilds everything from scratch.

## Quick start

```bash
uv sync                        # install the pipeline (Python 3.12+, managed by uv)
uv run sf acquire              # download all source data (~5 GB), record checksums
uv run sf ingest               # normalize to Parquet + DuckDB
uv run sf check                # run data-quality validation -> DATA_QUALITY.md
uv run sf analyze              # fit models, render figures
uv run sf export               # generate the site's JSON data
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, the data-integrity
rules, and how to add sources or curated facts.

## Layout

| Path | Contents |
|---|---|
| `src/schoolfactors/` | pipeline: `acquire/`, `ingest/`, `quality/`, `analysis/`, `cli.py` |
| `manifests/` | provenance: URL, version, sha256, dates for every source file |
| `known_issues/` | registry of documented problems in the source data |
| `curated/` | community-maintained, per-entry-sourced facts CDE doesn't publish (e.g. selective admissions) |
| `analysis/` | statistical writeups and figures (`first_analysis.md`) |
| `site/` | the schoolfactors.org website (SvelteKit, fully static) |
| `DATA_QUALITY.md` | generated data-quality report (`sf check`) |

## Data provenance and licensing

Code in this repository is MIT-licensed. The underlying data is published by the
California Department of Education and its assessment contractor; CDE does not attach
an explicit open-data license to these files. We redistribute derived aggregates with
attribution, as is standard practice in this space (Ed-Data, GreatSchools, county
offices of education), and we document our sources exhaustively. If you are from CDE
and have concerns, please open an issue.
