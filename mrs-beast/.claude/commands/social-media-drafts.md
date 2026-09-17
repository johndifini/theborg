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
   body (pick + why, the post, the follow-up post, and the image prompt) directly
   into this session.
3. Do not record scheduled delivery or consume pending entries in **RECORD
   STATE**. An interactive draft must not mark a topic as spent for the next
   scheduled run. When the user requests a topic for the next or a future
   scheduled draft, save it in the same state's `## Pending topics` section as
   `user-requested`, with date and source references. Re-read before editing,
   deduplicate by subject, and note any draft already supplied in this session.
   A request to draft something here alone does not queue scheduled delivery.
   If the user later says an interactive draft was posted or used, add the topic
   to delivered history as `manual` and remove its pending entry so the scheduled
   job cannot propose it again.
