import os
import asyncio
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv
from database import db

load_dotenv()

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.guilds = True

bot = commands.Bot(
    command_prefix="?",
    intents=intents,
    help_command=None,
    case_insensitive=True
)

PRESENCE_MESSAGES = [
    "› Play BIG Studios.",
    "› Dev: Supskevv!"
]

@tasks.loop(seconds=10)
async def rotate_presence():
    for msg in PRESENCE_MESSAGES:
        await bot.change_presence(
            activity=discord.Activity(type=discord.ActivityType.watching, name=msg)
        )
        await asyncio.sleep(10)

@tasks.loop(minutes=5)
async def check_tempbans():
    expired = await db.get_expired_tempbans()
    for entry in expired:
        guild = bot.get_guild(entry["guild_id"])
        if not guild:
            continue
        try:
            user = await bot.fetch_user(entry["user_id"])
            await guild.unban(user, reason="Temporary ban expired")
            await db.clear_tempban(entry["guild_id"], entry["user_id"])
        except (discord.NotFound, discord.Forbidden):
            await db.clear_tempban(entry["guild_id"], entry["user_id"])

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    await bot.tree.sync()
    if not rotate_presence.is_running():
        rotate_presence.start()
    if not check_tempbans.is_running():
        check_tempbans.start()

@bot.event
async def setup_hook():
    await db.connect()
    await bot.load_extension("welcome")
    await bot.load_extension("applications")
    await bot.load_extension("moderation")

@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You lack the required permissions.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Missing argument: `{error.param.name}`")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("❌ Invalid argument provided.")
    elif isinstance(error, commands.CommandNotFound):
        pass
    else:
        print(f"Error in {ctx.command}: {error}")
        await ctx.send("❌ An unexpected error occurred.")

async def main():
    token = os.getenv("TOKEN")
    if not token:
        raise ValueError("TOKEN environment variable is required")
    async with bot:
        await bot.start(token)

if __name__ == "__main__":
    asyncio.run(main())
