"""Audio commands cog for core audio playback features."""

import discord
import os
import asyncio
import time
import subprocess
from discord import app_commands
from discord.ext import commands
from checks import interaction_has_allowed_role


class ChooseTrackView(discord.ui.View):
    """Ephemeral view to pick one track when multiple files share the same name."""

    def __init__(self, cog, paths, start_at, guild, channel, user, timeout=60):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.paths = paths
        self.start_at = start_at
        self.guild = guild
        self.channel = channel
        self.user = user
        for i, path in enumerate(paths[:25]):
            label = path if len(path) <= 80 else path[:77] + "..."
            self.add_item(ChooseTrackButton(label=label, path=path, row=i // 5))

    async def on_timeout(self):
        self.stop()


class ChooseTrackButton(discord.ui.Button):
    def __init__(self, label, path, row=0):
        super().__init__(label=label, style=discord.ButtonStyle.primary, row=row)
        self._path = path

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if interaction.user != view.user:
            await interaction.response.send_message("Only the person who requested play can choose.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=False)
        # Validate start_at if provided
        if view.start_at is not None:
            parsed = view.cog.parse_timestamp(view.start_at)
            if parsed is None or parsed < 0:
                await interaction.followup.send(
                    "Invalid timestamp. Use e.g. `1:15`, `1:15:30`, or `75` (seconds).",
                    ephemeral=True,
                )
                return
        success, msg = await view.cog._queue_single_track(
            view.guild, view.channel, view.user, self._path, view.start_at
        )
        await interaction.followup.send(msg)
        view.stop()


class AudioCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.audio_queues = {}
        self.looping = {}
        self.current_track = {}
        self.skip_requested = {}
        self.queue_cache = {}
        self.audio_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "audio")
        self.next_play_start_offset = {}
        self.playback_start_time = {}
        self.total_duration_seconds = {}
        self.accumulated_pause_seconds = {}
        self.pause_start_time = {}
        self.start_offset_seconds = {}
        self.skipto_in_progress = {}
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

    def get_audio_duration(self, file_path):
        """Return duration in seconds (float) or None if unknown."""
        try:
            out = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", file_path],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if out.returncode == 0 and out.stdout.strip():
                return float(out.stdout.strip())
        except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
            pass
        return None

    @staticmethod
    def parse_timestamp(s):
        """Parse '1:15', '1:15:30', or '75' into seconds. Returns None if invalid."""
        if not s or not s.strip():
            return None
        s = s.strip()
        parts = s.split(":")
        if len(parts) == 1:
            try:
                return int(parts[0])
            except ValueError:
                return None
        if len(parts) == 2:
            try:
                m, sec = int(parts[0]), int(parts[1])
                return m * 60 + sec
            except ValueError:
                return None
        if len(parts) == 3:
            try:
                h, m, sec = int(parts[0]), int(parts[1]), int(parts[2])
                return h * 3600 + m * 60 + sec
            except ValueError:
                return None
        return None

    @staticmethod
    def format_timestamp(seconds):
        """Format seconds as M:SS or H:MM:SS."""
        if seconds is None or seconds < 0:
            return "0:00"
        secs = int(seconds)
        if secs >= 3600:
            h = secs // 3600
            rem = secs % 3600
            return f"{h}:{rem // 60:02d}:{rem % 60:02d}"
        return f"{secs // 60}:{secs % 60:02d}"

    def get_current_elapsed(self, guild_id):
        """Return current playback position in seconds (including start_offset), or None."""
        if guild_id not in self.playback_start_time:
            return None
        start = self.playback_start_time[guild_id]
        acc_pause = self.accumulated_pause_seconds.get(guild_id, 0)
        pause_start = self.pause_start_time.get(guild_id)
        if pause_start is not None:
            elapsed = pause_start - start - acc_pause
        else:
            elapsed = time.monotonic() - start - acc_pause
        offset = self.start_offset_seconds.get(guild_id, 0)
        return offset + elapsed

    def clear_timestamp_state(self, guild_id):
        """Clear timestamp tracking for a guild."""
        self.playback_start_time.pop(guild_id, None)
        self.total_duration_seconds.pop(guild_id, None)
        self.accumulated_pause_seconds.pop(guild_id, None)
        self.pause_start_time.pop(guild_id, None)
        self.start_offset_seconds.pop(guild_id, None)
        self.next_play_start_offset.pop(guild_id, None)
        self.skipto_in_progress.pop(guild_id, None)

    def collect_audio_from_folder(self, folder_path):
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

    def find_audio_by_basename(self, basename, under_path=None):
        """Return list of relative paths (forward slashes) under audio_folder with this basename.
        If under_path is set (e.g. 'subfolder' or 'subfolder/nested'), only paths under that directory are returned.
        """
        valid_extensions = ('.mp3', '.wav', '.ogg', '.flac', '.m4a')
        if not basename.lower().endswith(valid_extensions):
            return []
        path_prefix = None
        if under_path:
            path_prefix = under_path.replace("\\", "/").strip("/") + "/"
        matches = []
        for root, _dirs, files in os.walk(self.audio_folder):
            for f in files:
                if f.lower() == basename.lower():
                    full = os.path.join(root, f)
                    rel = os.path.relpath(full, self.audio_folder)
                    rel_norm = rel.replace(os.sep, "/")
                    if path_prefix is not None and not rel_norm.startswith(path_prefix):
                        continue
                    matches.append(rel_norm)
        return matches

    def _make_after_callback(self, channel, guild_id, voice_client):
        """Return the after_playing callback used when a track ends (loop, skip, or next)."""
        def after_playing(error):
            if self.skipto_in_progress.pop(guild_id, False):
                return
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
                self.start_offset_seconds[guild_id] = 0
                self.playback_start_time[guild_id] = time.monotonic()
                self.accumulated_pause_seconds[guild_id] = 0
                self.pause_start_time[guild_id] = None
                new_source = discord.FFmpegPCMAudio(self.current_track[guild_id], executable="ffmpeg")
                if voice_client:
                    voice_client.play(new_source, after=after_playing)
                return
            asyncio.run_coroutine_threadsafe(
                self._safe_play_next(channel, guild_id), self.bot.loop
            )
        return after_playing

    def play_next(self, channel, guild_id):
        """Queue consumer; sends status to channel"""
        queue = self.get_queue(guild_id)
        guild = self.bot.get_guild(guild_id)
        voice_client = guild.voice_client if guild else None

        async def _play():
            if queue.empty():
                self.current_track.pop(guild_id, None)
                self.clear_timestamp_state(guild_id)
                return
            filename = await queue.get()
            self.queue_cache[guild_id].pop(0)
            file_path = self.resolve_audio_path(filename)
            if not os.path.exists(file_path):
                await channel.send(f"Couldn't find `{filename}`; please check your spelling and try again.")
                self.play_next(channel, guild_id)
                return

            self.current_track[guild_id] = self.resolve_audio_path(filename)
            start_offset = self.next_play_start_offset.pop(guild_id, 0)
            duration = await asyncio.to_thread(self.get_audio_duration, file_path)
            self.total_duration_seconds[guild_id] = duration
            self.start_offset_seconds[guild_id] = start_offset
            self.playback_start_time[guild_id] = time.monotonic()
            self.accumulated_pause_seconds[guild_id] = 0
            self.pause_start_time[guild_id] = None

            before_options = f"-ss {int(start_offset)}" if start_offset else None
            source = discord.FFmpegPCMAudio(file_path, executable="ffmpeg", before_options=before_options)
            after_playing = self._make_after_callback(channel, guild_id, voice_client)

            print(f"[DEBUG] Now playing: {filename}")
            await channel.send(f"Now playing `{filename}`.")
            if voice_client:
                voice_client.play(source, after=after_playing)

        asyncio.create_task(_play())

    async def _safe_play_next(self, channel, guild_id):
        await asyncio.sleep(1)
        self.play_next(channel, guild_id)

    async def _queue_single_track(self, guild, channel, user, path, start_at):
        """Connect to voice if needed, queue one track, start playback if idle. Returns (success, message)."""
        voice_client = guild.voice_client
        just_connected = False
        if not voice_client:
            author_voice = getattr(user, "voice", None)
            if not author_voice or not author_voice.channel:
                return False, "You must be in a voice channel to play audio."
            await author_voice.channel.connect()
            voice_client = guild.voice_client
            just_connected = True
        guild_id = guild.id
        queue = self.get_queue(guild_id)
        queue_was_empty = queue.empty() and not voice_client.is_playing()
        await queue.put(path)
        self.queue_cache[guild_id].append(path)
        if start_at is not None and queue_was_empty:
            parsed = self.parse_timestamp(start_at)
            if parsed is not None and parsed >= 0:
                self.next_play_start_offset[guild_id] = parsed
        if not voice_client.is_playing():
            self.play_next(channel, guild_id)
        if just_connected:
            msg = f"Joined {voice_client.channel.name}, queued track: `{path}`."
        else:
            msg = f"Queued the following track: `{path}`."
        return True, msg

    @app_commands.command(name="play", description="Queue audio from the audio folder. Use /audio to list files.")
    @app_commands.describe(
        filename="Filename with extension, e.g. song.mp3 or subfolder/song.mp3 or folder path to queue all tracks",
        start_at="Optional. Start playback from this time (e.g. 1:15 or 75). Only used when queue is empty and a single file is played.",
    )
    async def play(self, interaction: discord.Interaction, filename: str, start_at: str = None):
        """Queue audio from the audio folder. Use /audio to list files."""
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
            # Resolve by basename; scope to path prefix if user provided one
            basename_only = os.path.basename(filename)
            has_path = "/" in filename or "\\" in filename
            under_path = os.path.dirname(filename).replace("\\", "/").strip("/") or None if has_path else None
            matches = self.find_audio_by_basename(basename_only, under_path=under_path)
            if not matches:
                await interaction.response.send_message(
                    f"Couldn't find `{filename}`; please check your spelling and try again.",
                    ephemeral=True,
                )
                return
            if len(matches) == 1:
                to_queue = [matches[0]]
            else:
                # Multiple matches -> let user choose (ephemeral for requester only)
                view = ChooseTrackView(
                    self, matches, start_at,
                    interaction.guild, interaction.channel, interaction.user,
                )
                await interaction.response.send_message(
                    f"Found **{len(matches)}** tracks named `{os.path.basename(filename)}`. Choose one:",
                    view=view,
                    ephemeral=True,
                )
                return
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

        if start_at is not None:
            parsed = self.parse_timestamp(start_at)
            if parsed is None or parsed < 0:
                await interaction.response.send_message("Invalid timestamp. Use e.g. `1:15`, `1:15:30`, or `75` (seconds).", ephemeral=True)
                return
            # Only used when single file and queue empty and nothing playing (set below)

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
        queue_was_empty = queue.empty() and not voice_client.is_playing()
        for entry in to_queue:
            await queue.put(entry)
            self.queue_cache[guild_id].append(entry)

        if start_at is not None and len(to_queue) == 1 and queue_was_empty:
            self.next_play_start_offset[guild_id] = self.parse_timestamp(start_at)

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

    @app_commands.command(name="skipto", description="Skip to a timestamp in the currently playing track.")
    @app_commands.describe(
        timestamp="Time to skip to (e.g. 1:15, 1:15:30, or 75 for seconds).",
    )
    async def skipto(self, interaction: discord.Interaction, timestamp: str):
        if not interaction_has_allowed_role(interaction):
            await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
            return
        if not interaction.guild:
            await interaction.response.send_message("This command only works in servers.", ephemeral=True)
            return
        guild_id = interaction.guild.id
        voice_client = interaction.guild.voice_client
        if not voice_client:
            await interaction.response.send_message("Not currently in a voice channel.", ephemeral=True)
            return
        if not (voice_client.is_playing() or voice_client.is_paused()):
            await interaction.response.send_message("No audio is currently playing to skip within.", ephemeral=True)
            return
        if guild_id not in self.current_track:
            await interaction.response.send_message("No track is currently focused.", ephemeral=True)
            return

        parsed = self.parse_timestamp(timestamp)
        if parsed is None or parsed < 0:
            await interaction.response.send_message(
                "Invalid timestamp. Use e.g. `1:15`, `1:15:30`, or `75` (seconds).",
                ephemeral=True,
            )
            return

        total_duration = self.total_duration_seconds.get(guild_id)
        if total_duration is not None and parsed >= total_duration:
            await interaction.response.send_message(
                "This timestamp exceeds the total runtime of the focused audio track.",
                ephemeral=True,
            )
            return

        file_path = self.current_track[guild_id]
        self.skipto_in_progress[guild_id] = True  # so after() from stop() doesn't advance queue
        voice_client.stop()
        self.start_offset_seconds[guild_id] = parsed
        self.playback_start_time[guild_id] = time.monotonic()
        self.accumulated_pause_seconds[guild_id] = 0
        self.pause_start_time[guild_id] = None

        before_options = f"-ss {int(parsed)}"
        source = discord.FFmpegPCMAudio(file_path, executable="ffmpeg", before_options=before_options)
        after_playing = self._make_after_callback(interaction.channel, guild_id, voice_client)
        voice_client.play(source, after=after_playing)

        await interaction.response.send_message(f"Skipped to **{self.format_timestamp(parsed)}**.")

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
            self.clear_timestamp_state(guild_id)
            self.current_track.pop(guild_id, None)
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
        guild_id = interaction.guild.id
        voice_client = interaction.guild.voice_client
        if voice_client and voice_client.is_playing():
            voice_client.pause()
            self.pause_start_time[guild_id] = time.monotonic()
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
        guild_id = interaction.guild.id
        voice_client = interaction.guild.voice_client
        if voice_client and voice_client.is_paused():
            voice_client.resume()
            if guild_id in self.pause_start_time and self.pause_start_time[guild_id] is not None:
                self.accumulated_pause_seconds[guild_id] = self.accumulated_pause_seconds.get(guild_id, 0) + (time.monotonic() - self.pause_start_time[guild_id])
                self.pause_start_time[guild_id] = None
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
            total_sec = self.total_duration_seconds.get(guild_id)
            elapsed_sec = self.get_current_elapsed(guild_id)
            if total_sec is not None and elapsed_sec is not None:
                # Clamp elapsed to total for display (e.g. past end while switching)
                display_elapsed = min(int(elapsed_sec), int(total_sec))
                now_playing_value = f"`{current_filename}` — {self.format_timestamp(display_elapsed)}/{self.format_timestamp(total_sec)}"
            else:
                now_playing_value = f"`{current_filename}`"
            embed.add_field(name="Now playing", value=now_playing_value, inline=False)

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

    @app_commands.command(name="audio", description="List available audio.")
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
            # When inside a subfolder, show only names (no path prefix) for cleaner display
            display = (lambda p: os.path.basename(p)) if opt_dir else (lambda p: p)
            folder_line = ("📁 " + ", ".join(f"**{display(path)}**" for path in folders)) if folders else ""
            file_entries = [f"`{display(path)}`" for path in files]
            all_entries = ([folder_line] if folder_line else []) + file_entries

            if not all_entries:
                await interaction.response.send_message("No audio files or subfolders were found in this folder.")
                return

            page_size = 12
            pages = [all_entries[i:i+page_size] for i in range(0, len(all_entries), page_size)]
            total_pages = len(pages)
            current_page = 0
            title_prefix = f'Available audio in "{opt_dir}"' if opt_dir else "Available audio"

            def get_page_embed(page):
                lines = [f"{1 + page * page_size + i}. {name}" for i, name in enumerate(pages[page])]
                embed = discord.Embed(
                    title=f"{title_prefix} (page {page+1}/{total_pages})",
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
                await interaction.response.send_message("There was an error attempting to read the audio folder.", ephemeral=True)
            except Exception:
                await interaction.followup.send("There was an error attempting to read the audio folder.", ephemeral=True)
                
async def setup(bot):
    await bot.add_cog(AudioCog(bot))
