"""Tests for the pure query logic: sort, paginate, search, rate.

These are the exact traps the reviewed buggy_api.py falls into, pinned so our
version cannot regress into the same bugs.
"""
import pytest

from app.store import SongRepository


def _repo(songs, tmp_path):
    return SongRepository(songs, str(tmp_path / "r.json"))


def _songs(*vals):
    """Build minimal song dicts with a tempo value and required keys."""
    return [
        {"index": i, "id": f"id{i}", "title": f"t{i}", "tempo": v}
        for i, v in enumerate(vals)
    ]


# --- sort ------------------------------------------------------------------
def test_sort_is_applied_across_whole_dataset_then_paged(repo):
    """Regression guard for the buggy sort-after-slice bug.

    Sorting by tempo desc then taking page 1 must yield the global maximum,
    not the max of an arbitrary first slice.
    """
    all_desc = repo.sorted(repo.all(), "tempo", "desc")
    page1 = repo.paginate(all_desc, page=1, size=5)
    tempos = [s["tempo"] for s in page1 if s["tempo"] is not None]
    assert tempos == sorted(tempos, reverse=True)
    # the single largest tempo in the whole set must be on page 1
    global_max = max(s["tempo"] for s in repo.all() if s["tempo"] is not None)
    assert page1[0]["tempo"] == global_max


def test_nulls_sort_last_ascending(tmp_path):
    r = _repo(_songs(120.0, None, 90.0), tmp_path)
    out = r.sorted(r.all(), "tempo", "asc")
    assert [s["tempo"] for s in out] == [90.0, 120.0, None]


def test_nulls_sort_last_descending(tmp_path):
    r = _repo(_songs(120.0, None, 90.0), tmp_path)
    out = r.sorted(r.all(), "tempo", "desc")
    assert [s["tempo"] for s in out] == [120.0, 90.0, None]


def test_title_sort_is_case_insensitive(tmp_path):
    songs = [
        {"index": 0, "id": "a", "title": "banana"},
        {"index": 1, "id": "b", "title": "Apple"},
    ]
    r = _repo(songs, tmp_path)
    out = r.sorted(r.all(), "title", "asc")
    assert [s["title"] for s in out] == ["Apple", "banana"]


def test_unknown_sort_field_raises(repo):
    with pytest.raises(ValueError):
        repo.sorted(repo.all(), "not_a_field", "asc")
    with pytest.raises(ValueError):
        repo.sorted(repo.all(), "; DROP TABLE", "asc")


# --- paginate --------------------------------------------------------------
def test_page_one_returns_first_items(tmp_path):
    r = _repo(_songs(*range(20)), tmp_path)
    page1 = r.paginate(r.all(), page=1, size=10)
    # Regression guard for start = page*size (which skipped the first page).
    assert [s["tempo"] for s in page1] == list(range(10))


def test_last_partial_page(tmp_path):
    r = _repo(_songs(*range(25)), tmp_path)
    page3 = r.paginate(r.all(), page=3, size=10)
    assert [s["tempo"] for s in page3] == [20, 21, 22, 23, 24]


def test_page_beyond_end_is_empty(tmp_path):
    r = _repo(_songs(*range(5)), tmp_path)
    assert r.paginate(r.all(), page=99, size=10) == []


# --- search ----------------------------------------------------------------
def test_search_is_case_and_space_insensitive(repo):
    assert repo.search_by_title("SHAPE OF YOU")
    assert repo.search_by_title("  shape   of you  ")


def test_search_returns_all_matches_for_nonunique_title(repo):
    matches = repo.search_by_title("perfect")
    assert len(matches) == 2


def test_search_no_match_returns_empty(repo):
    assert repo.search_by_title("no such song") == []


# --- rate ------------------------------------------------------------------
def test_rating_persists_and_round_trips(repo):
    song = repo.all()[0]
    repo.set_rating(song["id"], 4)
    assert repo.get_by_id(song["id"])["rating"] == 4


def test_rating_survives_a_fresh_repository(normalized_rows, tmp_path):
    path = str(tmp_path / "ratings.json")
    r1 = SongRepository(normalized_rows, path)
    sid = normalized_rows[0]["id"]
    r1.set_rating(sid, 5)
    # New instance reads the persisted file.
    r2 = SongRepository(normalized_rows, path)
    assert r2.get_by_id(sid)["rating"] == 5


@pytest.mark.parametrize("bad", [0, 6, -1, 100])
def test_rating_rejects_out_of_range(repo, bad):
    sid = repo.all()[0]["id"]
    with pytest.raises(ValueError):
        repo.set_rating(sid, bad)


def test_rating_unknown_id_raises_keyerror(repo):
    with pytest.raises(KeyError):
        repo.set_rating("nope", 3)


def test_rating_does_not_mutate_canonical_dataset(repo):
    sid = repo.all()[0]["id"]
    repo.set_rating(sid, 3)
    # The stored song dict must not have gained a 'rating' key in place.
    assert "rating" not in repo._songs[0]
