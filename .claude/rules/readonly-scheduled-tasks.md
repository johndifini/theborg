---
name: readonly-scheduled-tasks
description: "When authoring or running a scheduled task whose .conf sets REPORT=1 (the read-only kind, editing .bin/run-scheduled-task.sh or a .claude/scheduled/*.conf): it has no Bash, no state gate and cannot email itself, so the runner's generic preamble does not apply to it."
paths:
  - ".bin/run-scheduled-task.sh"
  - "**/.claude/scheduled/*.conf"
---
# REPORT=1 tasks cannot do what the generic preamble tells them to do

`.bin/run-scheduled-task.sh` prepends one preamble to every job, ending
"Perform every phase below yourself, including the state gate, the
notify-email.sh delivery, and the state write."

A task whose `.conf` sets `REPORT=1` is read-only — typically
`--allowedTools "WebSearch,WebFetch"`, deliberately no Bash so a fetched page
cannot inject actions into the repo. It has no state gate, cannot reach
`notify-email.sh`, and cannot write state. The runner captures its stdout and
emails that on success. All three duties in the generic preamble are false
for it, and the runner now says so — but the guidance below still applies to
anyone editing either side.

Observed on all five `waiq-tts-watch` runs in the week of 2026-08-19: three ran
`find` sweeps across the workspace hunting for `notify-email.sh`, one spawned a
subagent to look for it, and one concluded the wrapper text was "spurious."
Each eventually did the right thing — but only by reasoning past its own
instructions, which is exactly the state in which a run silently does the
wrong thing instead.

- **Authoring a read-only task:** set `REPORT=1` in the `.conf` and say plainly
  in the `.prompt` what the run is expected to emit. The runner suppresses the
  three-duties sentence for `REPORT=1`, so do not restate it.
- **Running as one:** if Bash is unavailable, that is by design, not a fault to
  route around. Do not search the filesystem for `notify-email.sh`, do not
  spawn a subagent to find it, and do not treat the absence as a reason to
  abandon the task. Produce the report on stdout and stop.
- **Editing the preamble:** it is built after the `.conf` is sourced, because
  `REPORT` is not known before that. Keep it there — moving the construction
  back above the sidecar silently reintroduces the mismatch for every
  read-only task at once.
