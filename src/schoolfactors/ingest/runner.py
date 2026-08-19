"""Ingestion orchestrator for `sf ingest`."""

from __future__ import annotations


def run_ingest(dataset: str = "all") -> None:
    from schoolfactors.ingest import caaspp, cde, census, db, lausd_gis, lausd_seni

    if dataset in ("all", "caaspp"):
        print("Ingesting CAASPP research files:")
        caaspp.ingest_all()
    if dataset in ("all", "census"):
        print("Ingesting census ACS files:")
        census.ingest_all()
    if dataset in ("all", "lausd_gis"):
        print("Ingesting LAUSD GIS files:")
        lausd_gis.ingest_all()
    if dataset in ("all", "lausd_seni"):
        lausd_seni.ingest_all()
    if dataset == "all":
        print("Ingesting CDE families:")
        cde.ingest_all()
    elif dataset not in ("caaspp", "census", "lausd_gis", "lausd_seni"):
        cde.ingest_family(dataset)
    print("Rebuilding DuckDB views:")
    db.build()
    print("ingest done")
