# app/api/avatar_api.py

from fastapi import APIRouter, HTTPException
from app.services.avatar_generator import (
    generate_and_save_avatar,
    bulk_generate_and_save_avatars,
)

router = APIRouter()

@router.post("/avatar/{user_id}")
def generate_avatar_for_user(user_id: str):
    """
    針對單一 user_id 重新產生頭貼（不用 JWT）
    """
    try:
        url = generate_and_save_avatar(user_id)
        return {"user_id": user_id, "avatarUrl": url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/avatar/generate-all")
def generate_avatar_for_all_users(limit: int | None = None):
    """
    批次：從 user_preference_vectors 抓 user_id，一次產生一輪頭貼。

    limit：可選，給你測試時先跑 3, 5 個用的。
    """
    try:
        success, failed = bulk_generate_and_save_avatars(limit=limit)
        return {"success": success, "failed": failed}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))