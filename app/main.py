# app/main.py
from fastapi import FastAPI

# === Import Routers ===
from app.api.auth_api import router as auth_router            # NEW: Email/Password + JWT
from app.api.spotify_auth_api import router as spotify_router
from app.api.heartbeat import router as heartbeat_router
from app.api.match_api import router as match_router          # Redis Matching
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Spotify Match Backend",
    description=(
        "Backend for: "
        "• User Login (JWT) "
        "• Spotify OAuth (PKCE) "
        "• Heartbeat → Pub/Sub → Redis "
        "• Geo + Music Matching"
    ),
    version="2.0.0"
)

# === CORS Middleware ===
origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    "*" # 開發階段為了確保能動，可以先允許所有來源
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,       # 前端網址（目前先允許全部）
    allow_credentials=True,
    allow_methods=["*"],       # ⭐ 修正 OPTIONS 405 的關鍵
    allow_headers=["*"],
)

# === User Auth (JWT 登入 / 註冊) ===
app.include_router(auth_router, prefix="/auth", tags=["User Auth"])

# === Spotify OAuth（PKCE Flow） ===
app.include_router(spotify_router, prefix="/spotify", tags=["Spotify OAuth"])

# === 心跳資料 API ===
app.include_router(heartbeat_router, prefix="/api", tags=["Heartbeat"])

# === Redis 配對 API ===
app.include_router(match_router, prefix="/api", tags=["Matching"])

@app.get("/")
def root():
    return {
        "status": "ok",
        "message": "Spotify Match Backend running with JWT + PKCE + Firestore + Redis v2"
    }