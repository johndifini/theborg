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

The prompt's phases are named (GATE, SCOPE, CONSOLIDATE, REPORT, RECORD STATE).
Apply these overrides for interactive invocation, referenced by phase name:

1. Skip the **GATE** phase entirely — do not check the weekly state file. An
   interactive run should always execute, regardless of whether the scheduled job
   already ran this week.
2. In the **REPORT** phase — do NOT pipe to `notify-email.sh`. Output the digest
   directly into this session, and drop the silent-if-clean rule: always report
   what was examined and what changed, including "no changes" for an already-tidy
   store, so the run is legible. (SCOPE and CONSOLIDATE still run for real — the
   skill consolidates each store; that is the point of the command.)
3. Skip the **RECORD STATE** phase entirely — do not write the state file. An
   interactive run must not block the next scheduled run from firing.
