# Songs Dashboard — Take-Home

A small full-stack app over a messy song catalog: a Python normalization step
reconciles two dirty JSON exports into one clean table; a FastAPI backend serves
it with pagination, whole-dataset sorting (any column, including rating),
substring title filtering, and persisted star ratings; a React dashboard
consumes it with a sortable paginated table, search-as-filter, CSV export,
editable star ratings, and a songs-by-rating chart with a click-to-open drawer.
The design principle throughout is **every value is trustworthy or dropped** —
bad values become `null` (shown as `—`) rather than being coerced to something
plausible; the reasoning lives in DECISIONS.md.

## Tour of the solution
- `backend/app/normalize.py` — Section 1. Pure reconciliation logic (dedup by
  id, part2-wins-if-valid conflict rule, drop-to-null for bad values, durations
  kept exactly as received). Emits `backend/app/data/songs.normalized.json`.
- `backend/app/store.py` + `main.py` — Section 2. Testable query logic
  (sort/paginate/search/rate) behind a thin FastAPI layer.
- `frontend/` — Section 3. React + Vite + Recharts dashboard.
- `DECISIONS.md`, `REVIEW.md`, `PROMPTS.md`, `REFLECTION.md` — the write-ups.

## Prerequisites
Python 3.11+ and Node 18+ (developed on Python 3.13, Node 23).

## 1. Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# (Re)generate the clean dataset from the two raw exports.
# Prints a data-quality summary; the committed songs.normalized.json is
# already up to date, so this is optional.
python -m scripts.normalize_cli --print

# Run the API (http://localhost:8000, docs at /docs)
uvicorn app.main:app --reload
```

## 2. Frontend

```bash
cd frontend
npm install
npm run dev            # http://localhost:5173
```

The dev server proxies `/api/*` to the backend on `:8000`, so start the backend
first. To point elsewhere: `VITE_API_TARGET=http://host:port npm run dev`.

Production build: `npm run build` (output in `frontend/dist/`).

## 3. Tests

```bash
cd backend
source .venv/bin/activate
python -m pytest -q          # 53 tests: normalization rules, sort (incl. rating),
                             # pagination, substring filter, lookup, rating
                             # validation & persistence, HTTP API
```

## API quick reference
| Method | Path | Notes |
|---|---|---|
| GET | `/songs?page&size&sort_by&order&q` | sort/filter applied to the whole dataset, then paged. `sort_by` = any column incl. `rating` (unrated sorts last); `q` = case/spacing-insensitive **substring** title filter; `size` capped at 100 |
| GET | `/songs/search?title=` | exact (normalized) title lookup; returns a list (0/1/many) |
| GET | `/songs/id/{id}` | one song by stable id |
| POST | `/songs/{id}/rating` | body `{"stars": 1-5}`; persisted; 422 if invalid, 404 if unknown |
| GET | `/stats/duration` | average duration, excluding unit-suspect + missing rows |
| GET | `/health`, `/docs` | liveness, interactive OpenAPI |

## Notable data findings (see DECISIONS.md for the full log)
- 25 unique songs after reconciling on `id` (16 + 13 − 4 overlapping).
- **Unit outlier:** 3 `duration_ms` values are actually seconds — kept exactly
  as received (we don't alter upstream values); `/stats/duration` excludes them
  from the average so a summary stat isn't skewed.
- Out-of-range ratios, `tempo=0`, `"N/A"`, nulls, string-typed numbers, and a
  dirty title are each handled by an explicit, documented rule (bad values are
  dropped to `null`, shown as `—`).
- Two different songs are both titled "Perfect" → titles are not unique, which
  the search/filter handles by showing all matches.
