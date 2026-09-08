---
description: Save a gist of this conversation (or a specific note) to the agent's Auto Memory store.
argument-hint: "[optional: specific thing to remember, otherwise summarize the convo]"
---

# /remember

Save durable context to this agent's Auto Memory store so it persists across sessions.

## Where memory lives

Use the Auto Memory directory for the **git repository root** of the current
working directory:

```
~/.claude/projects/<git-root-with-slashes-as-dashes>/memory/
```

Derivation:

1. Run `git rev-parse --show-toplevel` from the current working directory to get the absolute path of the repo root.
2. Replace every `/` in that path with `-`.
3. The memory store lives at `~/.claude/projects/<that-encoded-string>/memory/`.

Example: cwd `${BORG_ROOT}/bones` → git root `${BORG_ROOT}` →
`~/.claude/projects/<dash-encoded-git-root>/memory/`. All agents under the same
repo share this store.

**Fallback (no git repo):** if `git rev-parse --show-toplevel` fails (not inside a repo), fall back to encoding the current working directory itself with the same dash-replacement scheme, and tell the user you did so.

**Do not** create memory files inside the project tree (e.g. `bones/MEMORY.md`,
`theborg/MEMORY.md`). The Auto Memory directory under `~/.claude/projects/` is
the correct location.

If the `memory/` directory does not exist, create it. Keep `MEMORY.md` as a
concise index, not the sole store: Claude Code loads only its first 200 lines or
25 KB. Put substantive detail in clearly named Markdown topic files in the same
directory and link those files from `MEMORY.md`. If either the index or a topic
file already exists, update it in place without overwriting unrelated entries.

## Cross-agent scope

Because the memory store is keyed to the git repo root, **all agents under the
same repo share it** (e.g., in The Borg: bones, c4po, mrs-beast,
warren-bot-fett all read/write the same directory). Two consequences:

- Name topic files by topic and owning agent when relevant so each agent can
  quickly find its own context. Keep only a short description and link in
  `MEMORY.md`.
- Be mindful of sensitive content — medical/financial notes are visible to sibling agents in the same repo. If something must stay isolated, ask the user before saving.

## What to write

- **If `$ARGUMENTS` is present:** save that specific item. Phrase it as a standing fact or rule, not a transcript line.
- **If `$ARGUMENTS` is empty:** write a concise gist of the current conversation — the durable facts, decisions, and open follow-ups. Skip the back-and-forth. Aim for what a future session would actually need to know.

Choose the narrowest existing topic file that owns the information, or create a
descriptively named topic file when none exists. Keep `MEMORY.md` organized as a
short index with links to those files. When adding to an existing topic, edit in
place rather than duplicating it. When new information contradicts old, update
the old entry instead of appending a second version.

## Before writing

Show the user the proposed addition (file path + exact text) and wait for approval, unless the request is unambiguous (e.g. `/remember the user prefers metric units` — just save it).

## After writing

Confirm the file path and the section(s) touched. Keep the confirmation to one or two lines.
