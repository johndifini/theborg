---
description: Run the weekly dream (session harvest → proposals) interactively, reporting to this session.
argument-hint: "[optional: harvest window, e.g. 'last 14 days']"
---

Run the weekly dream interactively. Same logic as the launchd job
`com.theborg.c4po-dream`, executed here in the session instead of on a schedule —
no duplicated instructions.

Read and follow the instructions in
`${BORG_ROOT}/c4po/.claude/scheduled/c4po-dream.prompt`.
Treat every occurrence of `${BORG_ROOT}` in that file as the repo root — the
output of `git rev-parse --show-toplevel` (the `theborg` directory).

The prompt's phases are named (GATE, WINDOW, HARVEST, OUTPUT, RECORD STATE).
Apply these overrides for interactive invocation, referenced by phase name:

1. Skip the **GATE** phase entirely — do not check the weekly state file. An
   interactive run should always execute, regardless of whether the scheduled job
   already ran this week.
2. In the **WINDOW** phase — do not read the state file for the boundary. Use the
   last 7 days, or the window named in `$ARGUMENTS` if one is given (e.g. "last 14
   days").
3. In the **OUTPUT** phase — do NOT pipe to `notify-email.sh`. Output the full
   digest into this session, and drop the silent-if-empty rule: say "nothing
   cleared the bar" when that is the outcome. For cerebruh candidates, do NOT
   auto-stage into `cerebruh/ingest/`; instead show the proposed source file (path
   + content) and ask before staging it. (Rule / CLAUDE.md / skill candidates
   remain propose-only, exactly as in the scheduled run.)
4. Skip the **RECORD STATE** phase entirely — do not write the state file. An
   interactive run must not move the harvest-window boundary for the next
   scheduled run.
