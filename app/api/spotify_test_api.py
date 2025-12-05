# app/api/spotify_test_api.py

from fastapi import APIRouter, HTTPException
from app.services.spotify_user_service import (
    fetch_and_store_top_tracks,
    fetch_and_store_top_artists,
    fetch_and_store_favorite_tracks
)
from app.services.firestore_client import get_db

router = APIRouter()


@router.post("/spotify/test/{user_id}")
def test_spotify_update(user_id: str):
    """
    更新單一使用者的 Spotify top tracks / artists / favorite tracks
    """
    try:
        fetch_and_store_top_tracks(user_id)
        fetch_and_store_top_artists(user_id)
        fetch_and_store_favorite_tracks(user_id)
        return {"status": "ok", "user_id": user_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/spotify/test/all")
def test_spotify_update_all():
    """
    更新所有已連 Spotify 的使用者
    （會讀取 Firestore 裡的 spotify_tokens collection）
    """
    db = get_db()
    docs = db.collection("spotify_tokens").stream()

    results = []

    for doc in docs:
        user_id = doc.id
        try:
            fetch_and_store_top_tracks(user_id)
            fetch_and_store_top_artists(user_id)
            fetch_and_store_favorite_tracks(user_id)

            results.append({"user_id": user_id, "status": "ok"})
        except Exception as e:
            results.append({
                "user_id": user_id,
                "status": "error",
                "detail": str(e)
            })

    return {"results": results}