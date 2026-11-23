---
description: Find un-pushed work across The Borg's git repos, then prune merged branches and stale worktrees — report first, delete only after confirmation.
argument-hint: "[optional: --report (no changes) | a repo path to limit the scan, e.g. repos/atm]"
---

# /git-cleanup

Audit every git repository in the workspace for work that exists only on this
machine, then clean up branches and worktrees that no longer hold anything.
The job is **find, report, confirm, then delete** — never the other order.

`$ARGUMENTS`: `--report` stops after step 4 and changes nothing. A path limits
the run to that repository. Empty means every repository, with cleanup.

This checkout is shared by concurrent sessions. Follow
`.claude/rules/shared-checkout-git-safety.md` throughout: never run
`git stash`, `git reset --hard`, `git checkout .`, `git clean`, or a branch
switch in a repository's main checkout, and re-derive every fact in the same
turn you act on it.

## 1. Find the repositories

From the workspace root (`git rev-parse --show-toplevel`):

```sh
find . \( -name node_modules -o -path ./bernard -o -path '*/.claude/worktrees' \) -prune \
  -o -name .git -type d -print
```

(`-type d` skips linked worktrees, whose `.git` is a file; step 3 finds those
through `git worktree list`.)

That is the workspace itself, each child of `repos/`, and any stray repository
(for example one under `tmp/`). Scan them all. Label a repository under `tmp/`
as scratch in the report, but still look for un-pushed work in it — scratch is
where forgotten commits hide.

## 2. Refresh remote state

For each repository with a remote, run `git fetch --prune --quiet`. It changes
only remote-tracking refs, never the tree. If a fetch fails (offline, auth),
say so and treat that repository's "pushed" and "merged" claims as unknown:
report it, delete nothing in it.

Find the default branch with
`git symbolic-ref --short refs/remotes/origin/HEAD` (fall back to `main`).

## 3. Collect state — read-only

For each repository, gather:

- **Uncommitted changes** in every worktree: `git -C <wt> status --short`.
  Report the counts and paths. Never touch them; in the shared checkout they may
  belong to another session.
- **Stashes**: `git stash list`. Report only; never pop or drop.
- **Worktrees**: `git worktree list --porcelain`. For each one record its path,
  branch, whether the directory still exists (`prunable`), whether it is
  locked, and whether it is dirty.
- **Branches**: `git for-each-ref refs/heads --format='%(refname:short)%09%(objectname:short)%09%(upstream:short)%09%(upstream:track)%09%(committerdate:short)'`.
  For each branch decide:
  - *Un-pushed*: no upstream and not merged into `origin/<default>`, or
    `[ahead N]` against its upstream. List the commits with
    `git log --oneline <upstream-or-origin/default>..<branch>`.
  - *Merged*: `git merge-base --is-ancestor <branch> origin/<default>`.
  - *Squash- or rebase-merged*: not an ancestor, but either
    `git cherry origin/<default> <branch>` prints only `-` lines, or the
    upstream is `[gone]` and `gh pr list --state merged --head <branch> --json number,headRefOid`
    returns a PR whose `headRefOid` equals the branch tip. Anything short of
    that exact match is un-pushed work, not merged.
  - *Checked out*: its name appears in a worktree's `branch` line. A checked-out
    branch is never deleted.

`warning: ignoring ref with broken name refs/heads/Icon?` is not a branch. It is
a Google Drive `Icon\r` file inside `.git`. Report it and point to
`.bin/sweep-git-icon-files.sh`, the scheduled sweep for those files. Never
`git branch -D` it or hand-delete files under `.git/`.

Then find who is using each non-primary worktree. List live sessions
(`ListAgents`, and in Claude Desktop `mcp__ccd_session_mgmt__list_sessions`)
and match their working directories against worktree paths. Treat a worktree
under `.claude/worktrees/` with no matching session as possibly in use by a
session you cannot see — say so rather than assuming it is abandoned.

## 4. Report

One section per repository, in this order:

1. **Un-pushed work** — branch, commit count, the commit subjects, and whether
   a worktree holds it. Include un-pushed commits on the default branch itself.
   Lead with this; it is the point of the command.
2. **Uncommitted changes and stashes** — where and how many.
3. **Proposed deletions** — a table of each branch and worktree you would
   remove, with its tip SHA and the reason (merged, squash-merged as PR #N,
   prunable worktree).
4. **Kept, and why** — everything else, briefly.

A repository with nothing to report gets one line. If `$ARGUMENTS` is
`--report`, stop here.

## 5. Confirm

Ask with `AskUserQuestion` — one question per category that has candidates,
with multi-select so the user can drop items:

- Delete the merged branches listed.
- Remove the clean, unused worktrees listed (and `git worktree prune` the
  missing ones).
- Push the un-pushed branches listed. Offer this only for branches that have
  an upstream or an obvious remote; never offer a force push, and never push
  another session's branch without the user naming it.

Silence or "no" means leave it. Approval covers only the items listed in that
question.

## 6. Act

For each approved item, re-check its state first (rule 2 of the shared-checkout
rule — your own pushes and a sibling's commits both move pointers):

- **Branch, merged**: `git branch -d <branch>`. If git refuses, stop on that
  branch and report it; do not escalate to `-D`.
- **Branch, squash-merged**: re-run the exact `headRefOid` match, then
  `git branch -D <branch>`. This is the only case `-D` is allowed.
- **Worktree**: re-run `git -C <wt> status --short` and confirm it is empty and
  its branch is pushed or merged, then `git worktree remove <wt>` (no
  `--force`). A worktree the Claude Desktop app created is better removed with
  `mcp__ccd_host__clean_up_worktrees` when that tool is available, so the app's
  session records stay consistent. Warn the owning session first if one exists:
  removing its worktree deletes its working directory.
- **Missing worktrees**: `git worktree prune`.
- **Push**: `git push` (or `git push -u origin <branch>` for a new upstream).
  Report a rejected push; do not pull, rebase, or force to get past it.

Never delete the default branch, the current branch of any worktree, a locked
worktree, or anything in a repository whose fetch failed.

## 7. Close

Report what was deleted, pushed, and kept. For every deleted branch, print a
restore line, since the reflog is the only other way back:

```sh
git -C <repo> branch <branch> <full-sha>
```

End with the workspace's closing sections. Un-pushed work the user chose to
keep is a follow-up.
