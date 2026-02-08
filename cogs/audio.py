"""Audio commands cog for core audio playback features."""

import discord
import os
import asyncio
from discord import app_commands
from discord.ext import commands
from checks import interaction_has_allowed_role

class AudioCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.audio_queues = {}
        self.looping = {}
        self.current_track = {}
        self.skip_requested = {}
        self.queue_cache = {}
        self.audio_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "audio")
        print("Cog 'audio' loaded.")
        self.__cog_name__ = "Audio"

    def get_queue(self, guild_id):
        if guild_id not in self.audio_queues:
            self.audio_queues[guild_id] = asyncio.Queue()
            self.skip_requested[guild_id] = False
            self.queue_cache[guild_id] = []
        if guild_id not in self.looping:
            self.looping[guild_id] = False
        return self.audio_queues[guild_id]

    def resolve_audio_path(self, filename):
        return os.path.join(self.audio_folder, filename)

    def collect_audio_from_folder(self, folder_path):
        # Get audio paths from folder, used when playing a folder
        audio_folder_real = os.path.realpath(self.audio_folder)
        folder_real = os.path.realpath(folder_path)
        if not folder_real.startswith(audio_folder_real):
            return
        valid_extensions = ('.mp3', '.wav', '.ogg', '.flac', '.m4a')
        for root, _dirs, files in os.walk(folder_path):
            for f in files:
                if f.lower().endswith(valid_extensions):
                    full = os.path.join(root, f)
                    rel = os.path.relpath(full, self.audio_folder)
                    yield rel.replace(os.sep, '/')

    def play_next(self, channel, guild_id):
        # Queue consumer; sends status to channel
        queue = self.get_queue(guild_id)
        guild = self.bot.get_guild(guild_id)
        voice_client = guild.voice_client if guild else None

        async def _play():
            if queue.empty():
                return
            filename = await queue.get()
            self.queue_cache[guild_id].pop(0)
            file_path = self.resolve_audio_path(filename)
            if not os.path.exists(file_path):
                await channel.send(f"Couldn't find `{filename}`; please check your spelling and try again.")
                self.play_next(channel, guild_id)
                return

            self.current_track[guild_id] = self.resolve_audio_path(filename)
            print(f"[DEBUG] Now playing: {filename}")
            await channel.send(f"Now playing `{filename}`.")
            source = discord.FFmpegPCMAudio(file_path, executable="ffmpeg")

            def after_playing(error):
                if error:
                    print(f"[ERROR] Playback error: {error}")
                if self.skip_requested.get(guild_id):
                    print(f"[DEBUG] Skip was requested; ignoring current loop.")
                    self.skip_requested[guild_id] = False
                    asyncio.run_coroutine_threadsafe(
                        self._safe_play_next(channel, guild_id), self.bot.loop
                    )
                    return
                if self.looping.get(guild_id):
                    print(f"[DEBUG] Looping track: {self.current_track[guild_id]}")
                    new_source = discord.FFmpegPCMAudio(self.current_track[guild_id], executable="ffmpeg")
                    if voice_client:
                        voice_client.play(new_source, after=after_playing)
                    return
                asyncio.run_coroutine_threadsafe(
                    self._safe_play_next(channel, guild_id), self.bot.loop
                )

            if voice_client:
                voice_client.play(source, after=after_playing)

        asyncio.create_task(_play())

    async def _safe_play_next(self, channel, guild_id):
        await asyncio.sleep(1)
        self.play_next(channel, guild_id)

    @app_commands.command(name="play", description="Queue audio from the bot's audio folder. Use /audio to list files.")
    @app_commands.describe(filename="Filename with extension, e.g. song.mp3 or subfolder/song.mp3 or folder path to queue all tracks")
    async def play(self, interaction: discord.Interaction, filename: str):
        # Check if user has command permissions
        if not interaction_has_allowed_role(interaction):
            await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
            return
        if not interaction.guild:
            await interaction.response.send_message("Hey, this command only works in servers! What are you doing?", ephemeral=True)
            return
        guild_id = interaction.guild.id
        print(f"[DEBUG] Play command received with filename: {filename!r}")
        file_path = self.resolve_audio_path(filename)
        valid_extensions = ('.mp3', '.wav', '.ogg', '.flac', '.m4a')

        # Determine if single file or folder
        to_queue = []
        if filename.lower().endswith(valid_extensions):
            if not os.path.exists(file_path):
                await interaction.response.send_message(f"Couldn't find `{filename}`; please check your spelling and try again.", ephemeral=True)
                return
            if not os.path.isfile(file_path):
                await interaction.response.send_message(f"`{filename}` is a folder. Omit the extension to queue the whole folder, or use a file path.", ephemeral=True)
                return
            to_queue = [filename]
        else:
            if not os.path.isdir(file_path):
                await interaction.response.send_message(f"Couldn't find folder or file `{filename}`. Use a supported audio file or a folder path under the audio folder.", ephemeral=True)
                return
            audio_folder_real = os.path.realpath(self.audio_folder)
            folder_real = os.path.realpath(file_path)
            if not folder_real.startswith(audio_folder_real):
                await interaction.response.send_message("That folder path is not valid.", ephemeral=True)
                return
            to_queue = list(self.collect_audio_from_folder(file_path))
            if not to_queue:
                await interaction.response.send_message(f"No audio files found in folder `{filename}`.", ephemeral=True)
                return

        # Connect to voice client
        voice_client = interaction.guild.voice_client
        just_connected = False
        if not voice_client:
            author_voice = getattr(interaction.user, "voice", None)
            if not author_voice or not author_voice.channel:
                await interaction.response.send_message("You must be in a voice channel to play audio.", ephemeral=True)
                return
            await author_voice.channel.connect()
            voice_client = interaction.guild.voice_client
            just_connected = True

        queue = self.get_queue(guild_id)
        for entry in to_queue:
            await queue.put(entry)
            self.queue_cache[guild_id].append(entry)

        if just_connected:
            if len(to_queue) == 1:
                await interaction.response.send_message(f"Joined {voice_client.channel.name}, queued track: `{to_queue[0]}`.")
            else:
                await interaction.response.send_message(f"Joined {voice_client.channel.name}, queued **{len(to_queue)}** tracks from `{filename}`.")
        else:
            if len(to_queue) == 1:
                await interaction.response.send_message(f"Queued the following track: `{to_queue[0]}`.")
            else:
                await interaction.response.send_message(f"Queued **{len(to_queue)}** tracks from `{filename}`.")

        if not voice_client.is_playing():
            self.play_next(interaction.channel, guild_id)


    @app_commands.command(name="skip", description="Skip the currently playing track.")
    async def skip(self, interaction: discord.Interaction):
        if not interaction_has_allowed_role(interaction):
            await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
            return
        if not interaction.guild:
            await interaction.response.send_message("Not currently in a voice channel.", ephemeral=True)
            return
        guild_id = interaction.guild.id
        voice_client = interaction.guild.voice_client
        if not voice_client:
            await interaction.response.send_message("Not currently in a voice channel.")
            return
        if voice_client.is_playing():
            self.skip_requested[guild_id] = True
            voice_client.stop()
            await asyncio.sleep(1)
            queue = self.get_queue(guild_id)
            if queue.empty():
                await interaction.response.send_message("The end of the queue has been reached. Use /play (file) to continue audio playback.")
            else:
                await interaction.response.send_message("Skipped to the next track.")
        else:
            await interaction.response.send_message("There's no audio playing to skip!")


    @app_commands.command(name="stop", description="Stop playing and clear the queue.")
    async def stop(self, interaction: discord.Interaction):
        if not interaction_has_allowed_role(interaction):
            await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
            return
        if not interaction.guild:
            await interaction.response.send_message("Not currently in a voice channel.", ephemeral=True)
            return
        guild_id = interaction.guild.id
        voice_client = interaction.guild.voice_client
        if voice_client:
            voice_client.stop()
            queue = self.get_queue(guild_id)
            self.queue_cache[guild_id].clear()
            self.looping[guild_id] = False
            while not queue.empty():
                queue.get_nowait()
            await interaction.response.send_message("Audio has been stopped and the queue has been erased.")
        else:
            await interaction.response.send_message("Not currently in a voice channel.")
    
    @app_commands.command(name="clearqueue", description="Clear the rest of the song queue.")
    async def clearqueue(self, interaction: discord.Interaction):
        if not interaction_has_allowed_role(interaction):
            await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
            return
        if not interaction.guild:
            await interaction.response.send_message("Not currently in a voice channel to clear the queue.", ephemeral=True)
            return
        guild_id = interaction.guild.id
        voice_client = interaction.guild.voice_client
        if voice_client:
            queue = self.get_queue(guild_id)
            self.queue_cache[guild_id].clear()
            if not queue.empty():
                while not queue.empty():
                    queue.get_nowait()
                await interaction.response.send_message("The queue has been cleared.")
            else:
                await interaction.response.send_message("The queue is already empty.")
        else:
            await interaction.response.send_message("Not currently in a voice channel to clear the queue.")

    @app_commands.command(name="loop", description="Toggle looping for the current track.")
    async def loop(self, interaction: discord.Interaction):
        if not interaction_has_allowed_role(interaction):
            await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
            return
        if not interaction.guild:
            await interaction.response.send_message("Please use this command in a server.", ephemeral=True)
            return
        guild_id = interaction.guild.id
        if self.looping.get(guild_id, False):
            self.looping[guild_id] = False
            await interaction.response.send_message("Looping is now disabled.")
        else:
            self.looping[guild_id] = True
            await interaction.response.send_message("Looping is now enabled.")

    @app_commands.command(name="pause", description="Pause the currently playing track.")
    async def pause(self, interaction: discord.Interaction):
        if not interaction_has_allowed_role(interaction):
            await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
            return
        if not interaction.guild:
            await interaction.response.send_message("No audio is currently playing that can be paused.", ephemeral=True)
            return
        voice_client = interaction.guild.voice_client
        if voice_client and voice_client.is_playing():
            voice_client.pause()
            await interaction.response.send_message("Audio is now paused.")
        else:
            await interaction.response.send_message("No audio is currently playing that can be paused.")

    @app_commands.command(name="unpause", description="Resume the paused track.")
    async def unpause(self, interaction: discord.Interaction):
        if not interaction_has_allowed_role(interaction):
            await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
            return
        if not interaction.guild:
            await interaction.response.send_message("Audio is not currently paused.", ephemeral=True)
            return
        voice_client = interaction.guild.voice_client
        if voice_client and voice_client.is_paused():
            voice_client.resume()
            await interaction.response.send_message("Continuing playback.")
        else:
            await interaction.response.send_message("Audio is not currently paused.")

    @app_commands.command(name="queue", description="View the current queue and now playing.")
    async def queue(self, interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message("The queue is currently empty.", ephemeral=True)
            return
        guild_id = interaction.guild.id
        current = self.current_track.get(guild_id)
        queue = self.queue_cache.get(guild_id, [])

        if not current and not queue:
            embed = discord.Embed(
                title="Queue",
                description="The queue is currently empty.",
                color=0x5865F2,
            )
            await interaction.response.send_message(embed=embed)
            return

        embed = discord.Embed(title="Queue", color=0x5865F2)

        if current:
            current_filename = os.path.basename(current)
            embed.add_field(name="Now playing", value=f"`{current_filename}`", inline=False)

        if queue:
            # Discord field value limit is 1024; show up to ~20 tracks or truncate
            lines = [f"{i}. `{track}`" for i, track in enumerate(queue[:20], start=1)]
            queue_text = "\n".join(lines)
            if len(queue) > 20:
                queue_text += f"\n*...and {len(queue) - 20} more*"
            embed.add_field(name="Up next", value=queue_text or "—", inline=False)

        loop_status = "Looping is enabled." if self.looping.get(guild_id) else "Looping is disabled."
        embed.set_footer(text=loop_status)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="audio", description="List available audio. Optionally give a subfolder to view its contents.")
    @app_commands.describe(subfolder="Optional subfolder path, e.g. 'wip', 'soundtrack', 'sfx', etc.")
    async def audio(self, interaction: discord.Interaction, subfolder: str = None):
        if not interaction_has_allowed_role(interaction):
            await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
            return
        try:
            opt_dir = subfolder
            search_folder = os.path.join(self.audio_folder, opt_dir) if opt_dir else self.audio_folder
            audio_folder_real = os.path.realpath(self.audio_folder)
            search_folder_real = os.path.realpath(search_folder)

            if not os.path.isdir(search_folder):
                await interaction.response.send_message("That folder couldn't be found. Please check your spelling and try again.", ephemeral=True)
                return
            if not search_folder_real.startswith(audio_folder_real):
                await interaction.response.send_message("That folder path is not valid.", ephemeral=True)
                return

            valid_extensions = ('.mp3', '.wav', '.ogg', '.flac', '.m4a')
            folders = []
            files = []
            with os.scandir(search_folder) as entries:
                for entry in entries:
                    path = f"{opt_dir}/{entry.name}" if opt_dir else entry.name
                    if entry.is_dir():
                        folders.append(path)
                    elif entry.is_file() and entry.name.lower().endswith(valid_extensions):
                        files.append(path)

            folders.sort()
            files.sort()
            folder_entries = [f"📁 **{path}**" for path in folders]
            file_entries = [f"`{path}`" for path in files]
            all_entries = folder_entries + file_entries

            if not all_entries:
                await interaction.response.send_message("No audio files or subfolders were found in this folder.")
                return

            page_size = 10
            pages = [all_entries[i:i+page_size] for i in range(0, len(all_entries), page_size)]
            total_pages = len(pages)
            current_page = 0

            def get_page_embed(page):
                lines = [f"{1 + page * page_size + i}. {name}" for i, name in enumerate(pages[page])]
                embed = discord.Embed(
                    title=f"Available audio (page {page+1}/{total_pages})",
                    description="\n".join(lines),
                    color=0x5865F2,
                )
                footer = "Use /audio (folder) to view a folder, /play (filename) to play"
                if total_pages > 1:
                    footer += " • Arrow reactions to change pages"
                embed.set_footer(text=footer)
                return embed

            await interaction.response.send_message(embed=get_page_embed(current_page))
            message = await interaction.original_response()

            if total_pages == 1:
                return

            await message.add_reaction("⬅️")
            await message.add_reaction("➡️")

            def check(reaction, user):
                return (
                    user == interaction.user and reaction.message.id == message.id and str(reaction.emoji) in ["⬅️", "➡️"]
                )

            while True:
                try:
                    reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=check)
                    if str(reaction.emoji) == "➡️":
                        if current_page < total_pages - 1:
                            current_page += 1
                            await message.edit(embed=get_page_embed(current_page))
                    elif str(reaction.emoji) == "⬅️":
                        if current_page > 0:
                            current_page -= 1
                            await message.edit(embed=get_page_embed(current_page))
                    await message.remove_reaction(reaction, user)
                except asyncio.TimeoutError:
                    await message.clear_reactions()
                    break

        except Exception as e:
            print(f"[ERROR] Error reading audio folder in audio command: {e}")
            try:
                await interaction.response.send_message("There was an error attempting to read the audio folder.`", ephemeral=True)
            except Exception:
                await interaction.followup.send("There was an error attempting to read the audio folder.", ephemeral=True)
                
async def setup(bot):
    await bot.add_cog(AudioCog(bot))
