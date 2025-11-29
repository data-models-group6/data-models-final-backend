# app/services/auth_service.py

# 目前沒用，jwt目前是存在前端用 JWT decode 的方式運作（Stateless Auth）
# from google.cloud import firestore
# from datetime import datetime

# DB = firestore.Client(database="(default)")


# def save_refresh_token(user_id: str, refresh_token: str, expires_at: int):
#     DB.collection("user_auth").document(user_id).set({
#         "refresh_token": refresh_token,
#         "expires_at": expires_at,
#         "last_login": datetime.utcnow()
#     })


# def get_refresh_token(user_id: str):
#     doc = DB.collection("user_auth").document(user_id).get()
#     return doc.to_dict() if doc.exists else None