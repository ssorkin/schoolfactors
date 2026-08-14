"""CAASPP research-file acquisition.

Files are static zips under https://caaspp-elpac.ets.org/caaspp/researchfiles/ named
    sb_ca{YEAR}_{scope}_{format}_{vN}.zip
The version suffix differs per year and bumps when CDE reposts corrected data, so we
probe v1..v9 and take the highest that exists. 2020 does not exist (COVID).
"""

from __future__ import annotations

BASE = "https://caaspp-elpac.ets.org/caaspp/researchfiles"
SB_YEARS = [2015, 2016, 2017, 2018, 2019, 2021, 2022, 2023, 2024, 2025]

REFERENCE_FILES = [
    (f"{BASE}/Tests.zip", "test-ID lookup"),
    (f"{BASE}/StudentGroups.zip", "student-group lookup (current-year snapshot)"),
    (
        "https://caaspp-elpac.cde.ca.gov/caaspp/docs/CAASPP%20Public%20Web%20Reporting%20Change%20Log.pdf",
        "official change log of reporting-definition changes",
    ),
]


def find_versioned(year: int, scope: str = "all", fmt: str = "csv") -> str | None:
    """Return the highest-version URL that exists for a year's research file."""
    from schoolfactors.acquire.base import head_ok

    found = None
    for v in range(1, 10):
        url = f"{BASE}/sb_ca{year}_{scope}_{fmt}_v{v}.zip"
        if head_ok(url):
            found = url
    return found


def acquire(year: int | None = None) -> None:
    from schoolfactors.acquire.base import download

    years = [year] if year else SB_YEARS
    print("CAASPP reference files:")
    for url, note in REFERENCE_FILES:
        download("caaspp", url, note=note)

    for y in years:
        print(f"CAASPP Smarter Balanced {y}:")
        url = find_versioned(y)
        if url is None:
            print(f"  no research file found for {y} (2020 is expected to be missing)")
            continue
        # The _all_ zip bundles the entities file, so one download covers both.
        download("caaspp", url, note=f"SB summative research file, all student groups, {y}")
