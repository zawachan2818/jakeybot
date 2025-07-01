import discord
from discord.ext import commands
from discord import app_commands
from discord.app_commands import Choice
import google.generativeai as genai
from config.gemini import gemini_config
from config.emoji import LOADING_EMOJI
from util.gemini.infer import ask_gemini, create_content_from_string
from util.gemini.markdown_parser import parse_markdown
import time

genai.configure(api_key=gemini_config["api_key"])

class MessageActions(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="ask", description="Send a message to Gemini AI")
    @app_commands.choices(
        stream=[Choice(name="ON", value="True"), Choice(name="OFF", value="False")]
    )
    async def ask(
        self,
        interaction: discord.Interaction,
        question: str,
        stream: Choice[str],
    ):
        await interaction.response.defer(thinking=True)
        stream_bool = stream.value == "True"
        message = await interaction.original_response()

        content = create_content_from_string(question)

        start_time = time.time()

        try:
            if stream_bool:
                response_stream = await ask_gemini(content, stream=True)
                full_response = ""
                async for chunk in response_stream:
                    chunk_text = chunk.text
                    full_response += chunk_text
                    if full_response.strip():
                        await message.edit(content=parse_markdown(full_response))
                end_time = time.time()
            else:
                response = await ask_gemini(content)
                full_response = response.text
                await message.edit(content=parse_markdown(full_response))
                end_time = time.time()

        except Exception as e:
            await message.edit(content=f"❌ エラーが発生しました: {str(e)}")
            return

        await message.edit(
            content=f"{parse_markdown(full_response)}\n\n> ⏱️ 処理時間: {end_time - start_time:.2f}秒"
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author == self.bot.user:
            return

        if message.content.lower().startswith("gemini:"):
            prompt = message.content[len("gemini:"):].strip()
            content = create_content_from_string(prompt)
            response = await ask_gemini(content)
            await message.channel.send(parse_markdown(response.text))

async def setup(bot):
    await bot.add_cog(MessageActions(bot))