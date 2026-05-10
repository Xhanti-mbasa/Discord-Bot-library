"""
cogs/ctf.py — CTF (Capture The Flag) cog.

Sources: CTFtime API

Slash commands:
  /ctf active       — Upcoming / ongoing CTF events
  /hackathons       — Tech hackathons (from CTFtime broader feed)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import discord
import httpx
from discord import app_commands
from discord.ext import commands

from bot import config

log = logging.getLogger(__name__)

CTFTIME_EVENTS_URL = "https://ctftime.org/api/v1/events/"
CTFTIME_HEADERS = {"User-Agent": "CyberCapeBot/1.0 (discord community bot)"}


def _parse_dt(iso: str) -> str:
    """Parse ISO datetime and return a short human-readable version."""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return iso[:19]


def _ctf_embed(event: dict) -> discord.Embed:
    embed = discord.Embed(
        title=f"🚩 {event.get('title', 'CTF Event')[:200]}",
        url=event.get("url", "https://ctftime.org"),
        description=event.get("description", "")[:400] or "*No description.*",
        color=0xFF4444,
    )
    embed.add_field(name="📅 Start", value=_parse_dt(event.get("start", "")), inline=True)
    embed.add_field(name="⏰ Finish", value=_parse_dt(event.get("finish", "")), inline=True)
    embed.add_field(name="🌐 Format", value=event.get("format", "Unknown"), inline=True)
    embed.add_field(
        name="🏅 Weight", value=str(event.get("weight", "N/A")), inline=True
    )
    logo = event.get("logo", "")
    if logo:
        embed.set_thumbnail(url=logo)
    embed.set_footer(text="Source: CTFtime.org")
    return embed


async def _fetch_ctftime_events(limit: int = 8) -> list[dict]:
    now = datetime.now(timezone.utc)
    params = {
        "limit": limit,
        "start": int(now.timestamp()),
    }
    try:
        async with httpx.AsyncClient(timeout=15, headers=CTFTIME_HEADERS) as client:
            r = await client.get(CTFTIME_EVENTS_URL, params=params)
            r.raise_for_status()
            return r.json()
    except httpx.HTTPError as exc:
        log.error("CTFtime fetch failed: %s", exc)
        return []


class CTFCog(commands.Cog, name="CTF"):
    """CTF events and hackathon listings."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="ctf", description="List upcoming and active CTF competitions."
    )
    @app_commands.describe(filter="Filter: 'active', 'upcoming' (default: upcoming)")
    async def ctf(
        self,
        interaction: discord.Interaction,
        filter: str = "upcoming",
    ) -> None:
        await interaction.response.defer(thinking=True)
        events = await _fetch_ctftime_events(limit=10)

        if not events:
            await interaction.followup.send(
                "⚠️ Could not fetch CTF events right now. Visit <https://ctftime.org>."
            )
            return

        now_ts = datetime.now(timezone.utc).timestamp()
        if filter.lower() == "active":
            filtered = [
                e for e in events
                if e.get("start") and e.get("finish")
                and datetime.fromisoformat(e["start"].replace("Z", "+00:00")).timestamp() <= now_ts
                and datetime.fromisoformat(e["finish"].replace("Z", "+00:00")).timestamp() >= now_ts
            ]
            title = "🚩 Currently Active CTFs"
        else:
            filtered = events[:6]
            title = "🚩 Upcoming CTF Events"

        if not filtered:
            await interaction.followup.send(
                f"No {filter} CTFs found right now. Check <https://ctftime.org>."
            )
            return

        embeds = [_ctf_embed(e) for e in filtered[:5]]
        await interaction.followup.send(content=f"**{title}**", embeds=embeds)

    @app_commands.command(
        name="hackathons",
        description="List upcoming hackathons and tech competitions.",
    )
    async def hackathons(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True)
        # CTFtime covers CTFs; for hackathons we show a curated static list
        # with a note to check Devpost and MLH.
        embed = discord.Embed(
            title="🏆 Hackathons & Tech Competitions",
            description=(
                "Here are the best places to find hackathons relevant to the "
                "Cape Town cybersecurity community:"
            ),
            color=0x6C63FF,
        )
        sources = [
            ("Devpost", "https://devpost.com/hackathons", "Largest hackathon aggregator."),
            ("MLH Events", "https://mlh.io/seasons/2025/events", "Major League Hacking events."),
            ("CTFtime", "https://ctftime.org/event/list/upcoming", "Security-focused CTF competitions."),
            ("ZATech Slack", "https://zatech.co.za", "Local ZA tech community events."),
            ("Meetup.com CT", "https://www.meetup.com/find/?location=Cape%20Town&keywords=security", "Cape Town security meetups."),
        ]
        for name, url, desc in sources:
            embed.add_field(name=f"🔗 {name}", value=f"{desc}\n[→ Visit]({url})", inline=False)
        await interaction.followup.send(embed=embed)

    # ── Scheduled auto-post ───────────────────────────────────────────────────

    async def auto_post_ctf(self) -> None:
        channel_id = config.CHANNEL_CTF
        if not channel_id:
            return
        channel = self.bot.get_channel(channel_id)
        if channel is None:
            return

        events = await _fetch_ctftime_events(limit=5)
        if not events:
            return

        await channel.send("**🚩 Upcoming CTF Events This Week**")
        for ev in events[:4]:
            await channel.send(embed=_ctf_embed(ev))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(CTFCog(bot))
