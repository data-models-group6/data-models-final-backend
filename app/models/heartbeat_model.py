# app/models/heartbeat_model.py
from pydantic import BaseModel

class Heartbeat(BaseModel):
    user_id: str
    track_id: str
    track_name: str
    artist_id: str
    artist_name: str
    popularity: int
    timestamp: int
    album_image: str
    lat: float
    lng: float