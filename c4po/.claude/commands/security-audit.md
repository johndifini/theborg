---
description: Run the daily security audit interactively, reporting results to this session.
---

Run the daily security audit interactively. Same audit logic as the launchd job
`com.theborg.c4po-security-audit`, executed here in the session instead of
on a schedule — no duplicated instructions.

Read and follow the instructions in
`${BORG_ROOT}/c4po/.claude/scheduled/c4po-security-audit.prompt`.
Treat every occurrence of `${BORG_ROOT}` in that file as the repo root — the
output of `git rev-parse --show-toplevel` (the `theborg` directory).

Two overrides for interactive invocation:
1. Do NOT pipe to `notify-email.sh`. Instead, output the result directly into
   this session: what was checked and the verdict — including a clean
   `All clear — no findings.` — so the run is legible.
2. SKIP the RECORD STATE step entirely — do not write
   `c4po/.claude/scheduled/state/c4po-security-audit.json`. That file is the
   scheduled run's repeat-classification and `accepted_risks` baseline, and an
   interactive run must not overwrite it. Still READ it as the prompt directs,
   so repeats and accepted risks are classified correctly in what you report;
   only the write is suppressed.
