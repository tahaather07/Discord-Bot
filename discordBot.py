# Bot configuration
TOKEN = 'MTI5MzE3ODYzMTc5OTA0NjE0NA.G_bmIO.hDno3ZkydVF96Mdl-CQd7LDwB4Dv00ztAyplJA'
SPOTIFY_CLIENT_ID = '5eb759f5d962404c83a04cee3ed54d39'
SPOTIFY_CLIENT_SECRET = '6399304e4c674cd084181aef15f9b16c'
import discord
from discord.ext import commands
import yt_dlp
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import asyncio
from async_timeout import timeout
from collections import deque


# Set up Spotify client
sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
    client_id=SPOTIFY_CLIENT_ID,
    client_secret=SPOTIFY_CLIENT_SECRET
))

# YouTube DL options
YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'extractaudio': True,
    'audioformat': 'mp3',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
}

# FFmpeg options
FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -re',
    'options': '-vn'
}

# Initialize the YouTube DL client
ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
        
        if 'entries' in data:
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **FFMPEG_OPTIONS), data=data)

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queue = {}
        self.current_song = {}
        self.play_next_song = {}

    async def audio_player_task(self, ctx):
        while True:
            try:
                async with timeout(300):  # 5 minutes
                    source = await self.queue[ctx.guild.id].get()
            except asyncio.TimeoutError:
                return self.destroy(ctx)

            if not isinstance(source, YTDLSource):
                try:
                    source = await YTDLSource.from_url(source, loop=self.bot.loop, stream=True)
                except Exception as e:
                    await ctx.send(f'There was an error processing your song.\n'
                                   f'```css\n[{e}]\n```')
                    continue

            ctx.voice_client.play(source, after=lambda _: self.bot.loop.call_soon_threadsafe(self.play_next_song[ctx.guild.id].set))
            self.current_song[ctx.guild.id] = source
            await ctx.send(f'Now playing: {source.title}')
            await self.play_next_song[ctx.guild.id].wait()

    def destroy(self, ctx):
        return self.bot.loop.create_task(self.cleanup(ctx))

    async def cleanup(self, ctx):
        try:
            await ctx.voice_client.disconnect()
        except AttributeError:
            pass

        try:
            del self.play_next_song[ctx.guild.id]
        except KeyError:
            pass

        try:
            del self.queue[ctx.guild.id]
        except KeyError:
            pass

        try:
            del self.current_song[ctx.guild.id]
        except KeyError:
            pass

    @commands.command(name='join')
    async def join(self, ctx):
        if ctx.author.voice is None:
            await ctx.send("You're not connected to a voice channel.")
            return

        channel = ctx.author.voice.channel
        if ctx.voice_client is None:
            await channel.connect()
        else:
            await ctx.voice_client.move_to(channel)

    @commands.command(name='play')
    async def play(self, ctx, *, url):
        if ctx.voice_client is None:
            if ctx.author.voice:
                await ctx.author.voice.channel.connect()
            else:
                await ctx.send("You're not connected to a voice channel.")
                return

        if ctx.guild.id not in self.queue:
            self.queue[ctx.guild.id] = asyncio.Queue()
            self.play_next_song[ctx.guild.id] = asyncio.Event()
            self.bot.loop.create_task(self.audio_player_task(ctx))

        if 'spotify' in url:
            if 'playlist' in url:
                await ctx.send(f"Now processing playlist")
                playlist_id = url.split('/')[-1].split('?')[0]
                results = sp.playlist_tracks(playlist_id)
                tracks = results['items']
                
                for track in tracks:
                    track_name = track['track']['name']
                    artist_name = track['track']['artists'][0]['name']
                    search_query = f"{track_name} {artist_name}"
                    await self.queue[ctx.guild.id].put(search_query)
                
                await ctx.send(f"Added {len(tracks)} songs from Spotify playlist to the queue.")
            else:
                track_id = url.split('/')[-1].split('?')[0]
                track = sp.track(track_id)
                search_query = f"{track['name']} {track['artists'][0]['name']}"
                await self.queue[ctx.guild.id].put(search_query)
                await ctx.send(f"Added to queue: {track['name']}")
        else:
            await self.queue[ctx.guild.id].put(url)
            await ctx.send(f"Added to queue: {url}")

    @commands.command(name='skip')
    async def skip(self, ctx):
        if ctx.voice_client is None:
            await ctx.send("I'm not connected to a voice channel.")
            return

        if not ctx.voice_client.is_playing():
            await ctx.send("Nothing is playing right now.")
            return

        ctx.voice_client.stop()
        await ctx.send("Skipped the current song.")

    @commands.command(name='queue')
    async def show_queue(self, ctx):
        if ctx.guild.id not in self.queue or len(self.queue[ctx.guild.id]) == 0:
            await ctx.send("The queue is empty.")
            return

        queue_list = [f"{i+1}. {song.title}" for i, song in enumerate(self.queue[ctx.guild.id])]
        queue_text = "\n".join(queue_list)
        await ctx.send(f"Current queue:\n{queue_text}")

    @commands.command(name='leave')
    async def leave(self, ctx):
        if ctx.voice_client is not None:
            await ctx.voice_client.disconnect()
            if ctx.guild.id in self.queue:
                self.queue[ctx.guild.id].clear()
            if ctx.guild.id in self.current_song:
                del self.current_song[ctx.guild.id]

    @commands.command(name='pause')
    async def pause(self, ctx):
        if ctx.voice_client is None:
            await ctx.send("I'm not connected to a voice channel.")
            return

        if ctx.voice_client.is_playing():
            ctx.voice_client.pause()
            await ctx.send("Playback paused.")
        else:
            await ctx.send("Nothing is playing right now.")

    @commands.command(name='resume')
    async def resume(self, ctx):
        if ctx.voice_client is None:
            await ctx.send("I'm not connected to a voice channel.")
            return

        if ctx.voice_client.is_paused():
            ctx.voice_client.resume()
            await ctx.send("Playback resumed.")
        else:
            await ctx.send("The audio is not paused.")

bot = commands.Bot(command_prefix='!', intents=discord.Intents.all())

@bot.event
async def on_ready():
    print(f'Bot is ready. Logged in as {bot.user}')
    await bot.add_cog(Music(bot))

bot.run(TOKEN)
