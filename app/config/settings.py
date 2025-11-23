# config/settings.py
import os
from dotenv import load_dotenv

# settings.py → config → app → spotify-backend
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ENV_PATH = os.path.join(BASE_DIR, ".env")

print("Loading env from:", ENV_PATH)

load_dotenv(ENV_PATH)

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")

if not CLIENT_ID or not CLIENT_SECRET or not REDIRECT_URI:
    print(".env 讀取失敗，請檢查變數名稱與格式")
else:
    print(".env 讀取成功")