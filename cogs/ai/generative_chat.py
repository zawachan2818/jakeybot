from core.ai.assistants import Assistants
from core.ai.core import ModelsList
from core.exceptions import *
from core.ai.history import History as typehint_History
from discord import Message
from os import environ
from google import genai
from google.genai.types import Content, Part, GenerateContentConfig
import discord
import inspect
import logging
import re

class BaseChat():
    def __init__(self, bot, author, history: typehint_History):
        self.bot: discord.Bot = bot
        self.author = author
        self.DBConn = history
        self.pending_ids = []

    async def _ask(self, prompt: Message):
        if environ.get("SHARED_CHAT_HISTORY", "false").lower() == "true":
            guild_id = prompt.guild.id if prompt.guild else prompt.author.id
        else:
            guild_id = prompt.author.id

        _model = await self.DBConn.get_default_model(guild_id=guild_id)
        if _model is None:
            logging.info("No default model found, using default model")
            _model = "gemini::gemini-1.5-flash"

        _model_provider, _model_name = _model.split("::")

        if "/model:" in prompt.content:
            _modelUsed = await prompt.channel.send(f"🔍 Using specific model")
            async for _model_selection in ModelsList.get_models_list_async():
                prov, name = _model_selection.split("::")
                if re.search(rf"/model:{name}(\s|$)", prompt.content):
                    _model_provider, _model_name = prov, name
                    await _modelUsed.edit(content=f"🔍 Using model: **{_model_name}**")
                    break
            else:
                await _modelUsed.edit(content=f"🔍 Using model: **{_model_name}**")

        _append_history = "/chat:ephemeral" not in prompt.content
        _show_info = "/chat:info" in prompt.content
        if not _append_history:
            await prompt.channel.send("🔒 This conversation is not saved and Jakey won't remember this")

        if _model_provider != "gemini":
            raise CustomErrorMessage(f"❌ Only Gemini provider is supported in this chat")

        if prompt.attachments:
            await prompt.reply("🚫 File attachments are not supported in Gemini chat at this time.")
            return

        _final_prompt = re.sub(
            rf"(<@{self.bot.user.id}>(\s|$)|/model:{_model_name}(\s|$)|/chat:ephemeral(\s|$)|/chat:info(\s|$))",
            "", prompt.content).strip()
        _system_prompt = await Assistants.set_assistant_type("jakey_system_prompt", type=0)

        client = genai.AsyncClient(api_key=environ["GOOGLE_API_KEY"])
        config = GenerateContentConfig(
            temperature=0.7,
            top_p=1.0
        )
        request_content = Content(parts=[Part(text=_final_prompt)])
        async with prompt.channel.typing():
            result = await client.models.generate_content(
                model=_model_name,
                contents=request_content,
                config=config
            )

        if not result.candidates:
            await prompt.channel.send("⚠️ No response received from Gemini API.")
            return

        message_text = result.candidates[0].content.parts[0].text
        await prompt.channel.send(message_text[:2000])

        if _append_history and hasattr(self.DBConn, "append_to_history"):
            await self.DBConn.append_to_history(guild_id=guild_id, prompt=_final_prompt, response=message_text)

    async def on_message(self, message: Message):
        if message.author.id == self.bot.user.id:
            return

        if message.guild is None or self.bot.user.mentioned_in(message):
            if message.content.startswith(self.bot.command_prefix) or message.content.startswith("/"):
                if message.content.startswith(self.bot.command_prefix):
                    _command = message.content.split(" ")[0].replace(self.bot.command_prefix, "")
                    if self.bot.get_command(_command):
                        return

            if message.author.id in self.pending_ids:
                await message.reply("⚠️ I'm still processing your previous request, please wait for a moment...")
                return

            if not message.attachments and not re.sub(f"<@{self.bot.user.id}>", '', message.content).strip():
                return

            message.content = re.sub(f"<@{self.bot.user.id}>", '', message.content).strip()

            if message.attachments:
                message.content = inspect.cleandoc(
                    f"""<extra_metadata>
                    Related Attachment URL: {message.attachments[0].url}
                    </extra_metadata>

                    {message.content}"""
                )

            if message.reference:
                _context_message = await message.channel.fetch_message(message.reference.message_id)
                message.content = inspect.cleandoc(
                    f"""<reply_metadata>
                    # Replying to referenced message excerpt from {_context_message.author.display_name} (username: @{_context_message.author.name}):
                    <|begin_msg_contexts|>
                    {_context_message.content}
                    <|end_msg_contexts|>
                    </reply_metadata>
                    {message.content}"""
                )
                await message.channel.send(f"✅ Referenced message: {_context_message.jump_url}")

            try:
                self.pending_ids.append(message.author.id)
                await message.add_reaction("⌛")
                await self._ask(message)
            except Exception as e:
                await message.reply(f"🚫 Sorry, I couldn't answer your question at the moment. Error: **{type(e).__name__}**")
                logging.error("Error in message processing", exc_info=True)
            finally:
                await message.remove_reaction("⌛", self.bot.user)
                self.pending_ids.remove(message.author.id)
