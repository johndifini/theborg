---
name: session-wrap
description: End-of-session cleanup — run when done with a work session to leave the wiki in a consistent, committed state. Runs structural lint, verifies sources.md coverage, updates the domain log and AGENT-HANDOFF.md, stages and commits wiki changes, and prints the GBrain reindex command.
---

# /session-wrap

End-of-session cleanup. Run this when you're done with a work session to ensure the wiki is in a consistent, committed state.

## Steps

### 1. Structural lint

```bash
bash .claude/scripts/wiki-lint-structural.sh
```

Fix any **critical** issues before proceeding. Warnings are acceptable if pre-existing — note any new ones.

### 2. Verify sources.md coverage

For every file moved or processed this session: confirm it has a row in `wikis/sources.md`. Batch entries are acceptable for admin/duplicate files. No source should be unregistered.

### 3. Update the domain log

Append a session entry to the relevant `log.md` (usually `wikis/health/clinical/wiki/log.md` for health sessions, or the appropriate domain log). Include:
- Date and session type
- Files/records created or updated
- Key clinical findings now in wiki
- Any contradictions or flags raised

### 4. Update AGENT-HANDOFF.md

Update these fields:
- `Last Session` — date, agent, summary of what changed
- `Last Structural Lint` — date + result
- `Ingest Queue` counts — set to 0 for any pipeline you cleared
- `Active Sessions` phase status — mark completed phases done
- `Open Items` — check off completed items; add any new flags discovered this session

### 5. Check for uncommitted files

```bash
git status
```

Stage and commit everything wiki-related. Use a clear commit message describing what changed. Do not commit audio binaries or `.env` files.

Commit message format:
```
health: <one-line summary of what changed>

<bullet points of key items if needed>

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
```

### 6. Print GBrain update command

After committing, output this for the curator to run manually:

```
gbrain import ~/life-wiki/wikis/ --no-embed && gbrain embed --stale && gbrain extract links --source db
```

Do not run it yourself — it requires an active Ollama instance and may be slow.

### 7. Report

Output a brief summary:
- Lint result (0 critical / N warnings)
- Files committed
- New open items added to AGENT-HANDOFF
- Any curator actions needed (Tier B reviews, open questions, flagged contradictions)
