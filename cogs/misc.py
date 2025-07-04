from discord.ext import commands
from discord import Member, DiscordException
from os import environ
import discord
import logging

class Misc(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.author = environ.get("BOT_NAME", "Jakey Bot")

    @commands.slash_command()
    async def mimic(self, ctx, user: Member, message_body: str):
        await ctx.response.defer(ephemeral=True)

        avatar_url = user.avatar.url if user.avatar else "https://cdn.discordapp.com/embed/avatars/0.png"
        user_name = user.display_name

        webhook = await ctx.channel.create_webhook(name=f"Mimic command by {self.author}")

        if not message_body:
            await ctx.respond("⚠️ Please specify a message to mimic!")
            return

        await webhook.send(content=message_body, username=user_name, avatar_url=avatar_url)
        await webhook.delete()
        await ctx.respond("✅ Done!")

    @mimic.error
    async def on_command_error(self, ctx: commands.Context, error: DiscordException):
        if isinstance(error, commands.MissingRequiredArgument) or isinstance(error, commands.BadUnionArgument):
            await ctx.respond("⚠️ Specify a valid user and message!")
        else:
            logging.error("Error in /mimic", exc_info=True)

async def setup(bot):
    await bot.add_cog(Misc(bot))