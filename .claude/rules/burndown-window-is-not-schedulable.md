---
name: burndown-window-is-not-schedulable
description: "When adding or rescheduling a Borg model job in .bin/install-scheduled-tasks.sh: Wednesday 01:00 through the weekly usage reset belongs to c4po-backlog-burndown, which is designed to consume the entire remaining budget. Anything else scheduled there fails on the session limit."
paths:
  - ".bin/install-scheduled-tasks.sh"
---
# Wednesday morning is spoken for

`c4po-backlog-burndown` fires Wed 01:00 with a 06:10 retry and its stated
purpose is to spend the whole remaining weekly budget before the reset. It
is not a job that shares. Any other model job scheduled between Wed 01:00
and the weekly reset is competing with something built to leave nothing.

Observed 2026-09-02: the burndown ran to 06:34 and exhausted the window
(reset 11:10am). Four jobs then died on the session limit —
`c4po-lint-audit-monthly`, `c4po-assumptions-audit-monthly`,
`warren-bot-fett-ai-sleeve-monthly`, and `waiq-tts-watch`. Three of those
have a state gate and simply retried later. `waiq-tts-watch` does not: it
exited 1 after two seconds, produced nothing, and no email said so.

Respacing jobs relative to each other does not fix this — the six-hour
spacing added to the monthly rows on 2026-09-02 addresses monthly-vs-monthly
collision only, and still leaves `month-first5-03-00` and
`month-first5-09-00` inside the burn window whenever days 1-5 include a
Wednesday.

When adding or moving a model job:
- Prefer Thu-Sun, or Wed afternoon after the weekly reset.
- If a job must run Wed morning, it needs a state gate and a later retry
  firing, so a starved run is a no-op rather than a lost week.
- A job with no state gate (a pure report like `waiq-tts-watch`) must not
  be scheduled Wed at all.

Model-less shell jobs (`kind` of `cli-update` or `script`) are unaffected —
they consume no model budget and may run in this window freely.
