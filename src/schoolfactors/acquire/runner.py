"""Acquisition orchestrator for `sf acquire`."""

from __future__ import annotations

from schoolfactors.acquire import caaspp, cde, dashboard

CAASPP_SETS = {"caaspp"}
DASHBOARD_SETS = {"dashboard", "growth"}


def run_acquire(dataset: str = "all", year: int | None = None) -> None:
    from schoolfactors.acquire.base import WafBlocked

    try:
        if dataset in ("all", *CAASPP_SETS):
            caaspp.acquire(year=year)
        if dataset in ("all", *DASHBOARD_SETS):
            dashboard.acquire(year=year)
        if dataset == "all" or dataset not in (CAASPP_SETS | DASHBOARD_SETS):
            cde.acquire(dataset=dataset)
    except WafBlocked as exc:
        print(f"\nSTOPPED: {exc}")
        print("CDE's WAF has blocked this client. Wait a few hours and re-run; the")
        print("downloader is idempotent and will resume where it left off.")
        raise SystemExit(2)
    print("acquire done")
