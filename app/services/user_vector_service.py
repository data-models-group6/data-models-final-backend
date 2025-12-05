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

    # 1. 讀取 user 的資料
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

    # 2. 一次查所有 track_features / artist_features
    all_track_ids = set(tracks["track_id"].tolist()) | set(favorites["track_id"].tolist())
    all_artist_ids = set(artists["artist_id"].tolist())

    track_features = fetch_track_features(client, list(all_track_ids))
    artist_features = fetch_artist_features(client, list(all_artist_ids))

    # 3. 權重
    period_weight = {"short_term": 1.3, "medium_term": 1.0, "long_term": 0.7}
    favorite_weight = 1.0

    style_acc = np.zeros(8)
    genre_acc = np.zeros(len(GENRE_LIST))
    lang_acc = np.zeros(len(LANG_LIST))
    total_weight = 0

    # ================================
    # Favorite Tracks
    # ================================
    for _, row in favorites.iterrows():
        f = track_features.get(row["track_id"])
        if f is None:
            continue

        w = favorite_weight
        style_acc += np.array(f["style_vector"]) * w
        genre_acc += encode_one_hot(f["genres"], GENRE_LIST) * w
        lang_acc += encode_one_hot(f["languages"], LANG_LIST) * w
        total_weight += w

    # ================================
    # Top Tracks
    # ================================
    for _, row in tracks.iterrows():
        f = track_features.get(row["track_id"])
        if f is None:
            continue

        w = period_weight.get(row["period"], 1.0)
        style_acc += np.array(f["style_vector"]) * w
        genre_acc += encode_one_hot(f["genres"], GENRE_LIST) * w
        lang_acc += encode_one_hot(f["languages"], LANG_LIST) * w
        total_weight += w

    # ================================
    # Top Artists
    # ================================
    for _, row in artists.iterrows():
        f = artist_features.get(row["artist_id"])
        if f is None:
            continue

        w = period_weight.get(row["period"], 1.0)
        style_acc += np.array(f["style_vector"]) * w
        genre_acc += encode_one_hot(f["genres"], GENRE_LIST) * w
        lang_acc += encode_one_hot(f["languages"], LANG_LIST) * w
        total_weight += w

    # ================================
    # 正規化
    # ================================
    if total_weight == 0:
        return None

    return {
        "user_id": user_id,
        "style_vector": (style_acc / total_weight).tolist(),
        "genre_vector": (genre_acc / total_weight).tolist(),
        "language_vector": (lang_acc / total_weight).tolist(),
        "total_interactions": int(round(total_weight)),
        "last_update": datetime.now(timezone.utc).isoformat()
    }


# ---------------------------
# BigQuery Lookup Functions
# ---------------------------
def fetch_track_features(client, track_ids):
    if not track_ids:
        return {}

    ids_str = ",".join([f"'{tid}'" for tid in track_ids])

    df = client.query(f"""
        SELECT track_id, genres, languages, style_vector
        FROM `spotify-match-project.user_event.track_features`
        WHERE track_id IN ({ids_str})
    """).to_dataframe()

    result = {}
    for _, row in df.iterrows():
        result[row["track_id"]] = {
            "genres": safe_array(row.get("genres")),
            "languages": safe_array(row.get("languages")),
            "style_vector": safe_array(row.get("style_vector")),
        }
    return result


def fetch_artist_features(client, artist_ids):
    if not artist_ids:
        return {}

    ids_str = ",".join([f"'{aid}'" for aid in artist_ids])

    df = client.query(f"""
        SELECT artist_id, genres, languages, style_vector
        FROM `spotify-match-project.user_event.artist_features`
        WHERE artist_id IN ({ids_str})
    """).to_dataframe()

    result = {}
    for _, row in df.iterrows():
        result[row["artist_id"]] = {
            "genres": safe_array(row.get("genres")),
            "languages": safe_array(row.get("languages")),
            "style_vector": safe_array(row.get("style_vector")),
        }
    return result


# ---------------------------
# 寫入 BigQuery
# ---------------------------
def save_user_vector(vector_data):
    """
    使用 BigQuery MERGE 寫入（Upsert）
    - 若 user_id 已存在 → UPDATE
    - 若不存在 → INSERT
    """

    client = get_bq_client()
    table = "spotify-match-project.user_event.user_preference_vectors"

    # --- 轉換 Python list → BigQuery ARRAY 格式 ---
    style_vec = ",".join([str(v) for v in vector_data["style_vector"]])
    genre_vec = ",".join([str(v) for v in vector_data["genre_vector"]])
    lang_vec = ",".join([str(v) for v in vector_data["language_vector"]])

    # total_interactions：轉成 INT，避免型別衝突
    total_interactions_int = int(round(float(vector_data["total_interactions"])))

    sql = f"""
    MERGE `{table}` T
    USING (
        SELECT
            '{vector_data["user_id"]}' AS user_id,
            ARRAY[{style_vec}] AS style_vector,
            ARRAY[{genre_vec}] AS genre_vector,
            ARRAY[{lang_vec}] AS language_vector,
            {total_interactions_int} AS total_interactions,
            TIMESTAMP('{vector_data["last_update"]}') AS last_update
    ) S
    ON T.user_id = S.user_id

    WHEN MATCHED THEN
      UPDATE SET
        style_vector = S.style_vector,
        genre_vector = S.genre_vector,
        language_vector = S.language_vector,
        total_interactions = S.total_interactions,
        last_update = S.last_update

    WHEN NOT MATCHED THEN
      INSERT (user_id, style_vector, genre_vector, language_vector, total_interactions, last_update)
      VALUES (S.user_id, S.style_vector, S.genre_vector, S.language_vector, S.total_interactions, S.last_update)
    """

    try:
        client.query(sql).result()
        print(f"[OK] Upserted preference vector for user {vector_data['user_id']}")
    except Exception as e:
        print("BigQuery MERGE error:", e)
        raise