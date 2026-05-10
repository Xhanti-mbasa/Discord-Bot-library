"""
main.py — CyberCape Discord Intelligence Bot entry point.

Startup sequence
----------------
1. Load environment + config
2. Initialise SQLite database
3. Register all cogs
4. Register APScheduler jobs
5. Sync slash commands to Discord
6. Start the bot

Run with:
    python main.py
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

import discord
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from discord.ext import commands

# Ensure project root is on sys.path when running as a script
sys.path.insert(0, str(Path(__file__).resolve().parent))

from bot import config
from bot.db import database as db

config.configure_logging()
log = logging.getLogger("cybercape")

# ── Cog list ─────────────────────────────────────────────────────────────────
COGS = [
    "bot.cogs.news",
    "bot.cogs.cve",
    "bot.cogs.jobs",
    "bot.cogs.events",
    "bot.cogs.moderation",
    "bot.cogs.ranking",
    "bot.cogs.resources",
    "bot.cogs.ctf",
]


# ── Bot class ─────────────────────────────────────────────────────────────────
class CyberCapeBot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True

        super().__init__(
            command_prefix="!",  # prefix kept for legacy; main interface is slash commands
            intents=intents,
            description="CyberCape — Cybersecurity Intelligence Bot for Cape Town",
        )
        self.scheduler = AsyncIOScheduler(timezone="Africa/Johannesburg")

    # ── Startup ───────────────────────────────────────────────────────────────

    async def setup_hook(self) -> None:
        """Called by discord.py before login; sets up cogs and scheduler."""
        log.info("Initialising database …")
        await db.init_db(path=config.DB_PATH)

        log.info("Loading cogs …")
        for cog in COGS:
            try:
                await self.load_extension(cog)
                log.info("  ✔ %s", cog)
            except Exception as exc:
                log.error("  ✘ Failed to load %s: %s", cog, exc)

        log.info("Syncing slash commands …")
        try:
            synced = await self.tree.sync()
            log.info("  Synced %d global commands.", len(synced))
        except Exception as exc:
            log.error("  Command sync failed: %s", exc)

        self._register_scheduled_jobs()
        self.scheduler.start()
        log.info("Scheduler started.")

    def _register_scheduled_jobs(self) -> None:
        """Wire APScheduler cron jobs to cog auto-post methods."""

        async def _news_job() -> None:
            cog = self.get_cog("News")
            if cog:
                await cog.auto_post_news()

        async def _events_job() -> None:
            cog = self.get_cog("Events")
            if cog:
                await cog.auto_post_events()

        async def _jobs_job() -> None:
            cog = self.get_cog("Jobs")
            if cog:
                await cog.auto_post_jobs()

        async def _ctf_job() -> None:
            cog = self.get_cog("CTF")
            if cog:
                await cog.auto_post_ctf()

        # Daily news at 08:00 SAST
        self.scheduler.add_job(
            _news_job, CronTrigger(hour=8, minute=0), id="daily_news"
        )
        # Daily events at 09:00 SAST
        self.scheduler.add_job(
            _events_job, CronTrigger(hour=9, minute=0), id="daily_events"
        )
        # Weekly jobs digest — every Monday at 07:00
        self.scheduler.add_job(
            _jobs_job, CronTrigger(day_of_week="mon", hour=7, minute=0), id="weekly_jobs"
        )
        # Weekly CTF digest — every Friday at 15:00
        self.scheduler.add_job(
            _ctf_job, CronTrigger(day_of_week="fri", hour=15, minute=0), id="weekly_ctf"
        )

    # ── Events ────────────────────────────────────────────────────────────────

    async def on_ready(self) -> None:
        log.info("=" * 60)
        log.info("  CyberCape Bot is ONLINE")
        log.info("  Logged in as: %s (ID: %s)", self.user, self.user.id)
        log.info("  Guilds: %d", len(self.guilds))
        log.info("=" * 60)
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="🛡️ Cape Town cyber threats",
            )
        )

    async def on_command_error(
        self, ctx: commands.Context, error: commands.CommandError
    ) -> None:
        log.error("Command error in %s: %s", ctx.command, error)

    async def on_application_command_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
    ) -> None:
        log.error("Slash command error: %s", error)
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "❌ An unexpected error occurred. Please try again.", ephemeral=True
            )


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    bot = CyberCapeBot()
    try:
        asyncio.run(bot.start(config.DISCORD_TOKEN))
    except KeyboardInterrupt:
        log.info("Bot shutting down (KeyboardInterrupt).")
    except discord.LoginFailure:
        log.critical("Invalid Discord token. Check your .env file.")
        sys.exit(1)


if __name__ == "__main__":
    main()
