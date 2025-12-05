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
    SpotifyCallbackResponse,
)
from app.services.spotify_pkce_service import (
    save_code_verifier,
    get_and_delete_code_verifier,
)
router = APIRouter()



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
    # 1. 從 JWT 取得目前登入的 user_id
    user_id = user["user_id"]

    # 2. 產生 PKCE 的 code_verifier / code_challenge
    code_verifier, code_challenge = generate_pkce_pair()

    # 3. 將 code_verifier 存到 Firestore（spotify_pkce_sessions）
    save_code_verifier(user_id, code_verifier)

    # 4. 定義需要的 scope
    scope = (
        "user-read-currently-playing "
        "user-top-read "
        "user-library-read "
        "playlist-read-private "
        "playlist-read-collaborative"
    )

    # 5. 組出 Spotify 授權 URL
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

    # 6. 回傳給前端，前端直接 redirect 到這個 URL
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
    # 1. Spotify 回傳的 state 就是我們當初送出去的 user_id
    user_id = state

    # 2. 從 Firestore 撈出剛才存的 code_verifier（同時刪掉）
    code_verifier = get_and_delete_code_verifier(user_id)

    if not code_verifier:
        # 可能原因：
        # - 沒有呼叫 /login 就直接打 /callback
        # - PKCE 已過期（超過我們設定 TTL）
        # - Cloud Run / Render 上 instance 重啟，但我們本來用記憶體存 → 這版已解決
        raise HTTPException(status_code=400, detail="Missing or expired code_verifier")

    # 3. 組 token 交換的 payload
    token_url = "https://accounts.spotify.com/api/token"
    payload = {
        "client_id": CLIENT_ID,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "code_verifier": code_verifier,
    }

    # 4. 跟 Spotify 交換 access_token
    r = requests.post(token_url, data=payload)
    token_data = r.json()

    if "access_token" not in token_data:
        # 可以印出 token_data 來 debug
        raise HTTPException(status_code=400, detail=token_data)

    # 5. 算出 expires_at（秒數），方便之後 refresh_token 使用
    token_data["expires_at"] = int(time.time()) + token_data["expires_in"]

    # 6. 存到 Firestore 的 spotify_tokens collection
    save_spotify_token(user_id, token_data)

    # 7. 授權完成後 redirect 回前端的某個頁面（之後你可以改成設定檔）
    return RedirectResponse(url="https://data-models-final-frontend.onrender.com/authorization/location")