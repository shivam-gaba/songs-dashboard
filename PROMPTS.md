# PROMPTS.md — AI collaboration log

Tool: **Claude Code**. This is a faithful, in-order log of how I drove the AI
to build this submission, with the turning points annotated. The full raw
session transcript is available on request; below is the honest sequence and
where the steering mattered.

> Note on honesty: I let the AI do the typing, but every *decision* below was
> mine — I made the AI surface the choices explicitly and I picked (and in one
> case overruled its recommendation). The signal is in the steering, not volume.

---

### 1. "Look at this folder and see what's up"
Opened cold, no context. The AI read both data files, the buggy API, and the
PDF, then produced a briefing that already spotted the key traps (seconds-not-ms
duration, out-of-range values, the two sort/pagination bugs in the buggy file).

- **Where it got it right first try:** the initial data-quirk inventory was
  accurate and matched what I found reading the files myself.
- **My steer:** rather than let it start coding immediately, I had it stop and
  ask me for scope and how to handle the graded judgment calls. I did **not**
  want a beautiful app with an empty decision log — the rubric explicitly
  punishes that.

### 2. Scope decision
I chose **full-stack, everything**, and — importantly — **collaborative,
decision-by-decision** rather than "AI drafts everything." I wanted to own the
Section-1 reconciliation calls, since that's 30% of the grade and the part an AI
will happily paper over with a plausible-but-arbitrary rule.

### 3. Before any code: verify the data precisely
- **My steer:** I made the AI write a throwaway analysis script to *prove* the
  data issues (exact overlap count, which values conflict, which durations are
  suspect) instead of eyeballing. This turned "I think there's a units problem"
  into "3 specific rows: 158/270/356."
- **Payoff:** the reconciliation decisions rest on facts, and it caught that the
  *only* real value conflict between the files is one danceability value.

### 4. The reconciliation decisions (I decided each)
The AI presented each with a recommendation and trade-offs; my calls:
1. **Dedup by `id`; part2 wins on conflict, but only if the value is valid.**
2. **Bad values → drop the value (null, shown as `—`), keep the row.** (Not
   clamp — I didn't want fabricated numbers. Not drop-row — too lossy. And no
   flag column — see step 5.)
3. **Duration unit outlier → keep exactly as received, do NOT convert.** ←
   *This is where I overruled the AI.* Its recommendation was to auto-detect and
   multiply by 1000. I overrode it: we can't change an upstream value no matter
   how small it looks — converting bakes a *guess* in as fact. `/stats/duration`
   excludes them from its average, but the stored value is untouched.
4. **Non-unique titles → search returns all matches / filters the table.**

### 5. Steering it back to a *user-facing* mindset
The AI's first cut leaked its own engineering into the UI — a `data_quality`
provenance-flag column and footer/subtitle text describing how the backend
works. **It forgot this is a user-facing application**; a listener doesn't need
`duration_suspect` codes. I had it strip all of that: bad values just render as
`—`, and the internal-facing copy is gone. It had also shipped **strict
(exact-normalized) title search** and missed **partial-word search** — searching
"21" wouldn't surface "21 Guns" — so I had it add substring matching and make
the search filter the table in place.

- **Why I care:** the difference between an engineer's debug view and a product.
  The provenance still exists (DECISIONS.md, the raw files); it just doesn't
  belong in a user's face.

### 6. Build the rest, tests first-class
- API: sort-the-whole-set-then-paginate, allow-listed sort fields, substring
  title filter, ratings by id with two-layer validation and atomic persistence.
- **My steer:** treat tests as expected, not bonus, and point them at the
  non-trivial logic the rubric names (normalization rules, sort, pagination,
  filter, lookup, invalid rating). Result: 53 passing tests including explicit
  regression guards for the two buggy-file bugs.
- Frontend: sortable/paginated table, search-as-filter, CSV export, star
  ratings, and a first-pass duration chart (later replaced — see step 8).

### 7. Code review via adversarial verification
For Section 4 I had the AI fan out multiple independent reviewers over
`buggy_api.py` (correctness / HTTP-contract / state / robustness / ops lenses),
then **adversarially verify each finding** to filter out cry-wolf, then I did
the ranking myself. See REVIEW.md, including a note on where the AI over-claimed.

### 8. Second pass: running it, then iterating on the dashboard
After seeing it live I drove a round of product-focused changes:
- **Killed the whole `data_quality` flag system** — bad values just render `—`;
  duration shown `MM:SS:MS`, kept as-is (no convert).
- **Search moved above the table and filters it in place**, debounced to **1s**
  so we don't fire an API call per keystroke; **1-based** row numbers.
- **Replaced the duration chart with a songs-by-rating distribution** (Unrated +
  ★1–★5). When I flagged that a tooltip can't hold 1000+ songs, the fix was to
  **cap the tooltip at 5 and open a side drawer** with the full list on bar
  click. Made the **Rating column sortable** (needed `rating` in the backend
  sort allow-list; unrated sorts last).
- **Caught a real bug I introduced:** the chart fetched `size=1000`, which the
  API rejects (422) because `size` is capped at 100. Fixed by **paging** under
  the cap rather than raising it (raising it would reopen the DoS hole I'd just
  flagged in REVIEW.md).
- Refined REVIEW.md: raised the "rating write mutates the cache but never
  persists" finding from nit to **Major** (it's silent data loss).

---

### Where the AI got it right first try
- The **basic UI and a working API were on point first try** — scaffolding,
  routes, table/pagination, and the happy path came out clean.
- What it consistently *missed* was the **edge cases**: the traps that actually
  matter here (sort-across-the-whole-set, non-unique titles, invalid ratings,
  the seconds-not-ms values, partial search). Those needed my steering — which
  is exactly the split the rubric is testing for.

### Where AI cost / nearly cost me time
- Its instinct to "helpfully" auto-convert the duration would have silently
  rewritten upstream data — caught at the decision gate (step 4.3).
- It defaulted to an engineer's view (provenance flags, backend-y UI copy) and
  to strict search — I had to steer it back to a user-facing product and insist
  on partial-match search (step 5).
