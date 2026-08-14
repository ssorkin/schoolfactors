"""Ingestion orchestrator for `sf ingest`."""

from __future__ import annotations


def run_ingest(dataset: str = "all") -> None:
    from schoolfactors.ingest import caaspp, cde, db

    if dataset in ("all", "caaspp"):
        print("Ingesting CAASPP research files:")
        caaspp.ingest_all()
    if dataset == "all":
        print("Ingesting CDE families:")
        cde.ingest_all()
    elif dataset != "caaspp":
        cde.ingest_family(dataset)
    print("Rebuilding DuckDB views:")
    db.build()
    print("ingest done")
