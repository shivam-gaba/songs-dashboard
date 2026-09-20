# REFLECTION.md

> These are honest answers grounded in how the build actually went. Read them
> in your own voice and adjust before submitting — the live follow-up will ask
> about exactly this, so it should be genuinely yours.

### 1. Single weakest part, and why I left it that way
**The frontend has no automated tests, and ratings persist to a flat JSON file
rather than a database.** With a ~3-hour budget I deliberately spent the test
effort where the rubric puts the weight and where the real logic lives — the
backend normalization/sort/pagination/lookup/rating (49 tests). The React app
is manually verified end-to-end but not unit-tested. The file-based rating store
is correct for a single process (atomic writes) but isn't safe under concurrent
processes. Both are conscious scope calls, not oversights.

### 2. Where AI saved the most time, and where it cost me / nearly led me wrong
- **Saved:** scaffolding and boilerplate — the FastAPI/React/Vite wiring, the
  test harness, CSV serialization, and the first normalization pass came out in
  minutes, freeing time for the judgment calls.
- **Nearly led me wrong:** the AI wanted to *auto-convert* the suspect duration
  values (× 1000). That's the "helpful" move that silently bakes a guess into
  the canonical data as if it were fact. I overrode it to **flag, don't
  convert**.
- **Cost me a beat:** its first merge implementation mislabeled data-quality
  flags (generic `_missing` instead of the real reason like `energy_malformed`).
  Plausible-looking, subtly wrong — the exact failure mode a blind paste ships.

### 3. What in the data surprised me, and what I chose not to fix
- **Surprise:** the units bug is disguised as ordinary small integers (158, 270,
  356). Nothing flags itself as wrong; you only catch it if you know a song
  can't be 158 ms. Also that two genuinely different songs share the title
  "Perfect."
- **Didn't fix — duration:** I detect and flag it but don't rewrite it. The
  conversion is a *guess* about upstream intent; storing it as fact would be
  dishonest. The flag lets a consumer decide.
- **Didn't fix — fuzzy title search:** lookup is case/spacing-insensitive but
  not spelling-tolerant. I'd rather return "no match" than a confidently wrong
  song.

### 4. If this shipped Monday and real users hit it, what breaks first?
The **rating store under concurrency.** Two simultaneous `POST /rating` calls
across worker processes can race on the flat file, and the in-memory dataset is
loaded once at startup, so nothing scales horizontally cleanly. Close behind:
`CORS allow_origins=["*"]` is dev-only and must be locked down, and there's no
auth or rate-limiting, so `size` and unbounded requests are a mild DoS surface
(the API caps `size` at 100, which helps). None of these are correctness bugs in
the single-process dev setup, but they're the first things to fail in prod.

### 5. (Lead/architect) What it would take to make this production-grade
- **Data pipeline:** move normalization into a scheduled/triggered job writing to
  a real store (Postgres); version the schema; keep the `data_quality`
  provenance as first-class columns; add validation gates that alert when an
  upstream export exceeds a bad-value threshold instead of silently ingesting.
- **Storage/API:** sort & paginate in the DB with indexes (not in-memory per
  request); ratings in a table keyed by (user, song); optimistic concurrency.
- **Testing:** keep the unit tests, add contract tests against the OpenAPI
  schema and a few Playwright E2E flows for the dashboard.
- **Observability:** structured logs, request tracing, a `/metrics` endpoint,
  and a dashboard on data-quality flag rates (a spike = upstream regression).
- **Deployment:** containerize; CI running tests + build; staged rollout; lock
  CORS to known origins; add auth + rate-limiting at the edge.
- **Where I'd draw the v1 line:** DB-backed data + ratings, indexed sort,
  locked-down CORS, and CI-run tests. Fuzzy search, per-user auth, and the
  full observability stack are v1.1.
