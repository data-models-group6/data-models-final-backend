# app/api/spotify_auth_api.py
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import RedirectResponse
from app.config.settings import CLIENT_ID, CLIENT_SECRET, REDIRECT_URI
from app.services.spotify_token_service import save_token_firestore, refresh_user_token
from app.services.user_auth import get_current_user
import requests
import time

router = APIRouter()


@router.get("/login")
def login(user=Depends(get_current_user)):
    """
    Step 1: 前端要求登入 Spotify → 回 Spotify 官方登入 URL
    """
    user_id = user["user_id"]

    scope = "user-read-currently-playing user-top-read"

    url = (
        "https://accounts.spotify.com/authorize"
        f"?client_id={CLIENT_ID}"
        f"&response_type=code"
        f"&redirect_uri={REDIRECT_URI}"
        f"&scope={scope}"
        f"&state={user_id}"    # 用 state 帶 user_id
    )

    return RedirectResponse(url)


@router.get("/callback")
def callback(code: str, state: str):
    """
    Step 2: Spotify 重導回來 → 交換 token → 存 Firestore
    state = user_id
    """
    user_id = state

    token_url = "https://accounts.spotify.com/api/token"
    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }

    r = requests.post(token_url, data=payload)
    token_data = r.json()

    if "access_token" not in token_data:
        raise HTTPException(status_code=400, detail=token_data)

    # 計算過期時間
    token_data["expires_at"] = int(time.time()) + token_data["expires_in"]

    # 存 Firestore
    save_token_firestore(user_id, token_data)

    return {"status": "success", "user_id": user_id, "token_saved": True}


@router.get("/now-playing")
def now_playing(user=Depends(get_current_user)):
    """
    直接抓目前播放（只看某個 user 的 Spotify 狀態）
    """
    user_id = user["user_id"]

    # 1. Firestore 查 token（會 auto refresh）
    token = refresh_user_token(user_id)
    if not token:
        raise HTTPException(status_code=401, detail="User has not linked Spotify")

    access_token = token["access_token"]

    # 2. Call Spotify API
    headers = {"Authorization": f"Bearer {access_token}"}
    url = "https://api.spotify.com/v1/me/player/currently-playing"

    r = requests.get(url, headers=headers)
    if r.status_code == 204:
        return {"message": "目前沒有播放任何音樂"}

    data = r.json()

    try:
        item = data["item"]
        return {
            "track_id": item["id"],
            "track_name": item["name"],
            "artist_id": item["artists"][0]["id"],
            "artist_name": item["artists"][0]["name"],
            "album_image": item["album"]["images"][0]["url"],
            "popularity": item.get("popularity", 0),
        }
    except Exception:
        return {"raw": data}