from .config import ModelParams
from core.ai.core import Utils
from core.exceptions import CustomErrorMessage
from google import genai
from google.genai.types import Content, Part, GenerateContentConfig, HarmCategory, HarmBlockThreshold
from google.api_core.exceptions import GoogleAPIError
from google.api_core import exceptions as errors
from os import environ
from pathlib import Path
import aiohttp
import aiofiles
import asyncio
import discord
import io
import logging
import typing
import random
import re

class Completions(ModelParams):
    def __init__(self, discord_ctx, discord_bot, guild_id = None, model_name = "gemini-2.0-flash-001"):
        super().__init__()

        # Discord context
        self._discord_ctx = discord_ctx

        # Check if the discord_ctx is either instance of discord.Message or discord.ApplicationContext
        if isinstance(discord_ctx, discord.Message):
            self._discord_method_send = self._discord_ctx.channel.send
        elif isinstance(discord_ctx, discord.ApplicationContext):
            self._discord_method_send = self._discord_ctx.send
        else:
            raise Exception("Invalid discord channel context provided")

        # Check if discord_bot whether if its a subclass of discord.Bot
        if not isinstance(discord_bot, discord.Bot):
            raise Exception("Invalid discord bot object provided")

        # Discord bot object lifecycle instance
        self._discord_bot: discord.Bot = discord_bot

        # Check if _gemini_api_client is in the self._discord_bot object
        if not hasattr(discord_bot, "_gemini_api_client"):
            raise Exception("Gemini API client for completions not initialized, please check the bot configuration")

        # Check if _aiohttp_main_client_session is in the self._discord_bot object
        if not hasattr(discord_bot, "_aiohttp_main_client_session"):
            raise Exception("aiohttp client session for get requests not initialized, please check the bot configuration")

        self._gemini_api_client: genai.Client = discord_bot._gemini_api_client
        self._aiohttp_main_client_session: aiohttp.ClientSession = discord_bot._aiohttp_main_client_session

        self._model_name = model_name
        self._guild_id = guild_id

    async def input_files(self, attachment: discord.Attachment):
        # Download the attachment
        _xfilename = f"{environ.get('TEMP_DIR')}/JAKEY.{random.randint(518301839, 6582482111)}.{attachment.filename}"

        # Sometimes mimetype has text/plain; charset=utf-8, we need to grab the first part
        _mimetype = attachment.content_type.split(";")[0]
        try:
            async with self._aiohttp_main_client_session.get(attachment.url, allow_redirects=True) as _xattachments:
                async with aiofiles.open(_xfilename, "wb") as filepath:
                    async for _chunk in _xattachments.content.iter_chunked(8192):
                        await filepath.write(_chunk)
        except aiohttp.ClientError as httperror:
            if Path(_xfilename).exists():
                await aiofiles.os.remove(_xfilename)
            raise httperror

        _msgstatus = None
        try:
            _filedata = await self._gemini_api_client.aio.files.upload(
                file=_xfilename,
                mime_type=_mimetype
            )

            while _filedata.state == "PROCESSING":
                if _msgstatus is None:
                    _msgstatus = await self._discord_method_send(f"⌚ Processing the file attachment, this may take longer than usual...")

                _filedata = await self._gemini_api_client.aio.files.get(name=_filedata.name)
                await asyncio.sleep(2.5)
        except Exception as e:
            raise e
        finally:
            if _msgstatus:
                await _msgstatus.delete()
            await aiofiles.os.remove(_xfilename)

        self._file_data = genai.Content(
            parts=[
                genai.Part.from_uri(
                    file_uri=_filedata.uri,
                    mime_type=_filedata.mime_type
                )
            ],
            role="user"
        ).model_dump(exclude_unset=True)

    ############################
    # Inferencing
    ############################
    # Completion
    async def completion(self, prompt: typing.Union[str, list, Content], tool: dict = None, system_instruction: str = None, return_text: bool = True):
        # Create response
        _response = await self._gemini_api_client.aio.models.generate_content(
            model=self._model_name,
            contents=prompt,
            config=genai.GenerateContentConfig(
                **self._genai_params,
                system_instruction=system_instruction or None,
                tools=tool
            )
        )

        if return_text:
            return _response.text
        else:
            return _response


    # Chat Completion
    async def chat_completion(self, prompt, db_conn, system_instruction: str = None):
        # Load history
        _chat_thread = await db_conn.load_history(guild_id=self._guild_id, model_provider=self._model_provider_thread)

        # Fetch tool
        _Tool = await self._fetch_tool(db_conn)

        if _chat_thread is None:
            _chat_thread = []

        # Attach file attachment if it exists
        if hasattr(self, "_file_data"): _chat_thread.append(self._file_data)

        # Parse prompts
        _chat_thread.append(
            Content(
    				parts=[Part.from_text(text=prompt)],
    				role="user"
			).model_dump(exclude_unset=True)
        )
    
        try:
            _response = await self.completion(prompt=_chat_thread, tool=_Tool["tool_schema"], system_instruction=system_instruction, return_text=False)
        # Check if we get ClientError and has PERMISSION_DENIED
        except errors.ClientError as e:
            logging.error("1st try: I think I found a problem related to the request... doing first fixes: %s", e.message)
            if "do not have permission" in e.message:
                # Curated history attribute are list of multipart chat turns under Content structured datatype
                # Inside, it has "part" -> List and "role" -> str fields, so we iterate on the parts
                for _chat_turns in _chat_thread:
                    for _part in _chat_turns["parts"]:
                        # Check if we have file_data key then we just set it as None and set the text to "Expired"
                        if _part.get("file_data"):
                            _part["file_data"] = None
                            _part["text"] = "⚠️ The file attachment expired and was removed."

                # Notify the user that the chat session has been re-initialized
                await self._discord_method_send("> ⚠️ One or more file attachments or tools have been expired, the chat history has been reinitialized!")

                # Retry the request
                _response = await self.completion(prompt=_chat_thread, tool=_Tool["tool_schema"], system_instruction=system_instruction, return_text=False)
            else:
                logging.error("2nd try: I think I found a problem related to the request: %s", e.message)
                raise e

        # Check if the response was blocked due to safety and other reasons than STOP
        # https://ai.google.dev/api/generate-content#FinishReason
        if _response.candidates[0].finish_reason == "SAFETY":
            raise CustomErrorMessage("🤬 I detected unsafe content in your prompt, Please rephrase your question.")
        elif _response.candidates[0].finish_reason == "MAX_TOKENS":
            raise CustomErrorMessage("⚠️ Response reached max tokens limit, please make your message concise.")
        elif _response.candidates[0].finish_reason != "STOP":
            raise CustomErrorMessage("⚠️ An error has occurred while giving you an answer, please try again later.")
    
        # Iterate through the parts and perform tasks
        _toolParts = []
        _toHalt = False
        _interstitial = None

        if _response.function_calls:
            _interstitial = await self._discord_method_send("▶️ Coming up with the plan...")

        for _part in _response.candidates[0].content.parts:
            if _part.text and _part.text.strip():
                await Utils.send_ai_response(self._discord_ctx, prompt, _part.text, self._discord_method_send)

            if _part.function_call:
                # Append the previous interaction to chat thread
                _chat_thread.append(_response.candidates[0].content.model_dump(exclude_unset=True))

                # Indicate the tool is called
                if not _interstitial:
                    _interstitial = await self._discord_method_send(f"✅ Tool started: **{_Tool['tool_human_name']}**")
                
                try:
                    # Edit the interstitial message
                    await _interstitial.edit(f"▶️ Executing tool: **{_part.function_call.name}**")

                    if hasattr(_Tool["tool_object"], "_tool_function"):
                        _toExec = getattr(_Tool["tool_object"], "_tool_function")
                    elif hasattr(_Tool["tool_object"], f"_tool_function_{_part.function_call.name}"):
                        _toExec = getattr(_Tool["tool_object"], f"_tool_function_{_part.function_call.name}")
                    else:
                        logging.error("I think I found a problem related to function calling or the tool function implementation is not available: %s")
                        raise CustomErrorMessage("⚠️ An error has occurred while calling tools, please try again later or choose another tool")

                    # Check if _toHalts is True, if it is, we just need to tell the model to try again later
                    # Since its not possible to just break the loop, it has to match the number of parts of toolInvoke
                    if _toHalt:
                        _toolResult = {
                            "error": f"⚠️ Error occurred previously which in order to prevent further issues, the operation was halted",
                            "tool_args": _part.function_call.args
                        }
                    else:
                        _toolResult = {
                            "toolResult": (await _toExec(**_part.function_call.args)),
                            "tool_args": _part.function_call.args
                        }
                # For other exceptions, log the error and add it as part of the chat thread
                except Exception as e:
                    _toHalt = True

                    # Also print the error to the console
                    logging.error("Something when calling specific tool lately, reason: %s", e)
                    _toolResult = {
                        "error": f"⚠️ Something went wrong while executing the tool: {e}\nTell the user about this error",
                        "tool_args": _part.function_call.args
                    }

                _toolParts.append(genai.Part.from_function_response(
                        name=_part.function_call.name,
                        response=_toolResult
                    )
                )

            # Function calling and code execution doesn't mix
            if _part.executable_code:
                await self._discord_method_send(f"✅ Code analysis complete")
                await self._discord_method_send(f"```py\n{_part.executable_code.code[:1975]}\n```")

            if _part.code_execution_result:
                if _part.code_execution_result.output:
                    # Send the code execution result
                    await self._discord_method_send(f"```{_part.code_execution_result.output[:1975]}```")

            # Render the code execution inline data when needed
            if _part.inline_data:
                if _part.inline_data.mime_type == "image/png":
                    await self._discord_method_send(file=discord.File(io.BytesIO(_part.inline_data.data), filename="image.png"))
                elif _part.inline_data.mime_type == "image/jpeg":
                    await self._discord_method_send(file=discord.File(io.BytesIO(_part.inline_data.data), filename="image.jpeg"))
                else:
                    await self._discord_method_send(file=discord.File(io.BytesIO(_part.inline_data.data), filename="code_exec_artifact.bin"))

        # Edit interstitial message
        if _toolParts and _interstitial:
            if _toHalt:
                await _interstitial.edit(f"⚠️ Error executing tool: **{_Tool['tool_human_name']}**")
            else:
                await _interstitial.edit(f"✅ Used: **{_Tool['tool_human_name']}**")

            # Append the tool parts to the chat thread
            _chat_thread.append(Content(parts=_toolParts).model_dump(exclude_unset=True))

            # Add function call parts to the response
            _response = await self.completion(prompt=_chat_thread, system_instruction=system_instruction, return_text=False)
            # Check if it has text part
            if _response.candidates[0].content.parts[0].text:
                await Utils.send_ai_response(self._discord_ctx, prompt, _response.candidates[0].content.parts[0].text, self._discord_method_send)

        # Append the final response to the chat thread
        _chat_thread.append(_response.candidates[0].content.model_dump(exclude_unset=True))

        # Return the status
        return {"response": "OK", "chat_thread": _chat_thread}

    async def save_to_history(self, db_conn, chat_thread = None):
        await db_conn.save_history(guild_id=self._guild_id, chat_thread=chat_thread, model_provider=self._model_provider_thread)
from .config import ModelParams
from core.ai.core import Utils
from core.exceptions import CustomErrorMessage
import google.generativeai as genai
from google.generativeai.types import Content, Part, GenerateContentConfig
from google.api_core import exceptions as errors

from os import environ
from pathlib import Path
import aiohttp
import aiofiles
import asyncio
import discord
import io
import logging
import typing
import random

class Completions(ModelParams):
    def __init__(self, discord_ctx, discord_bot, guild_id=None, model_name="gemini-1.5-flash"):
        super().__init__()
        self._discord_ctx = discord_ctx

        if isinstance(discord_ctx, discord.Message):
            self._discord_method_send = self._discord_ctx.channel.send
        elif isinstance(discord_ctx, discord.ApplicationContext):
            self._discord_method_send = self._discord_ctx.send
        else:
            raise Exception("Invalid discord context")

        if not isinstance(discord_bot, discord.Bot):
            raise Exception("Invalid discord bot object provided")

        if not hasattr(discord_bot, "_gemini_api_client"):
            raise Exception("Missing Gemini client")

        if not hasattr(discord_bot, "_aiohttp_main_client_session"):
            raise Exception("Missing aiohttp client")

        self._discord_bot: discord.Bot = discord_bot
        self._gemini_api_client: genai.Client = discord_bot._gemini_api_client
        self._aiohttp_main_client_session: aiohttp.ClientSession = discord_bot._aiohttp_main_client_session
        self._model_name = model_name
        self._guild_id = guild_id

    async def input_files(self, attachment: discord.Attachment):
        filename = f"{environ.get('TEMP_DIR')}/JAKEY.{random.randint(1000,9999999)}.{attachment.filename}"
        mime_type = attachment.content_type.split(";")[0]

        try:
            async with self._aiohttp_main_client_session.get(attachment.url) as response:
                async with aiofiles.open(filename, "wb") as f:
                    async for chunk in response.content.iter_chunked(8192):
                        await f.write(chunk)
        except Exception:
            if Path(filename).exists():
                await aiofiles.os.remove(filename)
            raise

        msg = None
        try:
            file_data = await self._gemini_api_client.aio.files.upload(file=filename, mime_type=mime_type)
            while file_data.state == "PROCESSING":
                if msg is None:
                    msg = await self._discord_method_send("⌚ ファイルを処理中です...")
                file_data = await self._gemini_api_client.aio.files.get(name=file_data.name)
                await asyncio.sleep(2.5)
        finally:
            if msg:
                await msg.delete()
            await aiofiles.os.remove(filename)

        self._file_data = Content(
            parts=[Part.from_uri(file_uri=file_data.uri, mime_type=file_data.mime_type)],
            role="user"
        ).model_dump(exclude_unset=True)

    async def completion(self, prompt: typing.Union[str, list, Content], tool: dict = None, system_instruction: str = None, return_text: bool = True):
        config = GenerateContentConfig(
            **self._genai_params,
            tools=tool,
            system_instruction=system_instruction or None
        )

        response = await self._gemini_api_client.aio.models.generate_content(
            model=self._model_name,
            contents=prompt,
            config=config
        )

        return response.text if return_text else response

    async def chat_completion(self, prompt, db_conn, system_instruction: str = None):
        history = await db_conn.load_history(guild_id=self._guild_id, model_provider=self._model_provider_thread) or []

        tool = await self._fetch_tool(db_conn)

        if hasattr(self, "_file_data"):
            history.append(self._file_data)

        history.append(
            Content(parts=[Part(text=prompt)], role="user").model_dump(exclude_unset=True)
        )

        try:
            response = await self.completion(prompt=history, tool=tool["tool_schema"], system_instruction=system_instruction, return_text=False)
        except errors.ClientError as e:
            if "do not have permission" in str(e):
                for turn in history:
                    for part in turn["parts"]:
                        if part.get("file_data"):
                            part["file_data"] = None
                            part["text"] = "⚠️ 添付ファイルの期限が切れました"
                await self._discord_method_send("⚠️ 添付ファイルが無効化されたため履歴を初期化しました")
                response = await self.completion(prompt=history, tool=tool["tool_schema"], system_instruction=system_instruction, return_text=False)
            else:
                raise

        candidate = response.candidates[0]

        if candidate.finish_reason == "SAFETY":
            raise CustomErrorMessage("🚫 不適切な内容が検出されました")
        elif candidate.finish_reason == "MAX_TOKENS":
            raise CustomErrorMessage("⚠️ レスポンスが長すぎます")
        elif candidate.finish_reason != "STOP":
            raise CustomErrorMessage("⚠️ 回答中にエラーが発生しました")

        for part in candidate.content.parts:
            if part.text:
                await Utils.send_ai_response(self._discord_ctx, prompt, part.text, self._discord_method_send)

        history.append(candidate.content.model_dump(exclude_unset=True))
        return {"response": "OK", "chat_thread": history}

    async def save_to_history(self, db_conn, chat_thread=None):
        await db_conn.save_history(guild_id=self._guild_id, chat_thread=chat_thread, model_provider=self._model_provider_thread)