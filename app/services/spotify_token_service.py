# # app/services/spotify_token_service.py
# import time
# import requests
# from typing import Optional, Dict

# from google.cloud import firestore
# from app.config.settings import CLIENT_ID, CLIENT_SECRET

# # Firestore 設定：auth-db 裡的 tokens 集合
# AUTH_DB_ID = "auth-db"
# TOKENS_COLLECTION = "tokens"


# def _get_firestore_client() -> firestore.Client:
#     """
#     回傳指向 auth-db 的 Firestore client。
#     會使用 GOOGLE_APPLICATION_CREDENTIALS 做認證。
#     """
#     return firestore.Client(database=AUTH_DB_ID)


# # ========== 1. 寫入 Token 到 Firestore ==========

# def save_token_firestore(user_id: str, token_data: Dict) -> None:
#     """
#     將某個 user 的 Spotify token 存到 Firestore。
#     """
#     db = _get_firestore_client()
#     doc_ref = db.collection(TOKENS_COLLECTION).document(user_id)
#     doc_ref.set(token_data)


# # ========== 2. 讀取 Token ==========

# def get_user_token(user_id: str) -> Optional[Dict]:
#     """
#     從 Firestore 讀取某個 user 的 Spotify token。
#     若不存在，回傳 None。
#     """
#     db = _get_firestore_client()
#     doc_ref = db.collection(TOKENS_COLLECTION).document(user_id)
#     doc = doc_ref.get()

#     if not doc.exists:
#         return None

#     return doc.to_dict()


# # ========== 3. 檢查 / 自動 refresh ==========

# def refresh_user_token(user_id: str) -> Optional[Dict]:
#     """
#     取得某個 user 的 token，若快過期則自動 refresh。
#     回傳「可用的 token dict」，若 user 尚未綁定 Spotify 或 refresh 失敗則回傳 None。
#     """
#     token = get_user_token(user_id)
#     if not token:
#         print(f"[SpotifyToken] No token found for user: {user_id}")
#         return None

#     now = int(time.time())
#     expires_at = token.get("expires_at", 0)

#     # 還剩 > 30 秒就當成有效，直接用
#     if expires_at > now + 30:
#         return token

#     # 已過期 → 用 refresh_token 換新的
#     refresh_token = token.get("refresh_token")
#     if not refresh_token:
#         print(f"[SpotifyToken] No refresh_token for user: {user_id}")
#         return None

#     url = "https://accounts.spotify.com/api/token"
#     payload = {
#         "grant_type": "refresh_token",
#         "refresh_token": refresh_token,
#         "client_id": CLIENT_ID,
#         "client_secret": CLIENT_SECRET,
#     }

#     r = requests.post(url, data=payload)
#     new_token = r.json()

#     if "access_token" not in new_token:
#         print(f"[SpotifyToken] Refresh failed for user {user_id}: {new_token}")
#         return None

#     # Spotify 不一定會回傳新的 refresh_token，沒給就沿用舊的
#     if "refresh_token" not in new_token:
#         new_token["refresh_token"] = refresh_token

#     # 計算新的過期時間（預設 3600 秒）
#     new_token["expires_at"] = int(time.time()) + new_token.get("expires_in", 3600)

#     # 存回 Firestore
#     save_token_firestore(user_id, new_token)

#     return new_token
# app/services/spotify_token_service.py
import time
import requests
from typing import Optional, Dict

from google.cloud import firestore
from app.config.settings import CLIENT_ID, CLIENT_SECRET

AUTH_DB_ID = "auth-db"
TOKENS_COLLECTION = "tokens"


def _get_firestore_client() -> firestore.Client:
    """連線到 auth-db"""
    return firestore.Client(database=AUTH_DB_ID)


def save_token_firestore(user_id: str, token_data: Dict) -> None:
    """將 token 存進 Firestore"""
    db = _get_firestore_client()
    doc_ref = db.collection(TOKENS_COLLECTION).document(user_id)
    doc_ref.set(token_data)


def get_user_token(user_id: str) -> Optional[Dict]:
    """取得某 user 的 token"""
    db = _get_firestore_client()
    doc_ref = db.collection(TOKENS_COLLECTION).document(user_id)
    doc = doc_ref.get()
    if not doc.exists:
        return None
    return doc.to_dict()


def refresh_user_token(user_id: str) -> Optional[Dict]:
    """自動 refresh Spotify token"""
    token = get_user_token(user_id)
    if not token:
        return None

    now = int(time.time())
    if token["expires_at"] > now + 30:
        return token

    refresh_token = token.get("refresh_token")
    if not refresh_token:
        return None

    url = "https://accounts.spotify.com/api/token"
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }

    r = requests.post(url, data=payload)
    new_token = r.json()

    if "access_token" not in new_token:
        return None

    if "refresh_token" not in new_token:
        new_token["refresh_token"] = refresh_token

    new_token["expires_at"] = int(time.time()) + new_token.get("expires_in", 3600)

    save_token_firestore(user_id, new_token)
    return new_token