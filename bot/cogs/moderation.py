"""
cogs/moderation.py — Full moderation system (MEE6 replacement).

Features
--------
• Auto spam detection (duplicate / rapid messages)
• Bad word filtering
• Raid detection (join spike monitoring)
• warn / mute / ban / modlogs slash commands
• Message delete logging
• All actions logged to #mod-logs
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict, deque
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

from bot import config
from bot.db import database as db

log = logging.getLogger(__name__)

# In-memory spam tracking: user_id -> deque of timestamps
_message_timestamps: dict[int, deque] = defaultdict(lambda: deque(maxlen=10))
_recent_joins: deque = deque()  # guild join timestamps for raid detection
_muted_users: dict[int, asyncio.Task] = {}


def _is_spam(user_id: int, now: float) -> bool:
    """Return True if the user sent 5+ messages in the last 5 seconds."""
    dq = _message_timestamps[user_id]
    dq.append(now)
    window = [t for t in dq if now - t < 5.0]
    return len(window) >= 5


def _contains_bad_words(content: str) -> bool:
    lower = content.lower()
    return any(word in lower for word in config.BAD_WORDS)


async def _send_mod_log(bot: commands.Bot, embed: discord.Embed) -> None:
    channel_id = config.CHANNEL_MOD_LOGS
    if not channel_id:
        return
    channel = bot.get_channel(channel_id)
    if channel:
        await channel.send(embed=embed)


def _mod_embed(
    title: str,
    description: str,
    color: int = 0xFF4444,
    **fields: str,
) -> discord.Embed:
    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=datetime.now(timezone.utc),
    )
    for name, value in fields.items():
        embed.add_field(name=name, value=value, inline=True)
    return embed


class ModerationCog(commands.Cog, name="Moderation"):
    """Server moderation: warns, mutes, bans, and auto-protection."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ── Auto-mod: message listener ────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or not message.guild:
            return

        now = datetime.now(timezone.utc).timestamp()
        user_id = message.author.id

        # Bad word filter
        if _contains_bad_words(message.content):
            try:
                await message.delete()
            except discord.Forbidden:
                pass
            warning = await _self_warn(
                message.guild, message.author, "Prohibited language", self.bot
            )
            embed = _mod_embed(
                "🤬 Bad Word Detected",
                f"{message.author.mention} used prohibited language.",
                Warnings=str(warning),
                Channel=message.channel.mention,
            )
            await _send_mod_log(self.bot, embed)
            return

        # Spam detection
        if _is_spam(user_id, now):
            try:
                await message.delete()
            except discord.Forbidden:
                pass
            embed = _mod_embed(
                "⚡ Spam Detected",
                f"{message.author.mention} is sending messages too quickly.",
                Channel=message.channel.mention,
            )
            await _send_mod_log(self.bot, embed)

    # ── Raid detection ────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        now = datetime.now(timezone.utc).timestamp()
        _recent_joins.append(now)
        # Purge old entries outside window
        window_start = now - config.RAID_JOIN_WINDOW_SECONDS
        while _recent_joins and _recent_joins[0] < window_start:
            _recent_joins.popleft()

        if len(_recent_joins) >= config.RAID_JOIN_THRESHOLD:
            embed = _mod_embed(
                "🚨 RAID ALERT",
                f"**{len(_recent_joins)}** accounts joined in the last "
                f"{config.RAID_JOIN_WINDOW_SECONDS}s. Verify server security.",
                color=0xFF0000,
                Latest=member.mention,
            )
            await _send_mod_log(self.bot, embed)
            log.warning("Raid detected! %d joins in %ds.", len(_recent_joins), config.RAID_JOIN_WINDOW_SECONDS)

    # ── Message delete tracking ───────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message) -> None:
        if message.author.bot or not message.guild:
            return
        embed = _mod_embed(
            "🗑️ Message Deleted",
            f"A message by {message.author.mention} was deleted.",
            color=0xAAAAAA,
            Channel=message.channel.mention,
            Content=message.content[:500] or "*[empty / attachment]*",
        )
        await _send_mod_log(self.bot, embed)

    # ── Slash commands ─────────────────────────────────────────────────────────

    @app_commands.command(name="warn", description="Issue a warning to a user.")
    @app_commands.describe(user="The user to warn", reason="Reason for the warning")
    @app_commands.default_permissions(manage_messages=True)
    async def warn(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        reason: str,
    ) -> None:
        conn = await db.get_db()
        try:
            await db.upsert_user(conn, user.id)
            count = await db.add_warning(conn, user.id, reason, interaction.user.id)
        finally:
            await conn.close()

        embed = _mod_embed(
            "⚠️ Warning Issued",
            f"{user.mention} has been warned.",
            Reason=reason,
            Moderator=interaction.user.mention,
            TotalWarnings=str(count),
        )
        await interaction.response.send_message(embed=embed)
        await _send_mod_log(self.bot, embed)

        if count >= config.MAX_WARNINGS_BEFORE_BAN:
            await interaction.channel.send(
                f"🔨 {user.mention} has reached {count} warnings. "
                "Consider banning this user."
            )

    @app_commands.command(name="mute", description="Temporarily mute a user.")
    @app_commands.describe(user="The user to mute", duration="Duration in seconds")
    @app_commands.default_permissions(manage_messages=True)
    async def mute(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        duration: int = 300,
    ) -> None:
        mute_role = discord.utils.get(interaction.guild.roles, name="Muted")
        if mute_role is None:
            await interaction.response.send_message(
                "❌ No `Muted` role found. Create a role called `Muted` with "
                "Send Messages permission denied.",
                ephemeral=True,
            )
            return

        await user.add_roles(mute_role, reason=f"Muted for {duration}s")
        await interaction.response.send_message(
            f"🔇 {user.mention} muted for **{duration}** seconds."
        )
        embed = _mod_embed(
            "🔇 User Muted",
            f"{user.mention} was muted for {duration}s.",
            Moderator=interaction.user.mention,
        )
        await _send_mod_log(self.bot, embed)

        async def _unmute() -> None:
            await asyncio.sleep(duration)
            try:
                await user.remove_roles(mute_role, reason="Mute expired")
                embed2 = _mod_embed(
                    "🔊 Mute Expired",
                    f"{user.mention} has been unmuted.",
                    color=0x00AA55,
                )
                await _send_mod_log(self.bot, embed2)
            except Exception:
                pass

        task = asyncio.create_task(_unmute())
        _muted_users[user.id] = task

    @app_commands.command(name="ban", description="Ban a user from the server.")
    @app_commands.describe(user="The user to ban", reason="Reason for the ban")
    @app_commands.default_permissions(ban_members=True)
    async def ban(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        reason: str = "No reason provided",
    ) -> None:
        await user.ban(reason=reason, delete_message_days=1)
        embed = _mod_embed(
            "🔨 User Banned",
            f"{user.mention} was banned.",
            Reason=reason,
            Moderator=interaction.user.mention,
        )
        await interaction.response.send_message(embed=embed)
        await _send_mod_log(self.bot, embed)

    @app_commands.command(name="modlogs", description="Show recent mod actions for a user.")
    @app_commands.describe(user="The user to check")
    @app_commands.default_permissions(manage_messages=True)
    async def modlogs(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
    ) -> None:
        conn = await db.get_db()
        try:
            warnings = await db.get_warnings(conn, user.id)
        finally:
            await conn.close()

        if not warnings:
            await interaction.response.send_message(
                f"✅ No warnings on record for {user.mention}.", ephemeral=True
            )
            return

        embed = discord.Embed(
            title=f"📋 Mod Logs — {user.display_name}",
            color=0xFF9900,
        )
        for w in warnings[:10]:
            embed.add_field(
                name=f"⚠️ {w['timestamp'][:19]}",
                value=w["reason"][:200],
                inline=False,
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)


# ── Internal helpers ──────────────────────────────────────────────────────────

async def _self_warn(
    guild: discord.Guild,
    member: discord.Member,
    reason: str,
    bot: commands.Bot,
) -> int:
    """Programmatic warning (from auto-mod)."""
    conn = await db.get_db()
    try:
        await db.upsert_user(conn, member.id)
        count = await db.add_warning(conn, member.id, reason, bot.user.id)
    finally:
        await conn.close()
    return count


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ModerationCog(bot))
