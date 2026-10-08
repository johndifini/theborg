---
name: git-history-rewrite
description: "When rewriting published git history (filter-repo, force-push): rewrite in a fresh clone, remap SHA citations from that clone's commit-map, and keep the finding open until GitHub Support has purged the orphaned commits."
---
# Rewriting published history: the steps that were re-derived three times

Whether to rewrite is the user's call (`../../../.claude/rules/tracked-agent-files-are-public.md`).
Once they approve one, these are the gotchas the 2026-08-13, 2026-08-16 and
2026-10-03 rewrites each worked out from scratch:

- Rewrite in a fresh clone outside the Drive mirror. After `filter-repo --refs main`, run `git remote remove origin` before any `--all` residue check, or the old remote-tracking ref fails it.
- Before deleting the scratch clone, copy its `.git/filter-repo/commit-map` and use it to remap every tracked SHA citation in the next commit. `~/theborg/.git/filter-repo/commit-map` belongs to an earlier rewrite.
- A force-push does not end public access. GitHub keeps serving orphaned commits by SHA (the commit page, raw files, and every fork's URL) until Support purges them. The finding stays open until all of those return 404.
- File through support.github.com → Repositories → sensitive data purge. State that no fork branch contains the first changed commit. Record the ticket number in the audit state.
- Clear every worktree or branch that pins the old history. Map a worktree's untracked `.claude/` to `<agent>/.claude/`, not root. Warn its owning session first: removing the worktree deletes that session's cwd.
