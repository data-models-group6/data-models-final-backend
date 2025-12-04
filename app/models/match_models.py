from pydantic import BaseModel, Field
from enum import Enum
from typing import Optional

# 定義滑動動作的枚舉 (Enum)，限制只能傳入 LIKE 或 PASS
class SwipeAction(str, Enum):
    LIKE = "LIKE"
    PASS = "PASS"

# 前端傳來的請求格式
class SwipeRequest(BaseModel):
    target_user_id: str = Field(..., description="被滑的使用者 ID")
    action: SwipeAction = Field(..., description="動作：LIKE(右滑) 或 PASS(左滑)")

# 後端回傳的格式
class SwipeResponse(BaseModel):
    status: str
    is_match: bool = Field(False, description="是否配對成功")
    match_id: Optional[str] = Field(None, description="若配對成功，回傳配對文件 ID")