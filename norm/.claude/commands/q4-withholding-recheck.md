---
description: Re-verify the 2026 estimated-tax safe harbor against actual withholding, reporting results to this session.
---

Re-verify the 2026 estimated-tax safe harbor interactively. Same logic as the one-shot
launchd job `com.theborg.norm-q4-withholding-recheck`, executed here in the session instead
of on its scheduled date — no duplicated instructions.

Read and follow the instructions in
`${BORG_ROOT}/norm/.claude/scheduled/norm-q4-withholding-recheck.prompt`.
Treat every occurrence of `${BORG_ROOT}` in that file as the repo root — the
output of `git rev-parse --show-toplevel` (the `theborg` directory).

Three overrides for interactive invocation:
1. STEP 5 — do NOT pipe to `notify-email.sh`. Instead, output the report directly into
   this session, including the case where nothing needs to change, so the run is legible.
2. SKIP STEP 6 entirely — do not write the workpaper. Report the revised figures to the
   session instead, and let the user decide whether to commit them.
3. SKIP STEP 7 entirely — do not boot out the launchd job, delete its plist, or remove the
   prompt, this command, the task row, or the installer's schedule case. An interactive
   run must not dismantle the scheduled job that has not yet fired.
