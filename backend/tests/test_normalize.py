"""Tests for the Section 1 normalization / reconciliation rules.

Each test pins a specific decision from DECISIONS.md so a regression in the
reconciliation logic fails loudly.
"""
from app.normalize import (
    DURATION_SUSPECT_MS,
    normalize,
    validate_field,
)


# --- field validators ------------------------------------------------------
def test_coerces_clean_numeric_strings_without_flag():
    cell = validate_field("danceability", "0.521")
    assert cell.value == 0.521 and cell.issue is None


def test_out_of_range_ratio_is_nulled_and_flagged():
    cell = validate_field("danceability", 1.42)
    assert cell.value is None and cell.issue == "danceability_out_of_range"


def test_negative_acousticness_is_out_of_range():
    cell = validate_field("acousticness", -0.05)
    assert cell.value is None and cell.issue == "acousticness_out_of_range"


def test_tempo_zero_is_invalid():
    cell = validate_field("tempo", 0)
    assert cell.value is None and cell.issue == "tempo_invalid"


def test_non_numeric_string_is_malformed():
    cell = validate_field("energy", "N/A")
    assert cell.value is None and cell.issue == "energy_malformed"


def test_short_duration_is_kept_raw_but_flagged_suspect():
    # Decision: DETECT the unit bug, do NOT convert. Value stays as-is.
    cell = validate_field("duration_ms", 158)
    assert cell.value == 158 and cell.issue == "duration_suspect"
    assert 158 < DURATION_SUSPECT_MS


def test_normal_duration_has_no_flag():
    cell = validate_field("duration_ms", 225947)
    assert cell.value == 225947 and cell.issue is None


def test_mood_must_be_binary():
    assert validate_field("mood", 1).value == 1
    assert validate_field("mood", 2).issue == "mood_invalid"


# --- reconciliation --------------------------------------------------------
def _mini(part1_over, part2_over):
    """Build two tiny column-oriented docs sharing id 'X'."""
    p1 = {"id": {"0": "X"}, "title": {"0": "Song"}, **part1_over}
    p2 = {"id": {"0": "X"}, "title": {"0": "Song"}, **part2_over}
    return normalize(p1, p2)


def test_dedup_by_id_collapses_shared_song_to_one_row():
    rows = _mini({"energy": {"0": 0.5}}, {"energy": {"0": 0.6}})
    assert len(rows) == 1


def test_part2_wins_conflict_when_valid():
    rows = _mini({"danceability": {"0": 0.727}}, {"danceability": {"0": 0.74}})
    assert rows[0]["danceability"] == 0.74


def test_falls_back_to_part1_when_part2_value_invalid():
    # part2 has an out-of-range value -> we keep part1's valid one.
    rows = _mini({"energy": {"0": 0.5}}, {"energy": {"0": 9.9}})
    assert rows[0]["energy"] == 0.5


def test_flag_reports_the_informative_reason_not_generic_missing():
    # part1-only bad value must be flagged for its REAL reason.
    p1 = {"id": {"0": "X"}, "title": {"0": "S"}, "energy": {"0": "N/A"}}
    p2 = {"id": {}, "title": {}}
    rows = normalize(p1, p2)
    assert "energy_malformed" in rows[0]["data_quality"]
    assert "energy_missing" not in rows[0]["data_quality"]


def test_valence_only_in_part2_is_carried_and_missing_flagged_for_others():
    p1 = {"id": {"0": "A", "1": "B"}, "title": {"0": "A", "1": "B"}}
    p2 = {"id": {"0": "A"}, "title": {"0": "A"}, "valence": {"0": 0.3}}
    rows = normalize(p1, p2)
    by_id = {r["id"]: r for r in rows}
    assert by_id["A"]["valence"] == 0.3
    assert by_id["B"]["valence"] is None
    assert "valence_missing" in by_id["B"]["data_quality"]


def test_title_whitespace_cleaned_casing_preserved():
    p1 = {"id": {"0": "X"}, "title": {"0": "  Naive  Song "}}
    p2 = {"id": {}, "title": {}}
    rows = normalize(p1, p2)
    assert rows[0]["title"] == "Naive Song"
    assert "title_cleaned" in rows[0]["data_quality"]


def test_indices_are_contiguous_from_zero():
    p1 = {"id": {"0": "A", "1": "B"}, "title": {"0": "A", "1": "B"}}
    p2 = {"id": {"0": "C"}, "title": {"0": "C"}}
    rows = normalize(p1, p2)
    assert [r["index"] for r in rows] == [0, 1, 2]


# --- end-to-end on the real files -----------------------------------------
def test_real_files_produce_25_unique_rows(normalized_rows):
    assert len(normalized_rows) == 25
    assert len({r["id"] for r in normalized_rows}) == 25


def test_real_files_two_perfect_songs_survive(normalized_rows):
    perfects = [r for r in normalized_rows if r["title"] == "Perfect"]
    assert len(perfects) == 2
    assert perfects[0]["id"] != perfects[1]["id"]
