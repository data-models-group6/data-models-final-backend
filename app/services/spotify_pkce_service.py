# app/services/spotify_pkce_service.py
import time
from typing import Optional
from app.services.firestore_client import get_db

PKCE_COLLECTION = "spotify_pkce_sessions"
PKCE_TTL_SECONDS = 600  # PKCE 有效 10 分鐘，可自行調整


def save_code_verifier(user_id: str, code_verifier: str) -> None:
    """
    將某個 user 本次 OAuth 的 code_verifier 存到 Firestore。
    如果 doc 不存在會新建；存在則覆蓋（只保留最後一次登入的 PKCE）。
    """
    db = get_db()
    now = int(time.time())
    db.collection(PKCE_COLLECTION).document(user_id).set(
        {
            "code_verifier": code_verifier,
            "created_at": now,
            "expires_at": now + PKCE_TTL_SECONDS,
        }
    )


def get_and_delete_code_verifier(user_id: str) -> Optional[str]:
    """
    從 Firestore 讀取該 user 的 code_verifier。
    - 若不存在 → 回傳 None
    - 若已過期 → 刪掉 doc，回傳 None
    - 若正常 → 回傳 code_verifier，並刪掉 doc（避免重複使用）
    """
    db = get_db()
    doc_ref = db.collection(PKCE_COLLECTION).document(user_id)
    doc = doc_ref.get()

    if not doc.exists:
        return None

    data = doc.to_dict()
    code_verifier = data.get("code_verifier")
    expires_at = data.get("expires_at")

    # 過期檢查
    now = int(time.time())
    if expires_at is not None and expires_at < now:
        # 過期就清掉，避免堆積
        doc_ref.delete()
        return None

    # 正常使用 → 讀完就刪
    doc_ref.delete()

    return code_verifier