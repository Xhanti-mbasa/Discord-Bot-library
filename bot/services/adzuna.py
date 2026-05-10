"""
services/adzuna.py — Adzuna Jobs API client.

Targets junior / internship cybersecurity roles in South Africa,
defaulting to Cape Town.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

import httpx

from bot import config

log = logging.getLogger(__name__)

BASE_URL = "https://api.adzuna.com/v1/api/jobs/za/search/1"

JUNIOR_KEYWORDS = [
    "junior", "graduate", "entry level", "entry-level",
    "internship", "intern", "trainee", "learnership",
]


def _is_junior(title: str, description: str) -> bool:
    combined = f"{title} {description}".lower()
    return any(kw in combined for kw in JUNIOR_KEYWORDS)


def _job_hash(job: dict) -> str:
    key = job.get("redirect_url", job.get("title", ""))
    return hashlib.md5(key.encode()).hexdigest()


async def fetch_jobs(
    *,
    remote: bool = False,
    internships_only: bool = False,
    location: str = "Cape Town",
    results: int = 10,
) -> list[dict[str, Any]]:
    """
    Search Adzuna for junior / internship cybersecurity roles.
    """
    what = "internship cybersecurity" if internships_only else "junior cybersecurity security"
    where = "" if remote else location

    params: dict[str, Any] = {
        "app_id": config.ADZUNA_APP_ID,
        "app_key": config.ADZUNA_APP_KEY,
        "results_per_page": results * 3,  # fetch more, filter down
        "what": what,
        "content-type": "application/json",
    }
    if where:
        params["where"] = where
    if remote:
        params["what"] = f"remote {what}"

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(BASE_URL, params=params)
            r.raise_for_status()
            data = r.json()
    except httpx.HTTPError as exc:
        log.error("Adzuna fetch failed: %s", exc)
        return []

    raw_jobs = data.get("results", [])
    jobs = []
    for job in raw_jobs:
        title = job.get("title", "")
        description = job.get("description", "")[:500]

        if not _is_junior(title, description):
            continue

        jobs.append(
            {
                "title": title,
                "company": job.get("company", {}).get("display_name", "Unknown"),
                "location": job.get("location", {}).get("display_name", location),
                "url": job.get("redirect_url", ""),
                "salary_min": job.get("salary_min"),
                "salary_max": job.get("salary_max"),
                "description": description,
                "created": job.get("created", ""),
                "remote": remote,
                "hash": _job_hash(job),
            }
        )
        if len(jobs) >= results:
            break

    return jobs
