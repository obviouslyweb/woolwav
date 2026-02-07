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

    # --------- TEST COMMAND, WILL BE REMOVED LATER ---------
    @app_commands.command(name="echo", description="Echoes a message.")
    @app_commands.describe(message="The message to echo.")
    async def echo(self, interaction: discord.Interaction, message: str) -> None:
        await interaction.response.send_message(message)
    # --------- TEST COMMAND, WILL BE REMOVED LATER ---------

    @app_commands.command(name="info", description="Display bot version and details.")
    async def info(self, interaction: discord.Interaction) -> None:
        print("Info command sent. Attempting to send response...")
        await interaction.response.send_message("Currently running TERMINAL_19. Specific details coming soon.")

    @app_commands.command(name="help", description="Display all commands.")
    async def help(self, interaction: discord.Interaction) -> None:
        if not interaction_has_allowed_role(interaction):
            await interaction.response.send_message(
                "You don't have permission to use this command.",
                ephemeral=True,
            )
            return
        await interaction.response.send_message(
            "```"
            "TERMINAL_19 COMMANDS\n\n"
            "[ CORE COMMANDS ]\n"
            "!help - Display all commands\n"
            "!info - Display bot version\n"
            "\n"
            "[ AUDIO COMMANDS ]\n"
            "!leave - Have the bot leave the voice channel it's in.\n"
            "!play (filename.ext) - Have the bot join the VC and play audio from the bot's sounds list. Filename & extension required.\n"
            "!sounds {subfolder} - Display the bot's sound list. Subfolder parameter is optional.\n"
            "!skip - Skips to the next song in the queue.\n"
            "!queue - Show the currently playing track and queued songs, as well as looping status.\n"
            "!loop - Toggles looping, where the currently playing song will replay indefinitely.\n"
            "!stop - Force the bot to stop playing audio entirely, AND clear the queue.\n"
            "!clearqueue - Clear all tracks in the queue.\n"
            "!pause - Pauses the currently playing track.\n"
            "!unpause - Resume playing a paused track.\n"
            "```"
        )

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
            await interaction.response.send_message("`DISCONNECTED FROM VOICE CHANNEL.`")
        else:
            await interaction.response.send_message("`NOT CURRENTLY IN A VOICE CHANNEL.`")

async def setup(bot):
    await bot.add_cog(CommandsCog(bot))
