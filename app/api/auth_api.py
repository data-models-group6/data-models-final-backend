# app/api/auth_api.py
from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from app.services.user_service import (
    create_user,
    get_user_by_email,
    update_avatar,
    update_gender,
    update_display_name
)
from app.services.jwt_service import create_jwt_token
from app.services.user_auth import get_current_user
from app.services.storage_client import upload_avatar_to_gcs
import hashlib
from app.models.auth_models import (
    RegisterRequest, RegisterResponse,
    LoginRequest, LoginResponse,
    UpdateGenderRequest, UpdateNameRequest
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

# === Update gender ===
@router.patch("/profile/gender")
def patch_gender(payload: UpdateGenderRequest, user = Depends(get_current_user)):
    update_gender(user["user_id"], payload.gender)
    return {"status": "ok"}

# === Upload avatar ===
@router.post("/avatar", summary="上傳頭像")
async def post_avatar(file: UploadFile = File(...), user = Depends(get_current_user)):
    content = await file.read()
    url = upload_avatar_to_gcs(user["user_id"], content, file.content_type)
    update_avatar(user["user_id"], url)
    return {"avatar_url": url}

# === Update display name ===
@router.patch("/profile/display-name")
def patch_display_name(payload: UpdateNameRequest, user = Depends(get_current_user)):
    update_display_name(user["user_id"], payload.display_name)
    return {"status": "ok"}

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

    return {"status": "ok", "user_id": user["user_id"], "token": token}