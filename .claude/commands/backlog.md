---
description: Add items to the workspace backlog — from this session's loose ends, or a specific item given as an argument.
argument-hint: "[optional: specific thing to backlog, otherwise mine the session for loose ends]"
---

# /backlog

Capture work worth doing later in the workspace backlog so it doesn't die with the session.

## Where the backlog lives

The single shared backlog file for the whole workspace:

```
<workspace-root>/BACKLOG.md
```

Derive `<workspace-root>` via `git rev-parse --show-toplevel` from the current working directory. All agents share this file. If it doesn't exist yet, create it with a `# Backlog` heading.

**Do not** create per-agent backlog files (e.g. `c4po/BACKLOG.md`) — one file, entries tagged by owning agent.

## Entry format

One checkbox line per item, newest at the top:

```
- [ ] **<short imperative title>** (<owning agent>, added YYYY-MM-DD) — <one or two sentences of context: what, why, and any file paths or links a future session needs to act without this conversation>.
```

- The owning agent is whichever agent the work belongs to (e.g. `c4po` for infra/security, `mrs-beast` for social, `workspace` if it spans agents), not necessarily the agent running this command.
- Entries must be self-contained — a future session reads only the entry, not this transcript.
- Convert relative dates ("next week", "after the audit") to absolute dates or concrete conditions.

## What to write

- **If `$ARGUMENTS` is present:** backlog that item. If the request is ambiguous — unclear scope, unclear owning agent, missing context needed to make the entry self-contained — ask clarifying questions **before** writing; don't guess and don't pad the entry with speculation.
- **If `$ARGUMENTS` is empty:** scan the current session for loose ends worth capturing:
  - Work the user explicitly deferred ("later", "not now", "another time")
  - Follow-ups you proposed that the user didn't act on
  - Problems noticed but not fixed (bugs, lint violations, stale docs, security findings)
  - Ideas raised mid-task and abandoned
  Be selective — most sessions yield zero to three real items, not ten. Skip anything already done, already in `BACKLOG.md` (check for duplicates before adding), or too vague to act on.

## Before writing

Show the user the proposed entry/entries (exact text) and wait for approval, unless the request is unambiguous (e.g. `/backlog upgrade node on the studio` — just add it). For session scans, always show the list first — the user decides what's backlog-worthy.

## After writing

Confirm with the item count and titles added, one line each. If an item duplicates an existing entry, say so instead of adding it.
