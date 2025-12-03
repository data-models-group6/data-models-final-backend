# app/api/spotify_auth_api.py
import base64
import hashlib
import os
import time
import requests
from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import RedirectResponse
from app.config.settings import CLIENT_ID, REDIRECT_URI
from app.services.spotify_token_service import save_spotify_token
from app.services.user_auth import get_current_user
from app.models.spotify_auth_models import (
    AuthLoginResponse,
    SpotifyCallbackQuery,
    SpotifyCallbackResponse
)

router = APIRouter()

PKCE_STORE = {}  # 暫存 code_verifier


def generate_pkce_pair():
    code_verifier = base64.urlsafe_b64encode(os.urandom(64)).rstrip(b"=").decode()
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).rstrip(b"=").decode()
    return code_verifier, code_challenge


@router.get(
    "/login",
    summary="Spotify Login — 建立 OAuth URL",
    description=(
        "使用 PKCE Flow 建立 Spotify 授權登入連結，"
        "前端應 redirect 使用者至該 URL 以進行 Spotify OAuth 授權。"
    ),
    response_model=AuthLoginResponse,
)
def login(user=Depends(get_current_user)):
    user_id = user["user_id"]

    code_verifier, code_challenge = generate_pkce_pair()
    PKCE_STORE[user_id] = code_verifier

    scope = (
    "user-read-currently-playing "
    "user-top-read "
    "user-library-read "
    "playlist-read-private "
    "playlist-read-collaborative"
)

    url = (
        "https://accounts.spotify.com/authorize"
        f"?client_id={CLIENT_ID}"
        f"&response_type=code"
        f"&redirect_uri={REDIRECT_URI}"
        f"&code_challenge={code_challenge}"
        f"&code_challenge_method=S256"
        f"&scope={scope}"
        f"&state={user_id}"
    )

    return {"authorization_url": url}


@router.get(
    "/callback",
    summary="Spotify OAuth Callback",
    description=(
        "Spotify 授權完成後會 redirect 到此 endpoint，"
        "並附上 code/state。後端再用 code + code_verifier 交換 access_token。"
    ),
    response_model=SpotifyCallbackResponse,
)
def callback(
    code: str = Query(..., description="Spotify 回傳的授權 code"),
    state: str = Query(..., description="我們原本傳出去的 user_id"),
):
    user_id = state

    if user_id not in PKCE_STORE:
        raise HTTPException(status_code=400, detail="Missing code_verifier")

    code_verifier = PKCE_STORE.pop(user_id)

    token_url = "https://accounts.spotify.com/api/token"
    payload = {
        "client_id": CLIENT_ID,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "code_verifier": code_verifier
    }

    r = requests.post(token_url, data=payload)
    token_data = r.json()

    if "access_token" not in token_data:
        raise HTTPException(status_code=400, detail=token_data)

    token_data["expires_at"] = int(time.time()) + token_data["expires_in"]
    

    save_spotify_token(user_id, token_data)

    return RedirectResponse(url="http://localhost:5173/authorization/location")