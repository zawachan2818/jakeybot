from core.ai.assistants import Assistants
from aimodels.gemini import Completions
from discord.ext import commands
from google.genai.types import Content, Part
from os import environ
import aiofiles
import datetime
import discord
import inspect
import logging
import json
import random

class GeminiAITools(commands.Cog):
    def __init__(self, bot):
        self.bot: discord.Bot = bot
        self.author = environ.get("BOT_NAME", "Jakey Bot")

    ###############################################
    # Summarize discord messages
    ###############################################
    @commands.slash_command(
        description="Summarize or catch up latest messages based on the current channel"
    )
    @discord.option(
        "before_date",
        description="Format mm/dd/yyyy - When to read messages before the particular date",
        default=None,
    )
    @discord.option(
        "after_date",
        description="Format mm/dd/yyyy - When to read messages after the particular date",
        default=None
    )
    @discord.option(
        "around_date",
        description="Format mm/dd/yyyy - When to read messages around the particular date",
        default=None
    )
    @discord.option(
        "max_references",
        description="How many references it should display - Max 10",
        min_value=1,
        max_value=10,
        default=5
    )
    @discord.option(
        "limit",
        description="Limit the number of messages to read (Max 100 recommended)",
        min_value=5,
        max_value=100,
        default=25
    )
    async def summarize(self, ctx: discord.ApplicationContext, before_date: str, after_date: str, around_date: str, max_references: int, limit: int):
        await ctx.response.defer(ephemeral=True)

        if ctx.channel.is_nsfw():
            await ctx.respond("❌ Sorry, I can't summarize messages in NSFW channels!")
            return

        # Parse dates
        def parse_date(val):
            return datetime.datetime.strptime(val, '%m/%d/%Y') if val else None

        before = parse_date(before_date)
        after = parse_date(after_date)
        around = parse_date(around_date)

        # Create prompt
        _prompt_feed = [
            Part(text=inspect.cleandoc(
                f"""Date today is {datetime.datetime.now().strftime('%m/%d/%Y')}
                OK, now generate summaries for me:"""
            ))
        ]

        # Collect messages
        _messages = ctx.channel.history(limit=limit, before=before, after=after, around=around)
        references = []

        async for x in _messages:
            if x.author.bot:
                continue
            references.append(x)
            _prompt_feed.append(Part(text=f"{x.author.display_name}: {x.content}"))

        if not references:
            await ctx.respond("❌ I couldn't find any messages to summarize.")
            return

        # Call Gemini
        _completion = Completions(discord_ctx=ctx, discord_bot=self.bot)
        _system_prompt = await Assistants.set_assistant_type("message_summarizer_prompt", type=1)
        _response = await _completion.completion(Content(parts=_prompt_feed), system_instruction=_system_prompt)

        # Create embed
        _embed = discord.Embed(
            title="Summary of recent messages",
            description=_response[:4096],
            color=discord.Color.random()
        )
        _embed.set_footer(text="Generated using AI, please verify the facts.")

        reference_text = "\n".join([f"[Jump]({x.jump_url})" for x in references[:max_references]])
        _embed.add_field(name="Referenced messages", value=reference_text, inline=False)

        await ctx.respond(embed=_embed)