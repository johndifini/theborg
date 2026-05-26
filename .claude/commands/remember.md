---
description: Save a gist of this conversation (or a specific note) to the agent's Auto Memory file.
argument-hint: "[optional: specific thing to remember, otherwise summarize the convo]"
---

# /remember

Save durable context to this agent's Auto Memory file so it persists across sessions.

## Where memory lives

Write to the Auto Memory path for the **current working directory**:

```
~/.claude/projects/<cwd-with-slashes-as-dashes>/memory/MEMORY.md
```

`<cwd-with-slashes-as-dashes>` = the absolute path of the current working directory with every `/` replaced by `-`. Example: cwd `/Users/john/theborg/bones` → `~/.claude/projects/-Users-john-theborg-bones/memory/MEMORY.md`.

**Do not** create memory files inside the project tree (e.g. `bones/MEMORY.md`, `bones/NOTES.md`). The Auto Memory location is the only correct place.

If the `memory/` directory does not exist, create it. If `MEMORY.md` does not exist, create it. If it does exist, append/update in place — don't overwrite unrelated sections.

## What to write

- **If `$ARGUMENTS` is present:** save that specific item. Phrase it as a standing fact or rule, not a transcript line.
- **If `$ARGUMENTS` is empty:** write a concise gist of the current conversation — the durable facts, decisions, and open follow-ups. Skip the back-and-forth. Aim for what a future session would actually need to know.

Organize MEMORY.md by topic with `##` headings. When adding to an existing section, edit in place — do not duplicate. When new information contradicts old, update rather than appending a second version.

## Before writing

Show the user the proposed addition (file path + exact text) and wait for approval, unless the request is unambiguous (e.g. `/remember John prefers metric units` — just save it).

## After writing

Confirm the file path and the section(s) touched. Keep the confirmation to one or two lines.
