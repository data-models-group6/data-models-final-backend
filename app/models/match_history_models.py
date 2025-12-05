# app/models/match_history_models.py

from typing import List, Optional
from pydantic import BaseModel


# ======================================================
# Model: API 1 — rebuild-all-vectors (POST)
# ======================================================

class RebuildAllVectorsResponse(BaseModel):
    status: str
    total_users: int
    updated: int
    skipped_no_data: int


# ======================================================
# Shared Models used in Candidates API
# ======================================================

class SharedArtist(BaseModel):
    id: str
    name: str


class SharedTrack(BaseModel):
    id: str
    name: str


class TopSong(BaseModel):
    id: str
    name: str
    artist: str
    album_image: Optional[str] = None


class SimilarityInfo(BaseModel):
    score: float
    reason: str
    reason_label: str
    shared_top_artists: List[SharedArtist]
    shared_top_tracks: List[SharedTrack]
    top_10_songs: List[TopSong]


class Candidate(BaseModel):
    userId: str
    name: str
    avatarUrl: str
    similarity_info: SimilarityInfo


class MatchCandidatesResponse(BaseModel):
    candidates: List[Candidate]