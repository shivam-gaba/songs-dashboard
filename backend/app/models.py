"""Pydantic schemas defining the API contract."""
from __future__ import annotations

from pydantic import BaseModel, Field


class Song(BaseModel):
    index: int
    id: str
    title: str | None
    danceability: float | None = None
    energy: float | None = None
    mood: int | None = None
    acousticness: float | None = None
    tempo: float | None = None
    valence: float | None = None
    duration_ms: int | None = None
    num_sections: int | None = None
    num_segments: int | None = None
    # Per-row provenance: which values are missing/suspect and why.
    data_quality: list[str] = Field(default_factory=list)
    # Current user star rating (1-5), or null if unrated.
    rating: int | None = None


class SongPage(BaseModel):
    """One page of results plus the metadata a client needs to page/sort."""

    items: list[Song]
    page: int
    size: int
    total: int
    total_pages: int
    sort_by: str
    order: str


class SearchResult(BaseModel):
    query: str
    count: int
    matches: list[Song]


class RatingIn(BaseModel):
    # ge/le make FastAPI reject out-of-range input with a 422 before it ever
    # reaches our handler — but store.set_rating re-checks as defense in depth.
    stars: int = Field(..., ge=1, le=5, description="Star rating, 1-5")


class DurationStats(BaseModel):
    avg_seconds: float | None
    counted: int
    excluded_suspect: int
    excluded_missing: int
    note: str
