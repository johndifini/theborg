---
description: Run the monthly assumptions audit on demand (test harness for the launchd job).
---

Run the monthly assumptions audit interactively. This is the test harness for
the launchd job `com.theborg.c4po-assumptions-audit-monthly` — same audit
logic, no duplicated instructions.

Read and follow the instructions in
`/Users/user/theborg/c4po/.claude/scheduled/c4po-assumptions-audit-monthly.prompt`.
Treat every occurrence of `${BORG_ROOT}` in that file as the literal path
`/Users/user/theborg`.

Two overrides for manual invocation:
1. SKIP STEP 1 entirely — do not check the state file. A manual run should
   always execute, regardless of whether the scheduled job already ran this
   month.
2. SKIP STEP 4 entirely — do not write the state file. A manual run must not
   block the next scheduled run from firing.

Everything else applies as written, including STEP 3's silent-if-clean rule
and the Telegram notification (testing the full pipeline is the point of the
test harness).
