# app/services/storage_client.py

import os
import base64
import json
from google.cloud import storage
from google.oauth2 import service_account
from app.config.settings import GCP_BUCKET_NAME
from datetime import timedelta

_cached_gcs_client = None


def get_gcs_client():
    """
    Lazy-load Storage client using service account credentials encoded in BASE64
    via environment variable GOOGLE_CLOUD_CREDENTIALS.

    和 firestore_client.py 的邏輯完全一致。
    """

    global _cached_gcs_client

    # 如果之前建立過 → 直接回傳
    if _cached_gcs_client is not None:
        return _cached_gcs_client

    # 讀取 BASE64 JSON
    raw = os.getenv("GOOGLE_CLOUD_CREDENTIALS")
    if not raw:
        raise Exception("Missing GOOGLE_CLOUD_CREDENTIALS in environment")

    try:
        creds_dict = json.loads(base64.b64decode(raw).decode("utf-8"))
    except Exception as e:
        raise Exception(f"Failed to decode GOOGLE_CLOUD_CREDENTIALS: {e}")

    try:
        credentials = service_account.Credentials.from_service_account_info(creds_dict)
    except Exception as e:
        raise Exception(f"Failed to create GCS credentials: {e}")

    try:
        _cached_gcs_client = storage.Client(
            credentials=credentials, project=credentials.project_id
        )
    except Exception as e:
        raise Exception(f"Failed to create GCS client: {e}")

    return _cached_gcs_client


def upload_avatar_to_gcs(user_id: str, file_bytes: bytes, content_type: str) -> str:
    """
    上傳使用者頭像到 GCS，並回傳公開網址。
    """
    client = get_gcs_client()
    bucket = client.bucket(GCP_BUCKET_NAME)

    blob = bucket.blob(f"avatars/{user_id}.png")
    blob.upload_from_string(file_bytes, content_type=content_type)

    # 測試階段，直接設成公開
    signed_url = blob.generate_signed_url(
        version="v4",
        expiration=timedelta(days=7),
        method="GET",
    )

    return signed_url