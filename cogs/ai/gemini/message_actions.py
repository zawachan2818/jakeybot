from aimodels.gemini import Completions
from core.ai.assistants import Assistants
from discord.ext import commands
from os import environ
import discord
import logging

class GeminiAIApps(commands.Cog):
    def __init__(self, bot):
        self.bot: discord.Bot = bot
        self.author = environ.get("BOT_NAME", "Jakey Bot")

    ###############################################
    # Rephrase command
    ###############################################
    @commands.message_command(
        name="Rephrase this message",
        contexts={None},  # Pycord用: discord.InteractionContextType.guild → None
        integration_types={None},  # discord.IntegrationType.guild_install → None
    )
    async def rephrase(self, ctx, message: discord.Message):
        """Rephrase this message"""
        await ctx.response.defer(ephemeral=True)

        _prompt_feed = f"Rephrase this message with variety to choose from:\n{message.content}"
        for _mention in message.mentions:
            _prompt_feed = _prompt_feed.replace(f"<@{_mention.id}>", f"(mentions user: {_mention.display_name})")

        _completion = Completions(discord_ctx=ctx, discord_bot=self.bot)
        _system_prompt = await Assistants.set_assistant_type("message_rephraser_prompt", type=1)
        _answer = await _completion.completion(prompt=_prompt_feed, system_instruction=_system_prompt)

        _embed = discord.Embed(
            title="Rephrased Message",
            description=str(_answer)[:4096],
            color=discord.Color.random()
        )
        _embed.set_footer(text="Responses generated by AI may not give accurate results! Double check with facts!")
        _embed.add_field(name="Referenced messages:", value=message.jump_url, inline=False)
        await ctx.respond(embed=_embed)

    ###############################################
    # Continue Message command
    ###############################################
    @commands.message_command(
        name="Continue this message",
        contexts={None},
        integration_types={None},
    )
    async def continue_message(self, ctx, message: discord.Message):
        """Continue this message"""
        await ctx.response.defer(ephemeral=True)

        _prompt_feed = f"Continue writing this message:\n{message.content}"
        for _mention in message.mentions:
            _prompt_feed = _prompt_feed.replace(f"<@{_mention.id}>", f"(mentions user: {_mention.display_name})")

        _completion = Completions(discord_ctx=ctx, discord_bot=self.bot)
        _system_prompt = await Assistants.set_assistant_type("message_continuer_prompt", type=1)
        _answer = await _completion.completion(prompt=_prompt_feed, system_instruction=_system_prompt)

        _embed = discord.Embed(
            title="Continued Message",
            description=str(_answer)[:4096],
            color=discord.Color.random()
        )
        _embed.set_footer(text="Responses generated by AI may not give accurate results! Double check with facts!")
        _embed.add_field(name="Referenced messages:", value=message.jump_url, inline=False)
        await ctx.respond(embed=_embed)