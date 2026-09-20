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

### 4. The four reconciliation decisions (I decided each)
The AI presented each with a recommendation and trade-offs; my calls:
1. **Dedup by `id`; part2 wins on conflict, but only if the value is valid.**
2. **Bad values → null + `data_quality` flag, keep the row.** (Not clamp — I
   didn't want fabricated numbers. Not drop-row — too lossy.)
3. **Duration unit bug → flag only, do NOT convert.** ← *This is where I
   overruled the AI.* Its recommendation was to auto-detect and multiply by
   1000. I overrode it: converting bakes a *guess* into the canonical table as
   fact. Flagging keeps the table honest and pushes the ambiguity to a consumer
   who can see the mark. The AI adjusted and implemented detection-without-
   mutation, and made `/stats/duration` exclude the flagged rows.
4. **Non-unique titles → title lookup always returns a list.**

### 5. Catching an AI mistake mid-build
After the first normalization run, the quality flags were **wrong**: part1-only
bad values were being labeled generic `_missing` instead of their real reason
(a `"N/A"` energy showed as `energy_missing`, not `energy_malformed`). The AI
noticed its own merge logic checked the empty part2 side first. It fixed the
flag-selection so the mark names the true reason.

- **Why I care:** the whole premise is "trust the value or see it clearly
  marked." A *mislabeled* mark is as bad as none. This is exactly the kind of
  subtle-but-important thing a blind paste ships.

### 6. Build the rest, tests first-class
- API: sort-the-whole-set-then-paginate, allow-listed sort fields, ratings by
  id with two-layer validation and atomic file persistence.
- **My steer:** treat tests as expected, not bonus, and point them at the
  non-trivial logic the rubric names (normalization rules, sort, pagination,
  lookup, invalid rating). Result: 49 passing tests including explicit
  regression guards for the two buggy-file bugs.
- Frontend: sortable/paginated table, CSV export, list-returning title search,
  star ratings, and a duration bar chart chosen specifically because it makes
  the seconds-not-ms rows visually vanish.

### 7. Code review via adversarial verification
For Section 4 I had the AI fan out multiple independent reviewers over
`buggy_api.py` (correctness / HTTP-contract / state / robustness / ops lenses),
then **adversarially verify each finding** to filter out cry-wolf, then I did
the ranking myself. See REVIEW.md, including a note on where the AI over-claimed.

---

### Where AI cost / nearly cost me time
- Its instinct to "helpfully" auto-convert the duration would have silently
  corrupted the canonical data — caught at the decision gate (step 4.3).
- The flag-mislabeling bug (step 5) — plausible output that was subtly wrong;
  needed a human to insist the mark be *accurate*, not just present.
