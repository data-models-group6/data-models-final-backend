from pydantic import BaseModel

# 登入（redirect）回傳的資訊
class AuthLoginResponse(BaseModel):
    authorization_url: str


# Callback Query
class SpotifyCallbackQuery(BaseModel):
    code: str
    state: str


# Callback 回傳給前端的內容
class SpotifyCallbackResponse(BaseModel):
    status: str