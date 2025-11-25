# app/services/jwt_service.py
import jwt
import time
from app.config.settings import JWT_SECRET

JWT_ALGORITHM = "HS256"
EXPIRE_SECONDS = 3600 * 24 * 7       # 7 天

def create_jwt_token(user_id: str):
    payload = {
        "user_id": user_id,
        "exp": int(time.time()) + EXPIRE_SECONDS
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)