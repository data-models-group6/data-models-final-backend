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
llm = genai.GenerativeModel("gemini-2.0-flash")

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
Your task is to classify each song below in terms of:
1. an 8-dimensional style vector
2. its main language and additional languages
3. its genres chosen from a fixed 15-genre list.

For EACH song below, output a JSON object with:
- "track_id": the Spotify track ID
- "track_name": the track name (as given)
- "artist_name": the artist name (as given)
- "primary_language": one main language
- "languages": 1–3 languages from the allowed list
- "genres": 2–3 genres from the fixed genre list
- "style_vector": the 8-dimensional vector (floats 0–1)

===============================
LANGUAGE CLASSIFICATION RULES
===============================
For each song:

- Choose EXACTLY one "primary_language".
- Choose 1–3 values for "languages" from this list:

english, mandarin, cantonese, korean, japanese,
spanish, hindi, french, thai, vietnamese, others

If you are unsure, choose "others" as one of the values.

===============================
GENRE CLASSIFICATION RULES
===============================
For each song:

- Choose 2–3 genres from the fixed list below.
- Genres MUST come ONLY from this list:

pop, rock, hip-hop, r&b, k-pop, c-pop, j-pop, edm, indie,
acoustic, lo-fi, metal, classical, jazz, soundtrack,
melodic-rap, trap-rap, boom-bap, drill

Choose genres that best represent their discography.
===============================
STYLE VECTOR (8 DIMENSIONS)
===============================
For each song, output "style_vector" as a list of 8 floats
between 0.0 and 1.0 (inclusive), in THIS EXACT ORDER:

1. energy
   - 0.0 = very calm / slow / low intensity
   - 1.0 = very energetic / loud / high intensity

2. valence
   - 0.0 = very dark / sad / negative mood
   - 1.0 = very bright / happy / positive mood

3. danceability
   - 0.0 = not suitable for dancing (irregular rhythm, weak beat)
   - 1.0 = very suitable for dancing (strong beat, stable groove)

4. acousticness
   - 0.0 = purely electronic / synthetic
   - 1.0 = fully acoustic / organic instruments

5. instrumentalness
   - 0.0 = clearly vocal-focused (singing, rap, spoken words)
   - 1.0 = purely instrumental (almost no human voice)

6. speechiness
   - 0.0 = almost no spoken words (typical songs)
   - 1.0 = mostly speech (podcast, talk, rap with dense words)

7. tempo_norm
   - A normalized tempo indicator (NOT the BPM itself).
   - 0.0 = very slow feeling, 1.0 = very fast feeling.

8. mainstream
   - 0.0 = niche / underground / indie
   - 1.0 = very mainstream / chart-hit style

===============================
OUTPUT FORMAT (STRICT)
===============================
Return STRICTLY a JSON array.
Each element MUST be a JSON object of the form:

{{
  "track_id": "...",
  "track_name": "...",
  "artist_name": "...",
  "primary_language": "english",
  "languages": ["english", "japanese"],
  "genres": ["pop", "edm"],
  "style_vector": [0.60, 0.75, 0.80, 0.20, 0.10, 0.15, 0.65, 0.90]
}}

Requirements:
- All 8 values in "style_vector" must be floats in [0.0, 1.0].
- Follow the input song order exactly.
- Do NOT add comments, explanations, or extra keys.
- Output must be a valid JSON array only.

===============================
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
Your task is to classify each artist below in terms of:
1. an 8-dimensional style vector representing their overall discography
2. the main language and additional languages commonly associated with their music
3. their genres chosen from a fixed 18-genre list.

For EACH artist below, output a JSON object with:
- "artist_id": the Spotify artist ID
- "artist_name": the artist name (as given)
- "primary_language": one main language
- "languages": 1–3 languages from the allowed list
- "genres": 2–3 genres from the fixed genre list
- "style_vector": the 8-dimensional vector (floats 0–1)
===============================
LANGUAGE CLASSIFICATION RULES
===============================
For each artist:

- Choose EXACTLY one "primary_language".
- Choose 1–3 values for "languages" from this list:

english, mandarin, cantonese, korean, japanese,
spanish, hindi, french, thai, vietnamese, others

If you are unsure, include "others".

===============================
GENRE CLASSIFICATION RULES
===============================
For each artist:

- Choose 2–3 genres that best represent their overall discography.
- Genres MUST come ONLY from this list:

pop, rock, hip-hop, r&b, k-pop, c-pop, j-pop, edm, indie,
acoustic, lo-fi, metal, classical, jazz, soundtrack,
melodic-rap, trap-rap, boom-bap, drill

===============================
STYLE VECTOR (8 DIMENSIONS)
===============================
For each artist, output "style_vector" as a list of 8 floats
between 0.0 and 1.0 (inclusive), in THIS EXACT ORDER:

1. energy
   - 0.0 = very calm / slow / low intensity
   - 1.0 = very energetic / loud / high intensity

2. valence
   - 0.0 = very dark / sad / negative emotion
   - 1.0 = very bright / happy / positive emotion

3. danceability
   - 0.0 = not danceable (weak beat, irregular rhythm)
   - 1.0 = very danceable (strong beat, steady rhythm)

4. acousticness
   - 0.0 = mainly electronic / synthetic sound
   - 1.0 = primarily acoustic instrumentation

5. instrumentalness
   - 0.0 = strongly vocal-driven (singing, rap)
   - 1.0 = mostly instrumental music

6. speechiness
   - 0.0 = minimal spoken words
   - 1.0 = heavy spoken-word content (rap, talk, narration)

7. tempo_norm
   - 0.0 = very slow-feeling music
   - 1.0 = very fast-feeling music

8. mainstream
   - 0.0 = niche / underground / indie
   - 1.0 = very mainstream / widely commercial
===============================
OUTPUT FORMAT (STRICT)
===============================
Return STRICTLY a JSON array.
Each element MUST be a JSON object of the form:

{{
  "artist_id": "...",
  "artist_name": "...",
  "primary_language": "english",
  "languages": ["english", "french"],
  "genres": ["pop", "edm"],
  "style_vector": [0.50, 0.60, 0.80, 0.20, 0.05, 0.10, 0.70, 0.90]
}}

Requirements:
- All 8 values in "style_vector" must be floats in [0.0, 1.0].
- Follow the input artist order exactly.
- Do NOT add comments, explanations, or extra keys.
- Output must be a valid JSON array only.

===============================
Artists:
{artist_list}
"""


# =====================================
# 呼叫 Gemini
# =====================================
def ask_llm(prompt: str):
    """
    呼叫 Gemini，強制要求回傳純 JSON。
    如果回傳不是合法 JSON，印出原始內容方便 debug。
    """
    response = llm.generate_content(
        prompt,
        generation_config={
            "response_mime_type": "application/json"
        }
    )
    text = (response.text or "").strip()

    if not text:
        # 這種情況多半是被 safety block 或其他錯誤
        raise Exception("Gemini 回傳空內容（可能是 safety block），無法解析 JSON")
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        # 直接把原始輸出印出來，之後你可以看 BigQuery / log 分析
        print("==== Raw LLM Output (for debug) ====")
        print(repr(text))
        print("====================================")
        raise



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
            "primary_language": item["primary_language"],
            "languages": item["languages"],
            "genres": item["genres"],
            "popularity": int(src.get("popularity") or 0),
            "style_vector": item["style_vector"],
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
            "primary_language": item["primary_language"],
            "languages": item["languages"],
            "genres": item["genres"],
            "popularity": int(src.get("popularity") or 0),
            "style_vector": item["style_vector"],
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