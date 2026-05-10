"""
config.py — Centralised configuration loader.
All settings come from environment variables; nothing is hard-coded.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root
load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")


def _require(key: str) -> str:
    """Raise early if a mandatory env-var is missing."""
    val = os.getenv(key)
    if not val:
        raise EnvironmentError(f"Missing required environment variable: {key}")
    return val


def _optional(key: str, default: str = "") -> str:
    return os.getenv(key, default)


def _int(key: str, default: int = 0) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except ValueError:
        return default


# ── Discord ──────────────────────────────────────────────────────────────────
DISCORD_TOKEN: str = _require("DISCORD_TOKEN")

# ── External APIs ─────────────────────────────────────────────────────────────
NVD_API_KEY: str = _optional("NVD_API_KEY")
ADZUNA_APP_ID: str = _optional("ADZUNA_APP_ID")
ADZUNA_APP_KEY: str = _optional("ADZUNA_APP_KEY")
EVENTBRITE_TOKEN: str = _optional("EVENTBRITE_TOKEN")

# ── Channel IDs ───────────────────────────────────────────────────────────────
CHANNEL_CYBER_NEWS: int = _int("CHANNEL_CYBER_NEWS")
CHANNEL_JOBS: int = _int("CHANNEL_JOBS")
CHANNEL_EVENTS: int = _int("CHANNEL_EVENTS")
CHANNEL_RESOURCES: int = _int("CHANNEL_RESOURCES")
CHANNEL_CTF: int = _int("CHANNEL_CTF")
CHANNEL_MOD_LOGS: int = _int("CHANNEL_MOD_LOGS")
CHANNEL_LEADERBOARD: int = _int("CHANNEL_LEADERBOARD")
CHANNEL_GENERAL: int = _int("CHANNEL_GENERAL")

# ── Database ──────────────────────────────────────────────────────────────────
DB_PATH: str = _optional("DB_PATH", "bot/db/cybercape.db")

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_LEVEL: str = _optional("LOG_LEVEL", "INFO").upper()

# ── XP / Ranking constants ────────────────────────────────────────────────────
XP_PER_MESSAGE: int = 10
XP_COOLDOWN_SECONDS: int = 60
XP_DAILY_CAP: int = 500
XP_STREAK_BONUS: dict[int, int] = {3: 50, 7: 150, 30: 500}

RANKS: list[tuple[int, str]] = [
    (0,    "Script Kiddie"),
    (500,  "Packet Sniffer"),
    (1500, "Recon Scout"),
    (3000, "Exploit Hunter"),
    (6000, "Threat Analyst"),
    (10000, "Red Teamer"),
    (20000, "Root"),
]

# ── Moderation constants ──────────────────────────────────────────────────────
RAID_JOIN_THRESHOLD: int = 10      # accounts joined within …
RAID_JOIN_WINDOW_SECONDS: int = 30  # … this many seconds
MAX_WARNINGS_BEFORE_BAN: int = 3

BAD_WORDS: frozenset[str] = frozenset(
    {
        # Add community-specific disallowed words here.
        # Kept intentionally minimal; extend in .env or a config file.
        "slur1",
        "slur2",
    }
)

# ── RSS feeds ─────────────────────────────────────────────────────────────────
RSS_FEEDS: list[str] = [
    "https://feeds.feedburner.com/TheHackersNews",
    "https://www.bleepingcomputer.com/feed/",
    "https://www.cisa.gov/cybersecurity-advisories/all.xml",
]

# ── Logging setup (called once in main.py) ────────────────────────────────────
def configure_logging() -> None:
    numeric_level = getattr(logging, LOG_LEVEL, logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
