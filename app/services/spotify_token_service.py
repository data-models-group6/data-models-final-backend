import time
import requests
from typing import Optional, Dict
from google.cloud import firestore
from app.config.settings import CLIENT_ID

# Lazy load Firestore client
def get_db():
    return firestore.Client()

def save_spotify_token(user_id: str, token_data: Dict):
    db = get_db()
    db.collection("spotify_tokens").document(user_id).set(token_data)

def get_spotify_token(user_id: str) -> Optional[Dict]:
    db = get_db()
    doc = db.collection("spotify_tokens").document(user_id).get()
    return doc.to_dict() if doc.exists else None

def refresh_spotify_token(user_id: str):
    token = get_spotify_token(user_id)
    if not token:
        return None

    now = int(time.time())

    # 不需要 refresh
    if token["expires_at"] > now + 30:
        return token

    refresh_token = token.get("refresh_token")
    if not refresh_token:
        return None

    url = "https://accounts.spotify.com/api/token"
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": CLIENT_ID,
    }

    r = requests.post(url, data=payload)
    new_token = r.json()

    if "access_token" not in new_token:
        return None

    # Spotify 有時不會回 refresh token，要沿用舊的
    if "refresh_token" not in new_token:
        new_token["refresh_token"] = refresh_token

    new_token["expires_at"] = int(time.time()) + new_token["expires_in"]

    save_spotify_token(user_id, new_token)
    return new_token