# app/api/spotify_test_api.py
from fastapi import APIRouter
from app.services.spotify_user_service import (
    fetch_and_store_top_tracks,
    fetch_and_store_top_artists,
    fetch_and_store_favorite_tracks
)
from app.services.firestore_client import get_db

router = APIRouter()

@router.post("/spotify/test/{user_id}")
def test_spotify_update(user_id: str):

    fetch_and_store_top_tracks(user_id)
    fetch_and_store_top_artists(user_id)
    fetch_and_store_favorite_tracks(user_id)

    return {"status": "ok", "user_id": user_id}

@router.post("/spotify/test/all")
def test_spotify_update_all():
    db = get_db()
    docs = db.collection("spotify_tokens").stream()

    result = []

    for doc in docs:
        user_id = doc.id
        try:
            fetch_and_store_top_tracks(user_id)
            fetch_and_store_top_artists(user_id)
            fetch_and_store_favorite_tracks(user_id)

            result.append({"user_id": user_id, "status": "ok"})
        except Exception as e:
            result.append({"user_id": user_id, "status": "error", "detail": str(e)})

    return {"results": result}