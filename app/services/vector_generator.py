# app/services/vector_generator.py
import json
import pandas as pd
from google.cloud import bigquery
import google.generativeai as genai

from app.services.bigquery_client import get_bq_client, insert_rows_json
from app.config.settings import BQ_PROJECT, BQ_DATASET, GEMINI_API_KEY
from datetime import datetime, timezone


def _now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
# =====================================
# 初始化
# =====================================

if not GEMINI_API_KEY:
    raise Exception("Missing GEMINI_API_KEY in environment variables")

genai.configure(api_key=GEMINI_API_KEY)
llm = genai.GenerativeModel("gemini-1.5-pro")

bq = get_bq_client()


# =====================================
# 抓還未建立向量的新歌曲
# =====================================
def fetch_new_tracks(batch_size=50):
    sql = f"""
    WITH union_tracks AS (
        SELECT track_id, track_name, artist_id, artist_name, popularity
        FROM `{BQ_PROJECT}.{BQ_DATASET}.user_favorite_tracks`
        WHERE track_id IS NOT NULL

        UNION DISTINCT

        SELECT track_id, track_name, artist_id, artist_name, popularity
        FROM `{BQ_PROJECT}.{BQ_DATASET}.user_top_tracks`
        WHERE track_id IS NOT NULL
    )
    SELECT u.*
    FROM union_tracks u
    LEFT JOIN `{BQ_PROJECT}.{BQ_DATASET}.track_features` t
        ON u.track_id = t.track_id
    WHERE t.track_id IS NULL
    LIMIT @limit
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("limit", "INT64", batch_size)]
    )

    return bq.query(sql, job_config=job_config).to_dataframe()


# =====================================
# 抓還未建立向量的新歌手
# =====================================
def fetch_new_artists(batch_size=50):
    sql = f"""
    WITH union_artists AS (
        SELECT artist_id, artist_name, popularity
        FROM `{BQ_PROJECT}.{BQ_DATASET}.user_top_artists`
        WHERE artist_id IS NOT NULL

        UNION DISTINCT

        SELECT artist_id, artist_name, popularity
        FROM `{BQ_PROJECT}.{BQ_DATASET}.user_favorite_tracks`
        WHERE artist_id IS NOT NULL
    )
    SELECT u.*
    FROM union_artists u
    LEFT JOIN `{BQ_PROJECT}.{BQ_DATASET}.artist_features` a
        ON u.artist_id = a.artist_id
    WHERE a.artist_id IS NULL
    LIMIT @limit
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("limit", "INT64", batch_size)]
    )

    return bq.query(sql, job_config=job_config).to_dataframe()


# =====================================
# Robust tracks Prompt
# =====================================
def build_track_prompt(df):
    songs_list = "\n".join([
        f"{i+1}. {row['track_id']} | {row['artist_name']} - {row['track_name']}"
        for i, row in df.iterrows()
    ])

    return f"""
You are a professional music curator and embedding designer.
Your task is to assign a stable 5-dimensional numeric vector to each song,
so that similar songs in terms of style and mood have similar vectors.

For EACH song below, output a JSON object with:
- "track_id": the Spotify track ID
- "track_name": the track name (as given)
- "artist_name": the artist name (as given)
- "vector": a list of 5 floats between 0.0 and 1.0 (inclusive), in this exact order:

Vector dimensions (in order):
1. energy      (0.0 = very calm / slow, 1.0 = very energetic / hype)
2. valence     (0.0 = dark / sad, 1.0 = bright / happy)
3. mainstream  (0.0 = indie / niche, 1.0 = very mainstream pop hit)
4. modern      (0.0 = vintage / old-school, 1.0 = very modern / current)
5. vocal       (0.0 = mostly instrumental, 1.0 = very vocal-focused)

Rules:
- Always produce 5 floats between 0.0 and 1.0 for each "vector".
- If you are uncertain about a song, make your best guess based on the artist and title.
- Keep the relative relationships consistent.
- Follow the input order exactly.
- Output strictly a JSON array with no explanations.

Songs:
{songs_list}
"""


# =====================================
# Robust Artists Prompt
# =====================================
def build_artist_prompt(df):
    artist_list = "\n".join([
        f"{i+1}. {row['artist_id']} | {row['artist_name']} | popularity={row['popularity']}"
        for i, row in df.iterrows()
    ])

    return f"""
You are a professional music curator and embedding designer.
Your task is to assign a stable 5-dimensional numeric vector to each artist,
representing the typical musical style of their discography.

For EACH artist below, output a JSON object with:
- "artist_id": the Spotify artist ID
- "artist_name": the artist name (as given)
- "vector": a list of 5 floats between 0.0 and 1.0 (inclusive), in this exact order:

Vector dimensions (in order):
1. energy      (0.0 = very calm / slow, 1.0 = very energetic / hype)
2. valence     (0.0 = dark / sad, 1.0 = bright / happy)
3. mainstream  (0.0 = indie / niche, 1.0 = very mainstream pop artist)
4. modern      (0.0 = old-school / classic, 1.0 = very modern / current)
5. vocal       (0.0 = mostly instrumental, 1.0 = very vocal-focused)

Interpretation:
- Consider their overall career, not one specific track.
- If an artist spans diverse genres, approximate an average.
- Use general music knowledge, genre, and public perception.

Rules:
- Always output 5 floats between 0.0 and 1.0.
- Keep vectors consistent across similar artists.
- Follow input order exactly.
- Output strictly a JSON array with no explanations.

Artists:
{artist_list}
"""


# =====================================
# 呼叫 Gemini
# =====================================
def ask_llm(prompt: str):
    resp = llm.generate_content(prompt)
    text = resp.text.strip()
    return json.loads(text)



# =====================================
# 寫入 track_features
# =====================================
def insert_track_vectors(results, df_original):
    now = _now()
    rows = []
    for item in results:
        tid = item["track_id"]
        src = df_original[df_original.track_id == tid].iloc[0]

        rows.append({
            "track_id": tid,
            "track_name": item["track_name"],
            "artist_id": src["artist_id"],
            "artist_name": src["artist_name"],
            "primary_language": None,
            "languages": [],
            "genres": [],
            "popularity": int(src.get("popularity") or 0),
            "style_vector": item["vector"],
            "created_at": now,
            "updated_at": now
        })

    insert_rows_json("track_features", rows)


# =====================================
# 寫入 artist_features
# =====================================
def insert_artist_vectors(results, df_original):
    now = _now()
    rows = []
    for item in results:
        aid = item["artist_id"]
        src = df_original[df_original.artist_id == aid].iloc[0]

        rows.append({
            "artist_id": aid,
            "artist_name": item["artist_name"],
            "primary_language": None,
            "languages": [],
            "genres": [],
            "popularity": int(src.get("popularity") or 0),
            "followers": None,
            "style_vector": item["vector"],
            "created_at": now,
            "updated_at": now
        })

    insert_rows_json("artist_features", rows)


# =====================================
# 主流程（批次，會重複跑直到沒資料）
# =====================================
def run_batch_generation(batch_size=50, max_rounds=20):
    """
    1. 每次抓 batch_size 筆資料
    2. LLM 生成向量
    3. 寫入 BigQuery
    4. 直到沒有資料 or 達到 max_rounds
    """
    round_count = 0

    while round_count < max_rounds:
        round_count += 1

        new_tracks = fetch_new_tracks(batch_size)
        if new_tracks.empty:
            break

        prompt = build_track_prompt(new_tracks)
        results = ask_llm(prompt)
        insert_track_vectors(results, new_tracks)

    round_count = 0
    while round_count < max_rounds:
        round_count += 1

        new_artists = fetch_new_artists(batch_size)
        if new_artists.empty:
            break

        prompt = build_artist_prompt(new_artists)
        results = ask_llm(prompt)
        insert_artist_vectors(results, new_artists)