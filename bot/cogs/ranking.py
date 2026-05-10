"""
cogs/ranking.py — XP, Levels, Streaks, Reputation cog.

XP awarded per message (with 60-second cooldown & daily cap).
Daily streak tracking with bonus rewards.
Reputation system (peer +1).

Slash commands:
  /rank                — Show your current rank card
  /profile             — Full profile: XP, level, streak, rep
  /leaderboard         — Top 10 users by XP
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

from bot import config
from bot.db import database as db

log = logging.getLogger(__name__)


def _get_rank(xp: int) -> str:
    rank = config.RANKS[0][1]
    for threshold, name in config.RANKS:
        if xp >= threshold:
            rank = name
    return rank


def _xp_to_next_rank(xp: int) -> tuple[str, int] | None:
    for i, (threshold, name) in enumerate(config.RANKS):
        if xp < threshold:
            return name, threshold - xp
    return None, 0  # already at max rank


def _rank_color(rank: str) -> int:
    colors = {
        "Script Kiddie": 0xAAAAAA,
        "Packet Sniffer": 0x00BFFF,
        "Recon Scout": 0x00CC66,
        "Exploit Hunter": 0xFFAA00,
        "Threat Analyst": 0xFF6600,
        "Red Teamer": 0xFF2222,
        "Root": 0x9B59B6,
    }
    return colors.get(rank, 0x0088CC)


def _should_grant_xp(user: dict, now_iso: str, now_ts: float) -> bool:
    """Return True if the user is eligible for XP (cooldown + daily cap)."""
    last_xp = user.get("last_xp_time") or ""
    if last_xp:
        try:
            last_ts = datetime.fromisoformat(last_xp).timestamp()
            if now_ts - last_ts < config.XP_COOLDOWN_SECONDS:
                return False
        except ValueError:
            pass

    if user.get("daily_xp", 0) >= config.XP_DAILY_CAP:
        return False

    return True


def _compute_streak(user: dict, today: date) -> tuple[int, int]:
    """Return (new_streak, bonus_xp)."""
    last_active_str = user.get("last_active") or ""
    if not last_active_str:
        return 1, 0

    try:
        last_active = date.fromisoformat(last_active_str)
    except ValueError:
        return 1, 0

    diff = (today - last_active).days
    current_streak = user.get("streak", 0)

    if diff == 0:
        # Same day — streak unchanged
        return current_streak, 0
    elif diff == 1:
        # Consecutive day — increment streak
        new_streak = current_streak + 1
        bonus = config.XP_STREAK_BONUS.get(new_streak, 0)
        return new_streak, bonus
    else:
        # Missed a day — reset
        return 1, 0


class RankingCog(commands.Cog, name="Ranking"):
    """XP, levelling, streaks, and leaderboard."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ── XP listener ───────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or not message.guild:
            return
        if len(message.content.strip()) < 5:
            return  # Ignore very short messages

        user_id = message.author.id
        now = datetime.now(timezone.utc)
        now_ts = now.timestamp()
        now_iso = now.isoformat()
        today = now.date()

        conn = await db.get_db()
        try:
            user = await db.upsert_user(conn, user_id)

            if not _should_grant_xp(user, now_iso, now_ts):
                return

            new_streak, bonus = _compute_streak(user, today)
            xp_delta = config.XP_PER_MESSAGE + bonus

            # Reset daily_xp if new day
            daily_xp = user.get("daily_xp", 0)
            last_active_str = user.get("last_active") or ""
            if last_active_str:
                try:
                    last_day = date.fromisoformat(last_active_str)
                    if last_day < today:
                        daily_xp = 0
                except ValueError:
                    daily_xp = 0

            new_xp = user["xp"] + xp_delta
            new_daily_xp = daily_xp + xp_delta
            new_level = sum(1 for t, _ in config.RANKS if new_xp >= t) - 1

            await db.update_xp(
                conn,
                user_id=user_id,
                delta=xp_delta,
                new_level=new_level,
                new_streak=new_streak,
                last_active=str(today),
                last_xp_time=now_iso,
                daily_xp=new_daily_xp,
            )

            # Level-up announcement
            old_level = user.get("level", 0)
            if new_level > old_level:
                rank = _get_rank(new_xp)
                await message.channel.send(
                    f"🎉 **{message.author.display_name}** levelled up to **{rank}**! "
                    f"(Total XP: {new_xp:,})",
                    delete_after=30,
                )

            # Streak milestone notification
            if bonus > 0:
                await message.channel.send(
                    f"🔥 **{message.author.display_name}** hit a **{new_streak}-day streak!** "
                    f"+{bonus} bonus XP awarded!",
                    delete_after=20,
                )
        finally:
            await conn.close()

    # ── Slash commands ────────────────────────────────────────────────────────

    @app_commands.command(name="rank", description="See your current cybersecurity rank.")
    async def rank(self, interaction: discord.Interaction) -> None:
        conn = await db.get_db()
        try:
            user = await db.get_user(conn, interaction.user.id)
        finally:
            await conn.close()

        if user is None:
            await interaction.response.send_message(
                "You have no XP yet — start chatting! 💬", ephemeral=True
            )
            return

        xp = user["xp"]
        rank_name = _get_rank(xp)
        next_rank, xp_needed = _xp_to_next_rank(xp)
        color = _rank_color(rank_name)

        embed = discord.Embed(
            title=f"🏅 {interaction.user.display_name}'s Rank",
            color=color,
        )
        embed.add_field(name="Rank", value=f"**{rank_name}**", inline=True)
        embed.add_field(name="XP", value=f"{xp:,}", inline=True)
        embed.add_field(name="🔥 Streak", value=f"{user.get('streak', 0)} days", inline=True)
        if next_rank:
            embed.add_field(
                name="Next Rank",
                value=f"{next_rank} (need {xp_needed:,} more XP)",
                inline=False,
            )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="profile", description="View your full profile.")
    async def profile(self, interaction: discord.Interaction) -> None:
        conn = await db.get_db()
        try:
            user = await db.get_user(conn, interaction.user.id)
        finally:
            await conn.close()

        if user is None:
            await interaction.response.send_message(
                "You have no profile yet — start chatting! 💬", ephemeral=True
            )
            return

        xp = user["xp"]
        rank_name = _get_rank(xp)
        color = _rank_color(rank_name)

        embed = discord.Embed(
            title=f"👤 {interaction.user.display_name}",
            color=color,
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.add_field(name="🏅 Rank", value=rank_name, inline=True)
        embed.add_field(name="⭐ XP", value=f"{xp:,}", inline=True)
        embed.add_field(name="📊 Level", value=str(user.get("level", 0)), inline=True)
        embed.add_field(name="🔥 Streak", value=f"{user.get('streak', 0)} days", inline=True)
        embed.add_field(name="⭐ Reputation", value=str(user.get("rep", 0)), inline=True)
        embed.add_field(
            name="📅 Last Active",
            value=user.get("last_active", "Never") or "Never",
            inline=True,
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="leaderboard", description="Top 10 community members by XP.")
    async def leaderboard(self, interaction: discord.Interaction) -> None:
        conn = await db.get_db()
        try:
            top = await db.get_leaderboard(conn, limit=10)
        finally:
            await conn.close()

        if not top:
            await interaction.response.send_message(
                "No leaderboard data yet. Start chatting! 💬"
            )
            return

        embed = discord.Embed(
            title="🏆 CyberCape Leaderboard",
            color=0xFFD700,
        )
        medals = ["🥇", "🥈", "🥉"]
        for i, row in enumerate(top):
            medal = medals[i] if i < 3 else f"**{i+1}.**"
            user_obj = self.bot.get_user(row["user_id"])
            name = user_obj.display_name if user_obj else f"User#{row['user_id']}"
            rank_name = _get_rank(row["xp"])
            embed.add_field(
                name=f"{medal} {name}",
                value=f"{rank_name} • {row['xp']:,} XP • 🔥{row['streak']}d",
                inline=False,
            )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="rep", description="Give +1 reputation to a community member.")
    @app_commands.describe(user="The user to give reputation to")
    async def rep(
        self, interaction: discord.Interaction, user: discord.Member
    ) -> None:
        if user.id == interaction.user.id:
            await interaction.response.send_message(
                "❌ You can't rep yourself!", ephemeral=True
            )
            return
        if user.bot:
            await interaction.response.send_message(
                "❌ Bots don't need reputation.", ephemeral=True
            )
            return

        conn = await db.get_db()
        try:
            await db.upsert_user(conn, user.id)
            await db.add_rep(conn, user.id)
            updated = await db.get_user(conn, user.id)
        finally:
            await conn.close()

        await interaction.response.send_message(
            f"⭐ You gave **+1 rep** to {user.mention}! "
            f"They now have {updated['rep']} reputation."
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(RankingCog(bot))
