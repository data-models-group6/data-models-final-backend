import os
from dotenv import load_dotenv

def load_env():
    if os.getenv("ENVIRONMENT") == "production":
        return
    
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    env_path = os.path.join(base_dir, ".env")

    if os.path.exists(env_path):
        load_dotenv(env_path)

# Load env now
load_env()

# Spotify
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")

# JWT
JWT_SECRET = os.getenv("JWT_SECRET", "PLEASE_SET_SECRET")

# Redis
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

# BigQuery
BQ_PROJECT = os.getenv("GCP_PROJECT_ID", "spotify-match-project")
BQ_DATASET = os.getenv("BQ_DATASET", "user_event")
GCP_BUCKET_NAME = os.getenv("GCP_BUCKET_NAME", "spotify-match-avatars")

# Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# GCP Credentials (base64)
GOOGLE_CLOUD_CREDENTIALS = os.getenv("GOOGLE_CLOUD_CREDENTIALS")