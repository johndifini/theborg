---
description: Run the daily security audit interactively, reporting results to this session.
---

Run the daily security audit interactively. Same audit logic as the launchd job
`com.theborg.c4po-security-audit`, executed here in the session instead of
on a schedule — no duplicated instructions.

Read and follow the instructions in
`/Users/user/theborg/c4po/.claude/scheduled/c4po-security-audit.prompt`.
Treat every occurrence of `${BORG_ROOT}` in that file as the literal path
`/Users/user/theborg`.

One override for interactive invocation:
1. Do NOT pipe to `notify-email.sh`. Instead, output the result directly into
   this session. Also drop the silent-if-clean rule: always report what was
   checked and the verdict — including a clean bill of health — so the run is
   legible.
