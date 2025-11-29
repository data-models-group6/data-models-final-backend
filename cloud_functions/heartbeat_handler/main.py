import base64
import json
import geohash2
import redis
import os

# 讀取環境變數（部署時在 Cloud Function 設定）
REDIS_HOST = os.getenv("REDIS_HOST")      # e.g. "10.0.0.3"（MemoryStore 內部 IP）
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")  # Secret Manager 拉進來

# Redis client
redis_client = redis.StrictRedis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    password=REDIS_PASSWORD,
    decode_responses=True,
)

def get_redis():
    """
    Lazy load Redis client.
    避免在 cold start / import 階段初始化 Redis client。
    """
    REDIS_HOST = os.getenv("REDIS_HOST")
    REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")

    return redis.StrictRedis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        password=REDIS_PASSWORD,
        decode_responses=True,
    )

def heartbeat_handler(event, context):
    """Triggered by Pub/Sub heartbeat message, store in Redis."""
    print("Heartbeat Function triggered")

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

    user_id = data.get("user_id")
    lat = data.get("lat")
    lng = data.get("lng")

    if not user_id or lat is None or lng is None:
        print("Missing field(s)")
        return

    # --------- Compute geohash ---------
    geo_hash = geohash2.encode(lat, lng, precision=8)

    # --------- Redis key ---------
    key = f"user:{user_id}"

    # --------- Write into Redis (Hash) ---------
    heartbeat = {
        "user_id": user_id,
        "track_id": data.get("track_id"),
        "track_name": data.get("track_name"),
        "artist_id": data.get("artist_id"),
        "artist_name": data.get("artist_name"),
        "popularity": data.get("popularity"),
        "timestamp": str(data.get("timestamp")),
        "album_image": data.get("album_image"),
        "lat": str(lat),
        "lng": str(lng),
        "geohash": geo_hash,
    }

    try:
        redis_client = get_redis()
        redis_client.hset(key, mapping=heartbeat)
        # 設定 TTL（例如 120 秒），避免舊資料殘留
        redis_client.expire(key, 120)

        print(f"Redis updated for {user_id}")

    except Exception as e:
        print("Redis write error:", e)
        return