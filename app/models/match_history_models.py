from pydantic import BaseModel
from typing import List, Optional

# ======================================================
# Top 10 Songs
# ======================================================

class Song(BaseModel):
    title: str               # 你的 BigQuery 欄位是 track_name → title
    artist: str
    album_image: Optional[str] = None


# ======================================================
# Similarity Info
# ======================================================

class SimilarityInfo(BaseModel):
    score: int
    reason: str
    reason_label: List[str]  # label 是 list[str]
    shared_top_artists: List[str]
    shared_top_tracks: List[str]
    top_10_songs: List[Song]  # 這裡用我們上面定義的 Song model


# ======================================================
# Candidate
# ======================================================

class Candidate(BaseModel):
    userId: str
    name: str
    avatarUrl: str
    similarity_info: SimilarityInfo


# ======================================================
# Final Response
# ======================================================

class MatchCandidatesResponse(BaseModel):
    candidates: List[Candidate]


# ======================================================
# Rebuild Vector Response
# ======================================================

class RebuildAllVectorsResponse(BaseModel):
    status: str
    total_users: int
    updated: int
    skipped_no_data: int