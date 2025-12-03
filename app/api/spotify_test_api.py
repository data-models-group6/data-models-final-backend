from fastapi import APIRouter
from app.services.spotify_user_service import (
    fetch_and_store_top_tracks,
    fetch_and_store_top_artists,
    fetch_and_store_favorite_tracks
)

router = APIRouter()

@router.post("/spotify/test/{user_id}")
def test_spotify_update(user_id: str):

    fetch_and_store_top_tracks(user_id)
    fetch_and_store_top_artists(user_id)
    fetch_and_store_favorite_tracks(user_id)

    return {"status": "ok", "user_id": user_id}