---
description: Run the monthly lint audit interactively, reporting results to this session.
---

Run the monthly lint audit interactively. Same audit logic as the launchd job
`com.theborg.c4po-lint-audit-monthly`, executed here in the session instead
of on a schedule — no duplicated instructions.

Read and follow the instructions in
`/Users/user/theborg/c4po/.claude/scheduled/c4po-lint-audit-monthly.prompt`.
Treat every occurrence of `${BORG_ROOT}` in that file as the literal path
`/Users/user/theborg`.

Three overrides for interactive invocation:
1. SKIP STEP 1 entirely — do not check the state file. An interactive run should
   always execute, regardless of whether the scheduled job already ran this month.
2. STEP 3 — do NOT pipe to `notify-telegram.sh`. Instead, output the report
   directly into this session. Also drop the silent-if-clean rule: always show
   the full result, including a clean audit with zero findings, so the run is
   legible.
3. SKIP STEP 4 entirely — do not write the state file. An interactive run must
   not block the next scheduled run from firing.
