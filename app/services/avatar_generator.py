# app/services/avatar_generator.py

import os
import base64
import json
from typing import Dict, Any, List, Tuple
from google.cloud import bigquery
from google.oauth2 import service_account
from app.services.bigquery_client import get_bq_client
from app.services.storage_client import upload_avatar_to_gcs
from app.services.firestore_client import get_db
from app.config.settings import BQ_PROJECT, BQ_DATASET

import vertexai
from vertexai.preview.vision_models import ImageGenerationModel


# ======================================================
# 1. 取得 service account credentials，給 Vertex AI 用
# ======================================================
def _get_sa_credentials():
    raw = os.getenv("GOOGLE_CLOUD_CREDENTIALS")
    if not raw:
        raise Exception("GOOGLE_CLOUD_CREDENTIALS missing for Vertex AI")

    try:
        creds_json = json.loads(base64.b64decode(raw))
        creds = service_account.Credentials.from_service_account_info(creds_json)
        return creds
    except Exception as e:
        raise Exception(f"Failed to load SA credentials for Vertex AI: {e}")


_image_model = None


def _get_image_model():
    """
    Lazy-init Vertex AI image 生成模型。

    location 預設 us-central1，如果你想放亞洲，
    可以在 Render / 本機 .env 設定：
        VERTEX_LOCATION=asia-east1  (或官方文件支援的其他 asia region)
    """
    global _image_model

    if _image_model is not None:
        return _image_model

    creds = _get_sa_credentials()
    project_id = creds.project_id
    location = os.getenv("VERTEX_LOCATION", "us-central1")

    # 初始化 Vertex AI
    vertexai.init(project=project_id, location=location, credentials=creds)

    # 載入預訓練 image generation 模型
    _image_model = ImageGenerationModel.from_pretrained("imagegeneration@002")
    return _image_model


# ======================================================
# 2. 從 BigQuery 抓 user_preference_vectors
# ======================================================
def fetch_user_preference_vector(user_id: str) -> Dict[str, Any]:
    """
    從 spotify-match-project.user_event.user_preference_vectors
    抓出指定 user_id 的 style / genre / language 向量。
    """
    client = get_bq_client()
    table = f"`{BQ_PROJECT}.{BQ_DATASET}.user_preference_vectors`"

    sql = f"""
        SELECT style_vector, genre_vector, language_vector
        FROM {table}
        WHERE user_id = @user_id
        LIMIT 1
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("user_id", "STRING", user_id)
        ]
    )
    df = client.query(sql, job_config=job_config).to_dataframe()

    if df.empty:
        raise ValueError(f"user_preference_vectors: no row for user_id={user_id}")

    row = df.iloc[0]

    def _safe(v) -> List[float]:
        if v is None:
            return []
        if isinstance(v, list):
            return v
        return list(v)

    return {
        "style_vector": _safe(row.get("style_vector")),
        "genre_vector": _safe(row.get("genre_vector")),
        "language_vector": _safe(row.get("language_vector")),
    }


def fetch_all_user_ids(limit: int | None = None) -> List[str]:
    """
    從 user_preference_vectors 抓出所有 user_id（1 row 就 1 個 user）。
    如果有 limit，就只取前 N 個，方便測試。
    """
    client = get_bq_client()
    table = f"`{BQ_PROJECT}.{BQ_DATASET}.user_preference_vectors`"

    sql = f"SELECT user_id FROM {table}"
    if limit is not None:
        sql += f" LIMIT {int(limit)}"

    df = client.query(sql).to_dataframe()
    return df["user_id"].dropna().astype(str).tolist()


# ======================================================
# 3. 把向量轉成 Avatar prompt
# ======================================================
GENRE_LIST = [
    "pop", "rock", "hip-hop", "r&b", "k-pop", "c-pop", "j-pop", "edm", "indie",
    "acoustic", "lo-fi", "metal", "classical", "jazz", "soundtrack",
    "melodic-rap", "trap-rap", "boom-bap", "drill",
]

LANG_LIST = [
    "english", "mandarin", "cantonese", "korean", "japanese",
    "spanish", "hindi", "french", "thai", "vietnamese", "others",
]


def _pick_max_index(vec: List[float]) -> int:
    if not vec:
        return 0
    return max(range(len(vec)), key=lambda i: vec[i])


def build_avatar_prompt_from_vector(vec: Dict[str, Any]) -> str:
    """
    依照 style/genre/language 三個向量，組一段 Vertex AI 圖像生成 prompt。
    風格：像素風 Q 版角色。
    主體：用不同動物代表不同主流曲風。
    """
    style = vec["style_vector"]
    genre = vec["genre_vector"]
    lang = vec["language_vector"]

    # style_vector: [energy, valence, danceability, acousticness,
    #                instrumentalness, speechiness, tempo_norm, mainstream]
    energy = style[0] if len(style) > 0 else 0.5
    valence = style[1] if len(style) > 1 else 0.5
    dance = style[2] if len(style) > 2 else 0.5
    acoustic = style[3] if len(style) > 3 else 0.5
    mainstream = style[7] if len(style) > 7 else 0.5

    # 1) 動物依主要曲風決定
    main_genre_idx = _pick_max_index(genre)
    main_genre = GENRE_LIST[main_genre_idx]

    genre2animal = {
        "pop": "cat",
        "c-pop": "cat",
        "k-pop": "fox",
        "j-pop": "red panda",
        "hip-hop": "wolf",
        "trap-rap": "wolf",
        "melodic-rap": "fox",
        "rock": "lion",
        "metal": "dragon",
        "indie": "deer",
        "lo-fi": "bear",
        "edm": "robot cat",
        "acoustic": "dog",
        "classical": "owl",
        "jazz": "tiger",
        "soundtrack": "hawk",
        "boom-bap": "raccoon",
        "drill": "panther",
    }
    animal = genre2animal.get(main_genre, "cat")

    # 2) 氣氛
    if valence > 0.65:
        mood = "happy and bright"
        color_tone = "warm pastel colors"
    elif valence < 0.35:
        mood = "melancholic but cool"
        color_tone = "cool blue and purple"
    else:
        mood = "chill and relaxed"
        color_tone = "neutral soft colors"

    # 3) 動作 / 場景
    if energy > 0.7 or dance > 0.7:
        action = "dancing with big headphones"
    elif acoustic > 0.6:
        action = "playing an acoustic guitar"
    else:
        action = "listening to music with headphones"

    # 4) 語言決定小細節
    main_lang_idx = _pick_max_index(lang)
    main_lang = LANG_LIST[main_lang_idx]

    if main_lang in ["korean", "japanese"]:
        outfit = "streetwear outfit inspired by East Asian fashion"
    elif main_lang in ["mandarin", "cantonese"]:
        outfit = "modern casual outfit with subtle East Asian elements"
    else:
        outfit = "casual hoodie and sneakers"

    # 5) mainstream 決定「主流 / 獨立」風格
    if mainstream > 0.7:
        style_desc = "very polished like a popular game character"
    elif mainstream < 0.3:
        style_desc = "slightly indie and quirky style"
    else:
        style_desc = "modern and stylish look"

    # 最終 prompt（像素風、Q 版、統一系列）
    prompt = (
        f"a cute pixel art avatar of an anthropomorphic {animal}, "
        f"{mood}, {action}, {outfit}, {style_desc}, "
        f"{color_tone}, 2D pixel art, clean background, "
        f"centered composition, ultra simple background, no text"
    )

    return prompt


# ======================================================
# 4. 呼叫 Vertex AI 產生圖片 → 回傳 bytes
# ======================================================
def generate_avatar_bytes(user_id: str) -> bytes:
    # 1) 抓向量
    vec = fetch_user_preference_vector(user_id)

    # 2) 組 prompt
    prompt = build_avatar_prompt_from_vector(vec)

    # 3) 呼叫 Vertex AI 圖像模型
    model = _get_image_model()

    images = model.generate_images(
    prompt=prompt,
    number_of_images=1,
    safety_settings={
        "HARASSMENT": "BLOCK_SOME",
        "HATE_SPEECH": "BLOCK_SOME",
        "DANGEROUS_CONTENT": "BLOCK_SOME",
        "SEXUAL_CONTENT": "BLOCK_SOME",
        "VIOLENCE": "BLOCK_SOME",
    }
)

    if not images:
        raise Exception("Vertex AI did not return any image")

    img = images[0]

    # 不同版本 SDK image_bytes 欄位名稱可能不同，這裡做個兼容
    image_bytes = getattr(img, "image_bytes", None)
    if image_bytes is None:
        image_bytes = getattr(img, "_image_bytes", None)

    if image_bytes is None:
        raise Exception("Cannot extract image bytes from Vertex AI image object")

    return image_bytes


# ======================================================
# 5. 單一使用者：生成圖片 + 上傳 GCS + 更新 Firestore
# ======================================================
def generate_and_save_avatar(user_id: str) -> str:
    """
    主要給 API 或批次程式用的高階函式：
    1. 用 user_preference_vectors 向量生成頭貼
    2. 上傳 GCS avatars/{user_id}.png
    3. 更新 Firestore users/{user_id}.avatarUrl
    4. 回傳 avatarUrl
    """
    # 1) 生成圖片 bytes
    img_bytes = generate_avatar_bytes(user_id)

    # 2) 上傳到 GCS
    avatar_url = upload_avatar_to_gcs(
        user_id=user_id,
        file_bytes=img_bytes,
        content_type="image/png",
    )

    # 3) Firestore 更新該使用者的 avatarUrl
    db = get_db()
    (
        db.collection("users")
        .document(user_id)
        .set({"avatarUrl": avatar_url}, merge=True)
    )

    return avatar_url


# ======================================================
# 6. 批次：從 BigQuery 抓全部 user_id，逐一生成頭貼
# ======================================================
def bulk_generate_and_save_avatars(limit: int | None = None) -> Tuple[int, int]:
    """
    不用 JWT，直接從 user_preference_vectors 抓 user_id 批次生圖。

    :param limit: 若有值，只處理前 N 個 user，方便測試。
    :return: (成功數, 失敗數)
    """
    user_ids = fetch_all_user_ids(limit=limit)

    success = 0
    failed = 0

    for uid in user_ids:
        try:
            print(f"[Avatar] Generating avatar for user_id={uid}")
            generate_and_save_avatar(uid)
            success += 1
        except Exception as e:
            print(f"[Avatar] Failed for user_id={uid}: {e}")
            failed += 1

    print(f"[Avatar] Done. success={success}, failed={failed}")
    return success, failed