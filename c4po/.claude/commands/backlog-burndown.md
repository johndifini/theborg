---
description: Run the weekly backlog burndown interactively — prioritize all backlogs, build the consolidated plan, and implement items, reporting to this session.
---

Run the backlog burndown interactively. Same logic as the launchd job
`com.theborg.c4po-backlog-burndown`, executed here in the session instead of
on a schedule — no duplicated instructions.

Read and follow the instructions in
`${BORG_ROOT}/c4po/.claude/scheduled/c4po-backlog-burndown.prompt`.
Treat every occurrence of `${BORG_ROOT}` in that file as the repo root — the
output of `git rev-parse --show-toplevel` (the `theborg` directory).

Overrides for interactive invocation, by the prompt's named phases:

1. GATE — skip entirely and treat the run as FRESH; do not read or write the
   state file or the plan file, so this never blocks, unblocks, or resumes the
   scheduled run.
2. WINDOW — skip; run regardless of day and time.
3. PRIORITIZE — as written (the reordering and commits are real).
4. CONSOLIDATE — do NOT write the plan file. Present the consolidated,
   prioritized plan in this session instead, and track check-offs/skips
   in-session for the rest of the run.
5. NOTIFY PLAN — do NOT pipe to `notify-email.sh`; the plan presented in this
   session replaces the email.
6. RECORD STATE — skip; never write the state file.
7. BURN — as written (source BACKLOG.md check-offs and commits are real),
   except: confirm with the user before starting the first item (they may
   want only the prioritization), and stop when the user says stop rather
   than running until credits are exhausted.
8. WRAP — do NOT email; report the summary (completed / skipped / needs-user,
   with commit hashes) to this session.
