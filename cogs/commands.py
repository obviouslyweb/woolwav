"""Basic commands cog for info, help, leave, etc."""

import discord
from discord import app_commands
from discord.ext import commands
from checks import check_allowed_roles, interaction_has_allowed_role

class CommandsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        print("Cog 'commands' loaded.")
        self.__cog_name__ = "Core"

    @app_commands.command(name="info", description="Display bot version and details.")
    async def info(self, interaction: discord.Interaction) -> None:
        embed = discord.Embed(
            title="TERMINAL_19",
            description="Currently running TERMINAL_19. Specific details coming soon.",
            color=0x5865F2,
        )
        embed.set_footer(text="Slash commands • Use /help for the full command list")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="help", description="Display all commands.")
    async def help(self, interaction: discord.Interaction) -> None:
        if not interaction_has_allowed_role(interaction):
            await interaction.response.send_message(
                "You don't have permission to use this command.",
                ephemeral=True,
            )
            return
        embed = discord.Embed(
            title="TERMINAL_19 Commands",
            description=(
                "**Core**\n"
                "/help — Display this message\n"
                "/info — Bot version and details\n"
                "/leave — Leave the voice channel\n\n"
                "**Audio**\n"
                "/play (filename) — Join VC and play; use /sounds to list files\n"
                "/sounds [subfolder] — List available audio; optional subfolder to browse\n"
                "/skip — Skip to the next track\n"
                "/queue — Show now playing and queue\n"
                "/loop — Toggle looping for the current track\n"
                "/stop — Stop and clear the queue\n"
                "/clearqueue — Clear the queue\n"
                "/pause — Pause playback\n"
                "/unpause — Resume playback"
            ),
            color=0x5865F2,
        )
        embed.set_footer(text="Use slash commands with / in the chat")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="leave", description="Leave the current voice channel.")
    async def leave(self, interaction: discord.Interaction) -> None:
        if not interaction_has_allowed_role(interaction):
            await interaction.response.send_message(
                "You don't have permission to use this command.",
                ephemeral=True,
            )
            return
        voice_client = interaction.guild.voice_client if interaction.guild else None
        if voice_client:
            await voice_client.disconnect()
            await interaction.response.send_message("Disconnected from voice channel.")
        else:
            await interaction.response.send_message("Not currently in a voice channel to leave.")

async def setup(bot):
    await bot.add_cog(CommandsCog(bot))
