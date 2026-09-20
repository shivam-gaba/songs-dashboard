# DECISIONS.md

Decisions I made, with the trade-off I accepted for each. The guiding
principle for Section 1: **a downstream consumer must be able to trust every
value in the table, or see it clearly marked.** I never silently invent or
overwrite data — when a value can't be trusted I set it to `null` and record
*why* in a per-row `data_quality` list.

---

## 1. Data reconciliation (Section 1)

### What's actually wrong with the data (found by inspection, not told to us)
Running [`backend/scripts/normalize_cli.py --print`](backend/scripts/normalize_cli.py) surfaces every issue:

| Issue | Where | Count |
|---|---|---|
| `valence` present only in part2 | all part1-only rows | 12 |
| `duration_ms` recorded in **seconds, not ms** | Sunflower 158, Uptown Funk 270, Sweet Child 356 | 3 |
| out-of-range ratio (`danceability` 1.42, `acousticness` -0.05) | 21 Guns, Another Brick | 2 |
| `tempo = 0` (impossible) | Blinding Lights | 1 |
| `energy = "N/A"` (malformed string) | Yesterday | 1 |
| `energy` key absent for a row | 11:11 | 1 |
| `acousticness = null` | Bohemian Rhapsody | 1 |
| numbers stored as strings (`"0.521"`, `"108.73"`) | 3AM | 2 |
| dirty title (`" 4 walls  "` — leading/trailing/inner whitespace) | row 1 | 1 |
| duplicate title, *different* songs (two "Perfect") | part2 | 1 pair |

Result: **25 unique songs**, 9 fully clean.

### Decision: dedup by `id`, not title
- **Why:** `id` is the stable Spotify-style identifier. Titles are dirty
  (`" 4 walls  "`) and genuinely non-unique (two different songs both named
  "Perfect", different ids). Matching on title would both wrongly merge the two
  "Perfect"s and wrongly split " 4 walls " from "4 Walls".
- **Trade-off:** if the same song ever appeared under two different ids we'd
  keep both. Given the data, id collisions are the right unit; I accept the
  small risk of a genuine cross-id duplicate.
- The two files overlap on **4 ids**. The only real *value* conflict is "Never
  Gonna Give You Up" danceability `0.727` (part1) vs `0.74` (part2).

### Decision: on conflict, **part2 wins — but only if its value is valid**
- **Why part2 is primary:** part2 is the enriched/newer export — it carries
  `valence`, which part1 lacks entirely. That's the signature of a later
  pipeline. So its values are the more current source of truth.
- **Why "only if valid":** part2 is *not* uniformly cleaner (it has the
  seconds-not-ms bug and a negative acousticness). Blindly preferring it would
  let a bad part2 value overwrite a good part1 one. So the rule is: take
  part2's value if it passes validation; else fall back to part1's valid value;
  else `null` + flag. Best of both, and defensible per-field.
- **Trade-off:** slightly more complex than "newest wins," but it never
  discards a good number for a bad one.

### Decision: bad values → **null the value + flag, keep the row** (never drop rows, never clamp)
- **Coerce** clean type errors silently: `"0.521"` → `0.521`. That's a
  formatting difference, not a data problem — no flag.
- **Null + flag** anything out of range / invalid / malformed / missing:
  `danceability_out_of_range`, `tempo_invalid`, `energy_malformed`,
  `acousticness_missing`, etc. The row stays; its other (good) attributes
  remain usable.
- **Why not clamp** (1.42 → 1.0)? Clamping fabricates a plausible-looking value
  and hides the upstream problem. A null the consumer can see beats a lie it
  can't.
- **Why not drop the row?** Too lossy — we'd lose ~5 of 25 songs over a single
  bad field while the rest of each row is fine.
- **Trade-off:** consumers must handle `null`s. That's the honest cost of not
  fabricating data, and the `data_quality` list makes the nulls self-describing.
- **Flag accuracy matters:** an early version of the merge reported a generic
  `_missing` flag for part1-only bad values (because part2's empty side is
  checked first). I fixed `_pick` so the flag names the *real* reason
  (`energy_malformed`, not `energy_missing`) — a mislabeled mark is as bad as no
  mark. See [`normalize.py` `_pick`](backend/app/normalize.py).

### Decision: the units bug (`duration_ms`) → **detect and flag, do NOT convert**
- **Detection:** any `duration_ms` below 10,000 (10 seconds) is physically
  impossible for a song, so it was almost certainly recorded in **seconds**.
  Three rows trip this (158, 270, 356 → 2:38, 4:30, 5:56 as seconds — all
  plausible track lengths).
- **What I store:** the raw value, marked `duration_suspect`. I deliberately do
  **not** auto-multiply by 1000.
- **Why not convert?** Converting *guesses* the upstream intent and bakes that
  guess into the canonical table as if it were fact. "Flag, don't convert"
  keeps the table honest: the value is clearly marked as untrustworthy-as-ms,
  and the fix (and the choice of whether 158 is really seconds) is left to a
  consumer who can see the flag. This still satisfies "trust every value **or
  see it clearly marked**." The API's `/stats/duration` demonstrates the payoff
  — it *excludes* suspect rows from the average instead of averaging garbage.
- **Trade-off:** consumers wanting a clean duration must apply the conversion
  themselves using the flag. Given the ambiguity, surfacing beats silently
  rewriting. *(This was a deliberate override of the "auto-convert" option — I
  chose transparency over convenience.)*

### Decision: `valence` (the extra attribute) → keep it, null for part1-only rows
- Dropping a real audio feature to make the schema symmetric would throw away
  good data. It's a first-class column; part1-only rows get `valence: null` +
  `valence_missing`.

### Decision: `title` cleaning → trim + collapse whitespace, **preserve casing & diacritics**
- Whitespace is noise (`" 4 walls  "` → `"4 walls"`). Casing and diacritics are
  meaning ("Naïve", "God's Plan") and are kept for display. Cleaned titles get a
  `title_cleaned` flag. Matching is done on a normalized key (casefold + collapse
  spaces) at query time, so lookups are case/spacing-insensitive without
  mangling the stored title.

### Kept as-is (documented non-issues)
- `mood` is a 0/1 category in both files (likely major/minor key); consistent,
  so kept as `int`. `num_sections`/`num_segments` appear in both and are valid
  counts; kept.

---

## 2. API design (Section 2)

**Contract**

| Endpoint | Purpose |
|---|---|
| `GET /songs?page&size&sort_by&order` | list, paginate, **sort across the whole dataset then slice** |
| `GET /songs/search?title=` | title lookup — always returns a **list** of matches |
| `GET /songs/id/{id}` | fetch one song by stable id |
| `POST /songs/{id}/rating` `{stars:1-5}` | rate a song, persisted to disk |
| `GET /stats/duration` | honest average duration (excludes suspect + null) |

### Sort-then-paginate, on the server
- Sorting is applied to the **full** dataset, then the page is sliced — the
  opposite of the reviewed buggy file, which sorted only the current page.
  `sort_by` is validated against an allow-list (unknown field → 400, so a bad
  param can't KeyError into a 500). Nulls always sort **last** regardless of
  direction, so missing values never masquerade as the min/max.
- **Trade-off:** re-sorting the whole set per request is O(n log n) every call.
  Fine for 25 rows; for a large table I'd sort in the DB with an index (noted in
  REFLECTION).

### Non-unique titles → return a list, always
- `GET /songs/search` returns `{query, count, matches[]}` — 0, 1, or many.
  A single-object contract can't represent "two Perfects," and forcing the
  client to guess is worse than handing it the array. The frontend renders "no
  match" and "N matches" from `count`.
- Lookup is **case- and spacing-insensitive** (`_normalize_title` = casefold +
  collapse whitespace) but **not fuzzy/spelling-tolerant** — I'd rather return
  nothing than a wrong song. Trade-off: a typo yields no match.

### Rate by `id`, not title; validate; persist to a file
- Ratings key on `id` because titles aren't unique — rating "Perfect" by title
  would ambiguously hit two songs (a real bug in the reviewed file).
- `stars` is validated at two layers: the Pydantic `RatingIn` model rejects
  out-of-range with a 422 before the handler runs, and `store.set_rating`
  re-checks (defense in depth). Unknown id → 404.
- Persistence is a JSON file written **atomically** (tmp + `os.replace`) so
  ratings survive restarts and a crash mid-write can't corrupt the file.
  **Trade-off:** a flat file isn't concurrent-safe across processes; a real
  deployment would use a DB. Fine for this scope (documented in REFLECTION).
- Ratings are merged into song responses as a `rating` field via a **copy**, so
  the canonical in-memory dataset is never mutated (another bug the reviewed
  file had).

---

## What I deliberately left out (and would do with more time)
- **DB layer.** Data lives in a normalized JSON file loaded into memory. For 25
  rows this is right; production wants SQLite/Postgres with indexes for sort.
- **Fuzzy title search.** Exact-normalized only. Would add trigram/`ILIKE`
  matching with a ranked result list.
- **Auth / rate-limiting / per-user ratings.** Ratings are global and anonymous.
- **Frontend tests.** Backend has 49 tests; the React app is manually verified.
  Given the time budget I put test effort where the graded "non-trivial logic"
  lives (normalization, sort, pagination, lookup, rating).
- **Pinning exact upstream provenance** (which file each surviving value came
  from) beyond the quality flags.
