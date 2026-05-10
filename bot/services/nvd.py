"""
services/nvd.py — National Vulnerability Database (NVD) v2 API client.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

import httpx

from bot import config

log = logging.getLogger(__name__)

NVD_BASE = "https://services.nvd.nist.gov/rest/json/cves/2.0"
HEADERS = {"apiKey": config.NVD_API_KEY} if config.NVD_API_KEY else {}


async def lookup_cve(cve_id: str) -> dict[str, Any] | None:
    """
    Fetch a single CVE by ID.  Returns a normalised dict or None on failure.
    """
    params = {"cveId": cve_id.upper()}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(NVD_BASE, params=params, headers=HEADERS)
            r.raise_for_status()
            data = r.json()
    except httpx.HTTPError as exc:
        log.error("NVD lookup failed for %s: %s", cve_id, exc)
        return None

    vulns = data.get("vulnerabilities", [])
    if not vulns:
        return None

    cve = vulns[0]["cve"]
    return _normalise(cve)


async def fetch_recent_cves(results_per_page: int = 10) -> list[dict[str, Any]]:
    """
    Fetch the most recently published CVEs.
    Used for automated daily feed posts.
    """
    params = {"resultsPerPage": results_per_page, "startIndex": 0}
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(NVD_BASE, params=params, headers=HEADERS)
            r.raise_for_status()
            data = r.json()
    except httpx.HTTPError as exc:
        log.error("NVD recent feed failed: %s", exc)
        return []

    return [_normalise(v["cve"]) for v in data.get("vulnerabilities", [])]


def _normalise(cve: dict) -> dict[str, Any]:
    cve_id = cve.get("id", "UNKNOWN")

    # Description (English preferred)
    descs = cve.get("descriptions", [])
    description = next(
        (d["value"] for d in descs if d.get("lang") == "en"), "No description."
    )

    # CVSS score
    metrics = cve.get("metrics", {})
    score, severity, vector = _extract_cvss(metrics)

    # References
    refs = [r["url"] for r in cve.get("references", [])[:3]]

    # Published date
    published = cve.get("published", "Unknown")

    return {
        "id": cve_id,
        "description": description[:1000],
        "score": score,
        "severity": severity,
        "vector": vector,
        "references": refs,
        "published": published,
        "hash": hashlib.md5(cve_id.encode()).hexdigest(),
    }


def _extract_cvss(metrics: dict) -> tuple[float | None, str, str]:
    """Try CVSS v3.1 → 3.0 → 2.0 in order."""
    for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
        entries = metrics.get(key, [])
        if entries:
            data = entries[0].get("cvssData", {})
            score = data.get("baseScore")
            severity = data.get("baseSeverity", "UNKNOWN")
            vector = data.get("vectorString", "")
            return score, severity, vector
    return None, "UNKNOWN", ""
