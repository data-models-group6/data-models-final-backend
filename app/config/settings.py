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

# === JWT ===
JWT_SECRET = os.getenv("JWT_SECRET", "CHANGEME")  # 給預設但正式版要改

# === Redis ===
REDIS_HOST = os.getenv("REDIS_HOST")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

print("CLIENT_ID Loaded:", CLIENT_ID is not None)
print("REDIRECT_URI Loaded:", REDIRECT_URI is not None)
print("JWT_SECRET Loaded:", JWT_SECRET is not None)
print("REDIS_HOST Loaded:", REDIS_HOST)
print("REDIS_PORT Loaded:", REDIS_PORT)