from fastapi import APIRouter, HTTPException, Depends
import logging

# 1. 引入你在 Heartbeat 用的 auth service
from app.services.user_auth import get_current_user

# 引入你的 Model 和 Service
from app.models.match_models import SwipeRequest, SwipeResponse
from app.services.match_service import process_swipe_transaction

router = APIRouter()

# 設定 Logger (這是上一段建議的優化，這裡順便幫你加進去)
logger = logging.getLogger(__name__)

@router.post("/swipe", response_model=SwipeResponse)
def swipe_user(
    payload: SwipeRequest,
    user: dict = Depends(get_current_user)
):
    """
    左滑/右滑功能 API
    - Header 需帶入 Bearer Token (由 get_current_user 解析)
    - Body: { "target_user_id": "...", "action": "LIKE" }
    """
    
    # 3. 從 user dict 中取出 user_id
    # 根據你的 heartbeat 程式碼，這裡回傳的是一個 dict，裡面有 "user_id"
    current_user_id = user["user_id"]

    # --- 以下邏輯保持不變 ---

    # 基本防呆：不能滑自己
    if payload.target_user_id == current_user_id:
        raise HTTPException(status_code=400, detail="You cannot swipe yourself.")

    try:
        # 呼叫 Service 處理交易
        result = process_swipe_transaction(
            from_user_id=current_user_id,
            target_user_id=payload.target_user_id,
            action=payload.action.value 
        )
        
        return SwipeResponse(
            status="success",
            is_match=result["is_match"],
            match_id=result["match_id"]
        )

    except Exception as e:
        # 使用 logger 紀錄錯誤，比較正規
        logger.error(f"Swipe Error: User {current_user_id} -> {payload.target_user_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")