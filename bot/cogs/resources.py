"""
cogs/resources.py — Cybersecurity Resources Library cog.

Static + dynamic curated database of learning resources.
Topics: web security, linux, networking, python security,
        reverse engineering, forensics, ctf, nmap, ...

Slash commands:
  /resource <topic>    — List resources for a topic
  /cheat <tool>        — Quick cheatsheet for a tool
"""

from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

log = logging.getLogger(__name__)

# ── Curated Resource Library ──────────────────────────────────────────────────
RESOURCES: dict[str, list[dict]] = {
    "xss": [
        {"title": "PortSwigger XSS Labs", "url": "https://portswigger.net/web-security/cross-site-scripting", "desc": "Interactive XSS labs by PortSwigger."},
        {"title": "OWASP XSS Prevention Cheat Sheet", "url": "https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html", "desc": "Comprehensive XSS prevention guide."},
        {"title": "HackTricks XSS", "url": "https://book.hacktricks.xyz/pentesting-web/xss-cross-site-scripting", "desc": "Real-world XSS tricks and bypasses."},
    ],
    "sql injection": [
        {"title": "PortSwigger SQLi Labs", "url": "https://portswigger.net/web-security/sql-injection", "desc": "SQL injection labs with solutions."},
        {"title": "SQLMap Documentation", "url": "https://sqlmap.org", "desc": "The premier automated SQLi tool."},
        {"title": "OWASP SQLi Prevention", "url": "https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html", "desc": "Prevention cheat sheet."},
    ],
    "linux": [
        {"title": "OverTheWire: Bandit", "url": "https://overthewire.org/wargames/bandit/", "desc": "Linux fundamentals through wargames."},
        {"title": "Linux Journey", "url": "https://linuxjourney.com", "desc": "Interactive Linux learning platform."},
        {"title": "ExplainShell", "url": "https://explainshell.com", "desc": "Explains any Linux command."},
        {"title": "HackTricks Linux PrivEsc", "url": "https://book.hacktricks.xyz/linux-hardening/privilege-escalation", "desc": "Linux privilege escalation techniques."},
    ],
    "networking": [
        {"title": "Cisco NetAcad Networking Basics", "url": "https://www.netacad.com/courses/networking-basics", "desc": "Free Cisco networking course."},
        {"title": "Wireshark User Guide", "url": "https://www.wireshark.org/docs/wsug_html_chunked/", "desc": "Official packet analysis guide."},
        {"title": "TryHackMe: Pre-Security", "url": "https://tryhackme.com/path/outline/presecurity", "desc": "Networking fundamentals path."},
    ],
    "python": [
        {"title": "Black Hat Python", "url": "https://nostarch.com/black-hat-python2E", "desc": "Python programming for hackers."},
        {"title": "Automate the Boring Stuff", "url": "https://automatetheboringstuff.com", "desc": "Free Python book for automation."},
        {"title": "Scapy Documentation", "url": "https://scapy.readthedocs.io", "desc": "Python packet manipulation library."},
    ],
    "reverse engineering": [
        {"title": "Ghidra", "url": "https://ghidra-sre.org", "desc": "NSA's free reverse engineering suite."},
        {"title": "Malware Unicorn Workshops", "url": "https://malwareunicorn.org/workshops", "desc": "Free malware RE workshops."},
        {"title": "pwn.college", "url": "https://pwn.college", "desc": "RE and pwning exercises."},
        {"title": "Crackmes.one", "url": "https://crackmes.one", "desc": "Community reverse engineering challenges."},
    ],
    "forensics": [
        {"title": "Autopsy", "url": "https://www.autopsy.com", "desc": "Open source digital forensics platform."},
        {"title": "SANS Cheat Sheets", "url": "https://www.sans.org/blog/the-ultimate-list-of-sans-cheat-sheets/", "desc": "DFIR quick reference cards."},
        {"title": "CyberDefenders", "url": "https://cyberdefenders.org", "desc": "Blue team and forensics challenges."},
    ],
    "ctf": [
        {"title": "CTFtime", "url": "https://ctftime.org", "desc": "CTF event calendar and team rankings."},
        {"title": "picoCTF", "url": "https://picoctf.org", "desc": "Beginner-friendly CTF by CMU."},
        {"title": "Hack The Box", "url": "https://www.hackthebox.com", "desc": "Real-world hacking labs."},
        {"title": "TryHackMe", "url": "https://tryhackme.com", "desc": "Guided cybersecurity learning rooms."},
    ],
    "osint": [
        {"title": "OSINT Framework", "url": "https://osintframework.com", "desc": "Comprehensive OSINT tool directory."},
        {"title": "Maltego Community", "url": "https://www.maltego.com", "desc": "OSINT and link analysis."},
        {"title": "Shodan", "url": "https://www.shodan.io", "desc": "Search engine for internet-connected devices."},
    ],
    "web security": [
        {"title": "PortSwigger Web Academy", "url": "https://portswigger.net/web-security", "desc": "Comprehensive free web security course."},
        {"title": "OWASP Top 10", "url": "https://owasp.org/www-project-top-ten/", "desc": "Top 10 web application security risks."},
        {"title": "HackTricks Web", "url": "https://book.hacktricks.xyz/pentesting-web", "desc": "Web pentest techniques encyclopedia."},
    ],
    "malware": [
        {"title": "ANY.RUN", "url": "https://any.run", "desc": "Interactive malware sandbox."},
        {"title": "VirusTotal", "url": "https://www.virustotal.com", "desc": "Multi-AV malware scanner."},
        {"title": "MalwareBazaar", "url": "https://bazaar.abuse.ch", "desc": "Malware sample repository."},
    ],
}

# ── Cheat sheets ──────────────────────────────────────────────────────────────
CHEAT_SHEETS: dict[str, str] = {
    "nmap": (
        "```\n"
        "# Quick scans\n"
        "nmap -sn 192.168.1.0/24          # Ping sweep\n"
        "nmap -sV -sC -p- <target>        # Full port + version + scripts\n"
        "nmap -A -T4 <target>             # Aggressive + timing\n"
        "nmap -sU --top-ports 200 <target> # Top 200 UDP ports\n\n"
        "# Output\n"
        "nmap -oA scan_output <target>    # All formats (xml, grep, nmap)\n\n"
        "# Scripts\n"
        "nmap --script=vuln <target>      # Vuln scan\n"
        "nmap --script=smb-vuln-* <target> # SMB vuln check\n"
        "```"
    ),
    "gobuster": (
        "```\n"
        "gobuster dir -u http://target -w /usr/share/wordlists/dirb/common.txt\n"
        "gobuster dns -d target.com -w /usr/share/wordlists/subdomains.txt\n"
        "gobuster vhost -u http://target -w wordlist.txt\n"
        "# -t 50 (threads) -x php,html,txt (extensions)\n"
        "```"
    ),
    "sqlmap": (
        "```\n"
        "sqlmap -u 'http://target/page?id=1' --dbs\n"
        "sqlmap -u 'http://target/page?id=1' -D dbname --tables\n"
        "sqlmap -u 'http://target/page?id=1' -D dbname -T users --dump\n"
        "sqlmap -r request.txt --level=5 --risk=3\n"
        "```"
    ),
    "hydra": (
        "```\n"
        "hydra -l admin -P passwords.txt ssh://target\n"
        "hydra -L users.txt -P pass.txt ftp://target\n"
        "hydra -l admin -P pass.txt http-post-form '/login:user=^USER^&pass=^PASS^:Invalid'\n"
        "```"
    ),
    "ffuf": (
        "```\n"
        "ffuf -u http://target/FUZZ -w wordlist.txt\n"
        "ffuf -u http://target/FUZZ -w wordlist.txt -e .php,.html,.txt\n"
        "ffuf -u http://target -H 'Host: FUZZ.target.com' -w subdomains.txt\n"
        "ffuf -u http://target/FUZZ -w wordlist.txt -fc 403,404\n"
        "```"
    ),
    "metasploit": (
        "```\n"
        "msfconsole\n"
        "search <exploit_name>\n"
        "use exploit/multi/handler\n"
        "set payload windows/meterpreter/reverse_tcp\n"
        "set LHOST <your_ip>\n"
        "set LPORT 4444\n"
        "run\n"
        "```"
    ),
    "burpsuite": (
        "```\n"
        "# Key shortcuts\n"
        "Ctrl+R — Send to Repeater\n"
        "Ctrl+I — Send to Intruder\n"
        "Ctrl+Shift+U — URL encode\n"
        "# Proxy: 127.0.0.1:8080\n"
        "# Add CA cert: http://burpsuite or http://127.0.0.1:8080\n"
        "```"
    ),
}


class ResourcesCog(commands.Cog, name="Resources"):
    """Cybersecurity learning resource library."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="resource", description="Get learning resources for a cybersecurity topic."
    )
    @app_commands.describe(topic="Topic (e.g. xss, linux, forensics, ctf, osint)")
    async def resource(self, interaction: discord.Interaction, topic: str) -> None:
        key = topic.lower().strip()
        # Fuzzy match — check if key appears in any resource key
        matches = [k for k in RESOURCES if key in k or k in key]

        if not matches:
            available = ", ".join(f"`{k}`" for k in sorted(RESOURCES.keys()))
            await interaction.response.send_message(
                f"❌ Topic `{topic}` not found.\n\n**Available topics:** {available}",
                ephemeral=True,
            )
            return

        best = matches[0]
        entries = RESOURCES[best]
        embed = discord.Embed(
            title=f"📚 Resources: {best.title()}",
            color=0x00BFAE,
            description=f"{len(entries)} curated resources found.",
        )
        for entry in entries:
            embed.add_field(
                name=f"🔗 {entry['title']}",
                value=f"{entry['desc']}\n[→ Open]({entry['url']})",
                inline=False,
            )
        embed.set_footer(text="CyberCape Resources Library")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="cheat", description="Quick command cheatsheet for a security tool."
    )
    @app_commands.describe(tool="Tool name (e.g. nmap, gobuster, sqlmap, hydra)")
    async def cheat(self, interaction: discord.Interaction, tool: str) -> None:
        key = tool.lower().strip()
        sheet = CHEAT_SHEETS.get(key)

        if sheet is None:
            available = ", ".join(f"`{k}`" for k in sorted(CHEAT_SHEETS.keys()))
            await interaction.response.send_message(
                f"❌ No cheatsheet for `{tool}`.\n\n**Available:** {available}",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title=f"📋 {tool.upper()} Cheatsheet",
            description=sheet,
            color=0x1ABC9C,
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="topics", description="List all available resource topics."
    )
    async def topics(self, interaction: discord.Interaction) -> None:
        topics_list = "\n".join(
            f"• `{k}` ({len(v)} resources)" for k, v in sorted(RESOURCES.items())
        )
        embed = discord.Embed(
            title="📚 Available Topics",
            description=topics_list,
            color=0x9B59B6,
        )
        embed.set_footer(text="Use /resource <topic> to get started")
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ResourcesCog(bot))
