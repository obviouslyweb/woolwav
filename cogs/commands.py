"""Basic commands cog for info, help, leave, etc."""

import discord
from discord import app_commands
from discord.ext import commands
from checks import check_allowed_roles

class CommandsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        print("Cog 'commands' loaded.")
        self.__cog_name__ = "Core"

    @app_commands.command(name="echo", description="Echoes a message.")
    @app_commands.describe(message="The message to echo.")
    async def echo(self, interaction: discord.Interaction, message: str) -> None:
        await interaction.response.send_message(message)

    @commands.command(name="info", help="Display bot version and details.")
    async def info(self, ctx):
        print("Info command sent. Attempting to send response...")
        await ctx.send("`CURRENTLY RUNNING TERMINAL_19 BOT VERSION 1.0.0.`")

    @commands.command()
    @commands.check(check_allowed_roles)
    async def help(self, ctx):
        await ctx.send("```"
            "TERMINAL_19 COMMANDS\n\n"
            "[ CORE COMMANDS ]\n"
            "!help - Display all commands\n"
            "!info - Display bot version\n"
            "\n"
            "[ AUDIO COMMANDS ]\n"
            "!leave - Have the bot leave the voice channel it's in.\n"
            "!play (filename.ext) - Have the bot join the VC and play audio from the bot's sounds list. Filename & extension required.\n"
            "!audio {subfolder} - Display the bot's sound list in full. Subfolder parameter is optional, allows you to view audio files in a subfolder.\n"
            "!skip - Skips to the next song in the queue.\n"
            "!queue - Show the currently playing track and queued songs, as well as looping status.\n"
            "!loop - Toggles looping, where the currently playing song will replay indefinitely.\n"
            "!stop - Force the bot to stop playing audio entirely, AND clear the queue.\n"
            "!clearqueue - Clear all tracks in the queue.\n"
            "!pause - Pauses the currently playing track.\n"
            "!unpause - Resume playing a paused track.\n"
            "```"
        )

    @commands.command(name="leave", help="Leave the current voice channel.")
    @commands.check(check_allowed_roles)
    async def leave(self, ctx):
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
            await ctx.send("`DISCONNECTED FROM VOICE CHANNEL.`")
        else:
            await ctx.send("`NOT CURRENTLY IN A VOICE CHANNEL.`")

async def setup(bot):
    await bot.add_cog(CommandsCog(bot))
