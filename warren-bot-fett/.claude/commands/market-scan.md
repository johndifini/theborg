---
description: Run the daily market scan interactively, reporting results to this session.
---

Run the daily market scan interactively. Same logic as the launchd job
`com.john.theborg.warren-bot-fett-daily-market-scan`, executed here in the
session instead of on a schedule — no duplicated instructions.

Read and follow the instructions in
`/Users/john/theborg/warren-bot-fett/.claude/scheduled/warren-bot-fett-daily-market-scan.prompt`.
Treat every occurrence of `${BORG_ROOT}` in that file as the literal path
`/Users/john/theborg`.

Two overrides for interactive invocation:
1. SKIP STEP 1 entirely — do not stop on market holidays. An interactive run
   should always execute, regardless of whether markets are open today.
2. STEP 7 — do NOT pipe to `notify-email.sh`. Instead, output the result
   directly into this session. Also drop the silent-if-clean rule: always show
   the full scan (current vs. target allocations, any flagged deviations, and
   whether a genuine buying opportunity exists) even when there's no opportunity
   to act on, so the run is legible.
