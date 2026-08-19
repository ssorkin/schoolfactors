"""Census ACS acquisition via api.census.gov.

Fetches ACS 5-year detailed tables for the geographies we compare against CDE data:
school-district summary levels (950 elementary / 960 secondary / 970 unified) statewide,
and block groups for specific counties (used to apportion demographics onto attendance
areas). Each table's variable metadata (`groups/<table>.json`) is snapshotted alongside
the data so analysis can select variables by label instead of hardcoding variable IDs.

The data API requires an API key (keyless requests redirect to a "Missing Key" page).
Set CENSUS_API_KEY in the environment; sign up at
https://api.census.gov/data/key_signup.html. The key is appended to request URLs but
is REDACTED from manifest entries, which are committed to the repository.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

import httpx

from schoolfactors.acquire.base import (
    ManifestEntry,
    client,
    load_manifest,
    save_manifest,
    sha256_file,
)
from schoolfactors.paths import RAW_DIR

DATASET = "census"
ACS_BASE = "https://api.census.gov/data"
LATEST_VINTAGE = 2023
# District tables are acquired for every 5-year release back to 2015 so the
# site can draw resident-population series (windows overlap; series are labeled
# by end year). Block groups changed definition at the 2020 census, so BG
# tables stay single-vintage.
DISTRICT_VINTAGES = tuple(range(2015, LATEST_VINTAGE + 1))

# Registry of ACS 5-year tables to acquire. geo "district" fetches all three
# school-district summary levels for the state; geo "blockgroup" fetches every block
# group in each listed county. Add entries here to bring more tables into the store.
ACS_TABLES: dict[str, dict] = {
    # Age by ratio of income to poverty level; the census-residents counterpart to FRPM.
    "B17024": {"geo": "district"},
    # Sex by school enrollment by type by age: resident children 5-17 split into
    # public school / private school / not enrolled — the residence-based side of
    # "where did the students go?" (the practical API equivalent of NCES ACS-ED's
    # grade-relevant-children universe, which assigns children by residence).
    "B14003": {"geo": "district"},
    # Ratio of income to poverty level (all ages) — B17024 is not published at block
    # group, so attendance-area poverty comes from C17002.
    "C17002": {"geo": "blockgroup", "counties": ["037"]},
    # Hispanic or Latino origin by race — attendance-area race/ethnicity shares.
    "B03002": {"geo": "blockgroup", "counties": ["037"]},
    # Sex by age — resident school-age children per attendance area, banded to
    # each school's grade span (bins 5-9 / 10-14 / 15-17, split per single year).
    "B01001": {"geo": "blockgroup", "counties": ["037"]},
}

STATE_FIPS = "06"
SD_LEVELS = {
    "unified": "school district (unified)",
    "elementary": "school district (elementary)",
    "secondary": "school district (secondary)",
}


def _api_key() -> str:
    key = os.environ.get("CENSUS_API_KEY", "").strip()
    if not key:
        # Fallback: a git-ignored .env at the repo root (KEY=value lines).
        env_file = Path(__file__).resolve().parents[3] / ".env"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                name, _, value = line.partition("=")
                if name.strip() == "CENSUS_API_KEY":
                    key = value.strip().strip("'\"")
    if not key:
        raise RuntimeError(
            "CENSUS_API_KEY is not set. The Census data API requires a key; sign up "
            "(free, instant) at https://api.census.gov/data/key_signup.html, then "
            "either export CENSUS_API_KEY or put CENSUS_API_KEY=<key> in a .env file "
            "at the repo root (git-ignored). See CONTRIBUTING.md."
        )
    return key


def _fetch_json(filename: str, url: str, note: str, key: str | None = None) -> Path | None:
    """GET a JSON endpoint into data/raw/census/ and record a key-redacted manifest entry.

    acquire.base.download() records the exact request URL; census requests carry the
    API key as a query parameter, so this helper records `url` (without the key) while
    requesting `url` + key. Idempotent on existing file + matching manifest size.
    """
    dest_dir = RAW_DIR / DATASET
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / filename

    manifest = load_manifest(DATASET)
    entry = manifest.get(filename)
    if entry and dest.exists() and dest.stat().st_size == entry["size"]:
        return dest

    request_url = f"{url}&key={key}" if key else url
    try:
        resp = client().get(request_url)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        print(f"  FAILED {url}: {exc}")
        return None
    body = resp.text
    # The API serves errors (missing key, bad geography) as HTML redirect targets or
    # plain-text messages; only valid JSON may be recorded as data.
    try:
        json.loads(body)
    except ValueError:
        print(f"  FAILED {url}: response is not JSON (missing/invalid API key?)")
        return None

    dest.write_text(body)
    manifest[filename] = ManifestEntry(
        dataset=DATASET,
        filename=filename,
        url=url,  # key redacted: manifests are committed
        sha256=sha256_file(dest),
        size=dest.stat().st_size,
        downloaded_at=datetime.now(UTC).isoformat(timespec="seconds"),
        note=note,
    ).__dict__
    save_manifest(DATASET, manifest)
    print(f"  ok {filename} ({dest.stat().st_size:,} bytes)")
    return dest


def _quote(geo: str) -> str:
    return geo.replace(" ", "%20").replace("(", "%28").replace(")", "%29")


def acquire(vintage: int = LATEST_VINTAGE) -> None:
    key = _api_key()
    base = f"{ACS_BASE}/{vintage}/acs/acs5"
    for table, spec in ACS_TABLES.items():
        t = table.lower()
        # Variable metadata (keyless endpoint): lets analysis pick bins by label.
        _fetch_json(
            f"acs5_{vintage}_groups_{t}.json",
            f"{base}/groups/{table}.json",
            note=f"ACS5 {vintage} variable metadata for {table}",
        )
        if spec["geo"] == "district":
            for v in sorted({vintage, *DISTRICT_VINTAGES}):
                vbase = f"{ACS_BASE}/{v}/acs/acs5"
                if v != vintage:
                    _fetch_json(
                        f"acs5_{v}_groups_{t}.json",
                        f"{vbase}/groups/{table}.json",
                        note=f"ACS5 {v} variable metadata for {table}",
                    )
                for level, geo_name in SD_LEVELS.items():
                    _fetch_json(
                        f"acs5_{v}_{t}_sd_{level}.json",
                        f"{vbase}?get=NAME,group({table})"
                        f"&for={_quote(geo_name)}:*&in=state:{STATE_FIPS}",
                        note=f"ACS5 {v} {table}, {geo_name}, state {STATE_FIPS}",
                        key=key,
                    )
        elif spec["geo"] == "blockgroup":
            for county in spec["counties"]:
                _fetch_json(
                    f"acs5_{vintage}_{t}_bg_{STATE_FIPS}{county}.json",
                    f"{base}?get=NAME,group({table})"
                    f"&for={_quote('block group')}:*&in=state:{STATE_FIPS}%20county:{county}",
                    note=f"ACS5 {vintage} {table}, block groups, county {STATE_FIPS}{county}",
                    key=key,
                )
        else:  # pragma: no cover - registry validation
            raise ValueError(f"unknown geo kind {spec['geo']!r} for {table}")
