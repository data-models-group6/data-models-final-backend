# app/services/user_auth.py
import jwt
from fastapi import HTTPException, Header
from google.cloud import firestore
from app.config.settings import JWT_SECRET

JWT_ALGORITHM = "HS256"

def get_current_user(authorization: str = Header(None)):
    """
    從 Authorization: Bearer <JWT token> 解析 user_id
    然後在 Firestore (default) 讀取該 user's 資料
    """

    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid token format")

    token = authorization.split(" ")[1]

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("user_id")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    # 🔥 改成使用 (default) Firestore
    db = firestore.Client(database="(default)")
    doc = db.collection("users").document(user_id).get()

    if not doc.exists:
        raise HTTPException(status_code=404, detail="User not found")

    data = doc.to_dict()
    data["user_id"] = user_id
    return data