from discord.commands import SlashCommandGroup
from discord.ext import commands
import asyncio
import discord
import logging
import typing
import wavelink

voice = SlashCommandGroup("voice", "Access voice features!")  # ✅ クラス外へ移動（インデント修正）

class Voice(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.current_user = {}
        self.enqueued_tracks = {}
        self.pendings = {}

    # ↓ すべての @voice.command はここから下に続く（元のままでOK）
    # 例:
    @voice.command()
    @discord.option("search", description="Search for a query or a YouTube URL to play", required=True)
    async def play(self, ctx, search: str):
        # （略）元のままでOK

    # 他のコマンド（status, skip, ping など）もそのままでOK


    async def cog_command_error(self, ctx: commands.Context, error: commands.CommandError):
        _error = getattr(error, "original", error)
        if isinstance(_error, commands.NoPrivateMessage):
            await ctx.respond("❌ Sorry, this feature is not supported in DMs. Please use this command inside the guild.")
        elif isinstance(_error, commands.MissingPermissions):
            await ctx.respond(f"❌ You are missing the required permissions to use this command. Needed permissions:\n```{_error}```")
        elif isinstance(_error, wavelink.InvalidNodeException):
            await ctx.respond("No nodes are currently active right now, please try again later.")
        else:
            await ctx.respond(f"❌ An error has occurred! Please try again later.")
        logging.error("An error has occurred when using the voice command features, reason: ", exc_info=True)


# ✅ setup は async def に変更 + await
async def setup(bot):
    await bot.add_cog(Voice(bot))