"""
db/database.py — Async SQLite layer (aiosqlite).

Tables
------
users        — XP, level, streak, reputation.
warnings     — Moderation warning log.
messages     — Per-message XP audit trail.
seen_items   — Deduplication store for news / CVE / jobs feeds.
resources    — Curated resource library.
"""

from __future__ import annotations

import logging
from pathlib import Path

import aiosqlite

log = logging.getLogger(__name__)

# Will be overridden by main.py via init_db(path=…)
_DB_PATH: str = "bot/db/cybercape.db"


async def init_db(path: str | None = None) -> None:
    """Create all tables if they don't exist. Call once at bot startup."""
    global _DB_PATH
    if path:
        _DB_PATH = path

    Path(_DB_PATH).parent.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(_DB_PATH) as db:
        await db.executescript(
            """
            PRAGMA journal_mode=WAL;
            PRAGMA foreign_keys=ON;

            CREATE TABLE IF NOT EXISTS users (
                user_id      INTEGER PRIMARY KEY,
                xp           INTEGER NOT NULL DEFAULT 0,
                level        INTEGER NOT NULL DEFAULT 0,
                streak       INTEGER NOT NULL DEFAULT 0,
                rep          INTEGER NOT NULL DEFAULT 0,
                last_active  TEXT,
                last_xp_time TEXT,
                daily_xp     INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS warnings (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id   INTEGER NOT NULL,
                reason    TEXT NOT NULL,
                mod_id    INTEGER,
                timestamp TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS messages (
                message_id  INTEGER PRIMARY KEY,
                user_id     INTEGER NOT NULL,
                timestamp   TEXT NOT NULL DEFAULT (datetime('now')),
                xp_awarded  INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS seen_items (
                item_hash   TEXT PRIMARY KEY,
                category    TEXT NOT NULL,
                first_seen  TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS resources (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                topic    TEXT NOT NULL,
                title    TEXT NOT NULL,
                url      TEXT NOT NULL,
                notes    TEXT
            );
            """
        )
        await db.commit()
    log.info("Database initialised at %s", _DB_PATH)


async def get_db() -> aiosqlite.Connection:
    """Return a live connection. Caller is responsible for closing."""
    return await aiosqlite.connect(_DB_PATH)


# ── User helpers ──────────────────────────────────────────────────────────────

async def get_user(db: aiosqlite.Connection, user_id: int) -> dict | None:
    async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cur:
        row = await cur.fetchone()
    if row is None:
        return None
    cols = [d[0] for d in cur.description]
    return dict(zip(cols, row))


async def upsert_user(db: aiosqlite.Connection, user_id: int) -> dict:
    """Ensure a user row exists; return the current record."""
    await db.execute(
        "INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,)
    )
    await db.commit()
    return await get_user(db, user_id)


async def update_xp(
    db: aiosqlite.Connection,
    user_id: int,
    delta: int,
    new_level: int,
    new_streak: int,
    last_active: str,
    last_xp_time: str,
    daily_xp: int,
) -> None:
    await db.execute(
        """
        UPDATE users
        SET xp = xp + ?,
            level = ?,
            streak = ?,
            last_active = ?,
            last_xp_time = ?,
            daily_xp = ?
        WHERE user_id = ?
        """,
        (delta, new_level, new_streak, last_active, last_xp_time, daily_xp, user_id),
    )
    await db.commit()


async def add_rep(db: aiosqlite.Connection, user_id: int) -> None:
    await db.execute("UPDATE users SET rep = rep + 1 WHERE user_id = ?", (user_id,))
    await db.commit()


# ── Warning helpers ───────────────────────────────────────────────────────────

async def add_warning(
    db: aiosqlite.Connection, user_id: int, reason: str, mod_id: int
) -> int:
    await db.execute(
        "INSERT INTO warnings (user_id, reason, mod_id) VALUES (?, ?, ?)",
        (user_id, reason, mod_id),
    )
    await db.commit()
    async with db.execute(
        "SELECT COUNT(*) FROM warnings WHERE user_id = ?", (user_id,)
    ) as cur:
        row = await cur.fetchone()
    return row[0] if row else 0


async def get_warnings(db: aiosqlite.Connection, user_id: int) -> list[dict]:
    async with db.execute(
        "SELECT * FROM warnings WHERE user_id = ? ORDER BY timestamp DESC",
        (user_id,),
    ) as cur:
        rows = await cur.fetchall()
        cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in rows]


# ── Deduplication helpers ─────────────────────────────────────────────────────

async def is_seen(db: aiosqlite.Connection, item_hash: str) -> bool:
    async with db.execute(
        "SELECT 1 FROM seen_items WHERE item_hash = ?", (item_hash,)
    ) as cur:
        return await cur.fetchone() is not None


async def mark_seen(
    db: aiosqlite.Connection, item_hash: str, category: str
) -> None:
    await db.execute(
        "INSERT OR IGNORE INTO seen_items (item_hash, category) VALUES (?, ?)",
        (item_hash, category),
    )
    await db.commit()


# ── Leaderboard ───────────────────────────────────────────────────────────────

async def get_leaderboard(
    db: aiosqlite.Connection, limit: int = 10
) -> list[dict]:
    async with db.execute(
        "SELECT user_id, xp, level, streak, rep FROM users ORDER BY xp DESC LIMIT ?",
        (limit,),
    ) as cur:
        rows = await cur.fetchall()
        cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in rows]
