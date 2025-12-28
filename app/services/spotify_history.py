import time
import requests
from app.services.spotify_token_service import get_spotify_token, refresh_spotify_token
from app.services.heartbeat_pubsub import publish_heartbeat
from app.services.firestore_client import get_db

def sync_recently_played(user_id: str, lat: float = None, lng: float = None) -> dict:
    """
    Fetch recently played tracks from Spotify and publish to BigQuery via Pub/Sub.
    Only publishes tracks played after the last sync time.
    """
    
    # 1. Get User Profile for last_sync_time
    db = get_db()
    user_ref = db.collection("users").document(user_id)
    user_doc = user_ref.get()
    
    last_sync_time = 0
    user_data = {}
    if user_doc.exists:
        user_data = user_doc.to_dict()
        last_sync_time = user_data.get("last_history_sync_at", 0)
        
    # 2. Get Spotify Token
    token = get_spotify_token(user_id)
    if not token:
        return {"status": "error", "message": "Spotify not linked"}
        
    now = int(time.time())
    if token["expires_at"] < now + 30:
        token = refresh_spotify_token(user_id)
        if not token:
            return {"status": "error", "message": "Token refresh failed"}
            
    access_token = token["access_token"]
    
    # 3. Call Spotify API
    url = "https://api.spotify.com/v1/me/player/recently-played?limit=50"
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # If we have a last sync time, we can use 'after' parameter (timestamp in ms)
    # Spotify API 'after' takes unix timestamp in milliseconds
    if last_sync_time > 0:
        url += f"&after={int(last_sync_time * 1000)}"
        
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        return {"status": "error", "message": f"Spotify API Error: {r.text}"}
        
    data = r.json()
    items = data.get("items", [])
    
    if not items:
        return {"status": "ok", "synced_count": 0}
        
    # 4. Process and Publish
    synced_count = 0
    max_played_at = last_sync_time
    
    for item in items:
        track = item["track"]
        played_at_str = item["played_at"] # ISO 8601 string
        # Convert to unix timestamp
        # Python 3.7+ fromisoformat handles 'Z' if replaced by +00:00
        try:
            # Simple parsing for ISO 8601
            import datetime
            dt = datetime.datetime.strptime(played_at_str.replace("Z", "+0000"), "%Y-%m-%dT%H:%M:%S.%f%z")
            played_at_ts = dt.timestamp()
        except:
            # Fallback or skip
            continue
            
        if played_at_ts > max_played_at:
            max_played_at = played_at_ts
            
        # Construct payload similar to heartbeat
        # Note: 'lat' and 'lng' might be from where they are NOW, not where they were then.
        # But for "filling gaps", using current location is an acceptable approximation 
        # or we can leave it null if the schema allows.
        # User requested to "fill gaps", so let's use current location if provided.
        
        payload = {
            "user_id": user_id,
            "track_id": track["id"],
            "track_name": track["name"],
            "artist_id": track["artists"][0]["id"],
            "artist_name": track["artists"][0]["name"],
            "popularity": track.get("popularity", 0),
            "timestamp": int(played_at_ts), # Use the actual played time
            "lat": lat,
            "lng": lng,
            # Additional fields if available
            "album_image": track["album"]["images"][0]["url"] if track["album"]["images"] else None,
            "display_name": user_data.get("display_name"),
            "avatarUrl": user_data.get("avatarUrl")
        }
        
        publish_heartbeat(payload)
        synced_count += 1
        
    # 5. Update last_sync_time
    if max_played_at > last_sync_time:
        user_ref.update({"last_history_sync_at": max_played_at})
        
    return {"status": "ok", "synced_count": synced_count}
