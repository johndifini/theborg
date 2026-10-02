---
name: codex-plugin-skills-not-bridged
description: "Third-party Claude Code plugins are NOT bridged to Codex by sync-codex-rule-skills.sh or the command bridge. Codex sees one only if it was hand-copied into ~/.codex/skills/, where it then drifts silently. Check before promising a plugin-backed capability from Codex."
---
# A Claude Code plugin is not available to Codex

The Borg bridges exactly two things to Codex: `.claude/rules/*.md` via
`.bin/sync-codex-rule-skills.sh`, and `.claude/commands/*.md` via the command
bridge, whose output is tracked in `~/.codex/skills/.theborg-managed-skills.tsv`.
**Neither covers third-party Claude Code plugins.** A plugin under
`~/.claude/plugins/` is invisible to Codex.

So a workflow that works in Claude Code degrades quietly in Codex. On
2026-09-15 a Codex run of `mrs-beast/ai-week-image-prompt` had no
`/last30days`, researched the week from the web alone, and shipped a
"Tooling health" caveat on the deliverable. The same job under Claude Code
had the tool.

Before promising a plugin-backed capability from Codex, check it is there:

    comm -23 <(command ls ~/.codex/skills | sort) \
             <(cut -f1 ~/.codex/skills/.theborg-managed-skills.tsv | sort)

Anything it prints is in the directory but absent from the TSV: a **hand-copied
plugin**, not a bridged artifact — nothing re-syncs it, so it goes stale the
next time the Claude plugin updates and nothing reports that. `last30days` is
currently one: v3.8.3, copied 2026-09-15.

When you do copy one, take it from the versioned plugin **cache**
(`~/.claude/plugins/cache/<plugin>/`), not the marketplace checkout, which can
be behind (observed 2026-09-15). Then verify with one live query rather than
assuming the copy loaded.

A scheduled job that depends on a plugin-backed tool must report the tool as
missing when it is, the way the 2026-09-15 run did. A quiet fallback to a
weaker source reads as a normal week.
