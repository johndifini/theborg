---
description: Stage this session's changes, commit, and push to the remote
model: sonnet
---

Stage, commit, and push the current changes:

1. Run `git status` and `git diff` to see what changed. If there are no changes (working tree clean and nothing unpushed), say so and stop.
2. This repo (the workspace root — the `theborg/` monorepo, resolve it with `git rev-parse --show-toplevel`) is a shared multi-agent monorepo — sibling agents may leave unrelated uncommitted changes. Stage and commit only the files you changed this session. If `git status` shows changes you did not author, either leave them unstaged or split them into their own commit with an accurate sub-path-scoped message, and confirm before committing anything you did not author.
3. Stage your session's files with `git add <paths>`.
4. Commit with a concise message summarizing the changes, following the style of recent commits (`git log --oneline -5`). If arguments were provided, use them as the commit message: $ARGUMENTS
5. Push to the current branch's remote with `git push`.
6. Report the commit hash and a one-line summary.
