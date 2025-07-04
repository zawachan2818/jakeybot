from discord.commands import SlashCommandGroup
from discord.ext import commands
import asyncio
import discord
import logging
import wavelink

voice = SlashCommandGroup("voice", "Access voice features!")

class Voice(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.current_user = {}
        self.enqueued_tracks = {}
        self.pendings = {}

    @voice.command()
    @discord.option("search", description="Search for a query or a YouTube URL to play", required=True)
    async def play(self, ctx, search: str):
        await ctx.respond(f"🔍 Searching for: {search} (dummy response)")  # テスト用

    async def cog_command_error(self, ctx: commands.Context, error: commands.CommandError):
        _error = getattr(error, "original", error)
        await ctx.respond("❌ An error has occurred.")
        logging.error("Voice command error:", exc_info=True)

async def setup(bot):
    await bot.add_cog(Voice(bot))