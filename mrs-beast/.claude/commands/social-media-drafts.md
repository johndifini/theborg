---
description: Generate the social-media post draft interactively, reporting the result to this session.
---

Generate the social-media post draft interactively. Same logic as the launchd
job `com.theborg.mrs-beast-social-media-drafts`, executed here in the
session instead of on a schedule — no duplicated instructions.

Read and follow the instructions in
`${BORG_ROOT}/mrs-beast/.claude/scheduled/mrs-beast-social-media-drafts.prompt`.
Treat every occurrence of `${BORG_ROOT}` in that file as the repo root — the
output of `git rev-parse --show-toplevel` (the `theborg` directory).

The prompt's phases are named (GATHER, FILTER, SELECT, COMPOSE, LINKS, VERIFY,
OUTPUT, RECORD STATE). Apply these overrides for interactive invocation,
referenced by phase name:

1. In the **FILTER** phase — still read the topics log and still report which
   candidates it excluded, but if the log rules out everything, say so and draft
   the best available candidate anyway rather than sending an empty run. An
   interactive run is on-demand and should produce something.
2. In the **OUTPUT** phase — do NOT pipe to `notify-email.sh`. Output the full
   body (pick + why, the post, the verbatim ChatGPT footer with the post
   repeated beneath it) directly into this session.
3. Skip the **RECORD STATE** phase entirely — do not create or append to the
   topics log. An interactive run must not mark a topic as spent for the next
   scheduled run.
