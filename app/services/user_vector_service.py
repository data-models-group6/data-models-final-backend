# app/services/user_vector_service.py

from google.cloud import bigquery
from app.services.bigquery_client import get_bq_client
import numpy as np
from datetime import datetime, timezone


GENRE_LIST = [
    "pop","rock","hip-hop","r&b","k-pop","c-pop","j-pop","edm","indie",
    "acoustic","lo-fi","metal","classical","jazz","soundtrack",
    "melodic-rap","trap-rap","boom-bap","drill"
]

LANG_LIST = [
    "english","mandarin","cantonese","korean","japanese",
    "spanish","hindi","french","thai","vietnamese","others"
]


# ---------------------------
# 工具：one-hot encoding
# ---------------------------
def encode_one_hot(values, dictionary):
    vec = np.zeros(len(dictionary))
    for v in values:
        if v in dictionary:
            idx = dictionary.index(v)
            vec[idx] += 1
    return vec
# ======================================================
# 工具：安全處理 BigQuery array (避免 numpy truth-value error)
# ======================================================
def safe_array(value):
    """
    BigQuery array → numpy array / list / None
    全部安全轉換成 Python list
    """
    if value is None:
        return []

    # numpy array
    if isinstance(value, np.ndarray):
        return value.tolist()

    # already list
    if isinstance(value, list):
        return value

    # fallback: scalar
    return [value]


# ---------------------------
# 主功能：計算單一使用者向量
# ---------------------------
def compute_user_vector(user_id):
    client = get_bq_client()

    # ---- 取得各來源資料 ----
    tracks = client.query(f"""
        SELECT track_id, period
        FROM `spotify-match-project.user_event.user_top_tracks`
        WHERE user_id = '{user_id}'
    """).to_dataframe()

    artists = client.query(f"""
        SELECT artist_id, period
        FROM `spotify-match-project.user_event.user_top_artists`
        WHERE user_id = '{user_id}'
    """).to_dataframe()

    favorites = client.query(f"""
        SELECT track_id
        FROM `spotify-match-project.user_event.user_favorite_tracks`
        WHERE user_id = '{user_id}'
    """).to_dataframe()

    if tracks.empty and artists.empty and favorites.empty:
        return None

    # ---- 權重設定 ----
    period_weight = {
        "short_term": 1.3,
        "medium_term": 1.0,
        "long_term": 0.7
    }

    favorite_weight = 1.0

    style_acc = np.zeros(8)
    genre_acc = np.zeros(len(GENRE_LIST))
    lang_acc = np.zeros(len(LANG_LIST))

    total_weight = 0

    # ---- 處理 favorite tracks ----
    for _, row in favorites.iterrows():
        track_id = row["track_id"]

        feature = fetch_track_feature(client, track_id)
        if feature is None:
            continue

        w = favorite_weight
        style_acc += np.array(feature["style_vector"]) * w
        genre_acc += encode_one_hot(feature["genres"], GENRE_LIST) * w
        lang_acc += encode_one_hot(feature["languages"], LANG_LIST) * w
        total_weight += w

    # ---- 處理 top_tracks ----
    for _, row in tracks.iterrows():
        track_id = row["track_id"]
        weight = period_weight.get(row["period"], 1.0)

        feature = fetch_track_feature(client, track_id)
        if feature is None:
            continue

        style_acc += np.array(feature["style_vector"]) * weight
        genre_acc += encode_one_hot(feature["genres"], GENRE_LIST) * weight
        lang_acc += encode_one_hot(feature["languages"], LANG_LIST) * weight
        total_weight += weight

    # ---- 處理 top_artists ----
    for _, row in artists.iterrows():
        artist_id = row["artist_id"]
        weight = period_weight.get(row["period"], 1.0)

        feature = fetch_artist_feature(client, artist_id)
        if feature is None:
            continue

        style_acc += np.array(feature["style_vector"]) * weight
        genre_acc += encode_one_hot(feature["genres"], GENRE_LIST) * weight
        lang_acc += encode_one_hot(feature["languages"], LANG_LIST) * weight
        total_weight += weight

    # ---- 正規化 ----
    if total_weight == 0:
        return None

    style_vec = (style_acc / total_weight).tolist()
    genre_vec = (genre_acc / total_weight).tolist()
    lang_vec = (lang_acc / total_weight).tolist()

    return {
        "user_id": user_id,
        "style_vector": style_vec,
        "genre_vector": genre_vec,
        "language_vector": lang_vec,
        "total_interactions": int(total_weight),
        "last_update": datetime.now(timezone.utc).isoformat()
    }


# ---------------------------
# BigQuery Lookup Functions
# ---------------------------
def fetch_track_feature(client, track_id):
    df = client.query(f"""
        SELECT genres, languages, style_vector
        FROM `spotify-match-project.user_event.track_features`
        WHERE track_id = '{track_id}'
        LIMIT 1
    """).to_dataframe()

    if df.empty:
        return None

    row = df.iloc[0]
    return {
        "genres": safe_array(row.get("genres")),
        "languages": safe_array(row.get("languages")),
        "style_vector": safe_array(row.get("style_vector")),
    }


def fetch_artist_feature(client, artist_id):
    df = client.query(f"""
        SELECT genres, languages, style_vector
        FROM `spotify-match-project.user_event.artist_features`
        WHERE artist_id = '{artist_id}'
        LIMIT 1
    """).to_dataframe()

    if df.empty:
        return None

    row = df.iloc[0]
    return {
        "genres": safe_array(row.get("genres")),
        "languages": safe_array(row.get("languages")),
        "style_vector": safe_array(row.get("style_vector")),
    }


# ---------------------------
# 寫入 BigQuery
# ---------------------------
def save_user_vector(vector_data):
    client = get_bq_client()

    table = "spotify-match-project.user_event.user_preference_vectors"

    errors = client.insert_rows_json(table, [vector_data])
    if errors:
        print("BigQuery insert error:", errors)