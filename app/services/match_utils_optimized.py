# app/services/match_utils_optimized.py

import numpy as np
from google.cloud import bigquery
from app.services.bigquery_client import get_bq_client
from app.services.firestore_client import get_db
from app.services.user_vector_service import safe_array
from app.services.match_utils import cosine_sim, similarity_score, build_similarity_reason


# ======================================================
# 取得所有 active users
# ======================================================
def get_all_active_users():
    client = get_bq_client()
    df = client.query("""
        SELECT DISTINCT user_id
        FROM (
            SELECT user_id FROM `spotify-match-project.user_event.user_top_tracks`
            UNION DISTINCT
            SELECT user_id FROM `spotify-match-project.user_event.user_top_artists`
            UNION DISTINCT
            SELECT user_id FROM `spotify-match-project.user_event.user_favorite_tracks`
        )
    """).to_dataframe()
    return df["user_id"].tolist()


# ======================================================
# 批次載入所有 user vectors
# ======================================================
def load_all_user_vectors():
    client = get_bq_client()
    df = client.query("""
        SELECT user_id, style_vector, language_vector, genre_vector
        FROM `spotify-match-project.user_event.user_preference_vectors`
    """).to_dataframe()

    vectors = {}
    for _, row in df.iterrows():
        vectors[row["user_id"]] = {
            "style": safe_array(row.get("style_vector")),
            "language": safe_array(row.get("language_vector")),
            "genre": safe_array(row.get("genre_vector")),
        }
    return vectors


# ======================================================
# 批次載入所有 user profiles（Firestore）
# ======================================================
def load_all_user_profiles(user_ids):
    db = get_db()
    profiles = {}

    for uid in user_ids:
        doc = db.collection("users").document(uid).get()
        if not doc.exists:
            profiles[uid] = {
                "name": "Guest",
                "avatarUrl": "https://example.com/default-avatar.png",
            }
        else:
            d = doc.to_dict() or {}
            profiles[uid] = {
                "name": d.get("name") or d.get("display_name") or "Guest",
                "avatarUrl": d.get("avatarUrl") or "https://example.com/default-avatar.png",
            }

    return profiles


# ======================================================
# 批次載入所有使用者 top songs
# ======================================================
def load_all_top_songs(user_ids):
    client = get_bq_client()
    df = client.query("""
        SELECT user_id, track_name, artist_name, album_image, rank
        FROM `spotify-match-project.user_event.user_top_tracks`
        ORDER BY rank ASC
    """).to_dataframe()

    result = {}
    for uid in user_ids:
        subset = df[df["user_id"] == uid].head(10)
        result[uid] = [
            {
                "title": row["track_name"],
                "artist": row["artist_name"],
                "album_image": row["album_image"]
            }
            for _, row in subset.iterrows()
        ]
    return result


# ======================================================
# 建立共享 artist map，優化後的共同藝人搜尋
# ======================================================
def compute_shared_artists_map():
    client = get_bq_client()
    df = client.query("""
        SELECT user_id, artist_id, artist_name
        FROM `spotify-match-project.user_event.user_top_artists`
    """).to_dataframe()

    artist_map = {}
    for _, row in df.iterrows():
        aid = row["artist_id"]
        if aid not in artist_map:
            artist_map[aid] = []
        artist_map[aid].append((row["user_id"], row["artist_name"]))
    return artist_map


def get_shared_artists_fast(user_a, user_b, artist_map, limit=5):
    shared = []
    for aid, entries in artist_map.items():
        users_here = {uid for uid, _ in entries}
        if user_a in users_here and user_b in users_here:
            shared.append(entries[0][1])
            if len(shared) >= limit:
                break
    return shared


# ======================================================
# 建立共享 track map，優化後的共同歌曲搜尋
# ======================================================
def compute_shared_tracks_map():
    client = get_bq_client()
    df = client.query("""
        SELECT user_id, track_name
        FROM `spotify-match-project.user_event.user_top_tracks`
    """).to_dataframe()

    track_map = {}
    for _, row in df.iterrows():
        tname = row["track_name"]
        uid = row["user_id"]
        if tname not in track_map:
            track_map[tname] = []
        track_map[tname].append(uid)
    return track_map


def get_shared_tracks_fast(u1, u2, track_map, limit=5):
    shared = []
    for tname, users_here in track_map.items():
        if u1 in users_here and u2 in users_here:
            shared.append(tname)
            if len(shared) >= limit:
                break
    return shared


# ======================================================
# 主邏輯：計算所有 candidates（API 會呼叫這個）
# ======================================================
def compute_similarity_candidates(user_id, users, vectors, profiles, top_songs,
                                  artists_map, tracks_map, top_k=10):

    if user_id not in vectors:
        return []

    target_vec = vectors[user_id]
    other_users = [u for u in users if u != user_id]

    candidates = []

    for uid in other_users:
        if uid not in vectors:
            continue

        vec = vectors[uid]

        # similarity score
        score = similarity_score(target_vec, vec)

        # shared artists / tracks
        shared_artists = get_shared_artists_fast(user_id, uid, artists_map)
        shared_tracks = get_shared_tracks_fast(user_id, uid, tracks_map)

        reason = build_similarity_reason(target_vec, vec, shared_artists, shared_tracks)

        candidates.append({
            "userId": uid,
            "name": profiles[uid]["name"],
            "avatarUrl": profiles[uid]["avatarUrl"],
            "similarity_info": {
                "score": score,
                "reason": reason["reason"],
                "reason_label": reason["reason_label"],
                "shared_top_artists": shared_artists,
                "shared_top_tracks": shared_tracks,
                "top_10_songs": top_songs.get(uid, [])
            }
        })

    candidates.sort(key=lambda x: x["similarity_info"]["score"], reverse=True)
    return candidates[:top_k]