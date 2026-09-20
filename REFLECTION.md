# REFLECTION.md

> These are honest answers grounded in how the build actually went. Read them
> in your own voice and adjust before submitting — the live follow-up will ask
> about exactly this, so it should be genuinely yours.

### 1. Single weakest part, and why I left it that way
The app is **not deployed anywhere**, ratings persist to a **flat JSON file
rather than a database**, I did **no load testing**, and I didn't add **fuzzy
(spelling-tolerant) search**. With a ~3-hour budget I spent the effort on the
data judgment, the API correctness, and the tests that matter; deployment,
scale-testing, and search fuzziness were conscious scope cuts, not oversights.

### 2. Where AI saved the most time, and where it cost me / nearly led me wrong
- **Saved:** the most time by far went to **coding** — scaffolding, the
  FastAPI/React/Vite wiring, the test harness, CSV, and the first normalization
  pass came out in minutes, so I could spend my time on the judgment calls.
- **Led me wrong: nowhere.** It did reach for questionable defaults a couple of
  times — auto-converting the short durations, and putting backend-flavored copy
  / a provenance column into a user-facing UI — but I caught those at the
  decision points, so nothing wrong actually shipped. The value was in reviewing
  and steering its output, not in it being right unattended.

### 3. What in the data surprised me, and what I chose not to fix
The **duration field** surprised me — a few values are implausibly small (158,
270, 356), i.e. recorded in seconds, not milliseconds. I chose **not to fix it**:
we cannot change an upstream value no matter how small it is when we receive it.
We surface exactly what we were given (and highlight it in the chart / exclude it
from the average), rather than guess the "real" number and store a fabrication.

### 4. If this shipped Monday and real users hit it, what breaks first?
- **Scalability — no load testing was done**, so behavior under real traffic is
  unproven.
- The dashboard **fetches the full dataset on load** (a requirement). That's fine
  for 25 songs but will break for a large catalog — the initial load blows up
  latency and memory. Real scale needs server-side windowing end to end.
- **CORS is wide open** (`allow_origins=["*"]`, dev-only) and must be locked down.
- The **UI hasn't been tested across screen sizes**, so it may break on smaller
  devices.

<!-- Q17 (lead/architect production-grade sketch) intentionally omitted. -->

