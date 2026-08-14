"""CDE downloadable-data acquisition.

Landing pages (www.cde.ca.gov/ds/ad/*.asp) are scraped for current file hrefs because
CDE silently reposts revised files with -v2/-v3 (or _v2 for FRPM) suffixes. Payloads
live mostly on www3.cde.ca.gov/demo-downloads/.
"""

from __future__ import annotations

CDE = "https://www.cde.ca.gov"

# (dataset, landing page, href-substring filter, note)
SCRAPED_FAMILIES: list[tuple[str, str, str, str]] = [
    (
        "enrollment",
        f"{CDE}/ds/ad/filesenrcensus.asp",
        "demo-downloads/census/cdenroll",
        "census-day enrollment by school, 2023-24+ format",
    ),
    (
        "enrollment_hist",
        f"{CDE}/ds/ad/fileshistenr8122.asp",
        "demo-downloads/enrsch/",
        "historical enrollment by school 1981-2023 (no names; join directory)",
    ),
    ("frpm", f"{CDE}/ds/ad/filessp.asp", "documents/frpm", "FRPM student poverty (xlsx)"),
    (
        "cupc",
        f"{CDE}/ds/ad/filescupc.asp",
        "documents/cupc",
        "CALPADS unduplicated pupil count (LCFF: FRPM ∪ EL ∪ foster)",
    ),
    ("staff_exp", f"{CDE}/ds/ad/filesstex.asp", "demo-downloads/staff/stex", "teacher experience"),
    ("staff_edu", f"{CDE}/ds/ad/filessted.asp", "demo-downloads/staff/sted", "teacher education"),
    (
        "staff_ratio",
        f"{CDE}/ds/ad/filesstrat.asp",
        "demo-downloads/staff/strat",
        "student/staff ratios (beware quoted thousands separators)",
    ),
    (
        "absenteeism",
        f"{CDE}/ds/ad/filesabd.asp",
        "demo-downloads/attendance/chronicabsenteeism",
        "chronic absenteeism (2016-17+, none for 2019-20)",
    ),
    (
        "suspension",
        f"{CDE}/ds/ad/filessd.asp",
        "demo-downloads/discipline/suspension",
        "suspension counts/rates",
    ),
    (
        "expulsion",
        f"{CDE}/ds/ad/filesed.asp",
        "demo-downloads/discipline/expulsion",
        "expulsion counts/rates",
    ),
    (
        "acgr",
        f"{CDE}/ds/ad/filesacgr.asp",
        "demo-downloads/acgr/acgr",
        "adjusted cohort graduation rate (2016-17+; methodology break vs earlier)",
    ),
    (
        "cgr",
        f"{CDE}/ds/ad/filescgr12.asp",
        "demo-downloads/cgr/cgr12mo",
        "12-month college-going rate",
    ),
    (
        "stability",
        f"{CDE}/ds/ad/filessr.asp",
        "demo-downloads/",
        "student stability rate (mobility covariate)",
    ),
    (
        "ppe",
        f"{CDE}/fg/ac/es/essappedata.asp",
        "documents/essappe",
        "ESSA per-pupil expenditure — only school-level spending file",
    ),
    (
        "currentexpense",
        f"{CDE}/ds/fd/ec/currentexpense.asp",
        "documents/currentexpense",
        "current expense of education, district per-ADA",
    ),
    (
        "tamo",
        f"{CDE}/ds/ad/filestamo.asp",
        "demo-downloads/tamo",
        "teacher assignment/credential alignment (large, ~230MB/yr)",
    ),
]

DIRECTORY_FILES = [
    (
        f"{CDE}/schooldirectory/report?rid=dl1&tp=txt",
        "pubschls.txt",
        "public schools directory (current snapshot; 'No Data' = null)",
    ),
    (
        f"{CDE}/schooldirectory/report?rid=dl2&tp=txt",
        "pubdistricts.txt",
        "districts/COE directory",
    ),
]

# English learner files are served only from dq.cde.ca.gov, whose robots.txt is a
# blanket Disallow. Decision (documented in docs/provenance): these are one-shot,
# human-directed downloads of files CDE links publicly from an allowed landing page
# (www.cde.ca.gov/ds/ad/fileselsch.asp); we throttle to 10s between requests.
EL_YEARS = [f"{y}-{str(y + 1)[2:]}" for y in range(2011, 2026)]
EL_URL = (
    "https://dq.cde.ca.gov/dataquest/dlfile/dlfile.aspx"
    "?cLevel=School&cYear={year}&cCat=EL&cPage=fileselsch"
)


def acquire(dataset: str = "all") -> None:
    from schoolfactors.acquire.base import download, scrape_hrefs

    want = None if dataset in ("all", "cde") else dataset

    print("CDE directory files:")
    if want in (None, "directory"):
        for url, filename, note in DIRECTORY_FILES:
            download("directory", url, filename=filename, note=note)

    for name, landing, contains, note in SCRAPED_FAMILIES:
        if want is not None and want != name:
            continue
        print(f"CDE {name} ({landing}):")
        try:
            hrefs = scrape_hrefs(landing, contains)
        except Exception as exc:  # noqa: BLE001 - keep acquiring other families
            from schoolfactors.acquire.base import WafBlocked

            if isinstance(exc, WafBlocked):
                raise
            print(f"  FAILED to scrape landing page: {exc}")
            continue
        if not hrefs:
            print("  no matching hrefs found — landing page layout may have changed")
        for url in hrefs:
            download(name, url, note=note)

    if want in (None, "el"):
        print("CDE English learners (dq.cde.ca.gov, throttled):")
        for year in EL_YEARS:
            yy = year[2:4]
            download(
                "el",
                EL_URL.format(year=year),
                filename=f"elsch{yy}.txt",
                note=f"EL by school/grade/language, {year}",
                throttle_seconds=10.0,
            )
