---
description: Save a gist of this conversation (or a specific note) to the agent's Auto Memory file.
argument-hint: "[optional: specific thing to remember, otherwise summarize the convo]"
---

# /remember

Save durable context to this agent's Auto Memory file so it persists across sessions.

## Where memory lives

Write to the Auto Memory path for the **git repository root** of the current working directory:

```
~/.claude/projects/<git-root-with-slashes-as-dashes>/memory/MEMORY.md
```

Derivation:

1. Run `git rev-parse --show-toplevel` from the current working directory to get the absolute path of the repo root.
2. Replace every `/` in that path with `-`.
3. The memory file lives at `~/.claude/projects/<that-encoded-string>/memory/MEMORY.md`.

Example: cwd `/Users/john/theborg/bones` → git root `/Users/john/theborg` → `~/.claude/projects/-Users-john-theborg/memory/MEMORY.md`. All agents under the same repo share this file.

**Fallback (no git repo):** if `git rev-parse --show-toplevel` fails (not inside a repo), fall back to encoding the current working directory itself with the same dash-replacement scheme, and tell the user you did so.

**Do not** create memory files inside the project tree (e.g. `bones/MEMORY.md`, `theborg/MEMORY.md`). The Auto Memory location under `~/.claude/projects/` is the only correct place.

If the `memory/` directory does not exist, create it. If `MEMORY.md` does not exist, create it. If it does exist, append/update in place — don't overwrite unrelated sections.

## Cross-agent scope

Because the memory file is keyed to the git repo root, **all agents under the same repo share it** (e.g., in The Borg: bones, c4po, mrs-beast, warren-bot-fett all read/write the same `MEMORY.md`). Two consequences:

- Organize entries by topic *and* by owning agent when relevant (e.g., `## Skincare (bones)`, `## Portfolio prefs (warren-bot-fett)`) so each agent can quickly find its own context.
- Be mindful of sensitive content — medical/financial notes are visible to sibling agents in the same repo. If something must stay isolated, ask the user before saving.

## What to write

- **If `$ARGUMENTS` is present:** save that specific item. Phrase it as a standing fact or rule, not a transcript line.
- **If `$ARGUMENTS` is empty:** write a concise gist of the current conversation — the durable facts, decisions, and open follow-ups. Skip the back-and-forth. Aim for what a future session would actually need to know.

Organize MEMORY.md by topic with `##` headings. When adding to an existing section, edit in place — do not duplicate. When new information contradicts old, update rather than appending a second version.

## Before writing

Show the user the proposed addition (file path + exact text) and wait for approval, unless the request is unambiguous (e.g. `/remember John prefers metric units` — just save it).

## After writing

Confirm the file path and the section(s) touched. Keep the confirmation to one or two lines.
