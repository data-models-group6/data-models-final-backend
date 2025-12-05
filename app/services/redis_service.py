import json
import math
import time
import redis
import os


class HeartbeatRedisService:
    def __init__(self, host=None, port=None, password=None):
        self.host = host or os.getenv("REDIS_HOST")
        self.port = port or int(os.getenv("REDIS_PORT", "6379"))
        self.password = password or os.getenv("REDIS_PASSWORD")
        self.redis = self.get_redis_client()

    # --------------------------
    # Redis Client
    # --------------------------
    def get_redis_client(self):
        return redis.Redis(
            host=self.host,
            port=self.port,
            password=self.password,
            decode_responses=True
        )

    # --------------------------
    # 取出所有 heartbeat（使用 SCAN）
    # --------------------------
    def get_all_heartbeats(self):
        cursor = 0
        all_data = []

        while True:
            cursor, keys = self.redis.scan(cursor=cursor, match="*:heartbeat", count=200)

            if keys:
                values = self.redis.mget(keys)
                for v in values:
                    if v:
                        try:
                            all_data.append(json.loads(v))
                        except:
                            pass

            if cursor == 0:
                break

        return all_data

    # --------------------------
    # 過濾：時間（例如 3 分鐘內）
    # --------------------------
    @staticmethod
    def filter_by_time(data, max_age_sec=180):
        now = int(time.time())
        return [
            d for d in data
            if (now - d.get("timestamp", 0)) <= max_age_sec
        ]

    # --------------------------
    # Haversine：計算距離（公里）
    # --------------------------
    @staticmethod
    def haversine(lat1, lon1, lat2, lon2):
        R = 6371
        dLat = math.radians(lat2 - lat1)
        dLon = math.radians(lon2 - lon1)

        a = (
            math.sin(dLat / 2) ** 2 +
            math.cos(math.radians(lat1)) *
            math.cos(math.radians(lat2)) *
            math.sin(dLon / 2) ** 2
        )

        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    # --------------------------
    # 過濾：距離（例如 150 公尺內）
    # --------------------------
    def filter_by_location(self, data, my_lat, my_lng, km=0.150):
        return [
            d for d in data
            if self.haversine(my_lat, my_lng, d["lat"], d["lng"]) <= km
        ]

    # --------------------------
    # 分類：同首歌 / 同歌手但不同歌
    # --------------------------
    @staticmethod
    def classify_by_music_simple(all_data, my_user_id, my_track_id, my_artist_id):
        same_track = []
        same_artist = []
        just_near = []

        for d in all_data:
            if not d:
                continue

            uid = d.get("user_id")
            track = d.get("track_id")
            artist = d.get("artist_id")

            # 排除自己
            if uid == my_user_id:
                continue

            # ✔ 同首歌
            if track == my_track_id:
                same_track.append(d)
                continue

            # ✔ 同歌手 + 不同歌
            if artist == my_artist_id and track != my_track_id:
                same_artist.append(d)

            if artist != my_artist_id:
                just_near.append(d)


        return {
            "same_track": same_track,
            "same_artist": same_artist,
            "just_near": just_near
        }

    # --------------------------
    # 綜合流程：取得附近音樂分組
    # --------------------------
    def get_nearby_music_groups(self, my_user_id, my_track_id, my_artist_id, my_lat, my_lng,
                                max_age_sec=180, km=0.150):
        # 1. 撈全部
        all_data = self.get_all_heartbeats()

        # 2. 時間過濾
        fresh = self.filter_by_time(all_data, max_age_sec=max_age_sec)

        # 3. 距離過濾
        nearby = self.filter_by_location(fresh, my_lat, my_lng, km=km)

        # 4. 分成 same_track / same_artist
        groups = self.classify_by_music_simple(
            all_data=nearby,
            my_user_id=my_user_id,
            my_track_id=my_track_id,
            my_artist_id=my_artist_id
        )

        return groups

    # --------------------------
    # 存 heartbeat
    # --------------------------
    def set_heartbeat(self, user_id, heartbeat, ttl_sec=180):
        self.redis.set(f"{user_id}:heartbeat", json.dumps(heartbeat), ex=ttl_sec)
