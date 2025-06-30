from discord.ext import bridge, commands
import google.generativeai as genai
from inspect import cleandoc
from os import chdir, mkdir, environ
from pathlib import Path
import aiohttp
import aiofiles.os
import discord
import dotenv
import importlib
import logging
import re
import socket
import yaml

print("discord version:", discord.__version__)
print("discord module path:", discord.__file__)


intents = discord.Intents.default()
intents.message_content = True  # これがないとメッセージ系のイベントを受け取れない
bot = commands.Bot(command_prefix="!", intents=intents)


# Go to project root directory
chdir(Path(__file__).parent.resolve())

# Load environment variables
dotenv.load_dotenv()

# Logging
logging.basicConfig(format='%(levelname)s %(asctime)s [%(filename)s:%(lineno)d - %(funcName)s()]: %(message)s', 
                    datefmt='%m/%d/%Y %I:%M:%S %p', 
                    level=logging.INFO)

# Check if DISCORD_TOKEN is set
if "DISCORD_TOKEN" in environ and (environ.get("DISCORD_TOKEN") == "INSERT_DISCORD_TOKEN" or environ.get("DISCORD_TOKEN") is None or environ.get("DISCORD_TOKEN") == ""):
    raise Exception("Please insert a valid Discord bot token")

# Intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# Subclass this bot
class InitBot(bridge.Bot):
    def __init__(self, *args, **kwargs):
        self._lock_socket_instance(45769)
        super().__init__(*args, **kwargs)

        if environ.get("TEMP_DIR") is not None:
            if Path(environ.get("TEMP_DIR")).exists():
                for file in Path(environ.get("TEMP_DIR", "temp")).iterdir():
                    file.unlink()
            else:
                mkdir(environ.get("TEMP_DIR"))
        else:
            environ["TEMP_DIR"] = "temp"
            mkdir(environ.get("TEMP_DIR"))

        self._wavelink = None
        try:
            self._wavelink = importlib.import_module("wavelink")
        except ModuleNotFoundError as e:
            logging.warning("Playback support is disabled: %s", e)
            self._wavelink = None

        genai.configure(api_key=environ.get("GEMINI_API_KEY"))
        self._gemini_api_client = genai.GenerativeModel("gemini-pro")
        self._aiohttp_main_client_session = aiohttp.ClientSession(loop=self.loop)

    def _lock_socket_instance(self, port):
        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.bind(('localhost', port))
            logging.info("Socket bound to port %s", port)
        except socket.error as e:
            logging.error("Failed to bind socket port: %s, reason: %s", port, str(e))
            raise e

    async def close(self):
        await self._aiohttp_main_client_session.close()
        if Path(environ.get("TEMP_DIR", "temp")).exists():
            for file in Path(environ.get("TEMP_DIR", "temp")).iterdir():
                await aiofiles.os.remove(file)
        self._socket.close()
        await super().close()

bot = InitBot(command_prefix=environ.get("BOT_PREFIX", "$"), intents=intents)

@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.Game(f"Preparing the bot for it's first use..."))
    if bot._wavelink is not None:
        await bot.change_presence(activity=discord.Game(f"Connecting to wavelink server..."))
        try:
            ENV_LAVALINK_URI = environ.get("ENV_LAVALINK_URI") or "http://127.0.0.1:2222"
            ENV_LAVALINK_PASS = environ.get("ENV_LAVALINK_PASS") or "youshallnotpass"
            ENV_LAVALINK_IDENTIFIER = environ.get("ENV_LAVALINK_IDENTIFIER") or "main"

            node = bot._wavelink.Node(
                identifier=ENV_LAVALINK_IDENTIFIER,
                uri=ENV_LAVALINK_URI,
                password=ENV_LAVALINK_PASS,
                retries=0
            )

            await bot._wavelink.Pool.connect(
                client=bot,
                nodes=[node]
            )
        except Exception as e:
            logging.error("Failed to setup wavelink: %s... Disabling playback support", e)
            bot._wavelink = None

    await bot.change_presence(activity=discord.Game(f"/ask me anything or {bot.command_prefix}help"))
    logging.info("%s is ready and online!", bot.user)

@bot.event
async def on_message(message: discord.Message):
    await bot.process_commands(message)
    if message.author == bot.user:
       return

    if bot.user.mentioned_in(message) and not message.attachments and not re.sub(f"<@{bot.user.id}>", '', message.content).strip():
        await message.channel.send(
            cleandoc(f"""Hello <@{message.author.id}>! I am **{bot.user.name}** ✨
                    ...
                    You can ask me questions, such as:
                    - **@{bot.user.name}** How many R's in the word strawberry?  
                    - **/ask** `prompt:`Can you tell me a joke?  
                    - Hey **@{bot.user.name}** can you give me quotes for today?  

                    If you have any questions, you can visit my [documentation or contact me here](https://zavocc.github.io)"""))

with open('commands.yaml', 'r') as file:
    cog_commands = yaml.safe_load(file)
    for command in cog_commands:
        if "voice" in command and not bot._wavelink:
           logging.warning("Skipping %s... Playback support is disabled", command)
           continue
        try:
            bot.load_extension(f'cogs.{command}')
        except Exception as e:
            logging.error("cogs.%s failed to load, skipping... The following error of the cog: %s", command, e)
            continue

class CustomHelp(commands.MinimalHelpCommand):
    def __init__(self):
        super().__init__()
        self.no_category = "Misc"

    def get_opening_note(self):
        command_name = self.invoked_with
        return (
            cleandoc(f"""**{bot.user.name}** help

            Welcome! here are the prefix commands that you can use!
            
            Use `{self.context.clean_prefix}{command_name} [command]` for more info on a command.

            You can also use `{self.context.clean_prefix}{command_name} [category]` for more info on a category.""")
        )

    async def send_pages(self):
        destination = self.get_destination()
        for page in self.paginator.pages:
            embed = discord.Embed(description=page, color=discord.Color.random())
            await destination.send(embed=embed)

bot.help_command = CustomHelp()

# ✅ 環境変数 DISCORD_TOKEN を使うように変更済み！
bot.run(environ.get('DISCORD_TOKEN'))
