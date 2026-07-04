---
description: Stage all changes, commit, and push to the remote
model: sonnet
---

Stage, commit, and push the current changes:

1. Run `git status` and `git diff` to see what changed. If there are no changes (working tree clean and nothing unpushed), say so and stop.
2. Run `git add -A` to stage everything.
3. Commit with a concise message summarizing the changes, following the style of recent commits (`git log --oneline -5`). If arguments were provided, use them as the commit message: $ARGUMENTS
4. Push to the current branch's remote with `git push`.
5. Report the commit hash and a one-line summary.
