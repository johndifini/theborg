---
name: backlog-write-safety
description: Before writing or editing any BACKLOG.md: re-read it from disk first, make the narrowest edit, and verify counts — never write from a copy read earlier in the session.
paths:
  - "**/BACKLOG.md"
---
# Re-read a backlog before writing it

A `BACKLOG.md` is the most-contended file in its repository. Scheduled jobs, the
weekly burndown, sibling agent sessions, and the user all edit it, and a session
that writes from a copy it read earlier silently reverts everything that landed
in between. The damage passes review: the file still parses, the counts still
look plausible, and the diff reads as a large but coherent restructure.

Before writing any `BACKLOG.md`:

1. **Re-read it from disk.** Do not write from a copy in context. Do not trust
   an item count, an item list, or a line number derived earlier in the session
   — including one you derived yourself minutes ago.
2. **Make the narrowest edit that does the job** — check one box, insert one
   line, move one block. Rewrite the whole file only when the task genuinely
   requires it (a full priority reorder is the usual legitimate case), and then
   only from a copy just re-read.
3. **Verify counts after writing.** Compare the open-item count and the
   Done-entry count against what you read moments before. If either dropped
   without you intending it, you clobbered a concurrent writer: restore with
   `git show HEAD:<path> > <path>`, re-apply only your own change, and say so.

Never resolve a surprising count by assuming your copy is the correct one.

**Why this exists.** On 2026-08-15 `repos/waiq/BACKLOG.md` was found holding a
stale whole-file copy that deleted 18 Done records and resurrected the finished
items into the Open tiers — an entire completed P3 tier among them, erasing
twelve real commits from the two preceding days. It was caught only because a
hunk-level read of the diff showed Done entries being deleted rather than added.
Nothing else would have flagged it.

The burndown carries a stricter version of this as STANDING RULE 2 in
`c4po/.claude/scheduled/c4po-backlog-burndown.prompt`, because it is the one job
that rewrites whole backlogs by design. This rule covers everyone else.

**Harness note:** Claude loads this file automatically from `.claude/rules/`.
Codex reaches it through the generated skill stub at
`.agents/skills/backlog-write-safety/SKILL.md`, but only when the model selects
that skill — which is why the root `AGENTS.md` also carries a one-line version.
Neither surface crosses into an independent repo under `repos/`, so each such
repo carries its own line (see `repos/waiq/AGENTS.md`).
