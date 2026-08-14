"""California School Dashboard indicator files + CA growth model.

Files live under https://www3.cde.ca.gov/researchfiles/cadashboard/ as
<stem>download<YYYY>.txt where YYYY is the Dashboard release year (spring of the
school year). No 2020/2021 releases (COVID). Stems are probed, not guessed blindly:
the census-enrollment stem, for instance, is censusenrollratesdownload, not
censusenrolldownload.
"""

from __future__ import annotations

BASE = "https://www3.cde.ca.gov/researchfiles/cadashboard"
YEARS = [2017, 2018, 2019, 2022, 2023, 2024, 2025]
STEMS = ["ela", "math", "chronic", "grad", "susp", "cci", "elpi", "censusenrollrates"]

# CA growth model data files (landing: cde.ca.gov/ta/ac/cm/growthmodeldatafiles.asp)
GROWTH_LANDING = "https://www.cde.ca.gov/ta/ac/cm/growthmodeldatafiles.asp"


def acquire(year: int | None = None) -> None:
    from schoolfactors.acquire.base import download, head_ok, scrape_hrefs

    years = [year] if year else YEARS
    for y in years:
        print(f"Dashboard {y}:")
        for stem in STEMS:
            for suffix in ("", "f"):  # 2017 files carry an 'f' suffix
                url = f"{BASE}/{stem}download{y}{suffix}.txt"
                if head_ok(url):
                    download("dashboard", url, note=f"Dashboard {stem} indicator, {y}")
                    break

    print("CA growth model files:")
    try:
        for url in scrape_hrefs(GROWTH_LANDING, "researchfiles/cadashboard"):
            if url.endswith(".txt"):
                download("growth", url, note="CA growth model (validation benchmark)")
    except Exception as exc:  # noqa: BLE001
        print(f"  FAILED to scrape growth-model landing page: {exc}")
