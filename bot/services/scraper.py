"""
services/scraper.py — Lightweight fallback scraper for OfferZen / PNet.

Used when Adzuna returns insufficient results.
Rate-limited and polite (robots.txt respected where possible).
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

import httpx

log = logging.getLogger(__name__)

OFFERZEN_URL = "https://www.offerzen.com/api/v1/job_listings?query=cybersecurity&location=cape+town"
PNET_URL = "https://www.pnet.co.za/api/jobs?keyword=cybersecurity+junior&location=cape+town"

HEADERS = {
    "User-Agent": "CyberCapeBot/1.0 (community Discord bot; contact via GitHub)"
}


def _hash_job(title: str, company: str) -> str:
    return hashlib.md5(f"{title}{company}".encode()).hexdigest()


async def scrape_offerzen(limit: int = 5) -> list[dict[str, Any]]:
    """
    Attempt to pull OfferZen listings via their unofficial JSON endpoint.
    Returns empty list on failure — this is a best-effort fallback.
    """
    try:
        async with httpx.AsyncClient(timeout=15, headers=HEADERS) as client:
            r = await client.get(OFFERZEN_URL)
            r.raise_for_status()
            listings = r.json()

        if not isinstance(listings, list):
            listings = listings.get("listings", listings.get("jobs", []))

        jobs = []
        for item in listings[:limit]:
            title = item.get("title", item.get("role", ""))
            company = item.get("company", {})
            company_name = company if isinstance(company, str) else company.get("name", "")
            jobs.append(
                {
                    "title": title,
                    "company": company_name,
                    "location": "Cape Town",
                    "url": item.get("url", "https://www.offerzen.com"),
                    "salary_min": None,
                    "salary_max": None,
                    "description": item.get("description", "")[:400],
                    "source": "OfferZen",
                    "hash": _hash_job(title, company_name),
                }
            )
        return jobs
    except Exception as exc:
        log.warning("OfferZen scrape failed (non-critical): %s", exc)
        return []


async def scrape_pnet(limit: int = 5) -> list[dict[str, Any]]:
    """
    Attempt to pull PNet listings. Returns empty list on failure.
    """
    try:
        async with httpx.AsyncClient(timeout=15, headers=HEADERS) as client:
            r = await client.get(PNET_URL)
            r.raise_for_status()
            data = r.json()

        listings = data if isinstance(data, list) else data.get("jobs", [])

        jobs = []
        for item in listings[:limit]:
            title = item.get("title", item.get("jobTitle", ""))
            company = item.get("company", item.get("employer", "Unknown"))
            jobs.append(
                {
                    "title": title,
                    "company": company,
                    "location": item.get("location", "Cape Town"),
                    "url": item.get("url", item.get("applyUrl", "https://www.pnet.co.za")),
                    "salary_min": None,
                    "salary_max": None,
                    "description": item.get("description", "")[:400],
                    "source": "PNet",
                    "hash": _hash_job(title, company),
                }
            )
        return jobs
    except Exception as exc:
        log.warning("PNet scrape failed (non-critical): %s", exc)
        return []
