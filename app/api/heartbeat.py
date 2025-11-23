# app/api/heartbeat.py
# app/api/heartbeat.py
from fastapi import APIRouter, Depends, HTTPException, Query
from app.services.heartbeat_pubsub import publish_heartbeat
from app.services.spotify_token_service import get_user_token
from app.services.spotify_token_service import refresh_user_token
from app.services.spotify_now_playing import fetch_now_playing
from app.services.user_auth import get_current_user
import time

router = APIRouter()

# # ---- 手動 heartbeat (前端送 track + GPS) ----
# @router.post("/heartbeat")
# async def heartbeat_manual(payload: dict, user=Depends(get_current_user)):
#     """
#     前端送自己的 track + GPS → 推到 Pub/Sub
#     payload 需要包含：
#     - track_id, track_name, artist_id, artist_name, album_image, popularity
#     - lat, lng, timestamp（也可以後端自己補）
#     """
#     user_id = user["user_id"]
#     payload["user_id"] = user_id

#     if "timestamp" not in payload:
#         payload["timestamp"] = int(time.time())

#     publish_heartbeat(payload)
#     return {"status": "ok", "sent": payload}
@router.post("/heartbeat-auto")
async def heartbeat_auto(payload: dict):

    user = get_current_user()
    user_id = user["user_id"]

    lat = payload.get("lat")
    lng = payload.get("lng")

    if lat is None or lng is None:
        raise HTTPException(status_code=400, detail="lat/lng required")

    token = get_user_token(user_id)
    if not token:
        raise HTTPException(401, "User not linked Spotify")

    item = fetch_now_playing(token["access_token"])
    if not item:
        return {"message": "No music playing"}

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
        "lng": lng
    }

    publish_heartbeat(heartbeat)
    return {"status": "ok", "sent": heartbeat}

# # ---- 自動 heartbeat (後端自己抓 Spotify Now Playing) ----
# @router.post("/heartbeat-auto")
# async def heartbeat_auto(
#     user_id: str = Query(..., description="你的系統 user_id，例如 test_user_001"),
#     payload: dict = None,
# ):
#     """
#     前端只送 GPS → 後端自己去 Spotify 抓正在播放的歌再推 Pub/Sub
#     payload 需要包含：
#     - lat, lng
#     """
#     lat = payload.get("lat")
#     lng = payload.get("lng")

#     if lat is None or lng is None:
#         raise HTTPException(status_code=400, detail="lat/lng required")

#     # 1. 從 Firestore 抓 token（會自動 refresh）
#     token = refresh_user_token(user_id)
#     if not token:
#         raise HTTPException(status_code=401, detail="User has not linked Spotify")

#     access_token = token["access_token"]

#     # 2. 抓 Spotify Now Playing（只回 item）
#     item = fetch_now_playing(access_token)
#     if item is None:
#         return {"message": "No music playing"}

#     # 3. 組合 heartbeat 資料
#     heartbeat = {
#         "user_id": user_id,
#         "track_id": item["id"],
#         "track_name": item["name"],
#         "artist_id": item["artists"][0]["id"],
#         "artist_name": item["artists"][0]["name"],
#         "album_image": item["album"]["images"][0]["url"],
#         "popularity": item.get("popularity", 0),
#         "timestamp": int(time.time()),
#         "lat": lat,
#         "lng": lng,
#     }

#     # 4. 推到 Pub/Sub
#     publish_heartbeat(heartbeat)

#     return {"status": "ok", "sent": heartbeat}