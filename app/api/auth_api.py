# app/api/auth_api.py
from fastapi import APIRouter, HTTPException
from app.services.user_service import create_user, get_user_by_email
from app.services.jwt_service import create_jwt_token
import hashlib
from app.models.auth_models import (
    RegisterRequest, RegisterResponse,
    LoginRequest, LoginResponse
)

router = APIRouter()


@router.post(
    "/register",
    summary="註冊帳號",
    description="建立 email/password 使用者，儲存於 Firestore。",
    response_model=RegisterResponse
)
def register(payload: dict):
    email = payload.get("email")
    password = payload.get("password")

    if not email or not password:
        raise HTTPException(400, "email/password required")

    # 檢查是否已存在
    existing = get_user_by_email(email)
    if existing:
        raise HTTPException(400, "Email already registered")

    # SHA256 密碼雜湊
    password_hash = hashlib.sha256(password.encode()).hexdigest()

    # 建立 Firestore 使用者
    user_id = create_user(email, password_hash)

    # 回傳成功
    return {
        "status": "ok",
        "user_id": user_id,
        "message": "User registered"
    }



@router.post(
    "/login",
    summary="登入帳號",
    description="驗證 email/password，成功後產生 JWT Token。",
    response_model=LoginResponse
)
def login(payload: dict):
    email = payload.get("email")
    password = payload.get("password")

    if not email or not password:
        raise HTTPException(400, "email/password required")

    user = get_user_by_email(email)
    if not user:
        raise HTTPException(401, "User not found")

    hashed = hashlib.sha256(password.encode()).hexdigest()
    if hashed != user["password_hash"]:
        raise HTTPException(401, "Password incorrect")

    token = create_jwt_token(user["user_id"])

    return {
        "status": "ok",
        "user_id": user["user_id"],
        "token": token
    }