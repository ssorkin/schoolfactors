"""Shared download machinery: HTTP client, streaming downloads, provenance manifests.

Every downloaded file gets a manifest entry (manifests/<dataset>.json) recording the
exact URL, size, SHA-256, and timestamp, so any published number can be traced back to
a byte-identical source file. Downloads are idempotent: a file whose manifest entry and
on-disk hash both match is skipped.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import httpx

from schoolfactors.paths import MANIFEST_DIR, RAW_DIR

USER_AGENT = (
    "SchoolFactors/0.1 (open-source education data project; "
    "https://github.com/ssorkin/schoolfactors; ssorkin@gmail.com)"
)

_client: httpx.Client | None = None


class WafBlocked(RuntimeError):
    """CDE's Radware WAF has blocked this client (303 → www6.cde.ca.gov/wafalert.html).

    When this fires, stop hitting CDE hosts entirely and retry hours later with slow
    pacing — continuing just extends the block.
    """


def client() -> httpx.Client:
    global _client
    if _client is None:
        _client = httpx.Client(
            headers={"User-Agent": USER_AGENT},
            timeout=httpx.Timeout(30.0, read=120.0),
            follow_redirects=True,
        )
    return _client


def _check_waf(resp: httpx.Response) -> None:
    for r in [*resp.history, resp]:
        loc = r.headers.get("location", "")
        if "wafalert" in loc:
            raise WafBlocked(f"CDE WAF block redirect at {r.url}")


def _waf_guard(exc: httpx.HTTPError, url: str) -> None:
    """Redirect loops on cde.ca.gov hosts are the WAF block in disguise."""
    if isinstance(exc, httpx.TooManyRedirects) and "cde.ca.gov" in url:
        raise WafBlocked(f"redirect loop (WAF block) at {url}") from exc


def head_ok(url: str, throttle_seconds: float = 2.0) -> bool:
    """True if the URL exists (HEAD 200). Throttled: probe bursts trip CDE's WAF."""
    time.sleep(throttle_seconds)
    try:
        resp = client().head(url)
        _check_waf(resp)
        return resp.status_code == 200
    except WafBlocked:
        raise
    except httpx.HTTPError:
        return False


@dataclass
class ManifestEntry:
    dataset: str
    filename: str
    url: str
    sha256: str
    size: int
    downloaded_at: str
    note: str = ""


def _manifest_path(dataset: str) -> Path:
    return MANIFEST_DIR / f"{dataset}.json"


def load_manifest(dataset: str) -> dict[str, dict]:
    path = _manifest_path(dataset)
    if path.exists():
        return json.loads(path.read_text())
    return {}


def save_manifest(dataset: str, manifest: dict[str, dict]) -> None:
    path = _manifest_path(dataset)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(sorted(manifest.items())), indent=2) + "\n")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download(
    dataset: str,
    url: str,
    filename: str | None = None,
    note: str = "",
    throttle_seconds: float = 3.0,
    force: bool = False,
) -> Path | None:
    """Stream-download url into data/raw/<dataset>/ and record a manifest entry.

    Returns the local path, or None if the download failed (recorded nowhere).
    """
    from urllib.parse import unquote

    filename = filename or unquote(url.rsplit("/", 1)[-1].split("?")[0]).replace(" ", "_")
    dest_dir = RAW_DIR / dataset
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / filename

    manifest = load_manifest(dataset)
    entry = manifest.get(filename)
    if not force and entry and dest.exists() and dest.stat().st_size == entry["size"]:
        return dest  # trust size match for speed; `sf check` re-verifies hashes

    tmp = dest.with_suffix(dest.suffix + ".part")
    h = hashlib.sha256()
    first = b""
    try:
        with client().stream("GET", url) as resp:
            _check_waf(resp)
            resp.raise_for_status()
            with tmp.open("wb") as f:
                for chunk in resp.iter_bytes(1 << 20):
                    if not first:
                        first = chunk[:2048]
                    h.update(chunk)
                    f.write(chunk)
    except httpx.HTTPError as exc:
        tmp.unlink(missing_ok=True)
        _waf_guard(exc, url)
        print(f"  FAILED {url}: {exc}")
        return None

    # A WAF block page served with 200 must never be recorded as data.
    if b"Department of Education Block" in first or (
        not filename.endswith((".html", ".pdf")) and first.lstrip()[:6].lower() == b"<html>"
    ):
        tmp.unlink(missing_ok=True)
        raise WafBlocked(f"block page served for {url}")

    tmp.rename(dest)
    manifest[filename] = ManifestEntry(
        dataset=dataset,
        filename=filename,
        url=url,
        sha256=h.hexdigest(),
        size=dest.stat().st_size,
        downloaded_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        note=note,
    ).__dict__
    save_manifest(dataset, manifest)
    print(f"  ok {filename} ({dest.stat().st_size:,} bytes)")
    time.sleep(throttle_seconds)
    return dest


def scrape_hrefs(page_url: str, contains: str) -> list[str]:
    """Return absolute hrefs on a landing page whose URL contains `contains`.

    CDE/CAASPP silently repost files with -v2/-v3/_v2 suffixes, so URLs must be
    discovered from the landing page at download time, never hardcoded.
    """
    from urllib.parse import urljoin

    from bs4 import BeautifulSoup

    try:
        resp = client().get(page_url)
    except httpx.HTTPError as exc:
        _waf_guard(exc, page_url)
        raise
    _check_waf(resp)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")
    out: list[str] = []
    for a in soup.find_all("a", href=True):
        href = urljoin(page_url, a["href"])
        if contains.lower() in href.lower() and href not in out:
            out.append(href)
    return out
