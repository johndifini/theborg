---
name: inbox-triage
description: Drain the companion question inbox — each line is a question Bernard (the VPS WhatsApp companion) could not answer from the mirrored wiki, i.e. a wiki gap. Fix the gap, then move the line to the archive. Use after a mirror sync pulls new questions, or when wiki-eval/self-interrogate file [eval]/[self-interrogate] items.
---

# /inbox-triage

Drain the companion question inbox. Every line in `.claude/inbox/wiki-question-inbox.md` is a question Bernard (the VPS WhatsApp companion) could NOT answer from the mirrored wiki — each one is a wiki gap. Triage = fix the gap so the same question is answerable after the next mirror sync.

**Flow context:** friend texts Bernard → Bernard searches its mirror → unanswerable questions get logged on the VPS → `vps-mirror-sync.sh` pulls-and-drains them into the local inbox (deduped against this file + the archive). This skill is the curation half of that loop.

## Steps

### 1. Read the inbox

```bash
cat .claude/inbox/wiki-question-inbox.md
```

Group similar lines first — repeated questions about the same topic are ONE gap (and a strong signal it matters to the reader).

### 2. For each gap, locate the failure

Find out why the wiki couldn't answer. Search the compiled wiki first (never bulk-search `raw/`):

```bash
bash .claude/scripts/wiki-query "<the question>"
```

Plus targeted grep over `wikis/health/shared/` and `wikis/health/wiki/`. Classify the gap:

- **Missing synthesis** — facts exist across pages but no single page answers it (e.g. "current medications" scattered across med pages, visit notes, and tracking logs) → create a synthesis page in the right shared/wiki location, two-zone pattern, every claim cited.
- **Thin entity page** — the page exists but lacks the asked-for content → enrich the compiled-truth zone; promote `staged` → `active` if it now qualifies.
- **Genuinely unanswerable** — the wiki has no source for it → add it to the right page under `wikis/health/shared/questions/` so it's tracked and citable.

### 3. Fix it

Follow normal page rules: frontmatter standard, citations on every factual claim, `## Entity Links` section, index updates. Remember the downstream reader — plain-language summary at the top, since Bernard quotes these pages to a non-technical person.

### 4. Archive the line

Move each handled line from `wiki-question-inbox.md` to `.claude/inbox/inbox-archive.md`, appending the resolution:

```
- 2026-06-12 — current medication med list — no single reconciled page  [done 2026-06-12 → wikis/health/wiki/current-medications.md]
```

(Lines must MOVE, not copy — the mirror sync dedupes new pulls against both files, so a line left in the inbox stays "pending".) Create the archive file with a one-line header if it doesn't exist.

### 5. Close the loop

1. GBrain reindex (required after any page changes):
   `gbrain import ~/life-wiki/wikis/ --no-embed && gbrain embed --stale && gbrain extract links --source db`
2. Confirm the next mirror sync ships the new pages — check `.claude/logs/wiki-mirror-sync.log` after the next 07:00/login run, or note for the curator to run `bash .claude/scripts/vps-mirror-sync.sh`.
3. Update `AGENT-HANDOFF.md` (Last Session + note remaining inbox count).
