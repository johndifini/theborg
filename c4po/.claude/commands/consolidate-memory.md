---
description: Run the weekly memory consolidation interactively, reporting results to this session.
---

Run the weekly memory consolidation interactively. Same logic as the launchd job
`com.theborg.c4po-consolidate-memory`, executed here in the session instead of on
a schedule — no duplicated instructions.

Read and follow the instructions in
`${BORG_ROOT}/c4po/.claude/scheduled/c4po-consolidate-memory.prompt`.
Treat every occurrence of `${BORG_ROOT}` in that file as the repo root — the
output of `git rev-parse --show-toplevel` (the `theborg` directory).

Three overrides for interactive invocation:
1. SKIP STEP 1 entirely — do not check the state file. An interactive run should
   always execute, regardless of whether the scheduled job already ran this week.
2. STEP 4 — do NOT pipe to `notify-email.sh`. Instead, output the digest directly
   into this session. Also drop the silent-if-clean rule: always report what was
   examined and what changed, including "no changes" for a store already tidy, so
   the run is legible. (The consolidation itself in STEP 3 still runs for real —
   that is the point of the command.)
3. SKIP STEP 5 entirely — do not write the state file. An interactive run must not
   block the next scheduled run from firing.
