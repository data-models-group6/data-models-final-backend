# app/api/match_chat.py
from fastapi import APIRouter, HTTPException
from app.services.firestore_client import get_db

router = APIRouter()


@router.get("/match-list/{user_id}")
def get_match_list(user_id: str):
    db = get_db()

    # -----------------------------------
    # 1. 找出所有 matches 中包含 user_id 的文件
    # -----------------------------------
    matches_ref = db.collection("matches")
    query = matches_ref.where("users", "array_contains", user_id).stream()

    match_results = []

    for doc in query:
        data = doc.to_dict()
        match_id = doc.id

        users = data.get("users", [])
        if len(users) != 2:
            # 保險處理：若資料結構錯誤
            continue

        # 另一個 user_id
        other_id = users[0] if users[1] == user_id else users[1]

        # -----------------------------------
        # 2. 到 users 集合抓另一個使用者資訊
        # -----------------------------------
        other_doc = db.collection("users").document(other_id).get()
        if not other_doc.exists:
            other_profile = {"user_id": other_id, "missing": True}
        else:
            other_profile = other_doc.to_dict()
            other_profile["user_id"] = other_id

        # -----------------------------------
        # 3. 回傳 match 內容 + 對方資料
        # -----------------------------------
        match_results.append({
            "match_id": match_id,
            "last_message": data.get("last_message", ""),
            "last_message_time": data.get("last_message_time"),
            "is_active": data.get("is_active", True),
            "other_user": other_profile
        })

    return {"matches": match_results}