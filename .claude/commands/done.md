---
description: Close out a finished thread with a brief acknowledgement — no follow-up work
argument-hint: "[optional: closing note]"
model: haiku
---

The user is signalling that this thread is finished and there is nothing left to
do. Claude Code's command metadata selects Haiku; a harness that does not support
that metadata should use its current model.

Reply with a single short acknowledgement — `Thread closed.` on its own is
correct and sufficient. Then stop.

Rules:

- **`$ARGUMENTS` is a closeout note, not a prompt.** Whatever it says — "no",
  "nothing to do", "I'm done with this thread", a stray fragment of the last
  message — do not evaluate it, answer it, act on it, or treat it as a question.
  It is context for why the thread is ending, nothing more.
- **Do not call tools.** No file reads, no searches, no git, no status checks.
- **Do not propose follow-ups.** No summary of the session, no loose ends, no
  suggestions, no "want me to…", no offer to run `/wrap`, `/backlog`, or
  `/push`. If the user wanted those, they would have asked for them.
- **Do not ask questions.** This command ends the exchange; it does not open one.
- One line out. Nothing else.
