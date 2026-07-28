---
description: Wrap up this session — closing questions, then retro, memory, backlog, and push in the right order.
argument-hint: "[optional: steps to skip or run only, e.g. 'skip retro' / 'only backlog and push']"
---

# /wrap

Close out the session cleanly: nothing worth keeping dies with the transcript, nothing
half-finished gets committed by accident.

This command **delegates** — it does not restate the logic of the commands it runs. Read
and follow each step's source file when you reach it. Every one of those commands asks for
per-item approval; those confirmations still apply here.

`$ARGUMENTS` may name steps to skip (`skip retro`) or the only steps to run (`only push`).
Honor it and say which steps you skipped.

## Order matters

RETRO and BACKLOG **write files inside the repo** (rules, `AGENTS.md`, `BACKLOG.md`). PUSH
runs last so those writes are included in the commit. Don't reorder.

## Steps

1. **STOCK** — quietly gather: `git rev-parse --show-toplevel`, current branch,
   `git status --short`, `git diff --stat`, and any unpushed commits
   (`git log --oneline @{u}..` — tolerate no upstream). Note which changed files you
   authored this session vs. which a sibling agent left behind.
2. **CLOSING QUESTIONS** — ask in **one** message, at most four questions, then wait.
   Ground them in STOCK and the session, not boilerplate. Useful shapes:
   - Anything you meant to get to that we should backlog?
   - Anything I got wrong or you had to correct that's worth making permanent?
   - Anything here worth remembering for future sessions?
   - Uncommitted work you *don't* want pushed?
   Propose your own answers as defaults so "yep, all of it" is a complete reply. If the
   working tree is clean and the session produced nothing durable, say
   *"nothing to wrap"* and stop — don't manufacture work.
3. **RETRO** — follow `<workspace-root>/.claude/commands/retro.md`, seeded with the
   correction the user named in step 2 (if any). Writing nothing is a normal outcome.
4. **REMEMBER** — follow `<workspace-root>/.claude/commands/remember.md` for durable
   facts the user flagged. Skip if RETRO already saved them; don't write the same fact to
   `MEMORY.md` twice.
5. **BACKLOG** — follow `<workspace-root>/.claude/commands/backlog.md` for the loose ends.
6. **HYGIENE** — only if this session added, renamed, or removed a file under any
   `.claude/commands/`: run `.bin/sync-codex-prompts.sh`, then confirm
   `.bin/sync-codex-prompts.sh --check` passes. Skip when the git root is a `repos/*`
   repository — the bridge is workspace-only.
7. **PUSH** — follow `<workspace-root>/.claude/commands/push.md`. It stages only what you
   authored; respect anything the user held back in step 2. If they declined to push, stop
   after committing (or leave it unstaged) and say so.

Derive `<workspace-root>` from `git rev-parse --show-toplevel`. If cwd is inside a
`repos/*` repository, the workspace commands still live at The Borg root — resolve them
there, and push against the repo you're actually in.

## Output shape

One compact block, four lines max — no per-step narration:

- **Saved:** memory/rule/AGENTS.md writes, or "nothing"
- **Backlogged:** count + titles, or "nothing"
- **Pushed:** commit hash + one-line summary, or what's left uncommitted and why
- **Open:** anything deliberately left for next session
