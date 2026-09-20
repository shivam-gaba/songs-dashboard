# REVIEW.md — PR review of `review/buggy_api.py`

**Verdict: Request changes. Do not merge.** The file runs and returns JSON, but
two independent correctness bugs make the primary `/songs` endpoint return the
wrong records *and* sort them wrongly — so "it returns data" is exactly the trap.
Below, ranked by whether I'd block on it.

> Method: I reviewed it myself, then ran a multi-lens pass (correctness /
> HTTP-contract / state / robustness / ops) and **adversarially verified every
> finding** — each claim had to produce a concrete trigger or be discarded. The
> ranking here is mine. Where the automated pass cried wolf, I say so at the end.

---

## 🔴 Blockers — I would block the PR on these

### B1. Pagination skips the first page entirely — `start = page * size`
- **What:** with 1-based `page` (default 1) and `size` 10, `start = 1*10 = 10`,
  so `/songs` returns `items[10:20]`. **The first 10 songs are unreachable** by
  any normal request; every page is shifted by one (page 1 shows page 2's data).
- **Impact:** every caller on the default/first page gets wrong records, on
  every call. Silent — the response *looks* valid.
- **Fix:** `start = (page - 1) * size` and guard `page >= 1`, `size >= 1`.

### B2. Sorting is applied *after* pagination — it only sorts one page (the subtle one)
- **What:** the code slices first (`page_items = songs[start:end]`) **then**
  `sorted(page_items, ...)`. So it sorts only the rows that happened to land in
  that window; the field/direction never determine *which* rows are on a page.
  `sort_by=title&order=asc` does **not** put the globally-first title on page 1.
- **Impact:** collection-level sorting is non-functional. Page boundaries are
  arbitrary; rows are skipped/repeated as sort params change. This is the bug a
  blind paste ships because it "looks fine and returns data" — the requirement
  (and any real UI) needs a whole-dataset sort.
- **Fix:** sort the full list first, then slice:
  `songs = sorted(songs, key=..., reverse=order=="desc")[start:end]` — and
  validate `sort_by` against an allow-list (see B3).

*(B1 and B2 compound: B1 sorts the wrong window, B2 sorts it wrongly. Either
alone is a merge-blocker.)*

---

## 🟠 Major — must fix before this is trusted, not necessarily merge-blocking

### M1. No validation on `stars` — accepts any integer (the requirement's explicit trap)
- **What:** `rate_song(title, stars: int)` stores whatever it's given —
  `stars=-5`, `0`, `999` all "succeed." Section 2.4 specifically says to handle
  invalid input; this does the opposite. (Bonus smell: `stars` is a bare scalar,
  so FastAPI treats it as a **query param**, not a JSON body —
  `POST /songs/X/rating?stars=3`.)
- **Impact:** garbage ratings enter the store; downstream averages/labels are
  corrupted with no way to reject bad input.
- **Fix:** a Pydantic body model `stars: int = Field(ge=1, le=5)` → automatic
  422; move `stars` into the request body.

### M2. Non-unique `title` used as the resource identifier
- **What:** both `GET /songs/{title}` and `POST /songs/{title}/rating` key on
  title. Titles are **not unique** in the cleaned data (two different songs are
  both "Perfect"). GET silently returns the *first* match; the rating loop writes
  `song["rating"] = stars` to **every** matching row and stores one shared
  `ratings[title]` that collides across distinct songs.
- **Impact:** you can't address a song deterministically; rating "Perfect"
  mutates two different songs at once.
- **Fix:** identify by unique `id` in the path (`/songs/{id}`); keep title as a
  collection filter that returns a list.

### M3. Not-found returns HTTP 200 with an error body
- **What:** `GET /songs/{title}` returns `{"error": "not found"}` with the
  default **200 OK**.
- **Impact:** any client that branches on status (retries, caches, monitoring,
  generated SDKs) reads a miss as success.
- **Fix:** `raise HTTPException(status_code=404, detail="song not found")`.

### M4. Unvalidated `sort_by` → `KeyError` → 500 (and field-probing)
- **What:** `key=lambda s: s[sort_by]` with `sort_by` fully client-controlled.
  Any unknown field 500s; a null/mixed-type column (`None` mixed with `float`,
  which the real data has in `valence`, `energy`, `acousticness`) raises
  `TypeError` → 500 during comparison.
- **Impact:** trivial to crash the main endpoint with a query param; leaks
  internals via stack traces.
- **Fix:** allow-list sortable fields (400 on others); sort `None`s last.

### M5. Ratings are never persisted and split across two stores
- **What:** ratings live in a module-level `ratings = {}` **and** are written
  into cached song dicts — two sources that can diverge, both **in-memory only**.
- **Impact:** the "persists across requests" requirement fails on restart; the
  two stores drift.
- **Fix:** one persistence layer (DB, or an atomically-written file), keyed by id.

### M6. Rating writes only mutate the in-memory cache, not a durable store
- **What:** `rate_song` does `song["rating"] = stars` directly on the objects in
  the mutable-default `_cache` (`load_songs(_cache=[])`). The write lands only in
  that in-process cache; nothing is written back to a database or file.
- **Impact:** **updates are non-persistent** — a rating looks like it saved
  (subsequent reads hit the same cache) but is silently lost on restart/redeploy
  or in any second worker process that has its own cache. That's data loss, not a
  style nit — which is why this is a Major, not the mutable-default idiom alone.
- **Fix:** write ratings through a real store (DB, or an atomic file write),
  keyed by `id`, and never mutate shared cached rows in place — return copies.
- *(Compounds M5: M5 is the split/divergent stores; M6 is that the write never
  reaches durable storage at all — together they mean ratings silently vanish.)*

---

## 🟡 Minor / robustness / nits

- **N1. Cold-start cache is not thread-safe** — FastAPI runs these sync handlers
  on a threadpool; concurrent first requests can double-populate `_cache`. Guard
  with a lock or load once at startup.
- **N2. `/stats/duration` crashes on empty data** — `total / len(songs)` →
  `ZeroDivisionError` (500) if the dataset is empty; and `s["duration_ms"]`
  `KeyError`s if any row lacks the key. Guard both.
- **N3. `load_songs` opens a hardcoded `"songs.json"`** — a bare relative path
  (resolved against CWD) that **doesn't exist in this repo** (the data files are
  `songs_part1/2.json`). Any file/JSON error is unhandled → 500 on every
  endpoint. Make the path configurable and handle load errors.
- **N4. No Pydantic request/response models** — raw scalars in, ad-hoc dicts
  out; no schema, no docs fidelity. Quality issue, not a bug.

---

## Where the automated pass cried wolf (discounted — not real bugs here)
The brief asked me to note this. The multi-lens pass raised these; adversarial
verification showed each does **not** hold against the actual code + data:

- **"Non-numeric `duration_ms` → TypeError"** — *false positive.* All
  `duration_ms` values in the data are numeric; the string/`"N/A"` problems are
  in *other* columns. No trigger.
- **"Missing `title` key → KeyError"** — *false positive.* Every row has a
  `title`; the required trigger (a row without the key) doesn't exist.
- **"DoS via unbounded page size"** — *false positive as stated.* Because of the
  B1 offset bug, a huge `size` yields `songs[huge:huge+huge]` = **empty**, not
  "materialize the whole list." (There *is* a real "no upper bound on size" nit,
  but the claimed memory-blowup mechanism is wrong.)
- **"Docstring/filename mismatch (`songs_api.py` vs `buggy_api.py`)"** —
  *cosmetic, not a bug.* Real observation, wrong severity; discount it.

I also **downgraded** the "POST should be PUT for idempotent rating" finding to a
nit — it's a valid REST observation but nowhere near the correctness bugs.

## What a naive (blind-paste) review misses
The file compiles, starts, and returns JSON, so "does it run?" says pass. The two
things that actually matter — **B1** (wrong records) and **B2** (sort that only
sorts one page) — are invisible unless you trace the index math and the
sort/slice ordering. That's the whole point of the exercise, and it's why I'd
block on B1/B2 over any number of the style nits.
