# app/services/storage_client.py
from google.cloud import storage
from app.config.settings import GCP_BUCKET_NAME

# 會使用 GOOGLE_APPLICATION_CREDENTIALS 那個 json
storage_client = storage.Client()

def upload_avatar_to_gcs(user_id: str, file_bytes: bytes, content_type: str) -> str:
    """
    把使用者頭像上傳到 GCS，回傳公開網址
    """
    bucket = storage_client.bucket(GCP_BUCKET_NAME)
    blob = bucket.blob(f"avatars/{user_id}.jpg")

    blob.upload_from_string(file_bytes, content_type=content_type)

    # 開發階段：直接設成公開
    blob.make_public()

    return blob.public_url