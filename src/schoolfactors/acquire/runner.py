"""Acquisition orchestrator for `sf acquire`."""

from __future__ import annotations

from schoolfactors.acquire import caaspp, cde, dashboard

CAASPP_SETS = {"caaspp"}
DASHBOARD_SETS = {"dashboard", "growth"}


def run_acquire(dataset: str = "all", year: int | None = None) -> None:
    if dataset in ("all", *CAASPP_SETS):
        caaspp.acquire(year=year)
    if dataset in ("all", *DASHBOARD_SETS):
        dashboard.acquire(year=year)
    if dataset == "all" or dataset not in (CAASPP_SETS | DASHBOARD_SETS):
        cde.acquire(dataset=dataset)
    print("acquire done")
