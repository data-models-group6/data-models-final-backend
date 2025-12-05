# app/api/match_history.py

from fastapi import APIRouter, HTTPException
from app.services.user_vector_service import compute_user_vector, save_user_vector
from app.services.match_utils import (
    get_all_active_users,
    get_user_vector,
    get_shared_artists,
    get_shared_tracks,
    similarity_score,
    build_similarity_reason,
    get_user_profile,
    get_user_top_songs
)
from app.models.match_history_models import (
    RebuildAllVectorsResponse,
    MatchCandidatesResponse
)
router = APIRouter()


# ======================================================
# API 1：重建所有使用者偏好向量（批次更新）
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
# API 2：取得相似使用者前 N 名
# ======================================================
@router.get("/candidates/{user_id}", response_model=MatchCandidatesResponse)
def get_match_candidates(user_id: str, top_k: int = 10):
    # -----------------------------
    # 1. 取得 target user vector
    # -----------------------------
    target_vec = get_user_vector(user_id)
    if target_vec is None:
        raise HTTPException(status_code=404, detail="Target user vector not found")

    # -----------------------------
    # 2. 取得所有具有向量的使用者
    # -----------------------------
    users = get_all_active_users()
    other_users = [u for u in users if u != user_id]

    candidates = []

    # -----------------------------
    # 3. 計算相似度
    # -----------------------------
    for uid in other_users:
        vec = get_user_vector(uid)
        if vec is None:
            continue

        # cosine similarity + weighted score
        score = similarity_score(target_vec, vec)

        # 找共同喜好
        shared_artists = get_shared_artists(user_id, uid, limit=5)
        shared_tracks = get_shared_tracks(user_id, uid, limit=5)

        # 產生原因（含 labels）
        reason = build_similarity_reason(target_vec, vec, shared_artists, shared_tracks)

        # Firestore 撈 profile
        profile = get_user_profile(uid)

        # 撈 top songs
        top_songs = get_user_top_songs(uid, limit=10)

        candidates.append({
            "userId": uid,
            "name": profile["name"],
            "avatarUrl": profile["avatarUrl"],
            "similarity_info": {
                "score": score,
                "reason": reason["reason"],
                "reason_label": reason["reason_label"],
                "shared_top_artists": shared_artists,
                "shared_top_tracks": shared_tracks,
                "top_10_songs": top_songs
            }
        })

    # -----------------------------
    # 4. 排序並取前 top_k
    # -----------------------------
    candidates.sort(key=lambda x: x["similarity_info"]["score"], reverse=True)
    top_candidates = candidates[:top_k]

    return {"candidates": top_candidates}