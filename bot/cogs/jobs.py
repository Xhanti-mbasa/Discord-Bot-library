"""
cogs/jobs.py — Jobs & Internships cog.

Slash commands:
  /jobs              — General junior cybersecurity jobs in Cape Town
  /jobs remote       — Remote junior roles
  /internships       — Internship listings

Auto-post: weekly job digest to #jobs-internships
"""

from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from bot import config
from bot.db import database as db
from bot.services import adzuna, scraper

log = logging.getLogger(__name__)


def _job_embed(job: dict, index: int) -> discord.Embed:
    salary = ""
    if job.get("salary_min") and job.get("salary_max"):
        salary = f"R{int(job['salary_min']):,} – R{int(job['salary_max']):,}"
    elif job.get("salary_min"):
        salary = f"From R{int(job['salary_min']):,}"

    embed = discord.Embed(
        title=f"💼 {job['title'][:200]}",
        url=job.get("url", ""),
        description=job.get("description", "")[:400],
        color=0x00BFAE,
    )
    embed.add_field(name="🏢 Company", value=job.get("company", "Unknown"), inline=True)
    embed.add_field(name="📍 Location", value=job.get("location", "Cape Town"), inline=True)
    if salary:
        embed.add_field(name="💰 Salary", value=salary, inline=True)
    source = job.get("source", "Adzuna")
    embed.set_footer(text=f"Source: {source} | #{index}")
    return embed


async def _get_jobs(
    remote: bool = False,
    internships_only: bool = False,
) -> list[dict]:
    jobs = await adzuna.fetch_jobs(remote=remote, internships_only=internships_only)
    if len(jobs) < 3:
        # Fallback to scrapers
        oz = await scraper.scrape_offerzen()
        pn = await scraper.scrape_pnet()
        jobs = jobs + oz + pn
    return jobs[:8]


class JobsCog(commands.Cog, name="Jobs"):
    """Junior cybersecurity jobs and internships."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    jobs_group = app_commands.Group(name="jobs", description="Cybersecurity job listings")

    @jobs_group.command(name="latest", description="Latest junior cybersecurity jobs in Cape Town.")
    async def jobs_latest(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True)
        jobs = await _get_jobs()
        if not jobs:
            await interaction.followup.send("⚠️ No jobs found right now. Try again later.")
            return
        embeds = [_job_embed(j, i + 1) for i, j in enumerate(jobs)]
        await interaction.followup.send(
            content="**💼 Junior Cybersecurity Jobs — Cape Town**", embeds=embeds
        )

    @jobs_group.command(name="remote", description="Remote junior cybersecurity jobs.")
    async def jobs_remote(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True)
        jobs = await _get_jobs(remote=True)
        if not jobs:
            await interaction.followup.send("⚠️ No remote jobs found right now.")
            return
        embeds = [_job_embed(j, i + 1) for i, j in enumerate(jobs)]
        await interaction.followup.send(
            content="**🌐 Remote Junior Cybersecurity Jobs**", embeds=embeds
        )

    @app_commands.command(name="internships", description="Cybersecurity internships in South Africa.")
    async def internships(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True)
        jobs = await _get_jobs(internships_only=True)
        if not jobs:
            await interaction.followup.send("⚠️ No internships found right now.")
            return
        embeds = [_job_embed(j, i + 1) for i, j in enumerate(jobs)]
        await interaction.followup.send(
            content="**🎓 Cybersecurity Internships**", embeds=embeds
        )

    # ── Scheduled weekly digest ───────────────────────────────────────────────

    async def auto_post_jobs(self) -> None:
        """Called by the scheduler weekly."""
        channel_id = config.CHANNEL_JOBS
        if not channel_id:
            log.warning("CHANNEL_JOBS not configured.")
            return
        channel = self.bot.get_channel(channel_id)
        if channel is None:
            return

        jobs = await _get_jobs()
        conn = await db.get_db()
        try:
            new_jobs = []
            for job in jobs:
                if not await db.is_seen(conn, job["hash"]):
                    await db.mark_seen(conn, job["hash"], "jobs")
                    new_jobs.append(job)
        finally:
            await conn.close()

        if not new_jobs:
            return

        await channel.send("**📋 Weekly Junior Cyber Jobs Digest**")
        for i, job in enumerate(new_jobs):
            await channel.send(embed=_job_embed(job, i + 1))
        log.info("Auto-posted %d job listings.", len(new_jobs))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(JobsCog(bot))
