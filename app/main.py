# app/main.py
from fastapi import FastAPI
from app.api.heartbeat import router as heartbeat_router
from app.api.spotify_auth_api import router as spotify_router
from app.api.match_api import router as match_router

app = FastAPI()

# Spotify 登入 / callback
app.include_router(spotify_router, prefix="/auth")
# 心跳相關
app.include_router(heartbeat_router, prefix="/api")
# 地理配對 API
app.include_router(match_router, prefix="/api")

@app.get("/")
def root():
    return {"message": "Spotify backend running"}