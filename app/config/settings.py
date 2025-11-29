import os
from dotenv import load_dotenv

# 優先讀取 Render / 環境變數
# 本機開發時才需要讀 .env
def load_env():
    # 如果 CLIENT_ID 之類的 key 已經存在，代表在 Render，不要再讀本機 .env
    if os.getenv("CLIENT_ID"):
        return
    
    # 只有本機才需要讀取 .env
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    env_path = os.path.join(base_dir, ".env")

    if os.path.exists(env_path):
        load_dotenv(env_path)

# 執行一次（本機才會真的作用）
load_env()

# 讀取設定值（Render 與本機一致）
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")

# === JWT ===
JWT_SECRET = os.getenv("JWT_SECRET")  # 不給預設，正式環境不允許預設
if not JWT_SECRET:
    JWT_SECRET = "PLEASE_SET_SECRET"  # 避免爆掉，但是會提醒你

# === Redis ===
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))