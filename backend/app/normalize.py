"""
Section 1 — Normalize & reconcile the two song exports into one clean,
row-oriented table.

Design goals (see DECISIONS.md for the full reasoning):
  * A downstream consumer can trust every value OR see it clearly marked.
    We never silently invent or overwrite data. When a value is
    untrustworthy we set it to ``None`` and record *why* in the row's
    ``data_quality`` list.
  * Reconciliation is keyed on ``id`` (the stable identifier), not title.
  * On conflict, the newer/enriched export (part2, which carries valence)
    wins — but only when its value is actually valid. Otherwise we fall
    back to the other file's valid value.
  * The duration unit bug is *detected and flagged*, not rewritten. We
    surface the problem rather than mutate upstream numbers.

This module is pure (no I/O). ``load_and_normalize`` at the bottom wires it
to files for the CLI and the API.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


# --- Field rules -----------------------------------------------------------
# Audio-feature ratios that must lie in [0, 1].
UNIT_INTERVAL_FIELDS = ("danceability", "energy", "acousticness", "valence")
# Every attribute we carry into the normalized table, in output order.
OUTPUT_FIELDS = (
    "index",
    "id",
    "title",
    "danceability",
    "energy",
    "mood",
    "acousticness",
    "tempo",
    "valence",
    "duration_ms",
    "num_sections",
    "num_segments",
    "data_quality",
)

# A song shorter than this many ms is physically implausible and almost
# certainly a value that was recorded in *seconds*. Used to DETECT (not fix)
# the unit bug. 10_000 ms = 10 s; the shortest real track here is ~2 min.
DURATION_SUSPECT_MS = 10_000


@dataclass
class Cell:
    """The outcome of validating one raw value for one field."""

    value: Any = None
    issue: str | None = None  # a data_quality flag, or None if clean


def _coerce_float(raw: Any) -> tuple[float | None, bool]:
    """Return (float_or_None, was_coerced_from_string).

    Clean numeric strings like "0.521" are coerced silently — that is a
    formatting difference, not a data-quality problem. Non-numeric junk
    ("N/A", "") cannot be coerced and yields None.
    """
    if isinstance(raw, bool):  # bools are ints in Python; reject explicitly
        return None, False
    if isinstance(raw, (int, float)):
        return float(raw), False
    if isinstance(raw, str):
        try:
            return float(raw.strip()), True
        except ValueError:
            return None, False
    return None, False


def _validate_unit_field(name: str, raw: Any) -> Cell:
    """[0, 1] ratio fields: danceability, energy, acousticness, valence."""
    if raw is None:
        return Cell(None, f"{name}_missing")
    val, _ = _coerce_float(raw)
    if val is None:
        return Cell(None, f"{name}_malformed")
    if not (0.0 <= val <= 1.0):
        # Out of range -> untrustworthy. Null it and flag; do NOT clamp
        # (clamping would fabricate a plausible-looking value).
        return Cell(None, f"{name}_out_of_range")
    return Cell(val, None)


def _validate_tempo(raw: Any) -> Cell:
    """Tempo in BPM. Must be a positive, musically plausible number."""
    if raw is None:
        return Cell(None, "tempo_missing")
    val, _ = _coerce_float(raw)
    if val is None:
        return Cell(None, "tempo_malformed")
    # 0 BPM is not a tempo; treat anything <= 0 as invalid. We keep an
    # upper sanity bound too (world-record-ish); nothing here trips it.
    if val <= 0 or val > 300:
        return Cell(None, "tempo_invalid")
    return Cell(val, None)


def _validate_duration(raw: Any) -> Cell:
    """duration_ms. DETECT the unit bug (values in seconds) and FLAG it.

    Per the locked decision we do NOT convert — we keep the raw number and
    mark it ``duration_suspect`` so a downstream consumer sees exactly which
    values it cannot trust as milliseconds.
    """
    if raw is None:
        return Cell(None, "duration_missing")
    val, _ = _coerce_float(raw)
    if val is None:
        return Cell(None, "duration_malformed")
    if val <= 0:
        return Cell(None, "duration_invalid")
    ival = int(round(val))
    if ival < DURATION_SUSPECT_MS:
        # Implausibly short => almost certainly seconds, not ms. Keep raw,
        # flag it. (e.g. 158 -> 2:38 if interpreted as seconds.)
        return Cell(ival, "duration_suspect")
    return Cell(ival, None)


def _validate_mood(raw: Any) -> Cell:
    """mood is a binary category (0/1) in both files; keep as-is if valid."""
    if raw is None:
        return Cell(None, "mood_missing")
    val, _ = _coerce_float(raw)
    if val is None or val not in (0.0, 1.0):
        return Cell(None, "mood_invalid")
    return Cell(int(val), None)


def _validate_count(name: str, raw: Any) -> Cell:
    """num_sections / num_segments: positive integers."""
    if raw is None:
        return Cell(None, f"{name}_missing")
    val, _ = _coerce_float(raw)
    if val is None or val < 0 or val != int(val):
        return Cell(None, f"{name}_invalid")
    return Cell(int(val), None)


def _clean_title(raw: Any) -> tuple[str | None, str | None]:
    """Trim and collapse internal whitespace; preserve casing & diacritics.

    Returns (clean_title, issue). Casing/diacritics are display-meaningful
    ("Naïve", "God's Plan") so we keep them; only whitespace is normalized.
    """
    if raw is None or not isinstance(raw, str):
        return None, "title_missing"
    collapsed = " ".join(raw.split())
    if not collapsed:
        return None, "title_missing"
    issue = "title_cleaned" if collapsed != raw else None
    return collapsed, issue


def validate_field(name: str, raw: Any) -> Cell:
    """Dispatch one raw value to the right validator."""
    if name in UNIT_INTERVAL_FIELDS:
        return _validate_unit_field(name, raw)
    if name == "tempo":
        return _validate_tempo(raw)
    if name == "duration_ms":
        return _validate_duration(raw)
    if name == "mood":
        return _validate_mood(raw)
    if name in ("num_sections", "num_segments"):
        return _validate_count(name, raw)
    return Cell(raw, None)


# --- Reading the column-oriented source format -----------------------------
def columns_to_rows(doc: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert one column-oriented export into a list of row dicts.

    The source format maps ``attribute -> {row_index: value}``. Row indices
    are strings; a value may be *absent* for a given row (e.g. energy has no
    key "2"). Absent keys become missing (None) downstream, not skipped.
    """
    all_indices = sorted(
        {idx for col in doc.values() for idx in col.keys()}, key=int
    )
    rows = []
    for idx in all_indices:
        row = {"_src_index": idx}
        for col_name, col in doc.items():
            row[col_name] = col.get(idx)  # None if this row lacks the key
        rows.append(row)
    return rows


# --- Merge / reconcile -----------------------------------------------------
# Fields we reconcile value-by-value between the two sources.
_MERGE_FIELDS = (
    "danceability",
    "energy",
    "mood",
    "acousticness",
    "tempo",
    "valence",
    "duration_ms",
    "num_sections",
    "num_segments",
)


def _pick(field_name: str, primary_raw: Any, fallback_raw: Any) -> Cell:
    """Conflict rule: prefer ``primary`` (part2) when it validates; else fall
    back to ``fallback`` (part1) when *that* validates; else null + flag.

    The returned Cell already reflects the winning source's validation.
    """
    primary = validate_field(field_name, primary_raw)
    if primary.value is not None:
        return primary
    fallback = validate_field(field_name, fallback_raw)
    if fallback.value is not None:
        return fallback
    # Neither source is valid -> the value is null. Report the *most
    # informative* reason: a source that actually carried a bad value
    # ("N/A", 1.42) explains more than one that simply lacked the field.
    # So a present-but-bad source outranks an absent one; if both are
    # present-and-bad (or both absent), part2 (primary) wins.
    primary_present = primary_raw is not None
    fallback_present = fallback_raw is not None
    if fallback_present and not primary_present:
        return fallback
    return primary if primary.issue else fallback


def normalize(
    part1: dict[str, Any], part2: dict[str, Any]
) -> list[dict[str, Any]]:
    """Reconcile both exports into one clean, row-oriented table.

    Returns a list of row dicts with keys == OUTPUT_FIELDS. part2 is the
    primary source on conflict (it is the enriched export carrying valence).
    """
    rows1 = columns_to_rows(part1)
    rows2 = columns_to_rows(part2)
    by_id2 = {r.get("id"): r for r in rows2 if r.get("id")}

    merged: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    def build(row_id: str, primary: dict[str, Any] | None,
              fallback: dict[str, Any] | None) -> dict[str, Any]:
        """primary = part2 row (or None), fallback = part1 row (or None)."""
        p = primary or {}
        f = fallback or {}
        quality: list[str] = []

        # Title: prefer part1's (part1 is the original catalog naming), fall
        # back to part2. Whichever we take, clean whitespace.
        raw_title = f.get("title") if f.get("title") is not None else p.get("title")
        title, t_issue = _clean_title(raw_title)
        if t_issue:
            quality.append(t_issue)

        out: dict[str, Any] = {"id": row_id, "title": title}
        for name in _MERGE_FIELDS:
            cell = _pick(name, p.get(name), f.get(name))
            out[name] = cell.value
            if cell.issue:
                quality.append(cell.issue)
        out["data_quality"] = quality
        return out

    # 1) Every part1 row, reconciled against its part2 twin (if any).
    for r1 in rows1:
        rid = r1.get("id")
        if not rid:
            continue
        seen_ids.add(rid)
        merged.append(build(rid, by_id2.get(rid), r1))

    # 2) part2-only rows (no part1 twin).
    for r2 in rows2:
        rid = r2.get("id")
        if not rid or rid in seen_ids:
            continue
        seen_ids.add(rid)
        merged.append(build(rid, r2, None))

    # 3) Assign a stable, contiguous output index and order the keys.
    result = []
    for i, row in enumerate(merged):
        row["index"] = i
        result.append({k: row.get(k) for k in OUTPUT_FIELDS})
    return result


def load_and_normalize(
    part1_path: str, part2_path: str
) -> list[dict[str, Any]]:
    with open(part1_path) as f:
        part1 = json.load(f)
    with open(part2_path) as f:
        part2 = json.load(f)
    return normalize(part1, part2)
