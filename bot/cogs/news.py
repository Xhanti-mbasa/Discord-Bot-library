"""
cogs/news.py — Cyber news feed cog.

Slash commands: /news latest | /news critical
Auto-post: scheduled daily at 08:00 to #cyber-news
"""

from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from bot import config
from bot.db import database as db
from bot.services import rss

log = logging.getLogger(__name__)

SEVERITY_COLORS = {
    "critical": 0xFF0000,
    "high": 0xFF6600,
    "medium": 0xFFAA00,
    "low": 0x00AA55,
    "info": 0x0088CC,
}

SEVERITY_EMOJI = {
    "critical": "🔴",
    "high": "🟠",
    "medium": "🟡",
    "low": "🟢",
    "info": "🔵",
}


def _build_embed(item: dict) -> discord.Embed:
    severity = item.get("severity", "info")
    color = SEVERITY_COLORS.get(severity, 0x0088CC)
    emoji = SEVERITY_EMOJI.get(severity, "🔵")

    embed = discord.Embed(
        title=f"{emoji} {item['title'][:250]}",
        url=item["url"],
        description=item.get("summary", "")[:300] or "*No summary available.*",
        color=color,
    )
    embed.set_footer(text=f"Source: {item['source']} | Severity: {severity.upper()}")
    if item.get("published"):
        embed.add_field(name="Published", value=item["published"][:30], inline=True)
    return embed


class NewsCog(commands.Cog, name="News"):
    """Cyber threat intelligence and news feed."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ── Slash commands ────────────────────────────────────────────────────────

    news_group = app_commands.Group(name="news", description="Cyber news commands")

    @news_group.command(name="latest", description="Show the latest cybersecurity news.")
    async def news_latest(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True)
        items = await rss.fetch_all_rss()
        hn_items = await rss.fetch_hackernews_cyber()
        all_items = items + hn_items
        all_items.sort(key=lambda x: x.get("severity", "info"))

        if not all_items:
            await interaction.followup.send("⚠️ No news items found right now. Try again later.")
            return

        embeds = [_build_embed(i) for i in all_items[:5]]
        await interaction.followup.send(
            content="**📡 Latest Cyber Intelligence**", embeds=embeds
        )

    @news_group.command(name="critical", description="Show only critical severity news.")
    async def news_critical(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True)
        items = await rss.fetch_all_rss()
        critical = [i for i in items if i.get("severity") == "critical"]

        if not critical:
            await interaction.followup.send(
                "✅ No **CRITICAL** alerts right now. Stay vigilant."
            )
            return

        embeds = [_build_embed(i) for i in critical[:5]]
        await interaction.followup.send(
            content="**🚨 CRITICAL Threat Intelligence**", embeds=embeds
        )

    # ── Scheduled auto-post ───────────────────────────────────────────────────

    async def auto_post_news(self) -> None:
        """Called by the scheduler every day at 08:00."""
        channel_id = config.CHANNEL_CYBER_NEWS
        if not channel_id:
            log.warning("CHANNEL_CYBER_NEWS not configured — skipping auto-post.")
            return

        channel = self.bot.get_channel(channel_id)
        if channel is None:
            log.error("Could not find #cyber-news channel (id=%d).", channel_id)
            return

        items = await rss.fetch_all_rss()
        hn_items = await rss.fetch_hackernews_cyber()
        all_items = items + hn_items

        conn = await db.get_db()
        try:
            new_items = []
            for item in all_items:
                if not await db.is_seen(conn, item["hash"]):
                    await db.mark_seen(conn, item["hash"], "news")
                    new_items.append(item)
        finally:
            await conn.close()

        if not new_items:
            log.info("No new news items to post.")
            return

        await channel.send("**📡 Daily Cyber Intelligence Briefing**")
        for item in new_items[:8]:
            await channel.send(embed=_build_embed(item))
        log.info("Auto-posted %d news items.", len(new_items[:8]))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(NewsCog(bot))
