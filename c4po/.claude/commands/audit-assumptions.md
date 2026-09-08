---
description: Run the monthly memory-governance and assumptions audit interactively, reporting results to this session.
---

Run the monthly memory-governance and assumptions audit interactively. Same
audit logic as the launchd job `com.theborg.c4po-assumptions-audit-monthly`,
executed here in the session instead of on a schedule — no duplicated
instructions.

Read and follow the instructions in
`${BORG_ROOT}/c4po/.claude/scheduled/c4po-assumptions-audit-monthly.prompt`.
Treat every occurrence of `${BORG_ROOT}` in that file as the repo root — the
output of `git rev-parse --show-toplevel` (the `theborg` directory).

Five overrides for interactive invocation:
1. Skip **STAGE 1 — GATE** entirely — do not check the state file. An interactive run
   should always execute, regardless of whether the scheduled job already ran
   this month.
2. In **STAGES 2-6**, private paths and contents may be inspected when needed
   because the result stays in this user-visible session. Keep private material
   out of tracked files, generated public snapshot data, and unrelated tool
   output; do not reveal more than the review requires.
3. In **STAGE 5 — SELECT**, the user may request a larger or narrower candidate
   cohort. Otherwise keep the scheduled run's bounded selection policy.
4. In **STAGE 9 — REPORT**, do NOT pipe to `notify-email.sh`. Instead, output the report
   directly into this session, including assumptions that are STILL VALID, so
   the run is legible.
5. Skip **STAGE 10 — RECORD GENERATED STATE** entirely — do not replace the
   snapshot or write the monthly gate state. An interactive run must not block
   the next scheduled run or make its review ledger claim scheduled completion.

This command remains report-only. `--apply` is reserved for migration step 7
and is not implemented by this command yet.
