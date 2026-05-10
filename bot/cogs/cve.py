"""
cogs/cve.py — CVE Lookup cog.

Slash command: /cve <CVE-ID>
Displays CVSS score, severity, description, and references.
"""

from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from bot.services import nvd

log = logging.getLogger(__name__)

SEVERITY_COLORS = {
    "CRITICAL": 0xFF0000,
    "HIGH": 0xFF6600,
    "MEDIUM": 0xFFAA00,
    "LOW": 0x00AA55,
    "NONE": 0xAAAAAA,
    "UNKNOWN": 0x555555,
}


def _build_cve_embed(cve: dict) -> discord.Embed:
    severity = cve.get("severity", "UNKNOWN").upper()
    color = SEVERITY_COLORS.get(severity, 0x555555)
    score = cve.get("score")
    score_str = f"{score}" if score is not None else "N/A"

    embed = discord.Embed(
        title=f"🛡️ {cve['id']}",
        description=cve.get("description", "No description available.")[:1500],
        color=color,
        url=f"https://nvd.nist.gov/vuln/detail/{cve['id']}",
    )
    embed.add_field(name="CVSS Score", value=score_str, inline=True)
    embed.add_field(name="Severity", value=severity, inline=True)
    if cve.get("vector"):
        embed.add_field(name="Vector String", value=f"`{cve['vector']}`", inline=False)
    if cve.get("published"):
        embed.add_field(name="Published", value=cve["published"][:19], inline=True)

    refs = cve.get("references", [])
    if refs:
        ref_lines = "\n".join(f"• <{r}>" for r in refs[:3])
        embed.add_field(name="References", value=ref_lines, inline=False)

    # Exploit flag heuristic
    desc_lower = cve.get("description", "").lower()
    if any(k in desc_lower for k in ("actively exploited", "exploit", "poc", "proof-of-concept")):
        embed.add_field(
            name="⚠️ Exploit Signal",
            value="Potential exploit activity detected in description.",
            inline=False,
        )

    embed.set_footer(text="Source: NVD (National Vulnerability Database)")
    return embed


class CVECog(commands.Cog, name="CVE"):
    """CVE lookup and vulnerability intelligence."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="cve", description="Look up a CVE by ID (e.g. CVE-2024-1234).")
    @app_commands.describe(cve_id="The CVE identifier, e.g. CVE-2024-12345")
    async def cve_lookup(
        self, interaction: discord.Interaction, cve_id: str
    ) -> None:
        await interaction.response.defer(thinking=True)

        # Basic format validation
        cve_id = cve_id.strip().upper()
        if not cve_id.startswith("CVE-"):
            await interaction.followup.send(
                "❌ Invalid format. Use: `/cve CVE-YYYY-NNNNN`"
            )
            return

        cve = await nvd.lookup_cve(cve_id)
        if cve is None:
            await interaction.followup.send(
                f"❌ Could not find **{cve_id}** in the NVD. "
                "Check the ID or try again later."
            )
            return

        embed = _build_cve_embed(cve)
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(CVECog(bot))
