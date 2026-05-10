"""
services/rss.py — RSS / Atom feed aggregator with deduplication.

Sources:
  - BleepingComputer
  - The Hacker News
  - CISA Advisories

Also polls the Hacker News JSON API for top cybersecurity stories.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from typing import Any

import feedparser
import httpx

from bot import config

log = logging.getLogger(__name__)

HN_TOP_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{}.json"

SEVERITY_KEYWORDS: dict[str, list[str]] = {
    "critical": ["critical", "zero-day", "0day", "actively exploited", "rce", "remote code"],
    "high": ["high", "privilege escalation", "auth bypass", "sql injection"],
    "medium": ["medium", "xss", "csrf", "information disclosure"],
    "low": ["low", "patch", "update", "advisory"],
}


def classify_severity(text: str) -> str:
    lower = text.lower()
    for level in ("critical", "high", "medium", "low"):
        if any(kw in lower for kw in SEVERITY_KEYWORDS[level]):
            return level
    return "info"


def _hash_item(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()


async def fetch_rss_feed(url: str) -> list[dict[str, Any]]:
    """Parse a single RSS/Atom feed and return normalised items."""
    try:
        loop = asyncio.get_event_loop()
        feed = await loop.run_in_executor(None, feedparser.parse, url)
    except Exception as exc:
        log.error("RSS parse error for %s: %s", url, exc)
        return []

    items = []
    for entry in feed.entries[:15]:
        title = entry.get("title", "")
        link = entry.get("link", "")
        summary = entry.get("summary", "")[:300]
        published = entry.get("published", "")
        if not link:
            continue
        items.append(
            {
                "title": title,
                "url": link,
                "summary": summary,
                "published": published,
                "source": feed.feed.get("title", url),
                "severity": classify_severity(f"{title} {summary}"),
                "hash": _hash_item(link),
            }
        )
    return items


async def fetch_all_rss() -> list[dict[str, Any]]:
    """Fetch all configured RSS feeds concurrently."""
    tasks = [fetch_rss_feed(url) for url in config.RSS_FEEDS]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    items: list[dict] = []
    for r in results:
        if isinstance(r, list):
            items.extend(r)
    # deduplicate by hash
    seen: set[str] = set()
    unique = []
    for item in items:
        if item["hash"] not in seen:
            seen.add(item["hash"])
            unique.append(item)
    return unique


async def fetch_hackernews_cyber(limit: int = 5) -> list[dict[str, Any]]:
    """
    Pull top Hacker News stories, filter for cybersecurity relevance.
    """
    cyber_keywords = {
        "hack", "vuln", "exploit", "security", "breach", "malware",
        "ransomware", "phishing", "cve", "cyber", "password", "leak",
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(HN_TOP_URL)
            r.raise_for_status()
            top_ids: list[int] = r.json()[:50]

            items = []
            for story_id in top_ids:
                if len(items) >= limit:
                    break
                try:
                    ir = await client.get(HN_ITEM_URL.format(story_id))
                    ir.raise_for_status()
                    story = ir.json()
                except Exception:
                    continue

                title = story.get("title", "")
                url = story.get("url", f"https://news.ycombinator.com/item?id={story_id}")
                if any(kw in title.lower() for kw in cyber_keywords):
                    items.append(
                        {
                            "title": title,
                            "url": url,
                            "summary": "",
                            "published": "",
                            "source": "Hacker News",
                            "severity": classify_severity(title),
                            "hash": _hash_item(url),
                        }
                    )
            return items
    except httpx.HTTPError as exc:
        log.error("Hacker News fetch failed: %s", exc)
        return []
