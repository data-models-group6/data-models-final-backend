# app/api/heartbeat.py
from fastapi import APIRouter, Depends, HTTPException
from app.services.heartbeat_pubsub import publish_heartbeat
from app.services.spotify_token_service import (
    get_spotify_token,
    refresh_spotify_token
)
from app.services.spotify_now_playing import fetch_now_playing
from app.services.user_auth import get_current_user
import time

router = APIRouter()


@router.post("/heartbeat-auto")
async def heartbeat_auto(payload: dict, user=Depends(get_current_user)):
    """
    自動 heartbeat：
    - 前端只送 GPS (lat/lng)
    - 後端根據 user_id → Firestore → Spotify tokens
    - 自動 refresh token
    - 抓 currently-playing
    - 推送 heartbeat 到 Pub/Sub
    """

    user_id = user["user_id"]

    lat = payload.get("lat")
    lng = payload.get("lng")

    if lat is None or lng is None:
        raise HTTPException(status_code=400, detail="lat/lng required")

    # 1. 從 Firestore 取得 Spotify token
    token = get_spotify_token(user_id)
    if not token:
        raise HTTPException(status_code=401, detail="Spotify not linked")

    # 2. 自動 refresh（如 access_token 快過期）
    now = int(time.time())
    if token["expires_at"] < now + 30:
        token = refresh_spotify_token(user_id)
        if not token:
            raise HTTPException(status_code=401, detail="Token refresh failed")

    access_token = token["access_token"]

    # 3. 抓 Spotify Currently Playing
    item = fetch_now_playing(access_token)
    if not item:
        return {"message": "No music playing"}

    # 4. 組 heartbeat 資料
    heartbeat = {
        "user_id": user_id,
        "track_id": item["id"],
        "track_name": item["name"],
        "artist_id": item["artists"][0]["id"],
        "artist_name": item["artists"][0]["name"],
        "album_image": item["album"]["images"][0]["url"],
        "popularity": item.get("popularity", 0),
        "timestamp": int(time.time()),
        "lat": lat,
        "lng": lng,
    }

    # 5. 推給 Pub/Sub
    publish_heartbeat(heartbeat)

    return {"status": "ok", "sent": heartbeat}