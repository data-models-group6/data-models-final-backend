from fastapi import APIRouter, HTTPException
from math import radians, cos, sin, asin, sqrt
from typing import Literal
import redis
import os
import time

router = APIRouter()

# Redis 連線設定
REDIS_HOST = os.getenv("REDIS_HOST")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")

redis_client = redis.StrictRedis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    password=REDIS_PASSWORD,
    decode_responses=True,
)

TIME_WINDOW_SECONDS = 90  # ±90 秒


# --------------------------------------
# Haversine 經緯度距離（公尺）
# --------------------------------------
def haversine(lat1, lng1, lat2, lng2):
    R = 6371000
    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    a = sin(dlat/2)**2 + cos(radians(lat1))*cos(radians(lat2))*sin(dlng/2)**2
    c = 2 * asin(sqrt(a))
    return R * c


# --------------------------------------
# Nearby Match API
# --------------------------------------
@router.post("/match-nearby")
def match_nearby(payload: dict):

    user_id = payload.get("user_id")
    lat = payload.get("lat")
    lng = payload.get("lng")
    radius_m = payload.get("radius_m", 150)
    mode: Literal["track", "artist"] = payload.get("mode", "track")

    if not user_id:
        raise HTTPException(400, "user_id required")
    if lat is None or lng is None:
        raise HTTPException(400, "lat/lng required")
    if mode not in ("track", "artist"):
        raise HTTPException(400, "mode must be 'track' or 'artist'")

    # --- 抓自己的資料 ---
    key = f"user:{user_id}"
    self_data = redis_client.hgetall(key)

    if not self_data:
        return {"matches": [], "message": "Self status not found"}

    self_track = self_data.get("track_id")
    self_artist = self_data.get("artist_id")
    self_timestamp = int(self_data.get("timestamp", 0))

    # --- 抓所有使用者 ---
    keys = redis_client.keys("user:*")

    matches = []

    for k in keys:
        if k == key:
            continue

        d = redis_client.hgetall(k)
        if not d:
            continue

        # --- 1. 距離 ---
        o_lat = float(d["lat"])
        o_lng = float(d["lng"])
        dist = haversine(lat, lng, o_lat, o_lng)
        if dist > radius_m:
            continue

        # --- 2. 曲目 / 歌手判斷 ---
        if mode == "track" and d.get("track_id") != self_track:
            continue
        if mode == "artist" and d.get("artist_id") != self_artist:
            continue

        # --- 3. 時間戳 ---
        o_ts = int(d.get("timestamp", 0))
        if abs(self_timestamp - o_ts) > TIME_WINDOW_SECONDS:
            continue

        d["distance_m"] = dist
        matches.append(d)

    return {
        "mode": mode,
        "radius_m": radius_m,
        "time_window_seconds": TIME_WINDOW_SECONDS,
        "count": len(matches),
        "matches": matches,
    }