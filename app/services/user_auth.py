# # app/services/user_auth.py
# import firebase_admin
# from firebase_admin import auth, credentials
# from fastapi import HTTPException, Header

# ======= 測試版本：完全不使用 Firebase ========

def get_current_user():
    """
    測試期間：永遠回傳固定 user_id
    未來要接登入系統（PostgreSQL / Firebase）再改。
    """
    return {
        "user_id": "test_user_001"
    }
# # =============================================
# # 1. 初始化 Firebase Admin
# # =============================================
# try:
#     firebase_admin.get_app()
# except ValueError:
#     cred = credentials.Certificate("credentials/firebase-adminsdk.json")
#     firebase_admin.initialize_app(cred)


# # =============================================
# # 2. 從 Authorization Bearer Token 解析 Firebase User
# # =============================================
# def get_current_user(authorization: str = Header(None)):
#     """
#     從 header: Authorization: Bearer <id_token>
#     解出 Firebase 使用者資料。

#     回傳:
#     {
#         "user_id": "<firebase_uid>",
#         "email": "...",
#         "name": "..."
#     }
#     """

#     if not authorization:
#         raise HTTPException(status_code=401, detail="Missing Authorization header")

#     if not authorization.startswith("Bearer "):
#         raise HTTPException(status_code=401, detail="Invalid Authorization header")

#     id_token = authorization.split(" ")[1]

#     try:
#         decoded = auth.verify_id_token(id_token)
#         return {
#             "user_id": decoded["uid"],
#             "email": decoded.get("email"),
#             "name": decoded.get("name"),
#         }
#     except Exception:
#         raise HTTPException(status_code=401, detail="Invalid Firebase ID token")