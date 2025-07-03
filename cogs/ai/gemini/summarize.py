from core.ai.assistants import Assistants
from aimodels.gemini import Completions
from discord.ext import commands
from google.genai.types import Content, Part, GenerateContentConfig, HarmCategory, HarmBlockThreshold
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
        self.bot = bot
        self.author = environ.get("BOT_NAME", "Jakey Bot")

    ###############################################
    # Summarize discord messages
    ###############################################
    @commands.slash_command(
        contexts={discord.InteractionContextType.guild},
        integration_types={discord.IntegrationType.guild_install}
    )
    @discord.option(
        "before_date",
        description="Format mm/dd/yyyy - When to read messages before the particular date",
        default=None,
    )
    @discord.option(
        "after_date",
        description="Format mm/dd/yyyy - When to read messages before the particular date",
        default=None
    )
    @discord.option(
        "around_date",
        description="Format mm/dd/yyyy - When to read messages before the particular date",
        default=None
    )
    @discord.option(
        "max_references",
        description="Determines how many references it should display - Max 10.",
        min_value=1,
        max_value=10,
        default=5
    )
    @discord.option(
        "limit",
        description="Limit the number of messages to read - higher the limits can lead to irrelevant summary",
        min_value=5,
        max_value=100,
        default=25
    )
    async def summarize(self, ctx, before_date: str, after_date: str, around_date: str, max_references: int, limit: int):
        """Summarize or catch up latest messages based on the current channel"""
        await ctx.response.defer(ephemeral=True)
        
        # Do not allow message summarization if the channel is NSFW
        if ctx.channel.is_nsfw():
            await ctx.respond("❌ Sorry, I can't summarize messages in NSFW channels!")
            return

        # Parse the dates
        if before_date is not None:
            before_date = datetime.datetime.strptime(before_date, '%m/%d/%Y')
        if after_date is not None:
            after_date = datetime.datetime.strptime(after_date, '%m/%d/%Y')
        if around_date is not None:
            around_date = datetime.datetime.strptime(around_date, '%m/%d/%Y')

        # Prompt feed which contains the messages
        _prompt_feed = [
            Part(
                text = inspect.cleandoc(
                    f"""Date today is {datetime.datetime.now().strftime('%m/%d/%Y')}
                    OK, now generate summaries for me:"""
                )
            )
        ]

        _messages = ctx.channel.history(limit=limit, before=before_date, after=after_date, around=around_date)
        references = []

        async for x in _messages:
            # Check if the message is valid for summarization
            if x.author.bot:
                continue
            references.append(x)
            _prompt_feed.append(
                Part(
                    text = f"{x.author.display_name}: {x.content}"
                )
            )

        if len(references) == 0:
            await ctx.respond("❌ I couldn't find any messages to summarize.")
            return

        _completion = Completions(discord_ctx=ctx, discord_bot=self.bot)
        _system_prompt = await Assistants.set_assistant_type("message_summarizer_prompt", type=1)

        _response = await _completion.completion(Content(parts=_prompt_feed), system_instruction=_system_prompt)

        _embed = discord.Embed(
            title="Summary of recent messages",
            description=_response[:4096],
            color=discord.Color.random()
        )
        _embed.set_footer(text="Generated using AI, please verify the facts.")
        
        reference_text = "\n".join([f"[Jump]({x.jump_url})" for x in references[:max_references]])
        _embed.add_field(name="Referenced messages", value=reference_text, inline=False)
        await ctx.respond(embed=_embed)