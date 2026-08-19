"""LAUSD Student Equity Needs Index (SENI) acquisition.

SENI is LAUSD's own equity index (built with community groups; 15 academic and
community indicators) that allocates ~$700M/yr directly to schools by need. The
per-school scores/ranks/allocations live in LAUSD's Open Data Catalog (Laserfiche
WebLink): https://my.lausd.net/OpenDataCatalog/Browse.aspx?id=6&dbid=0&repo=OpenDataCatalog

The catalog sits behind bot protection and its Download button is Angular-driven, so
this cannot be fully scripted here. The working flow (kept in the raw dir's README):

1. Open a DocView.aspx page in a real browser and export its session cookies.
2. POST ZipEntriesHandler.aspx/StartExport with the catalog entry id -> token.
3. Poll CheckExportStatus, then GET ExportJobHandler.aspx/GetExportJob/?token=...
   (single-entry "zip" exports come back as the raw CSV).

Drop the CSVs (SENI_<year>.csv and dictionaries/) into data/raw/lausd_seni/ and run
`sf acquire --dataset lausd_seni`; `register_manual()` records manifest entries
(sha256, size, catalog URL, manual-download note) so provenance stays complete.
"""

from __future__ import annotations

from datetime import UTC, datetime

import httpx

from schoolfactors.acquire.base import (
    ManifestEntry,
    load_manifest,
    save_manifest,
    sha256_file,
)
from schoolfactors.paths import RAW_DIR

DATASET = "lausd_seni"
SOURCE_PAGE = (
    "https://my.lausd.net/OpenDataCatalog/Browse.aspx?id=6&dbid=0&repo=OpenDataCatalog"
)

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# Candidate direct URLs observed for SENI documents; hosts rotate, so failures are
# expected and fall through to the manual path.
CANDIDATE_URLS: list[tuple[str, str]] = [
    (
        "https://media.edlio.net/64ddac7d/710e69a5/1fa710cd/b5f4b4f3ed6f48c784652e10b1798661",
        "seni_2024_25_overview.pdf",
    ),
]


def register_manual() -> int:
    """Record manifest entries for hand-downloaded files in data/raw/lausd_seni/."""
    raw = RAW_DIR / DATASET
    if not raw.exists():
        return 0
    manifest = load_manifest(DATASET)
    added = 0
    for path in sorted(p for p in raw.rglob("*") if p.is_file()):
        name = str(path.relative_to(raw))
        entry = manifest.get(name)
        if entry and entry["size"] == path.stat().st_size:
            continue
        manifest[name] = ManifestEntry(
            dataset=DATASET,
            filename=name,
            url=SOURCE_PAGE,
            sha256=sha256_file(path),
            size=path.stat().st_size,
            downloaded_at=datetime.now(UTC).isoformat(timespec="seconds"),
            note="manually exported from the bot-protected Open Data Catalog "
            "(see module docstring for the flow); URL is the catalog page",
        ).__dict__
        added += 1
        print(f"  registered manual file {name} ({path.stat().st_size:,} bytes)")
    if added:
        save_manifest(DATASET, manifest)
    return added


def acquire() -> None:
    raw = RAW_DIR / DATASET
    raw.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest(DATASET)
    for url, filename in CANDIDATE_URLS:
        dest = raw / filename
        entry = manifest.get(filename)
        if entry and dest.exists() and dest.stat().st_size == entry["size"]:
            continue
        try:
            resp = httpx.get(url, headers=BROWSER_HEADERS, follow_redirects=True, timeout=60)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            print(f"  FAILED {filename}: {exc}")
            continue
        if resp.content[:5].lstrip().lower().startswith(b"<html"):
            print(f"  FAILED {filename}: bot-protection page served instead of the file")
            continue
        dest.write_bytes(resp.content)
        manifest[filename] = ManifestEntry(
            dataset=DATASET,
            filename=filename,
            url=url,
            sha256=sha256_file(dest),
            size=dest.stat().st_size,
            downloaded_at=datetime.now(UTC).isoformat(timespec="seconds"),
            note="SENI document (LAUSD LCAP)",
        ).__dict__
        save_manifest(DATASET, manifest)
        print(f"  ok {filename} ({dest.stat().st_size:,} bytes)")

    register_manual()
    tables = list((RAW_DIR / DATASET).glob("SENI*.csv"))
    if not tables:
        print(
            "  NOTE: no SENI_<year>.csv present. The per-school scores/allocations "
            f"files are bot-protected; export them from {SOURCE_PAGE} (flow in this "
            "module's docstring) into data/raw/lausd_seni/ and re-run "
            "`sf acquire --dataset lausd_seni` to record provenance."
        )
