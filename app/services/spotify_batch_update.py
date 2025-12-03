from app.services.spotify_user_service import (
    fetch_and_store_top_tracks,
    fetch_and_store_top_artists,
    fetch_and_store_favorite_tracks
)
from app.services.firestore_client import get_db

def update_all_users_spotify_profile():

    db = get_db()
    users = db.collection("users").stream()

    for user in users:
        user_id = user.id

        try:
            fetch_and_store_top_tracks(user_id)
            fetch_and_store_top_artists(user_id)
            fetch_and_store_favorite_tracks(user_id)

            print(f"[OK] updated {user_id}")

        except Exception as e:
            print(f"[ERROR] {user_id}: {e}")