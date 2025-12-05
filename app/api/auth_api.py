# app/api/auth_api.py
from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from app.services.user_service import (
    create_user,
    get_user_by_email,
)
from app.services.jwt_service import create_jwt_token
import hashlib
from app.models.auth_models import (
    RegisterRequest, RegisterResponse,
    LoginRequest, LoginResponse,
)

router = APIRouter()

# === Register ===
@router.post("/register", response_model=RegisterResponse)
def register(payload: RegisterRequest):
    existing = get_user_by_email(payload.email)
    if existing:
        raise HTTPException(400, "Email already registered")

    password_hash = hashlib.sha256(payload.password.encode()).hexdigest()

    data = payload.dict()
    data["password_hash"] = password_hash

    user_id = create_user(data)

    return {"status": "ok", "user_id": user_id, "message": "User registered"}


# === Login ===
@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest):
    user = get_user_by_email(payload.email)
    if not user:
        raise HTTPException(401, "User not found")

    hashed = hashlib.sha256(payload.password.encode()).hexdigest()
    if hashed != user["password_hash"]:
        raise HTTPException(401, "Password incorrect")

    token = create_jwt_token(user["user_id"])
    # 若沒有 avatarUrl → 回傳空字串
    avatarUrl = user.get("avatarUrl", "") or ""
    display_name = user.get("display_name", "") or ""

    return {"status": "ok", "user_id": user["user_id"], "token": token, "avatarUrl":avatarUrl, "display_name": display_name}