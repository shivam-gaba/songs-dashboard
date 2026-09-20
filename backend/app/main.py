"""FastAPI app exposing the normalized songs.

API contract (see DECISIONS.md for the reasoning):

  GET  /health                          -> liveness
  GET  /songs                           -> paginated + whole-dataset sort
  GET  /songs/search?title=...          -> ALL title matches (0/1/many)
  GET  /songs/id/{song_id}              -> one song by stable id
  POST /songs/{song_id}/rating          -> set 1-5 star rating (persisted)
  GET  /stats/duration                  -> honest avg duration (excludes the
                                           unit-suspect + missing values)
"""
from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .models import DurationStats, RatingIn, SearchResult, Song, SongPage
from .store import SORTABLE_FIELDS, build_repository

HERE = os.path.dirname(os.path.abspath(__file__))
NORMALIZED_PATH = os.environ.get(
    "SONGS_DATA", os.path.join(HERE, "data", "songs.normalized.json")
)
RATINGS_PATH = os.environ.get(
    "RATINGS_DATA", os.path.join(HERE, "data", "ratings.json")
)

MAX_PAGE_SIZE = 100

app = FastAPI(
    title="Songs API",
    version="1.0.0",
    description="REST API over the normalized & reconciled song catalog.",
)

# The frontend is served from a different origin in dev (Vite on :5173).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # dev-only; lock down for production (see DECISIONS)
    allow_methods=["*"],
    allow_headers=["*"],
)

repo = build_repository(NORMALIZED_PATH, RATINGS_PATH)


@app.get("/health")
def health() -> dict[str, object]:
    return {"status": "ok", "songs": repo.total}


@app.get("/songs", response_model=SongPage)
def list_songs(
    page: int = Query(1, ge=1, description="1-based page number"),
    size: int = Query(10, ge=1, le=MAX_PAGE_SIZE),
    sort_by: str = Query("index"),
    order: str = Query("asc", pattern="^(asc|desc)$"),
) -> SongPage:
    """Return a page of songs, sorted across the WHOLE dataset first.

    Order of operations matters: we sort the full set, THEN slice the page.
    (The reviewed buggy_api.py sliced first and sorted only the page.)
    """
    if sort_by not in SORTABLE_FIELDS:
        raise HTTPException(
            status_code=400,
            detail=f"sort_by must be one of {sorted(SORTABLE_FIELDS)}",
        )
    ordered = repo.sorted(repo.all(), sort_by, order)
    items = repo.paginate(ordered, page, size)
    total = repo.total
    total_pages = (total + size - 1) // size if total else 0
    return SongPage(
        items=items,
        page=page,
        size=size,
        total=total,
        total_pages=total_pages,
        sort_by=sort_by,
        order=order,
    )


@app.get("/songs/search", response_model=SearchResult)
def search_songs(title: str = Query(..., min_length=1)) -> SearchResult:
    """Case/spacing-insensitive title lookup. Titles are not unique, so this
    always returns a list; the client renders 0, 1, or many matches."""
    matches = repo.search_by_title(title)
    return SearchResult(query=title, count=len(matches), matches=matches)


@app.get("/songs/id/{song_id}", response_model=Song)
def get_song(song_id: str) -> Song:
    song = repo.get_by_id(song_id)
    if song is None:
        raise HTTPException(status_code=404, detail="song not found")
    return song


@app.post("/songs/{song_id}/rating", response_model=Song)
def rate_song(song_id: str, body: RatingIn) -> Song:
    """Rate a song 1-5. Keyed by id (stable), persisted across restarts.

    Invalid star values are rejected by the RatingIn schema (422) before we
    get here; an unknown id yields 404.
    """
    try:
        return repo.set_rating(song_id, body.stars)
    except KeyError:
        raise HTTPException(status_code=404, detail="song not found")
    except ValueError as e:  # defense in depth
        raise HTTPException(status_code=422, detail=str(e))


@app.get("/stats/duration", response_model=DurationStats)
def duration_stats() -> DurationStats:
    """Average track duration in seconds — computed honestly.

    Excludes rows with a missing duration AND the unit-suspect rows (values
    recorded in seconds, not ms). Averaging those in — as the buggy file does
    — silently corrupts the result.
    """
    durations = [
        s["duration_ms"]
        for s in repo.all()
        if s["duration_ms"] is not None
        and "duration_suspect" not in s["data_quality"]
    ]
    excluded_suspect = sum(
        1 for s in repo.all() if "duration_suspect" in s["data_quality"]
    )
    excluded_missing = sum(1 for s in repo.all() if s["duration_ms"] is None)
    avg = (sum(durations) / len(durations) / 1000) if durations else None
    return DurationStats(
        avg_seconds=avg,
        counted=len(durations),
        excluded_suspect=excluded_suspect,
        excluded_missing=excluded_missing,
        note="Excludes unit-suspect (seconds-not-ms) and missing durations.",
    )
