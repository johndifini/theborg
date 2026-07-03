---
description: Run the monthly assumptions audit interactively, reporting results to this session.
---

Run the monthly assumptions audit interactively. Same audit logic as the
launchd job `com.theborg.c4po-assumptions-audit-monthly`, executed here in
the session instead of on a schedule — no duplicated instructions.

Read and follow the instructions in
`${BORG_ROOT}/c4po/.claude/scheduled/c4po-assumptions-audit-monthly.prompt`.
Treat every occurrence of `${BORG_ROOT}` in that file as the repo root — the
output of `git rev-parse --show-toplevel` (the `theborg` directory).

Three overrides for interactive invocation:
1. SKIP STEP 1 entirely — do not check the state file. An interactive run
   should always execute, regardless of whether the scheduled job already ran
   this month.
2. STEP 3 — do NOT pipe to `notify-email.sh`. Instead, output the report
   directly into this session, including assumptions that are STILL VALID, so
   the run is legible.
3. SKIP STEP 4 entirely — do not write the state file. An interactive run must
   not block the next scheduled run from firing.
