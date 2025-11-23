# app/models/token_model.py
from pydantic import BaseModel

class SpotifyToken(BaseModel):
    access_token: str
    refresh_token: str | None = None
    expires_at: int   # Unix timestamp
    token_type: str = "Bearer"
    scope: str | None = None