# app/services/user_service.py
from datetime import datetime
import uuid
from app.services.firestore_client import get_db


def create_user(email: str, password_hash: str):
    """
    在 users collection 建立新使用者資料
    """
    user_id = str(uuid.uuid4())

    data = {
        "email": data["email"],
        "password_hash": data["password_hash"],
        "created_at": datetime.utcnow(),
        "display_name": data.get("display_name"),
        "preferences": {},
        "first_name": data["first_name"],
        "last_name": data["last_name"],
        "birthday": data["birthday"],
        "gender": data.get("gender"),
    }
    db = get_db()
    db.collection("users").document(user_id).set(data)
    return user_id


def get_user(user_id: str):
    db = get_db()
    doc = db.collection("users").document(user_id).get()
    return doc.to_dict() if doc.exists else None

def get_user_by_email(email: str):
    db = get_db()
    q = db.collection("users").where("email", "==", email).stream()
    for doc in q:
        data = doc.to_dict()
        data["user_id"] = doc.id
        return data
    return None


def update_avatar(user_id: str, avatar_url: str):
    db = get_db()
    db.collection("users").document(user_id).update({
        "avatar_url": avatar_url
    })

from app.services.firestore_client import get_db

def update_gender(user_id: str, gender: str):
    db = get_db()
    db.collection("users").document(user_id).update({
        "gender": gender
    })

def update_display_name(user_id: str, name: str):
    db = get_db()
    db.collection("users").document(user_id).update({
        "display_name": name
    })