"""Audio commands cog for core audio playback features."""

import discord
import os
import asyncio
from discord.ext import commands
from checks import check_allowed_roles

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

    def play_next(self, ctx, guild_id):
        queue = self.get_queue(guild_id)

        async def _play(): # Main playing function
            if queue.empty():
                return
            filename = await queue.get()
            self.queue_cache[guild_id].pop(0)
            file_path = self.resolve_audio_path(filename)
            if not os.path.exists(file_path):
                await ctx.send(f"`FILE '{filename}' NOT FOUND.`")
                self.play_next(ctx, guild_id)
                return

            self.current_track[ctx.guild.id] = self.resolve_audio_path(filename)
            print(f"[DEBUG] Now playing: {filename}")
            await ctx.send(f"`NOW PLAYING '{filename}'.`")
            source = discord.FFmpegPCMAudio(file_path, executable="ffmpeg")

            def after_playing(error): # Checks after song conclusion to determine next action
                if error:
                    print(f"[ERROR] Playback error: {error}")
                if self.skip_requested.get(guild_id):
                    print(f"[DEBUG] Skip was requested; ignoring current loop.")
                    self.skip_requested[guild_id] = False
                    fut = asyncio.run_coroutine_threadsafe(
                        self._safe_play_next(ctx, guild_id), self.bot.loop
                    )
                    return
                if self.looping.get(guild_id):
                    print(f"[DEBUG] Looping track: {self.current_track[guild_id]}")
                    new_source = discord.FFmpegPCMAudio(self.current_track[guild_id], executable="ffmpeg")
                    ctx.voice_client.play(new_source, after=after_playing)
                    return
                fut = asyncio.run_coroutine_threadsafe(
                    self._safe_play_next(ctx, guild_id), self.bot.loop
                )

            ctx.voice_client.play(source, after=after_playing)

        asyncio.create_task(_play())

    async def _safe_play_next(self, ctx, guild_id): # Short delay called between track start/stop
        await asyncio.sleep(1)
        self.play_next(ctx, guild_id)

    @commands.command()
    @commands.check(check_allowed_roles)
    async def play(self, ctx, *, filename: str):
        """Queue up audio from the audio folder if it's a valid audio file."""
        guild_id = ctx.guild.id
        print(f"[DEBUG] Play command received with filename: {filename!r}")
        file_path = self.resolve_audio_path(filename)

        valid_extensions = ('.mp3', '.wav', '.ogg', '.flac', '.m4a')
        if not filename.lower().endswith(valid_extensions):
            await ctx.send(f"`'{filename}' IS NOT A SUPPORTED AUDIO FILE.`")
            print(f"[DEBUG] Could not play {filename!r}; it's unsupported.")
            return

        if not os.path.exists(file_path):
            await ctx.send(f"`FILE '{filename}' DOES NOT EXIST.`")
            print(f"[DEBUG] Could not play {filename!r}; it does not exist.")
            return

        if not ctx.voice_client:
            if ctx.author.voice and ctx.author.voice.channel:
                print(f"[DEBUG] Beginning connection attempt...")
                await ctx.author.voice.channel.connect()
                await ctx.send(f"`JOINED {ctx.author.voice.channel.name}.`")
                print(f"[DEBUG] Connection attempt passed.")
            else:
                print(f"[DEBUG] Player not in voice channel; cancelling request.")
                await ctx.send("`YOU MUST BE IN A VOICE CHANNEL TO PLAY AUDIO.`")
                return

        print(f"[DEBUG] Queuing song...")
        queue = self.get_queue(guild_id)
        await queue.put(filename)
        self.queue_cache[guild_id].append(filename)
        await ctx.send(f"`QUEUED: '{filename}'.`")
        print(f"[DEBUG] Song queued.")

        if not ctx.voice_client.is_playing():
            print(f"[DEBUG] Nothing playing; starting newly queued song.")
            self.play_next(ctx, guild_id)


    @commands.command()
    @commands.check(check_allowed_roles)
    async def skip(self, ctx):
        """Skip the currently playing track."""
        guild_id = ctx.guild.id
        if not ctx.voice_client:
            await ctx.send("`NOT IN A VOICE CHANNEL.`")
            return

        if ctx.voice_client.is_playing():
            self.skip_requested[guild_id] = True
            ctx.voice_client.stop()

            await asyncio.sleep(1)

            queue = self.get_queue(guild_id)
            if queue.empty():
                await ctx.send("`REACHED END OF QUEUE. USE !play (file) TO CONTINUE PLAYBACK.`")
            else:
                await ctx.send("`SKIPPED TO NEXT TRACK.`")
        else:
            await ctx.send("`NO AUDIO TO SKIP.`")


    @commands.command()
    @commands.check(check_allowed_roles)
    async def stop(self, ctx):
        """Stop playing current audio and clear the queue."""
        guild_id = ctx.guild.id
        if ctx.voice_client:
            ctx.voice_client.stop()
            queue = self.get_queue(ctx.guild.id)
            self.queue_cache[guild_id].clear()
            self.looping[ctx.guild.id] = False
            while not queue.empty():
                queue.get_nowait()
            await ctx.send("`AUDIO STOPPED AND QUEUE CLEARED.`")
        else:
            await ctx.send("`NOT IN A VOICE CHANNEL.`")
    
    @commands.command()
    @commands.check(check_allowed_roles)
    async def clearqueue(self, ctx):
        """Clear the rest of the song queue."""
        guild_id = ctx.guild.id
        if ctx.voice_client:
            queue = self.get_queue(ctx.guild.id)
            self.queue_cache[guild_id].clear()
            if not queue.empty():
                while not queue.empty():
                    queue.get_nowait()
                await ctx.send("`QUEUE CLEARED.`")
            else:
                await ctx.send("`THERE ARE NO QUEUED SONGS TO CLEAR.`")
        else:
            await ctx.send("`NOT IN A VOICE CHANNEL.`")

    @commands.command()
    @commands.check(check_allowed_roles)
    async def loop(self, ctx):
        """Disable or enable track looping."""
        if self.looping.get(ctx.guild.id, False):
            self.looping[ctx.guild.id] = False
            await ctx.send("`LOOPING HAS BEEN DISABLED.`")
        else:
            self.looping[ctx.guild.id] = True
            await ctx.send("`LOOPING HAS BEEN ENABLED.`")

    @commands.command()
    @commands.check(check_allowed_roles)
    async def pause(self, ctx):
        """Pause the currently playing track."""
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.pause()
            await ctx.send("`AUDIO PAUSED.`")
        else:
            await ctx.send("`NO AUDIO TO PAUSE.`")

    @commands.command()
    @commands.check(check_allowed_roles)
    async def unpause(self, ctx):
        """Resume playing the currently paused track."""
        if ctx.voice_client and ctx.voice_client.is_paused():
            ctx.voice_client.resume()
            await ctx.send("`AUDIO RESUMED.`")
        else:
            await ctx.send("`AUDIO IS NOT PAUSED.`")

    @commands.command()
    async def queue(self, ctx):
        """View the current queue, as well as currently playing music and the loop status."""
        guild_id = ctx.guild.id
        current = self.current_track.get(guild_id)
        queue = self.queue_cache.get(guild_id, [])

        if not current and not queue:
            await ctx.send("`QUEUE IS CURRENTLY EMPTY.`")
            return
        
        message = ""

        if current:
            current_filename = os.path.basename(current)
            message += f"`NOW PLAYING --> {current_filename}`\n\n"
        
        if queue:
            message += "`PLAYING NEXT:`\n"
            for i, track in enumerate(queue, start=1):
                message += f"`{i}. {track}`\n"
        
        if self.looping.get(guild_id):
            message += "`LOOPING = ON`"
        else:
            message += "`LOOPING = OFF`"
        
        await ctx.send(message)

    @commands.command()
    @commands.check(check_allowed_roles)
    async def audio(self, ctx, opt_dir=None):
        """Displays available tracks in the current folder; use !audio (folder) to view a subfolder."""
        try:
            search_folder = os.path.join(self.audio_folder, opt_dir) if opt_dir else self.audio_folder
            audio_folder_real = os.path.realpath(self.audio_folder)
            search_folder_real = os.path.realpath(search_folder)

            if not os.path.isdir(search_folder):
                await ctx.send("`FOLDER NOT FOUND.`")
                return
            if not search_folder_real.startswith(audio_folder_real):
                await ctx.send("`INVALID FOLDER PATH.`")
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
                await ctx.send("`NO AUDIO FILES OR SUBFOLDERS IN THIS FOLDER.`")
                return

            page_size = 10
            pages = [all_entries[i:i+page_size] for i in range(0, len(all_entries), page_size)]
            total_pages = len(pages)
            current_page = 0

            def get_page_embed(page):
                lines = [f"{1 + page * page_size + i}. {name}" for i, name in enumerate(pages[page])]
                embed = discord.Embed(
                    title=f"Available audio *(page {page+1}/{total_pages})*",
                    description="\n".join(lines),
                    color=0x5865F2,
                )
                embed.set_footer(text="Use !audio (folder) to view a folder • !play (filename) to play • Arrow reactions to change pages" if total_pages > 1 else "Use !audio (folder) to view a folder • !play (filename) to play")
                return embed

            message = await ctx.send(embed=get_page_embed(current_page))

            if total_pages == 1:
                return
                
            await message.add_reaction("⬅️")
            await message.add_reaction("➡️")

            def check(reaction, user):
                return (
                    user == ctx.author and reaction.message.id == message.id and str(reaction.emoji) in ["⬅️", "➡️"]
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
            await ctx.send(f"`ERROR READING AUDIO FOLDER.`")
            print(f"[ERROR] Error reading audio folder in audio command: {e}")
                
async def setup(bot):
    await bot.add_cog(AudioCog(bot))
