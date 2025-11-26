# app/services/user_service.py
from google.cloud import firestore
from google.oauth2 import service_account
from datetime import datetime
import uuid
import base64
import json
import os

def get_db():
    global _cached_db

    if _cached_db is not None:
        return _cached_db

    raw = os.getenv("GOOGLE_CLOUD_CREDENTIALS")
    if not raw:
        raise Exception("GOOGLE_CLOUD_CREDENTIALS missing")

    try:
        creds_json = json.loads(base64.b64decode(raw))
        creds = service_account.Credentials.from_service_account_info(creds_json)
    except Exception as e:
        raise Exception(f"Failed to decode GOOGLE_CLOUD_CREDENTIALS: {e}")

    _cached_db = firestore.Client(credentials=creds, project=creds.project_id)
    return _cached_db


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