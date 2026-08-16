---
name: shared-checkout-git-safety
description: "When running git in this workspace: a sibling agent session may be editing the same checkout — never use tree-wide commands (stash, reset --hard, checkout .) to inspect state, and re-derive branch relationships immediately before acting on them."
---
# Git in a shared, concurrently-edited checkout

`~/theborg` is one working directory shared by every agent, and sessions run
concurrently. `ListAgents` shows who else is live. Two failures happened here on
2026-08-16; both were caught without damage, and neither was noticed by the
session that caused it.

## 1. Never use a tree-wide command to inspect state

Do not run `git stash`, `git stash pop`, `git reset --hard`, `git checkout .`, or
`git clean` to answer a question. They act on the **whole tree**, including
another session's uncommitted work, which git attributes to nobody.

The specific near-miss: `git stash` → run a command → `git stash pop`, purely to
diff a script's output against its committed baseline. That swept a sibling
agent's in-flight changes into the stash and back. It restored cleanly, but a
concurrent write during the window would have lost their work, and nothing would
have reported it.

Instead:
- Compare against a committed state with `git show <ref>:<path>`, or check out a
  single path into a temp file — never mutate the tree.
- Split a shared file's changes with `git diff` → per-hunk patch →
  `git apply --cached`. `git add -p` is interactive and unavailable here.
- Before any command that *does* have to touch the tree, run `git status --short`
  and confirm it is empty. If it is not, find out whose it is first.
- Commit your own work before switching branches, so it cannot ride along onto
  someone else's.

## 2. Re-derive git relationships immediately before acting on them

A branch relationship is a fact about two moving pointers, and **your own
commits invalidate it**. Claiming "this is a fast-forward", then committing to
`main`, then merging with `--ff-only` fails — the claim was true when made and
stale when used. A sibling agent caught this one, not the session that made it.

Re-run `git merge-base --is-ancestor`, `git log <upstream>..`, or `git status -sb`
in the same turn you act on the answer. Never carry a branch fact forward from
earlier in a session, including one you derived yourself minutes ago. This is the
same hazard `backlog-write-safety` covers for file contents.

## 3. Coordinate rather than assume

When a sibling session owns the work, message it (`SendMessage`) and wait rather
than guessing its intent — whether a branch is finished, whether work is ready to
publish. Committing or merging another agent's work without asking is a judgment
call that usually belongs to them or to the user. Their independent verification
is also worth having: on 2026-08-16 the sibling caught both errors above.
