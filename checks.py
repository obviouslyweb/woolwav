"""Shared command checks. Allowed roles are configured via .env (ALLOWED_ROLES)"""

import discord
from discord.ext import commands


def _has_allowed_role(bot, user, guild) -> bool:
    # Single place for role logic, true if no restriction or user has an allowed role
    allowed = getattr(bot, "allowed_roles", None) or []
    if not allowed:
        return True
    if not guild:
        return False
    author_roles = {r.name for r in getattr(user, "roles", [])}
    return bool(author_roles & set(allowed))


def interaction_has_allowed_role(interaction: discord.Interaction) -> bool:
    # Use for slash commands
    return _has_allowed_role(interaction.client, interaction.user, interaction.guild)


async def check_allowed_roles(ctx: commands.Context) -> bool:
    # Used with @commands.check() for prefix commands, logs to console on failure
    passed = _has_allowed_role(ctx.bot, ctx.author, ctx.guild)
    if not passed:
        channel = getattr(ctx.channel, "name", "?")
        print(f"[DEBUG] Role check failed: {ctx.author} ({ctx.author.id}) tried !{ctx.command} in #{channel} but lacks an allowed role.")
    return passed
