---
description: Generate the social-media post drafts interactively, reporting results to this session.
---

Generate the social-media post drafts interactively. Same logic as the launchd
job `com.john.theborg.mrs-beast-social-media-drafts`, executed here in the
session instead of on a schedule — no duplicated instructions.

Read and follow the instructions in
`/Users/john/theborg/mrs-beast/.claude/scheduled/mrs-beast-social-media-drafts.prompt`.
Treat every occurrence of `${BORG_ROOT}` in that file as the literal path
`/Users/john/theborg`.

One override for interactive invocation:
1. Do NOT pipe the drafts to `notify-email.sh`. Instead, output them directly
   into this session.
