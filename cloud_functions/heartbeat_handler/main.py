# cloud_functions/heartbeat_handler/main.py
import base64
import json
import geohash2
from google.cloud import firestore

# Firestore 設定：專門存即時心跳
REALTIME_DB = "real-time-match"
COLLECTION_NAME = "user_status"


def heartbeat_handler(event, context):
    """Triggered by Pub/Sub heartbeat message."""
    print("Heartbeat Function triggered")

    # ========== 1. Decode Pub/Sub message ==========
    if "data" not in event:
        print("No data found in event")
        return

    try:
        message_bytes = base64.b64decode(event["data"])
        data = json.loads(message_bytes.decode("utf-8"))
    except Exception as e:
        print("Failed to decode message:", e)
        return

    print("Received heartbeat:", data)

    # ========== 2. Validate essential fields ==========
    user_id = data.get("user_id")
    lat = data.get("lat")
    lng = data.get("lng")

    if not user_id:
        print("Missing user_id")
        return

    if lat is None or lng is None:
        print(f"Missing location for user {user_id}")
        return

    # ========== 3. Compute geohash ==========
    geo_hash = geohash2.encode(lat, lng, precision=8)

    # ========== 4. Write to Firestore ==========
    try:
        db = firestore.Client(database=REALTIME_DB)
        doc_ref = db.collection(COLLECTION_NAME).document(user_id)

        doc_ref.set(
            {
                "user_id": user_id,
                "track_id": data.get("track_id"),
                "track_name": data.get("track_name"),
                "artist_id": data.get("artist_id"),
                "artist_name": data.get("artist_name"),
                "popularity": data.get("popularity"),
                "timestamp": data.get("timestamp"),
                "album_image": data.get("album_image"),
                "location": firestore.GeoPoint(lat, lng),
                "geohash": geo_hash,
            }
        )

        print(f"Firestore updated for user: {user_id}")

    except Exception as e:
        print("Firestore write error:", e)
        return