"""SchoolFactors pipeline CLI: acquire → ingest → check → analyze → export."""

import typer

app = typer.Typer(no_args_is_help=True, help=__doc__)


@app.command()
def acquire(
    dataset: str = typer.Option("all", help="Dataset family (caaspp, cde, dashboard, all)"),
    year: int | None = typer.Option(None, help="Single test/academic year (e.g. 2024); default all"),
) -> None:
    """Download source files and record provenance manifests."""
    from schoolfactors.acquire.runner import run_acquire

    run_acquire(dataset=dataset, year=year)


@app.command()
def ingest(
    dataset: str = typer.Option("all", help="Dataset family to ingest (caaspp, cde, all)"),
) -> None:
    """Normalize raw files into Parquet + DuckDB."""
    from schoolfactors.ingest.runner import run_ingest

    run_ingest(dataset=dataset)


@app.command()
def check() -> None:
    """Run data-quality validation and regenerate the DQ report."""
    from schoolfactors.quality.runner import run_checks

    run_checks()


@app.command()
def analyze() -> None:
    """Fit the school-performance models and write analysis outputs."""
    from schoolfactors.analysis.runner import run_analysis

    run_analysis()


@app.command()
def export() -> None:
    """Export prebuilt JSON for the website."""
    from schoolfactors.analysis.export import run_export

    run_export()


if __name__ == "__main__":
    app()
