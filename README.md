# CyberCape Discord Intelligence Bot 🛡️

> A production-ready Discord bot for the **CyberCape** cybersecurity learning community in Cape Town.
> Built with `discord.py`, async-first, fully modular, and API-driven.

---

## Features

| Module | Commands | Schedule |
|---|---|---|
| 📡 Cyber News | `/news latest` `/news critical` | Daily 08:00 SAST |
| 🛡️ CVE Lookup | `/cve CVE-YYYY-NNNNN` | On demand |
| 💼 Jobs | `/jobs latest` `/jobs remote` `/internships` | Weekly Mon 07:00 |
| 🗓️ Events | `/events free` `/events paid` `/events under <R>` | Daily 09:00 SAST |
| 🔨 Moderation | `/warn` `/mute` `/ban` `/modlogs` | Real-time auto-mod |
| 🏅 XP / Ranks | `/rank` `/profile` `/leaderboard` `/rep` | Per message |
| 📚 Resources | `/resource <topic>` `/cheat <tool>` `/topics` | On demand |
| 🚩 CTF | `/ctf active` `/ctf upcoming` `/hackathons` | Weekly Fri 15:00 |

---

## Quick Start

### 1. Prerequisites

```bash
python 3.11+
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env — fill in DISCORD_TOKEN and API keys
```

### 3. Run

```bash
python main.py
```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `DISCORD_TOKEN` | ✅ | Your bot token from Discord Developer Portal |
| `NVD_API_KEY` | ⚠️ optional | NVD API key (higher rate limits with key) |
| `ADZUNA_APP_ID` | ⚠️ optional | Adzuna Jobs API credentials |
| `ADZUNA_APP_KEY` | ⚠️ optional | Adzuna Jobs API credentials |
| `EVENTBRITE_TOKEN` | ⚠️ optional | Eventbrite API bearer token |
| `CHANNEL_CYBER_NEWS` | ⚠️ optional | Channel ID for auto-posting news |
| `CHANNEL_JOBS` | ⚠️ optional | Channel ID for weekly job digest |
| `CHANNEL_EVENTS` | ⚠️ optional | Channel ID for daily events |
| `CHANNEL_CTF` | ⚠️ optional | Channel ID for CTF alerts |
| `CHANNEL_MOD_LOGS` | ⚠️ optional | Channel ID for moderation log |

---

## Project Structure

```
Discord-Bot-library/
├── main.py                     ← Entry point
├── requirements.txt
├── .env.example
└── bot/
    ├── config.py               ← All settings from env vars
    ├── cogs/
    │   ├── news.py             ← Threat intel feed
    │   ├── cve.py              ← CVE lookup
    │   ├── jobs.py             ← Junior cyber jobs
    │   ├── events.py           ← Cape Town events
    │   ├── moderation.py       ← Auto-mod + slash commands
    │   ├── ranking.py          ← XP / streaks / leaderboard
    │   ├── resources.py        ← Learning resource library
    │   └── ctf.py              ← CTF events
    ├── services/
    │   ├── nvd.py              ← NVD API client
    │   ├── rss.py              ← RSS aggregator + HN
    │   ├── adzuna.py           ← Jobs API client
    │   ├── eventbrite.py       ← Events API client
    │   └── scraper.py          ← OfferZen / PNet fallback
    └── db/
        └── database.py         ← Async SQLite (aiosqlite)
```

---

## Ranks

| XP Required | Rank |
|---|---|
| 0 | Script Kiddie |
| 500 | Packet Sniffer |
| 1,500 | Recon Scout |
| 3,000 | Exploit Hunter |
| 6,000 | Threat Analyst |
| 10,000 | Red Teamer |
| 20,000 | Root 🔴 |

---

## Discord Server Setup

Recommended channels:

```
#cyber-news        ← Auto daily news briefing
#jobs-internships  ← Weekly job alerts
#cape-town-events  ← Daily event posts
#resources         ← /resource and /cheat commands
#ctf               ← CTF event alerts
#general           ← XP + rank levelling
#mod-logs          ← Auto-mod actions (mods only)
#leaderboard       ← /leaderboard output
```

Create a `Muted` role with **Send Messages** denied in all channels for the `/mute` command to work.

---

## Announcement Embed Format

The bot uses rich Discord embeds for all announcements, matching the format below:

```json
{
  "embeds": [{
    "title": "Resource Title",
    "description": "Description text",
    "color": 3394611,
    "fields": [
      { "name": "Provider", "value": "...", "inline": false },
      { "name": "Format",   "value": "...", "inline": true }
    ],
    "footer": { "text": "CyberCape Bot" }
  }]
}
```

---

## Upgrade Path

- **Database**: Replace `aiosqlite` with `asyncpg` + PostgreSQL in `db/database.py`
- **Caching**: Add Redis for deduplication at scale
- **Deployment**: See `Dockerfile` (coming soon) for VPS hosting

---

## License

MIT — Built for the Cape Town cybersecurity community. 🇿🇦