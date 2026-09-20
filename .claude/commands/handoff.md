---
description: Create a Markdown handoff of the current session for a fresh session to resume.
argument-hint: "[optional: focus or note for the next session]"
---

# /handoff

Create a self-contained Markdown handoff so a fresh session can resume the current
work without access to this transcript. `$ARGUMENTS`, when present, is an additional
focus or note to preserve; it does not replace the evidence gathered below.

This complements native session-copy features such as `/fork`. The artifact is the
portable contract: it must work when the next session uses a different harness.

## Destination

Locate The Borg workspace root as the ancestor that contains all three of:

- `.claude/commands/handoff.md`
- `BACKLOG.md`
- `repos/`

Do not assume the current git root is the workspace root: the current directory may be
inside an independent repository under `repos/`.

Write the handoff only under `<workspace-root>/tmp/`, which is the workspace's shared,
gitignored scratch directory. Create `tmp/` if it is missing. Use a name of the form
`handoff-YYYYMMDD-HHMMSS.md` in local time; if that path exists, append the smallest
unused numeric suffix. Never overwrite or update an existing handoff.

## Gather current evidence

Before drafting, inspect the current session and the live filesystem. At minimum:

1. Resolve the current working directory and any relevant git root(s).
2. For every repository touched by this session, gather the current branch, concise
   `git status --short`, session-authored diff summary, and relevant unpushed commits.
   Distinguish this session's work from pre-existing or sibling-session changes. Do not
   stage, commit, stash, reset, clean, switch branches, or otherwise mutate git state.
3. Record verification actually run and its result. Never claim a check passed merely
   because it was planned.
4. Re-read the files needed to state the present status accurately. Treat the handoff
   as a snapshot that the next session must verify, not as authority over newer disk
   state.

## Required Markdown structure

Use these headings, omitting no heading; write `None` where a section genuinely has no
content:

```markdown
# Session handoff

- Created: <ISO-8601 local timestamp with offset>
- Working directory: <workspace-relative path, or `.`>
- Repository: <workspace-relative repository path, or `none`>
- Branch: <branch name, or `none`>

## Objective
<the user's current desired outcome and success condition>

## Status
<where the work stands now, including whether it is complete, partial, or blocked>

## Completed
<concrete work completed in this session>

## Decisions and constraints
<decisions, user preferences, rejected approaches, safety boundaries, and assumptions>

## Files and git state
<workspace-relative files changed; separate session-authored work from pre-existing or
sibling changes; include branch/unpushed-commit facts that matter>

## Verification
<commands or checks actually run and their results, plus important checks not yet run>

## Blockers and risks
<current blockers, uncertainties, approvals needed, and concurrency or staleness risks>

## Next actions
<ordered, executable next steps with exact paths or commands when useful>

## Resume prompt
Read `<workspace-relative handoff path>` first, verify its git and filesystem snapshot
against the live workspace, then continue from `## Next actions`. Preserve unrelated
changes and do not assume the prior transcript is available.
```

Keep the file concise but sufficient to act without this conversation. Prefer exact
workspace-relative paths, command names, commit hashes, and observed results over prose.

## Privacy and integrity

- The canonical command is public, and `tmp/` is scratch rather than a secrets store.
  Do not include credentials, tokens, cookies, private keys, account numbers, private
  URLs, personal identifiers, confidential source text, or other sensitive values.
- When private material matters, cite its existing workspace-relative source and section
  without copying the private value into the handoff. If even the path is sensitive,
  describe the dependency generically.
- Do not paste transcript excerpts or hidden reasoning. Summarize only facts needed to
  resume the work.
- Do not create or modify any file except the new handoff Markdown file.
- After writing, re-read the file and confirm that every claimed path and verification
  result is accurate and that no obvious sensitive value was copied into it.

## Response

Reply compactly with:

```markdown
Handoff created: <absolute path>

Start the new session with:
Read `<absolute path>` first, verify its git and filesystem snapshot against the live
workspace, then continue from `## Next actions`. Preserve unrelated changes and do not
assume the prior transcript is available.
```
