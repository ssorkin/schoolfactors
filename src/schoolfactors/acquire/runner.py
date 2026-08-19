"""Acquisition orchestrator for `sf acquire`."""

from __future__ import annotations

from schoolfactors.acquire import caaspp, cde, census, dashboard, lausd_gis, lausd_seni

CAASPP_SETS = {"caaspp"}
DASHBOARD_SETS = {"dashboard", "growth"}
# Families with their own acquirers, which must not fall through to the CDE scraper.
NON_CDE_SETS = {"census", "lausd_gis", "lausd_seni"}


def run_acquire(dataset: str = "all", year: int | None = None) -> None:
    from schoolfactors.acquire.base import WafBlocked

    try:
        if dataset in ("all", *CAASPP_SETS):
            caaspp.acquire(year=year)
        if dataset in ("all", *DASHBOARD_SETS):
            dashboard.acquire(year=year)
        if dataset in ("all", "census"):
            try:
                census.acquire()
            except RuntimeError as exc:
                if dataset == "census":
                    raise
                print(f"  skipping census: {exc}")
        if dataset in ("all", "lausd_gis"):
            lausd_gis.acquire()
        if dataset in ("all", "lausd_seni"):
            lausd_seni.acquire()
        if dataset == "all" or dataset not in (CAASPP_SETS | DASHBOARD_SETS | NON_CDE_SETS):
            cde.acquire(dataset=dataset)
    except WafBlocked as exc:
        print(f"\nSTOPPED: {exc}")
        print("CDE's WAF has blocked this client. Wait a few hours and re-run; the")
        print("downloader is idempotent and will resume where it left off.")
        raise SystemExit(2)
    print("acquire done")
