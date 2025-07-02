from os import environ
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv()  # .env読み込み

MONGODB_URI = environ.get("MONGODB_URI")  # 環境変数からURIを取得
mongo_client = AsyncIOMotorClient(MONGODB_URI)
db = mongo_client["sample_mflix"]  # ←ここは次項で確認
