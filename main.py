from discord.ext import bridge, commands
from google import genai
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
import threading
import motor.motor_asyncio

# discord version info
print("discord version:", discord.__version__)
print("discord module path:", discord.__file__)

# Intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# Change working directory to script's location
chdir(Path(__file__).parent.resolve())

# Load environment variables
dotenv.load_dotenv()

# Setup logging
logging.basicConfig(
    format='%(levelname)s %(asctime)s [%(filename)s:%(lineno)d - %(funcName)s()]: %(message)s',
    datefmt='%m/%d/%Y %I:%M:%S %p',
    level=logging.INFO
)

# Check for valid token
if "DISCORD_TOKEN" not in environ or not environ.get("DISCORD_TOKEN") or environ.get("DISCORD_TOKEN") == "INSERT_DISCORD_TOKEN":
    raise Exception("Please insert a valid Discord bot token")

# Bot class
class InitBot(bridge.Bot):
    def __init__(self, *args, **kwargs):
        self._lock_socket_instance(45769)
        super().__init__(*args, **kwargs)

        temp_dir = environ.get("TEMP_DIR", "temp")
        environ["TEMP_DIR"] = temp_dir
        temp_path = Path(temp_dir)
        temp_path.mkdir(exist_ok=True)
        for file in temp_path.iterdir():
            file.unlink()

        self._wavelink = None
        try:
            self._wavelink = importlib.import_module("wavelink")
        except ModuleNotFoundError as e:
            logging.warning("Playback support is disabled: %s", e)

        # ✅ 新SDK方式で初期化（api_keyは直接渡す）
        self._gemini_api_client = genai.GenerativeModel(
            model_name="gemini-pro",
            api_key=environ.get("GEMINI_API_KEY")
        )

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
        temp_path = Path(environ.get("TEMP_DIR", "temp"))
        if temp_path.exists():
            for file in temp_path.iterdir():
                await aiofiles.os.remove(file)
        self._socket.close()
        await super().close()

bot = InitBot(command_prefix=environ.get("BOT_PREFIX", "$"), intents=intents)

@bot.event
async def on_ready():
    mongo_uri = environ.get("MONGO_DB_URL")
    bot._db_conn = motor.motor_asyncio.AsyncIOMotorClient(mongo_uri)

    # MongoDB 接続確認
    try:
        await bot._db_conn.server_info()
        logging.info("✅ MongoDB connected successfully")
    except Exception as e:
        logging.error("❌ MongoDB connection failed: %s", e)

    # 必要なら History の初期化（あとで使う場合）
    from core.ai.history import History
    bot._history = History(bot=bot, db_conn=bot._db_conn)

    # この下に元々あった処理を続けて書く（wavelink処理など）
    await bot.change_presence(activity=discord.Game("Preparing the bot for its first use..."))

    if bot._wavelink is not None:
        await bot.change_presence(activity=discord.Game("Connecting to wavelink server..."))
        try:
            node = bot._wavelink.Node(
                identifier=environ.get("ENV_LAVALINK_IDENTIFIER", "main"),
                uri=environ.get("ENV_LAVALINK_URI", "http://127.0.0.1:2222"),
                password=environ.get("ENV_LAVALINK_PASS", "youshallnotpass"),
                retries=0
            )
            await bot._wavelink.Pool.connect(client=bot, nodes=[node])
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
        await message.channel.send(cleandoc(f"""
            Hello <@{message.author.id}>! I am **{bot.user.name}** ✨

            You can ask me questions, such as:
            - **@{bot.user.name}** How many R's in the word strawberry?
            - **/ask** `prompt:` Can you tell me a joke?
            - Hey **@{bot.user.name}**, can you give me quotes for today?

            If you have any questions, you can visit my [documentation or contact me here](https://zavocc.github.io)
        """))

# Load cogs from commands.yaml
try:
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
except Exception as e:
    logging.error("Failed to load commands.yaml: %s", e)

# Custom HelpCommand
class CustomHelp(commands.MinimalHelpCommand):
    def __init__(self):
        super().__init__()
        self.no_category = "Misc"

    def get_opening_note(self):
        command_name = self.invoked_with
        return cleandoc(f"""**{bot.user.name}** help

        Welcome! here are the prefix commands that you can use!
        Use `{self.context.clean_prefix}{command_name} [command]` for more info on a command.
        You can also use `{self.context.clean_prefix}{command_name} [category]` for more info on a category.""")

    async def send_pages(self):
        destination = self.get_destination()
        for page in self.paginator.pages:
            embed = discord.Embed(description=page, color=discord.Color.random())
            await destination.send(embed=embed)

bot.help_command = CustomHelp()

# Run bot
bot.run(environ.get('DISCORD_TOKEN'))

# Dummy port listener (for Render)
def dummy_server():
    s = socket.socket()
    s.bind(('0.0.0.0', 10000))
    s.listen(1)
    while True:
        conn, addr = s.accept()
        conn.close()

threading.Thread(target=dummy_server, daemon=True).start()