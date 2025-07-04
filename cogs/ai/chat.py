from core.ai.core import ModelsList
from cogs.ai.generative_chat import BaseChat
from core.ai.history import History
from core.exceptions import *
from discord.commands import SlashCommandGroup
from discord.ext import commands
from os import environ
import discord
import inspect
import logging
import motor.motor_asyncio

class Chat(commands.Cog):
    def __init__(self, bot):
        self.bot: discord.Bot = bot
        self.author = environ.get("BOT_NAME", "Jakey Bot")

        try:
            self.DBConn: History = History(
                bot=bot,
                db_conn=motor.motor_asyncio.AsyncIOMotorClient(environ.get("MONGO_DB_URL"))
            )
        except Exception as e:
            raise RuntimeError(f"Failed to connect to MongoDB: {e}\n\nPlease set MONGO_DB_URL in dev.env")

        self._ask_event = BaseChat(bot, self.author, self.DBConn)

    async def _check_awaiting_response_in_progress(self, guild_id: int):
        if guild_id in self._ask_event.pending_ids:
            raise ConcurrentRequestError

    @commands.Cog.listener()
    async def on_message(self, message):
        await self._ask_event.on_message(message)

    model = SlashCommandGroup(name="model", description="Configure default models for the conversation")

    @model.command()
    @discord.option("model", description="Choose default model for the conversation", choices=ModelsList.get_models_list(), required=True)
    async def set(self, ctx, model: str):
        await ctx.response.defer(ephemeral=True)

        guild_id = ctx.guild.id if environ.get("SHARED_CHAT_HISTORY", "false").lower() == "true" and ctx.guild else ctx.author.id
        await self._check_awaiting_response_in_progress(guild_id)
        await self.DBConn.set_default_model(guild_id=guild_id, model=model)

        if "::" not in model:
            await ctx.respond("❌ Invalid model name, please choose a model from the list")
            return

        _model_provider, _model_name = model.split("::")[0], model.split("::")[-1]

        if _model_provider != "gemini":
            await ctx.respond(f"> This model lacks real time information and tools\n✅ Default model set to **{_model_name}** and chat history is set for provider **{_model_provider}**")
        else:
            await ctx.respond(f"✅ Default model set to **{_model_name}** and chat history is set for provider **{_model_provider}**")

    @set.error
    async def set_on_error(self, ctx: discord.ApplicationContext, error):
        _error = getattr(error, "original", error)
        if isinstance(_error, ConcurrentRequestError):
            await ctx.respond("⚠️ Please wait until processing your previous request is completed before changing the model...")
        else:
            await ctx.respond("❌ Something went wrong, please try again later.")
        logging.error("An error has occurred while executing models command", exc_info=True)

    @model.command()
    async def list(self, ctx):
        await ctx.response.defer(ephemeral=True)

        _embed = discord.Embed(
            title="Available models",
            description=inspect.cleandoc(f"""Here are the list of available models that you can use

You can set the default model for the conversation using `/model set` command or on demand through chat prompting
via `@{self.bot.user.name} /model:model-name` command.

Each provider has its own chat history, skills, and capabilities. Choose what's best for you."""),
            color=discord.Color.random()
        )

        _model_provider_tabledict = {}
        async for _model in ModelsList.get_models_list_async():
            _provider, _name = _model.split("::")[0], _model.split("::")[-1]
            _model_provider_tabledict.setdefault(_provider, []).append(_name)

        for provider, models in _model_provider_tabledict.items():
            _embed.add_field(name=provider, value=", ".join(models), inline=False)

        await ctx.respond(embed=_embed)

    @list.error
    async def list_on_error(self, ctx: discord.ApplicationContext, error):
        await ctx.respond("❌ Something went wrong, please try again later.")
        logging.error("An error has occurred while executing models command", exc_info=True)

    @commands.slash_command()
    @discord.option("model", description="Choose models at https://openrouter.ai/models", required=True)
    async def openrouter(self, ctx, model: str):
        await ctx.response.defer(ephemeral=True)
        guild_id = ctx.guild.id if environ.get("SHARED_CHAT_HISTORY", "false").lower() == "true" and ctx.guild else ctx.author.id
        await self._check_awaiting_response_in_progress(guild_id)

        await self.DBConn.set_key(guild_id=guild_id, key="default_openrouter_model", value=model)
        await self.DBConn.set_key(guild_id=guild_id, key="chat_thread_openrouter", value=None)

        await ctx.respond(f"✅ Default OpenRouter model set to **{model}** and chat history for OpenRouter chats are cleared!\nTo use this model, please set the model to OpenRouter using `/model set` command")

    @openrouter.error
    async def openrouter_on_error(self, ctx: discord.ApplicationContext, error):
        _error = getattr(error, "original", error)
        if isinstance(_error, ConcurrentRequestError):
            await ctx.respond("⚠️ Please wait until processing your previous request is completed before changing the OpenRouter model...")
        else:
            await ctx.respond("❌ Something went wrong, please try again later.")
        logging.error("An error has occurred while setting openrouter models", exc_info=True)

    @commands.slash_command()
    @discord.option("reset_prefs", description="Clear context history including default model and settings")
    async def sweep(self, ctx, reset_prefs: bool = False):
        await ctx.response.defer(ephemeral=True)
        guild_id = ctx.guild.id if environ.get("SHARED_CHAT_HISTORY", "false").lower() == "true" and ctx.guild else ctx.author.id
        await self._check_awaiting_response_in_progress(guild_id)

        if ctx.guild and not ctx.interaction.authorizing_integration_owners.guild:
            await ctx.respond("🚫 This command can only be used in DMs or authorized guilds!")
            return

        _feature = await self.DBConn.get_tool_config(guild_id=guild_id)
        _model = await self.DBConn.get_default_model(guild_id=guild_id)
        _openrouter_model = await self.DBConn.get_key(guild_id=guild_id, key="default_openrouter_model")
        await self.DBConn.clear_history(guild_id=guild_id)

        if not reset_prefs:
            await self.DBConn.set_tool_config(guild_id=guild_id, tool=_feature)
            await self.DBConn.set_default_model(guild_id=guild_id, model=_model)
            await self.DBConn.set_key(guild_id=guild_id, key="default_openrouter_model", value=_openrouter_model)
            await ctx.respond("✅ Chat history reset!")
        else:
            await ctx.respond("✅ Chat history reset, model and feature settings are cleared!")

    @sweep.error
    async def sweep_on_error(self, ctx: discord.ApplicationContext, error: discord.DiscordException):
        _error = getattr(error, "original", error)
        if isinstance(_error, ConcurrentRequestError):
            await ctx.respond("⚠️ Please wait until processing your previous request is completed before clearing the chat history...")
        else:
            await ctx.respond("❌ Something went wrong, please try again later.")
            logging.error("An error has occurred while executing sweep command", exc_info=True)

    @commands.slash_command()
    @discord.option("capability", description="Integrate tools to chat", choices=ModelsList.get_tools_list())
    async def feature(self, ctx, capability: str):
        await ctx.response.defer(ephemeral=True)
        guild_id = ctx.guild.id if environ.get("SHARED_CHAT_HISTORY", "false").lower() == "true" and ctx.guild else ctx.author.id
        await self._check_awaiting_response_in_progress(guild_id)

        if ctx.guild and not ctx.interaction.authorizing_integration_owners.guild:
            await ctx.respond("🚫 This command can only be used in DMs or authorized guilds!")
            return

        _cur_feature = await self.DBConn.get_tool_config(guild_id=guild_id)
        _model = await self.DBConn.get_default_model(guild_id=guild_id)

        if capability == "disabled":
            capability = None

        if _cur_feature == capability:
            await ctx.respond("✅ Feature already set!")
        else:
            if _cur_feature:
                await self.DBConn.clear_history(guild_id=guild_id)
            await self.DBConn.set_tool_config(guild_id=guild_id, tool=capability)
            await self.DBConn.set_default_model(guild_id=guild_id, model=_model)

            if capability is None:
                await ctx.respond("✅ Features disabled and chat is reset to reflect the changes")
            else:
                await ctx.respond(f"✅ Feature **{capability}** enabled successfully and chat is reset to reflect the changes")

    @feature.error
    async def feature_on_error(self, ctx: discord.ApplicationContext, error: discord.DiscordException):
        _error = getattr(error, "original", error)
        if isinstance(_error, ConcurrentRequestError):
            await ctx.respond("⚠️ Please wait until processing your previous request is completed before changing agents...")
        else:
            await ctx.respond("❌ Something went wrong, please try again later.")
        logging.error("An error has occurred while executing feature command", exc_info=True)


# ✅ 非同期 setup 関数（修正ポイント）
async def setup(bot):
    await bot.add_cog(Chat(bot))