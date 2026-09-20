"""Data access + query logic for the songs API.

The query logic (sort, paginate, search, rate) lives here as a plain,
side-effect-light class so it can be unit-tested without spinning up FastAPI.
This is deliberately the opposite of the reviewed buggy_api.py, where the
same logic was tangled into the route handlers and got the ordering wrong.
"""
from __future__ import annotations

import json
import os
import tempfile
from threading import RLock
from typing import Any

from .normalize import OUTPUT_FIELDS

# Fields a client may sort by: every column in the normalized table, plus the
# user-supplied rating (attached at response time, unrated sorts last).
SORTABLE_FIELDS = tuple(OUTPUT_FIELDS) + ("rating",)

MIN_STARS = 1
MAX_STARS = 5


def _normalize_title(title: str) -> str:
    """Casing- and spacing-insensitive key for title lookup."""
    return " ".join(title.split()).casefold()


class SongRepository:
    """Holds the normalized songs + persisted ratings and answers queries.

    Ratings are keyed by ``id`` (stable) rather than title (non-unique) and
    are persisted to a JSON file so they survive process restarts.
    """

    def __init__(self, songs: list[dict[str, Any]], ratings_path: str | None):
        self._songs = songs
        self._by_id = {s["id"]: s for s in songs}
        self._ratings_path = ratings_path
        self._lock = RLock()
        self._ratings: dict[str, int] = self._load_ratings()

    # --- ratings persistence ------------------------------------------
    def _load_ratings(self) -> dict[str, int]:
        if not self._ratings_path or not os.path.exists(self._ratings_path):
            return {}
        try:
            with open(self._ratings_path) as f:
                data = json.load(f)
            return {str(k): int(v) for k, v in data.items()}
        except (json.JSONDecodeError, ValueError, OSError):
            # Corrupt ratings file must not take down the API.
            return {}

    def _persist_ratings(self) -> None:
        if not self._ratings_path:
            return
        os.makedirs(os.path.dirname(self._ratings_path), exist_ok=True)
        # Atomic write: tmp file + rename, so a crash mid-write can't corrupt.
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(self._ratings_path))
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(self._ratings, f, indent=2)
            os.replace(tmp, self._ratings_path)
        except OSError:
            if os.path.exists(tmp):
                os.remove(tmp)
            raise

    # --- read helpers -------------------------------------------------
    def _with_rating(self, song: dict[str, Any]) -> dict[str, Any]:
        """Return a shallow copy of the song with its current rating attached.

        We copy so callers can never mutate the canonical in-memory dataset
        (a bug the reviewed file had: it wrote ratings straight into the
        shared cache).
        """
        out = dict(song)
        out["rating"] = self._ratings.get(song["id"])
        return out

    def all(self) -> list[dict[str, Any]]:
        return [self._with_rating(s) for s in self._songs]

    @property
    def total(self) -> int:
        return len(self._songs)

    def get_by_id(self, song_id: str) -> dict[str, Any] | None:
        song = self._by_id.get(song_id)
        return self._with_rating(song) if song else None

    # --- sort ---------------------------------------------------------
    def sorted(self, items: list[dict[str, Any]], sort_by: str,
               order: str) -> list[dict[str, Any]]:
        """Sort across the WHOLE list (caller passes the full set).

        - Unknown ``sort_by`` raises ValueError (route turns it into a 400).
        - Nulls always sort last, regardless of asc/desc, so missing values
          never masquerade as the smallest/largest.
        - String fields sort case-insensitively.
        """
        if sort_by not in SORTABLE_FIELDS:
            raise ValueError(f"cannot sort by {sort_by!r}")
        reverse = order == "desc"

        def key(song: dict[str, Any]):
            v = song.get(sort_by)
            missing = v is None
            if isinstance(v, str):
                v = v.casefold()
            # (missing_flag, value): missing rows collapse to a constant so
            # they group at the end. XOR with reverse keeps them last even
            # when the list is reversed.
            return (missing ^ reverse, v if not missing else 0)

        return sorted(items, key=key, reverse=reverse)

    # --- paginate -----------------------------------------------------
    @staticmethod
    def paginate(items: list[dict[str, Any]], page: int,
                 size: int) -> list[dict[str, Any]]:
        """1-based pagination. page 1 => first ``size`` items."""
        start = (page - 1) * size
        return items[start:start + size]

    # --- search -------------------------------------------------------
    def search_by_title(self, title: str) -> list[dict[str, Any]]:
        """Case- and spacing-insensitive exact-title lookup.

        Returns ALL matches (0, 1, or many) because titles are not unique
        in the cleaned data (e.g. two songs named "Perfect").
        """
        needle = _normalize_title(title)
        return [
            self._with_rating(s)
            for s in self._songs
            if s["title"] and _normalize_title(s["title"]) == needle
        ]

    def filter_by_title(self, query: str) -> list[dict[str, Any]]:
        """Case/spacing-insensitive **substring** title filter.

        Powers the dashboard's search-as-filter: typing "21" matches both
        "21" and "21 Guns". An empty/blank query returns everything.
        """
        needle = _normalize_title(query)
        if not needle:
            return self.all()
        return [
            self._with_rating(s)
            for s in self._songs
            if s["title"] and needle in _normalize_title(s["title"])
        ]

    # --- rate ---------------------------------------------------------
    def set_rating(self, song_id: str, stars: int) -> dict[str, Any]:
        """Set a 1-5 star rating for a song, persisted to disk.

        Raises KeyError if the song id is unknown, ValueError if stars is
        out of range. Routes map these to 404 / 422.
        """
        if song_id not in self._by_id:
            raise KeyError(song_id)
        if not isinstance(stars, int) or not (MIN_STARS <= stars <= MAX_STARS):
            raise ValueError(f"stars must be an integer {MIN_STARS}-{MAX_STARS}")
        with self._lock:
            self._ratings[song_id] = stars
            self._persist_ratings()
        return self._with_rating(self._by_id[song_id])


def build_repository(
    normalized_path: str, ratings_path: str | None
) -> SongRepository:
    with open(normalized_path, encoding="utf-8") as f:
        songs = json.load(f)
    return SongRepository(songs, ratings_path)
