# app/api/match_history.py

from fastapi import APIRouter, HTTPException
from app.models.match_history_models import MatchCandidatesResponse, RebuildAllVectorsResponse
from app.services.user_vector_service import compute_user_vector, save_user_vector
from app.services.match_utils_optimized import (
    get_all_active_users,
    load_all_user_vectors,
    load_all_user_profiles,
    load_all_top_songs,
    compute_shared_artists_map,
    compute_shared_tracks_map,
    compute_similarity_candidates
)
router = APIRouter()

# ======================================================
# API 1: 重建所有向量
# ======================================================
@router.post("/rebuild-all-vectors", response_model=RebuildAllVectorsResponse)
def rebuild_all_vectors():
    users = get_all_active_users()
    updated = 0
    skipped = 0

    for uid in users:
        vec = compute_user_vector(uid)
        if vec:
            save_user_vector(vec)
            updated += 1
        else:
            skipped += 1

    return {
        "status": "ok",
        "total_users": len(users),
        "updated": updated,
        "skipped_no_data": skipped,
    }


# ======================================================
# API 2: 取得相似使用者前 N 名
# ======================================================
@router.get("/candidates/{user_id}", response_model=MatchCandidatesResponse)
def get_match_candidates(user_id: str, top_k: int = 10):
    
    # 1. 取得 active users
    users = get_all_active_users()
    if user_id not in users:
        raise HTTPException(404, "User not found")

    # 2. 批次載入資料
    vectors = load_all_user_vectors()
    profiles = load_all_user_profiles(users)
    top_songs = load_all_top_songs(users)

    artists_map = compute_shared_artists_map()
    tracks_map = compute_shared_tracks_map()

    # 3. 計算相似度 candidate 結果
    candidates = compute_similarity_candidates(
        user_id=user_id,
        users=users,
        vectors=vectors,
        profiles=profiles,
        top_songs=top_songs,
        artists_map=artists_map,
        tracks_map=tracks_map,
        top_k=top_k
    )

    return {"candidates": candidates}