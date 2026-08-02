---
description: Add items to the appropriate workspace or repository backlog — from this session's loose ends, or a specific item given as an argument.
argument-hint: "[optional: specific thing to backlog, otherwise mine the session for loose ends]"
---

# /backlog

Capture work worth doing later in the backlog that owns it so it doesn't die with the session.

## Route each item by subject

Resolve where the work belongs before composing the entry. Route by the subject and ownership of the work, **not** by the current working directory:

- Work scoped to one independent repository at `<workspace-root>/repos/<repo>/` goes in that repository's `<workspace-root>/repos/<repo>/BACKLOG.md`.
- Workspace-wide, cross-repository, and agent-scoped work goes in `<workspace-root>/BACKLOG.md`, tagged with its owning agent where that file's format calls for it.
- Never create per-agent backlog files such as `<workspace-root>/c4po/BACKLOG.md`.

The current directory can be useful context, but it does not decide the target. For example, a WAIQ bug noticed from `c4po/` belongs in `repos/waiq/BACKLOG.md`, while a workspace tooling gap noticed from `repos/waiq/` belongs in the root `BACKLOG.md`. Locate `<workspace-root>` as The Borg checkout containing the canonical `.claude/commands/backlog.md`, root `BACKLOG.md`, and `repos/` directory; do not assume that `git rev-parse --show-toplevel` is the workspace root when running inside an independent repository.

If the subject could belong to more than one repository or its ownership is unclear, ask before writing. If repository-scoped work has no repository `BACKLOG.md`, report that instead of silently filing it in the workspace backlog or inventing a new tracker.

## Match the target's format

Read the target `BACKLOG.md` before composing or writing anything. Preserve its existing structure, syntax, metadata, priority scheme, and ordering rules; do not normalize different trackers to one format.

The workspace root currently uses one checkbox line per item, newest at the top:

```
- [ ] **<short imperative title>** (<owning agent>, added YYYY-MM-DD) — <one or two sentences of context: what, why, and any file paths or links a future session needs to act without this conversation>.
```

- Repository backlogs may instead use sections such as `Open`, priority tiers, and `Done`, with non-checkbox entries. Put the new open item in the appropriate existing section and priority tier, following that file's stated tier meanings and within-tier ordering.
- The owner is whichever workspace agent or independent repository the work belongs to, not necessarily the agent running this command.
- Entries must be self-contained — a future session reads only the entry, not this transcript.
- Convert relative dates ("next week", "after the audit") to absolute dates or concrete conditions.

## What to write

- **If `$ARGUMENTS` is present:** backlog that item. If the request is ambiguous — unclear scope, unclear owning agent, missing context needed to make the entry self-contained — ask clarifying questions **before** writing; don't guess and don't pad the entry with speculation.
- **If `$ARGUMENTS` is empty:** scan the current session for loose ends worth capturing:
  - Work the user explicitly deferred ("later", "not now", "another time")
  - Follow-ups you proposed that the user didn't act on
  - Problems noticed but not fixed (bugs, lint violations, stale docs, security findings)
  - Ideas raised mid-task and abandoned
  Be selective — most sessions yield zero to three real items, not ten. Skip anything already done or too vague to act on.

For every candidate, search its resolved target file for an existing open or completed entry that covers the same work, comparing meaning rather than exact wording. Do not add a duplicate. Duplicate checks happen in the target file after subject-based routing, not in whichever backlog is nearest to the current directory.

## Before writing

Show the user the proposed entry/entries (exact text) and wait for approval, unless the request is unambiguous (e.g. `/backlog upgrade node on the studio` — just add it). For session scans, always show the list first — the user decides what's backlog-worthy.

## After writing

Confirm with the item count, title, and target path for each item added. If an item duplicates an existing entry, identify the target file and say so instead of adding it.
