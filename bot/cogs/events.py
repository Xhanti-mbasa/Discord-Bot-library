"""
cogs/events.py — Cape Town Tech Events cog.

Slash commands:
  /events free          — Free events
  /events paid          — Paid events
  /events under <price> — Events under a given ZAR price

Auto-post: daily at 09:00 to #cape-town-events
"""

from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from bot import config
from bot.services import eventbrite

log = logging.getLogger(__name__)


def _event_embed(ev: dict) -> discord.Embed:
    price_label = "🆓 Free" if ev["is_free"] else (
        f"R{ev['min_price']:.0f}+" if ev["min_price"] else "Paid"
    )
    embed = discord.Embed(
        title=f"🗓️ {ev['name'][:200]}",
        url=ev.get("url", ""),
        description=ev.get("description", "")[:400] or "*No description.*",
        color=0x6C63FF,
    )
    embed.add_field(name="📅 Date", value=ev.get("start", "TBA")[:19], inline=True)
    embed.add_field(name="📍 Venue", value=ev.get("venue", "Cape Town"), inline=True)
    embed.add_field(name="💵 Price", value=price_label, inline=True)
    embed.set_footer(text="Source: Eventbrite | Cape Town Tech Events")
    return embed


class EventsCog(commands.Cog, name="Events"):
    """Cape Town tech and cybersecurity events."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    events_group = app_commands.Group(
        name="events", description="Cape Town tech event listings"
    )

    @events_group.command(name="free", description="Free Cape Town tech events.")
    async def events_free(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True)
        evs = await eventbrite.fetch_events(free_only=True)
        if not evs:
            await interaction.followup.send("⚠️ No free events found right now.")
            return
        embeds = [_event_embed(e) for e in evs[:5]]
        await interaction.followup.send(
            content="**🆓 Free Cape Town Tech Events**", embeds=embeds
        )

    @events_group.command(name="paid", description="Paid Cape Town tech events.")
    async def events_paid(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True)
        evs = await eventbrite.fetch_events(free_only=False)
        paid = [e for e in evs if not e["is_free"]]
        if not paid:
            await interaction.followup.send("⚠️ No paid events found right now.")
            return
        embeds = [_event_embed(e) for e in paid[:5]]
        await interaction.followup.send(
            content="**🎫 Paid Cape Town Tech Events**", embeds=embeds
        )

    @events_group.command(
        name="under", description="Events under a specified ZAR price."
    )
    @app_commands.describe(price="Maximum ticket price in ZAR (e.g. 200)")
    async def events_under(
        self, interaction: discord.Interaction, price: int
    ) -> None:
        await interaction.response.defer(thinking=True)
        evs = await eventbrite.fetch_events(max_price_zar=price)
        if not evs:
            await interaction.followup.send(
                f"⚠️ No events under R{price} found right now."
            )
            return
        embeds = [_event_embed(e) for e in evs[:5]]
        await interaction.followup.send(
            content=f"**🎟️ Cape Town Tech Events Under R{price}**", embeds=embeds
        )

    # ── Scheduled auto-post ───────────────────────────────────────────────────

    async def auto_post_events(self) -> None:
        channel_id = config.CHANNEL_EVENTS
        if not channel_id:
            log.warning("CHANNEL_EVENTS not configured.")
            return
        channel = self.bot.get_channel(channel_id)
        if channel is None:
            return

        evs = await eventbrite.fetch_events()
        if not evs:
            return

        await channel.send("**🗓️ Cape Town Tech Events Today**")
        for ev in evs[:6]:
            await channel.send(embed=_event_embed(ev))
        log.info("Auto-posted %d events.", min(6, len(evs)))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(EventsCog(bot))
