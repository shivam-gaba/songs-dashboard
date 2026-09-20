# DECISIONS.md

Decisions I made, with the trade-off I accepted for each. The guiding
principle for Section 1: **every value in the table is trustworthy, or it is
dropped.** I never invent, coerce-to-plausible, or overwrite data — when a
value can't be trusted I set it to `null`, which the dashboard renders as `—`.
There is no separate quality-flag column: for a user-facing app the absence of
a value is itself the mark, and showing internal provenance codes would be
noise.

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

Result: **25 unique songs**; 12/25 rows have no null fields.

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
  else `null`. Best of both, and defensible per-field.
- **Trade-off:** slightly more complex than "newest wins," but it never
  discards a good number for a bad one.

### Decision: bad values → **drop the value (null → `—`), keep the row** (never clamp, never drop rows)
- **Coerce** clean type errors silently: `"0.521"` → `0.521`. That's a
  formatting difference, not a data problem.
- **Drop to `null`** anything out of range / invalid / malformed / missing
  (e.g. `danceability = 1.42`, `tempo = 0`, `energy = "N/A"`, absent keys). The
  value shows as `—`; the row stays and its other (good) attributes remain
  usable. The merge (`_pick`) still prefers whichever source has a *valid*
  value before falling back to null, so we only drop when neither file offers a
  usable number.
- **Why drop rather than flag?** This is a user-facing app. A listener doesn't
  need provenance codes; a blank cell already communicates "not available."
  Provenance stays discoverable in this doc and the raw source files.
- **Why not clamp** (1.42 → 1.0)? Clamping fabricates a plausible-looking value
  and hides the upstream problem. A blank the user can see beats a lie it can't.
- **Why not drop the row?** Too lossy — we'd lose ~5 of 25 songs over a single
  bad field while the rest of each row is fine.
- **Trade-off:** consumers must handle `null`s, and the *reason* a value is
  missing is no longer machine-readable per-row (it lives in this doc instead).

### Decision: the units bug (`duration_ms`) → **keep exactly as received (no convert, no flag)**
- **Detection:** any `duration_ms` below 10,000 (10 seconds) is physically
  implausible for a song — recorded in seconds, not ms. Three rows trip this
  (158, 270, 356 → 2:38, 4:30, 5:56 as seconds).
- **What I store:** the raw value, unchanged. I do **not** convert it and I do
  **not** flag it in the data.
- **Why not convert?** We cannot change an upstream value no matter how small it
  looks — converting *guesses* the true value and bakes that guess in as fact.
  We surface exactly what we were given.
- **Where the quirk still shows:** detection-by-magnitude is used only for the
  honest average — `/stats/duration` excludes the short outliers so a summary
  stat isn't skewed by values in the wrong unit — never to alter the stored data.
- **Trade-off:** the table shows a few very short durations (e.g. `00:00:158`).
  That's the honest state of the upstream data; we don't paper over it.

### Decision: `valence` (the extra attribute) → keep it, null for part1-only rows
- Dropping a real audio feature to make the schema symmetric would throw away
  good data. It's a first-class column; part1-only rows get `valence: null`
  (shown as `—`).

### Decision: `title` cleaning → trim + collapse whitespace, **preserve casing & diacritics**
- Whitespace is noise (`" 4 walls  "` → `"4 walls"`). Casing and diacritics are
  meaning ("Naïve", "God's Plan") and are kept for display. Matching is done on a
  normalized key (casefold + collapse spaces) at query time, so lookups are
  case/spacing-insensitive without mangling the stored title.

### Kept as-is (documented non-issues)
- `mood` is a 0/1 category in both files (likely major/minor key); consistent,
  so kept as `int`. `num_sections`/`num_segments` appear in both and are valid
  counts; kept.

---

## 2. API design (Section 2)

**Contract**

| Endpoint | Purpose |
|---|---|
| `GET /songs?page&size&sort_by&order&q` | list, substring-filter (`q`), **sort across the whole (filtered) set then slice**; `size` capped at 100 |
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
- **Sortable by any column, including `rating`** — the user-supplied rating is
  attached at response time and added to the sort allow-list; **unrated songs
  sort last** in both directions (same nulls-last rule).
- **`size` is capped at 100** (a DoS guard). The dashboard's chart, which needs
  every song, pages under that cap rather than asking for an unbounded `size` —
  a request like `size=1000` is rejected with 422 by design.
- **Trade-off:** re-sorting the whole set per request is O(n log n) every call.
  Fine for 25 rows; for a large table I'd sort in the DB with an index (noted in
  REFLECTION).

### Search-as-filter (dashboard UX)
- The dashboard's search box filters the table in place via a `q` **substring**
  filter on `GET /songs` (case/spacing-insensitive), so filtering, sorting, and
  pagination all operate on the same server-side result set. Typing "21" matches
  both "21" and "21 Guns". The exact-match `GET /songs/search` endpoint remains
  for the precise API contract.
- **Trade-off:** substring matching is more forgiving (good for humans) but can
  return broad results; the exact endpoint stays available when precision
  matters.

### Presentation choices (user-facing dashboard)
- Rows are displayed **1-based** (`index + 1`) for readability; the stable
  0-based `index` is unchanged in the data/API.
- Duration is shown as **`MM:SS:MS`** (e.g. `03:45:947`) rather than raw ms.
- **No data-quality flags column** in the UI — dropped/missing values simply
  render as `—`. Durations are shown exactly as received (a short one reads as
  e.g. `00:00:158`); `/stats/duration` excludes those outliers from its average,
  but the table itself never editorializes.

### Chart choice: songs-by-rating distribution (Section 3.7)
- The dashboard chart is a **distribution of songs across rating classes**
  (Unrated + ★1–★5). It's the honest, user-relevant view for this app — it shows
  how the catalog is being rated and updates live as the user rates.
- **Scalability built in:** the hover tooltip previews at most 5 songs, and
  **clicking a bar opens a side drawer** with the full, scrollable list for that
  class — so the chart never tries to render 1000+ songs in a tooltip. For a very
  large catalog the drawer would page that list from the API (a `rating=` filter)
  rather than the in-memory set; noted as future work.
- *(An earlier version charted duration to expose the seconds-not-ms outliers;
  replaced because a rating breakdown is more useful to an actual listener.)*

### Non-unique titles → search returns all matches; table filters in place
- The dashboard search box **filters the table** to every match (0, 1, or many),
  case/spacing-insensitively and by substring (see Search-as-filter above), so
  "no match" is an empty table and "many" is several rows — both handled without
  a special contract.
- The `GET /songs/search` endpoint remains for exact-match API use and returns
  `{query, count, matches[]}`; a single-object contract couldn't represent "two
  Perfects."

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
- **Fuzzy title search.** Substring + case/spacing-insensitive, but not
  spelling-tolerant. Would add trigram/`ILIKE` matching with ranked results.
- **Auth / rate-limiting / per-user ratings.** Ratings are global and anonymous.
- **Frontend tests.** Backend has 53 tests; the React app is manually verified.
  Given the time budget I put test effort where the graded "non-trivial logic"
  lives (normalization, sort, pagination, lookup, rating).
- **Pinning exact upstream provenance** (which file each surviving value came
  from) beyond the quality flags.
