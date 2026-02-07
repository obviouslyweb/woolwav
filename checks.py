"""Shared command checks. Allowed roles are configured via .env (ALLOWED_ROLES)."""

from discord.ext import commands

async def check_allowed_roles(ctx: commands.Context) -> bool:
    # Check if allowed roles are set; if so, enforce them before executing command
    # If not, allow all users to execute commands
    allowed = getattr(ctx.bot, "allowed_roles", None) or []
    if not allowed:
        return True
    if not ctx.guild:
        print(f"[DEBUG] Role check failed: {ctx.author} tried !{ctx.command} in DMs (no guild).")
        return False
    author_roles = {r.name for r in ctx.author.roles}
    if author_roles & set(allowed):
        return True
    print(f"[DEBUG] Role check failed: {ctx.author} tried !{ctx.command} in #{getattr(ctx.channel, 'name', '?')} but lacks an allowed role")
    return False
