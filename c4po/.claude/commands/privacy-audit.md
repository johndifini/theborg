---
description: Run the monthly private-information audit interactively, reporting results to this session.
---

Run the monthly private-information audit interactively. Use the same logic as
the launchd job `com.theborg.c4po-privacy-audit-monthly`, executed here in the
session instead of on a schedule — no duplicated instructions.

Read and follow the instructions in
`${BORG_ROOT}/c4po/.claude/scheduled/c4po-privacy-audit-monthly.prompt`.
Treat every occurrence of `${BORG_ROOT}` in that file as the repo root — the
output of `git rev-parse --show-toplevel` (the `theborg` directory).

Four overrides for interactive invocation:
1. SKIP STEP 1 entirely — do not check the state file. An interactive run
   should always execute, regardless of whether the scheduled job already ran
   this month.
2. STEP 3 — do NOT pipe to `notify-email.sh`. Report findings directly in this
   session, then stop exactly as the step requires.
3. STEP 4 — do NOT pipe to `notify-email.sh`. Report the clean result directly
   in this session so the run is legible.
4. SKIP STEP 5 entirely — do not write the state file. An interactive run must
   not block the next scheduled run from firing.
