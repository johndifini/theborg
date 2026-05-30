---
description: Run the monthly AI Sleeve rebalance interactively, reporting results to this session.
---

Run the monthly AI Sleeve rebalance interactively. Same logic as the launchd job
`com.john.theborg.warren-bot-fett-ai-sleeve-monthly`, executed here in the
session instead of on a schedule — no duplicated instructions.

Read and follow the instructions in
`/Users/john/theborg/warren-bot-fett/.claude/scheduled/warren-bot-fett-ai-sleeve-monthly.prompt`.
Treat every occurrence of `${BORG_ROOT}` in that file as the literal path
`/Users/john/theborg`.

Overrides for interactive invocation:
1. SKIP STEP 1 entirely — do not gate on weekend/holiday/once-per-month. An
   interactive run should always execute the rebalance.
2. KEEP STEP 6 as written — still read `ai-sleeve/last-rebalance.json` (if it
   exists) and show the month-over-month diff. Reading it is fine; only the
   write is suppressed (see below).
3. STEP 7 — do NOT pipe to `notify-email.sh`. Instead, output the full report
   directly into this session.
4. SKIP STEP 8 entirely — do NOT write `ai-sleeve/last-rebalance.json`. That file
   is the month-over-month diff baseline for the scheduled run; an interactive
   run must not clobber it.
