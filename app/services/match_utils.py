# app/services/match_utils.py

import numpy as np
from google.cloud import bigquery
from app.services.bigquery_client import get_bq_client
from app.services.firestore_client import get_db


# ======================================================
# 工具：cosine similarity
# ======================================================
def cosine_sim(a, b):
    a = np.array(a, dtype=float)
    b = np.array(b, dtype=float)

    if a.shape != b.shape:
        return 0.0
    
    na = np.linalg.norm(a)
    nb = np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0

    return float(np.dot(a, b) / (na * nb))


# ======================================================
# 取得所有出現在 user_event 裡的使用者
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
            SELECT user_id FROM `spotify-match-project.user_event.user_favorite_track`
        )
    """).to_dataframe()
    return df["user_id"].tolist()


# ======================================================
# BigQuery：取得某 user 的向量
# ======================================================
def get_user_vector(user_id: str):
    client = get_bq_client()

    df = client.query(f"""
        SELECT user_id, style_vector, language_vector, genre_vector
        FROM `spotify-match-project.user_event.user_preference_vectors`
        WHERE user_id = '{user_id}'
        LIMIT 1
    """).to_dataframe()

    if df.empty:
        return None

    row = df.iloc[0]
    return {
        "user_id": row["user_id"],
        "style": row["style_vector"] or [],
        "language": row["language_vector"] or [],
        "genre": row["genre_vector"] or []
    }


# ======================================================
# BigQuery：共同喜愛藝人
# ======================================================
def get_shared_artists(user_a: str, user_b: str, limit: int = 5):
    client = get_bq_client()
    df = client.query(f"""
        SELECT artist_id, ANY_VALUE(artist_name) AS artist_name
        FROM `spotify-match-project.user_event.user_top_artists`
        WHERE user_id IN ('{user_a}', '{user_b}')
        GROUP BY artist_id
        HAVING COUNT(DISTINCT user_id) = 2
        LIMIT {limit}
    """).to_dataframe()

    return df["artist_name"].tolist()


# ======================================================
# BigQuery：共同聽過歌曲（你未來可用）
# ======================================================
def get_shared_tracks(user_a: str, user_b: str, limit: int = 5):
    client = get_bq_client()
    df = client.query(f"""
        SELECT track_id, ANY_VALUE(track_name) AS track_name
        FROM `spotify-match-project.user_event.user_top_tracks`
        WHERE user_id IN ('{user_a}', '{user_b}')
        GROUP BY track_id
        HAVING COUNT(DISTINCT user_id) = 2
        LIMIT {limit}
    """).to_dataframe()

    return df["track_name"].tolist()


# ======================================================
# 計算最終 similarity score（可調權重）
# ======================================================
def similarity_score(vec_a, vec_b):
    s = cosine_sim(vec_a["style"], vec_b["style"])
    g = cosine_sim(vec_a["genre"], vec_b["genre"])
    l = cosine_sim(vec_a["language"], vec_b["language"])

    return int((0.5 * s + 0.3 * g + 0.2 * l) * 100)


# ======================================================
# 建立相似原因（reason + label）
# ======================================================
def build_similarity_reason(vec_a, vec_b, shared_artists, shared_tracks):
    labels = []
    parts = []

    # 同歌手
    if shared_artists:
        labels.append("共同喜愛藝人")
        parts.append(f"你們都喜歡：{', '.join(shared_artists[:3])}")

    # 同歌
    if shared_tracks:
        labels.append("共同喜愛歌曲")
        parts.append(f"你們都聽過：{', '.join(shared_tracks[:3])}")

    # 曲風
    if cosine_sim(vec_a["genre"], vec_b["genre"]) > 0.7:
        labels.append("曲風相似")
        parts.append("你們的曲風偏好分佈非常接近")

    # 語言
    if cosine_sim(vec_a["language"], vec_b["language"]) > 0.7:
        labels.append("語言偏好一致")
        parts.append("你們常聽相同語言的歌曲")

    if not parts:
        parts.append("整體聽歌偏好高度相似")

    return {
        "reason": "；".join(parts),
        "reason_label": labels,
    }


# ======================================================
# Firestore：使用者基本資料
# ======================================================
def get_user_profile(user_id: str):
    db = get_db()
    doc = db.collection("users").document(user_id).get()

    if not doc.exists:
        return {
            "name": "Guest",
            "avatarUrl": "https://example.com/default-avatar.png",
        }

    data = doc.to_dict() or {}
    return {
        "name": data.get("name") or data.get("displayName") or "Guest",
        "avatarUrl": data.get("avatarUrl") or "https://example.com/default-avatar.png",
    }


# ======================================================
# BigQuery：使用者 top 10 tracks
# ======================================================
def get_user_top_songs(user_id: str, limit: int = 10):
    client = get_bq_client()

    df = client.query(f"""
        SELECT track_name, artist_name, album_image
        FROM `spotify-match-project.user_event.user_top_tracks`
        WHERE user_id = '{user_id}'
        ORDER BY rank ASC
        LIMIT {limit}
    """).to_dataframe()

    return [
        {
            "title": row["track_name"],
            "artist": row["artist_name"],
            "album_image": row.get("album_image")
        }
        for _, row in df.iterrows()
    ]