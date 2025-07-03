from core.exceptions import CustomErrorMessage
from google.genai.types import (
    Content,
    Part,
    GenerateContentConfig,
    HarmCategory,
    HarmBlockThreshold,
    Tool,
    ToolCodeExecution,
    FunctionDeclaration
)
import importlib
import logging

class ModelParams:
    def __init__(self):
        # Model provider thread
        self._model_provider_thread = "gemini"

        self._genai_params = {
            "candidate_count": 1,
            "max_output_tokens": 8192,
            "temperature": 0.7,
            "top_p": 0.95,
            "top_k": 40,
            "safety_settings": [
                {
                    "category": HarmCategory.HARM_CATEGORY_HARASSMENT,
                    "threshold": HarmBlockThreshold.BLOCK_ONLY_HIGH
                },
                {
                    "category": HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                    "threshold": HarmBlockThreshold.BLOCK_ONLY_HIGH
                },
                {
                    "category": HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                    "threshold": HarmBlockThreshold.BLOCK_ONLY_HIGH
                },
                {
                    "category": HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                    "threshold": HarmBlockThreshold.BLOCK_ONLY_HIGH
                }
            ]
        }

    # Methods
    async def _fetch_tool(self, db_conn) -> dict:
        _tool_selection_name = await db_conn.get_tool_config(guild_id=self._guild_id)

        try:
            if _tool_selection_name is None:
                _Tool = None
            else:
                _Tool = importlib.import_module(f"tools.{_tool_selection_name}").Tool(
                    method_send=self._discord_method_send,
                    discord_ctx=self._discord_ctx,
                    discord_bot=self._discord_bot
                )
        except ModuleNotFoundError as e:
            logging.error("I cannot import the tool because the module is not found: %s", e)
            raise CustomErrorMessage(
                "⚠️ The feature you've chosen is not available at the moment. "
                "Please choose another tool using `/feature` command or try again later."
            )

        if _Tool:
            if "gemini-2.0-flash-thinking" in self._model_name:
                await self._discord_method_send(
                    "> ⚠️ The Gemini 2.0 Flash Thinking doesn't support tools. "
                    "Please switch to another Gemini model to use it."
                )
                _tool_schema = None
            else:
                if _tool_selection_name == "code_execution":
                    _tool_schema = [Tool(code_execution=ToolCodeExecution())]
                else:
                    if isinstance(_Tool.tool_schema, list):
                        _tool_schema = [Tool(function_declarations=_Tool.tool_schema)]
                    else:
                        _tool_schema = [Tool(function_declarations=[_Tool.tool_schema])]
        else:
            _tool_schema = None

        return {
            "tool_schema": _tool_schema,
            "tool_human_name": _Tool.tool_human_name if _Tool else None,
            "tool_object": _Tool
        }