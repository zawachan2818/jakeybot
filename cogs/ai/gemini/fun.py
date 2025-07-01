from core.ai.assistants import Assistants
from core.ai.core import ModelsList
from aimodels.gemini import Completions
from core.exceptions import CustomErrorMessage, PollOffTopicRefusal
from discord.ext import commands
from discord import Member, ApplicationContext
import discord
import inspect
import io
import json
import logging
from os import environ

class GeminiUtils(commands.Cog):
    """Gemini powered utilities"""
    def __init__(self, bot):
        self.bot = bot
        self.author = environ.get("BOT_NAME", "Jakey Bot")

    ###############################################
    # Avatar tools
    ###############################################
    avatar = discord.SlashCommandGroup(
        name="avatar",
        description="Avatar tools"
    )

    @avatar.command(name="describe")
    async def describe_avatar(self, ctx: ApplicationContext, member: Member = None):
        await ctx.defer()

        member = member or ctx.author
        avatar_url = member.display_avatar.replace(size=1024).url

        prompt = f"Describe the user's avatar at this URL: {avatar_url}"

        try:
            result = await Completions.text(prompt)
            await ctx.respond(result, ephemeral=True)
        except PollOffTopicRefusal as refusal:
            await ctx.respond(str(refusal), ephemeral=True)
        except CustomErrorMessage as err:
            await ctx.respond(str(err), ephemeral=True)
        except Exception as e:
            logging.exception("Error in describe_avatar")
            await ctx.respond("Something went wrong.", ephemeral=True)