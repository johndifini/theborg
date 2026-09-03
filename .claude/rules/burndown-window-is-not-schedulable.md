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

Respacing jobs relative to each other does not fix this on its own. The
six-hour grid added to the monthly rows on 2026-09-02 addressed
monthly-vs-monthly collision only, and still left its 03:00 and 09:00 slots
inside the burn window whenever days 1-5 included a Wednesday.

On one day range the two constraints — jobs >5h apart, none inside the
window — cannot both hold: the window leaves 14h10m usable and four such
jobs need >15h, and any 6h grid's largest gap (6h) is narrower than the
window, so a slot always falls in. The monthly jobs are therefore split
across days 1-5 (11:00, 17:00, 23:00) and days 6-10 (11:00); a job alone on
its own day range is free to take a clean hour. If you add a fifth monthly
job, do not try to squeeze it onto days 1-5 — give it its own range.

When adding or moving a model job:
- Prefer Thu-Sun, or Wed afternoon after the weekly reset.
- If a job must run Wed morning, it needs a state gate and a later retry
  firing, so a starved run is a no-op rather than a lost week.
- A job with no state gate (a pure report like `waiq-tts-watch`) must not
  be scheduled Wed at all.

Model-less shell jobs (`kind` of `cli-update` or `script`) are unaffected —
they consume no model budget and may run in this window freely.
