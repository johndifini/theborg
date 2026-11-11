---
name: claude-bash-grep-is-ugrep
description: "When searching with grep in Claude Code's Bash: grep is an embedded ugrep that rejects large bounded repeats such as .{0,80}foo.{0,40} with 'exceeds complexity limits' (exit 2); use command grep, keep bounds near 30, or grep -C."
---
# In Claude Code's Bash, `grep` is ugrep

Claude Code's shell snapshot replaces `grep` with a function that runs an
embedded ugrep. ugrep rejects a pattern whose bounded repeats of `.` or a
negated class grow too large: `grep -o -E '.{0,80}foo.{0,40}'` fails with
"exceeds complexity limits" and exit 2, while `.{0,30}` works (2026-11-11).
In a `… || …` chain or a loop the error reads like "no match".

For text around a match, use `command grep` (the system grep, which
has no such limit), keep each bound to about 30, or use `grep -C`.
Codex shells don't load the snapshot and get the system grep.

Seen in 15 Claude sessions across atm, waiq, ari, c4po and RANDUG26
between 2026-09-27 and 2026-11-08.
