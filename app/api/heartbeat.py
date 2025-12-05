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
from app.services.redis_service import HeartbeatRedisService

router = APIRouter()

redis_service = HeartbeatRedisService()

@router.post("/heartbeat-auto")
async def heartbeat_auto(payload: dict, user=Depends(get_current_user)):

    user_id = user["user_id"]
    display_name = user.get("display_name")
    avatarUrl = user.get("avatarUrl")

    lat = payload.get("lat")
    lng = payload.get("lng")

    if lat is None or lng is None:
        raise HTTPException(status_code=400, detail="lat/lng required")

    # 1. 取 token
    token = get_spotify_token(user_id)
    if not token:
        raise HTTPException(status_code=401, detail="Spotify not linked")

    now = int(time.time())
    if token["expires_at"] < now + 30:
        token = refresh_spotify_token(user_id)
        if not token:
            raise HTTPException(status_code=401, detail="Token refresh failed")

    access_token = token["access_token"]

    # 2. 抓 currently playing
    item = fetch_now_playing(access_token)

    # Token 過期 → Refresh 再 call 一次
    if item == "TOKEN_EXPIRED":
        token = refresh_spotify_token(user_id)
        access_token = token["access_token"]
        item = fetch_now_playing(access_token)

    # 還是沒有 item → 就真的沒在播歌
    if not item:
        return {"message": "No music playing"}

    # 3. 組 heartbeat
    heartbeat = {
        "user_id": user_id,
        "track_id": item["id"],
        "track_name": item["name"],
        "artist_id": item["artists"][0]["id"],
        "artist_name": item["artists"][0]["name"],
        "album_image": item["album"]["images"][0]["url"],
        "popularity": item.get("popularity", 0),
        "timestamp": int(time.time()),
        "display_name":display_name,
        "avatarUrl":avatarUrl,
        "lat": lat,
        "lng": lng
    }

    # 4. 存到 Redis
    redis_service.set_heartbeat(user_id, heartbeat)
    
    groups = redis_service.get_nearby_music_groups(
        my_user_id=user_id,
        my_track_id=item["id"],
        my_artist_id=item["artists"][0]["id"],
        my_lat=lat,
        my_lng=lng
    )

    publish_heartbeat(heartbeat)

    return {
        "status": "ok",
        "sent": heartbeat,
        "same_track": groups["same_track"],
        "same_artist": groups["same_artist"],
        "just_near": groups["just_near"]
    }
