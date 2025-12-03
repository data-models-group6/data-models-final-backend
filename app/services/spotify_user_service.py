# app/services/spotify_user_service.py
import time
from datetime import datetime, timezone
from typing import Dict, Optional
import requests
from fastapi import HTTPException
from app.services.spotify_token_service import (
    get_spotify_token,
    refresh_spotify_token,
)
from app.services.bigquery_client import insert_rows_json

SPOTIFY_API_BASE = "https://api.spotify.com/v1"

# --------- 小工具 ---------
def _now_utc() -> datetime:
    return datetime.now(timezone.utc)

def _parse_iso_ts(ts: str) -> datetime:
    if ts.endswith("Z"):
        ts = ts.replace("Z", "+00:00")
    return datetime.fromisoformat(ts)

def _get_valid_access_token(user_id: str) -> str:
    """
    統一從 spotify_token_service 取得「可用的 access_token」：

    1. 先 get_spotify_token(user_id)
    2. 如果 expires_at 快過期 → refresh_spotify_token(user_id)
    3. 回傳 access_token
    """
    token = get_spotify_token(user_id)
    if not token:
        raise HTTPException(status_code=401, detail="Spotify not linked")

    now = int(time.time())
    if token.get("expires_at", 0) <= now + 30:
        token = refresh_spotify_token(user_id)
        if not token:
            raise HTTPException(status_code=401, detail="Token refresh failed")

    access_token = token.get("access_token")
    if not access_token:
        raise HTTPException(status_code=401, detail="Missing access_token")

    return access_token

# --------- Spotify API Wrapper ---------
def _spotify_get(access_token: str, path: str, params: Optional[Dict] = None) -> Dict:
    url = f"{SPOTIFY_API_BASE}/{path}"
    headers = {"Authorization": f"Bearer {access_token}"}

    r = requests.get(url, headers=headers, params=params)
    if r.status_code != 200:
        raise HTTPException(status_code=r.status_code, detail=f"Spotify error: {r.text}")

    return r.json()

# --------- Top Tracks ---------
def fetch_and_store_top_tracks(user_id: str) -> None:
    access_token = _get_valid_access_token(user_id)
    periods = ["short_term", "medium_term", "long_term"]
    now = _now_utc()
    rows = []

    for period in periods:
        data = _spotify_get(
            access_token,
            "me/top/tracks",
            params={"limit": 10, "time_range": period}
        )

        for idx, track in enumerate(data.get("items", []), start=1):
            artist = track["artists"][0] if track.get("artists") else {}
            images = track.get("album", {}).get("images", [])
            album_image = images[0]["url"] if images else None

            rows.append({
                "user_id": user_id,
                "track_id": track["id"],
                "track_name": track["name"],
                "artist_id": artist.get("id"),
                "artist_name": artist.get("name"),
                "popularity": track.get("popularity"),
                "period": period,
                "rank": idx,
                "album_image": album_image,
                "artist_image": None,
                "created_at": now,
            })

    insert_rows_json("user_top_songs", rows)

# --------- Top Artists ---------
def fetch_and_store_top_artists(user_id: str) -> None:
    access_token = _get_valid_access_token(user_id)
    periods = ["short_term", "medium_term", "long_term"]
    now = _now_utc()
    rows = []

    for period in periods:
        data = _spotify_get(
            access_token,
            "me/top/artists",
            params={"limit": 10, "time_range": period}
        )

        for idx, artist in enumerate(data.get("items", []), start=1):
            images = artist.get("images", [])
            artist_image = images[0]["url"] if images else None

            rows.append({
                "user_id": user_id,
                "artist_id": artist["id"],
                "artist_name": artist["name"],
                "popularity": artist["popularity"],
                "period": period,
                "rank": idx,
                "artist_image": artist_image,
                "created_at": now,
            })

    insert_rows_json("user_top_artists", rows)

# --------- Favorite Tracks (Saved Tracks) ---------
def fetch_and_store_favorite_tracks(user_id: str) -> None:
    access_token = _get_valid_access_token(user_id)
    rows = []
    now = _now_utc()
    limit = 50
    offset = 0

    while len(rows) < 100:
        data = _spotify_get(
            access_token,
            "me/tracks",
            params={"limit": limit, "offset": offset}
        )
        items = data.get("items", [])
        if not items:
            break

        for item in items:
            track = item["track"]
            added_at = _parse_iso_ts(item["added_at"])
            artist = track["artists"][0]
            images = track["album"]["images"]
            album_image = images[0]["url"] if images else None

            rows.append({
                "user_id": user_id,
                "track_id": track["id"],
                "track_name": track["name"],
                "artist_id": artist["id"],
                "artist_name": artist["name"],
                "album_image": album_image,
                "added_at": added_at,
                "popularity": track.get("popularity"),
                "created_at": now,
            })

            if len(rows) >= 100:
                break

        offset += limit

    insert_rows_json("user_favorite_tracks", rows)