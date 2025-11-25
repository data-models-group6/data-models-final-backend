# app/services/user_service.py
from google.cloud import firestore
from datetime import datetime
import uuid

DB = firestore.Client(database="(default)")


def create_user(email: str, password_hash: str):
    """
    在 users collection 建立新使用者資料
    """
    user_id = str(uuid.uuid4())

    data = {
        "email": email,
        "password_hash": password_hash,
        "created_at": datetime.utcnow(),
        "avatar_url": None,
        "display_name": None,
        "preferences": {},
    }

    DB.collection("users").document(user_id).set(data)
    return user_id


def get_user(user_id: str):
    doc = DB.collection("users").document(user_id).get()
    return doc.to_dict() if doc.exists else None

def get_user_by_email(email: str):
    q = DB.collection("users").where("email", "==", email).stream()
    for doc in q:
        data = doc.to_dict()
        data["user_id"] = doc.id
        return data
    return None


def update_avatar(user_id: str, avatar_url: str):
    DB.collection("users").document(user_id).update({
        "avatar_url": avatar_url
    })