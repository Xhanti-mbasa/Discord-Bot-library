"""
services/eventbrite.py — Eventbrite Events API client.

Fetches Cape Town tech / cybersecurity events.
Supports free, paid, and price-filtered queries.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from bot import config

log = logging.getLogger(__name__)

BASE_URL = "https://www.eventbriteapi.com/v3/events/search/"
HEADERS = {"Authorization": f"Bearer {config.EVENTBRITE_TOKEN}"}


async def fetch_events(
    *,
    free_only: bool = False,
    max_price_zar: int | None = None,
    location: str = "Cape Town",
    results: int = 8,
) -> list[dict[str, Any]]:
    """
    Search Eventbrite for Cape Town tech events.

    Parameters
    ----------
    free_only:      Only return events with is_free=True.
    max_price_zar:  Return events at or below this price in ZAR.
    location:       Override default Cape Town location.
    results:        Maximum number of events to return.
    """
    params: dict[str, Any] = {
        "location.address": location,
        "location.within": "50km",
        "categories": "102",          # Science & Technology
        "sort_by": "date",
        "page_size": 50,
        "expand": "ticket_classes,venue",
    }
    if free_only:
        params["price"] = "free"

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(BASE_URL, params=params, headers=HEADERS)
            r.raise_for_status()
            data = r.json()
    except httpx.HTTPError as exc:
        log.error("Eventbrite fetch failed: %s", exc)
        return []

    events = []
    for ev in data.get("events", []):
        is_free = ev.get("is_free", False)
        tickets = ev.get("ticket_classes", [])
        min_price = _min_price(tickets)

        # Apply price filters
        if free_only and not is_free:
            continue
        if max_price_zar is not None and not is_free:
            if min_price is None or min_price > max_price_zar:
                continue

        name = ev.get("name", {}).get("text", "Unnamed event")
        description = ev.get("description", {}).get("text", "")[:300]
        url = ev.get("url", "")
        start = ev.get("start", {}).get("local", "")
        venue_obj = ev.get("venue") or {}
        venue = venue_obj.get("name", location)

        events.append(
            {
                "name": name,
                "description": description,
                "url": url,
                "start": start,
                "venue": venue,
                "is_free": is_free,
                "min_price": min_price,
            }
        )
        if len(events) >= results:
            break

    return events


def _min_price(tickets: list[dict]) -> float | None:
    prices = [
        t.get("cost", {}).get("major_value", None)
        for t in tickets
        if not t.get("free", True)
    ]
    numeric = [float(p) for p in prices if p is not None]
    return min(numeric) if numeric else None
