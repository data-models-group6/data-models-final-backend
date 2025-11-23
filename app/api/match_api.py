# app/api/match_api.py
from fastapi import APIRouter, HTTPException
from typing import Literal
from math import radians, cos, sin, asin, sqrt
from google.cloud import firestore

REALTIME_DB = "real-time-match"
COLLECTION_NAME = "user_status"

router = APIRouter()

TIME_WINDOW_SECONDS = 15   # 正負 15 秒


def haversine(lat1, lng1, lat2, lng2):
    """
    回傳兩點距離（公尺）
    """
    R = 6371000  # 地球半徑（公尺）
    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)

    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
    c = 2 * asin(sqrt(a))
    return R * c


@router.post("/match-nearby")
def match_nearby(payload: dict):
    """
    POST /api/match-nearby
    {
        "user_id": "test_user_001",
        "lat": 25.0339,
        "lng": 121.5654,
        "radius_m": 150,
        "mode": "track"      // or "artist"
    }
    """

    user_id = payload.get("user_id")
    lat = payload.get("lat")
    lng = payload.get("lng")
    radius_m = payload.get("radius_m", 100)
    mode: Literal["track", "artist"] = payload.get("mode", "track")

    if not user_id:
        raise HTTPException(400, "user_id required")
    if lat is None or lng is None:
        raise HTTPException(400, "lat/lng required")
    if mode not in ("track", "artist"):
        raise HTTPException(400, "mode must be 'track' or 'artist'")

    db = firestore.Client(database=REALTIME_DB)
    docs = db.collection(COLLECTION_NAME).stream()

    self_track = self_artist = None
    self_timestamp = None

    records = []

    # 先抓全部 user_status
    for doc in docs:
        d = doc.to_dict()
        records.append(d)

        if d.get("user_id") == user_id:
            self_track = d.get("track_id")
            self_artist = d.get("artist_id")
            self_timestamp = d.get("timestamp")

    if not self_timestamp:
        return {"matches": [], "message": "Self status not found"}

    # 沒有 track，也沒有 artist
    if not self_track and not self_artist:
        return {"matches": [], "message": "Self track/artist not found"}

    matches = []

    for d in records:
        if d.get("user_id") == user_id:
            continue

        # ---------- 1. 對方位置 ----------
        other_loc = d.get("location")
        if not other_loc:
            continue

        other_lat = other_loc.latitude
        other_lng = other_loc.longitude

        # 座標距離
        dist = haversine(lat, lng, other_lat, other_lng)
        if dist > radius_m:
            continue

        # ---------- 2. 曲目/歌手是否一致 ----------
        if mode == "track" and d.get("track_id") != self_track:
            continue
        if mode == "artist" and d.get("artist_id") != self_artist:
            continue

        # ---------- 3. 時間戳相差是否 ≤ 15 秒 ----------
        other_timestamp = d.get("timestamp")
        if not other_timestamp:
            continue

        if abs(self_timestamp - other_timestamp) > TIME_WINDOW_SECONDS:
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