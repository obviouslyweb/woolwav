"""Main bot file. Handles bot init, event handling, command loading, logging, etc."""

# Required imports
import discord
from discord.ext import commands
import logging
from dotenv import load_dotenv
import os

# Print Discord.py version and file load location for debug
print("Discord.py Version:", discord.__version__)
print("Loaded from:", discord.__file__)

# Load .env file, import token and allowed roles (if any)
load_dotenv()
token = os.getenv('DISCORD_TOKEN')
_allowed_roles_raw = (os.getenv("ALLOWED_ROLES") or "").strip()
bot_allowed_roles = [name.strip() for name in _allowed_roles_raw.split(",") if name.strip()] if _allowed_roles_raw else []

# Create log directory if it doesn't exist
script_dir = os.path.dirname(os.path.abspath(__file__))
log_dir = os.path.join(script_dir, "logs")
os.makedirs(log_dir, exist_ok=True)  # create if missing
log_path = os.path.join(log_dir, "discord.log")

# Set up logging
handler = logging.FileHandler(filename=log_path, encoding="utf-8", mode="w")

# Set up Discord.py intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# Define bots, command prefix
bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)
bot.allowed_roles = bot_allowed_roles

# On ready event
@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')

# Load cogs
@bot.event
async def setup_hook():
    await bot.load_extension("cogs.commands")
    await bot.load_extension("cogs.events")
    await bot.load_extension("cogs.audio")

# Run bot
bot.run(token, log_handler=handler, log_level=logging.DEBUG)
