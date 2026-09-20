"""Shared pytest fixtures."""
import json
import os

import pytest

from app.normalize import load_and_normalize
from app.store import SongRepository

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
P1 = os.path.join(REPO, "data", "songs_part1.json")
P2 = os.path.join(REPO, "data", "songs_part2.json")


@pytest.fixture
def normalized_rows():
    return load_and_normalize(P1, P2)


@pytest.fixture
def repo(normalized_rows, tmp_path):
    """A repository backed by the real data with a throwaway ratings file."""
    return SongRepository(normalized_rows, str(tmp_path / "ratings.json"))


@pytest.fixture
def client(normalized_rows, tmp_path):
    """A FastAPI TestClient wired to the real data + a temp ratings file.

    We point the app's module-level repo at a fresh temp store so tests never
    touch the committed dataset or ratings.
    """
    from fastapi.testclient import TestClient

    import app.main as main

    norm_path = tmp_path / "songs.json"
    norm_path.write_text(json.dumps(normalized_rows), encoding="utf-8")
    main.repo = SongRepository(
        json.loads(norm_path.read_text(encoding="utf-8")),
        str(tmp_path / "ratings.json"),
    )
    return TestClient(main.app)
