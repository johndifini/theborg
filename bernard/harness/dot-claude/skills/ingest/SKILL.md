---
name: ingest
description: Process whatever is ready in ingest/. Handles single files and bulk batches automatically — no need to choose.
---

# /ingest

Run this whenever the sanitizer has dropped files into `ingest/`, or when you want to process a specific file.
It decides batch vs. single automatically.

## Step 0 — Structural pre-check

Run `bash .claude/scripts/wiki-lint-structural.sh`. If it reports any critical issues, fix them before proceeding.

**Take the shared write-lock** so the scheduled write jobs (synthesis/ingest/backlinks) defer instead of clobbering this ingest: `bash .claude/scripts/wiki-lock.sh acquire "ingest (claude)"`. Release it at close-out (Step 5): `bash .claude/scripts/wiki-lock.sh release`. (A forgotten hold self-frees after 2 h.) See CLAUDE.md "Concurrency and multi-agent safety".

## Step 1 — Inventory

Check what's pending (all files land flat in `ingest/` root — no subdirectories):

```bash
find ~/life-wiki/ingest -maxdepth 1 -name "*.md" ! -name ".gitkeep" ! -name "smoketest*" ! -name "queue*" | sort
```

If nothing is found, report "Nothing pending in ingest/ — done." and stop.

**All files are pre-sanitized. Process everything regardless of sidecar tier or flags.**
Speaker roles are determined by reading transcript content — not from the sidecar's `speakers[]` field.

## Step 2 — Route

**If a specific file was named in this conversation:** process that file only.

**Otherwise (one or more files pending):** process all pending `.md` files in order. For each file: read the full content, determine routing from content (appointment recording → `wikis/journal/raw/transcripts/` + journal entry; clinical doc → `wikis/health/clinical/raw/`; etc.), extract entities, create/update wiki pages, link bidirectionally, move the source file **and its sidecar** (see Step 2a), update indexes. If the batch is too large to finish in one session, process as many as possible and record the last file completed in `AGENT-HANDOFF.md`.

## Step 2a — Move rule: BOTH files, always

When moving a processed transcript, **always move both the `.md` and the paired `.meta.json` together:**

```bash
mv ingest/FILENAME.md        wikis/.../raw/transcripts/FILENAME.md
mv ingest/FILENAME.meta.json wikis/.../raw/transcripts/FILENAME.meta.json
```

**Never leave an orphaned `.meta.json` in `ingest/`.** The `ingest/` directory must be empty after a session (or contain only unprocessed files actively in the queue). Orphaned sidecars break pipeline integrity and are indistinguishable from unprocessed files on first glance.

## Step 3 — Read, extract, connect (REQUIRED — not optional)

Moving a file to `raw/` is not a complete ingest. For every file processed:

1. **Read the full content.** No skipping, no bulk-archiving without reading.
2. **Extract entities:** providers (name, specialty, facility), conditions, medications (name, dose), procedures, lab values, dates, follow-up actions.
3. **Populate structured frontmatter** on the entry page:
   - `providers: [slug-one, slug-two]` — every provider mentioned; slugs must match filenames in `wikis/health/shared/providers/`
   - `conditions: [slug-one, slug-two]` — every condition mentioned; slugs from `wikis/health/shared/conditions/`
   - `medications: [slug-one, slug-two]` — every medication mentioned; slugs from `wikis/health/shared/medications/`
   - GBrain uses these for entity resolution (metadata), but only body `[[wikilinks]]` create traversable graph edges.
4. **Update entity page timelines:** For each entity where a wiki page exists, add a dated bullet to its `## Timeline` section linking back to this entry. For each entity where no page exists, create one using the appropriate template (or flag to curator if identity is uncertain).
5. **Add an `## Entity Links` section** at the end of the entry page body. Include an inline `[[wikilink]]` for every provider, condition, and medication in the frontmatter lists. Use this format:
   ```
   ## Entity Links

   **Providers:** [[wikis/health/shared/providers/slug-one]] · [[wikis/health/shared/providers/slug-two]]
   **Conditions:** [[wikis/health/shared/conditions/slug-one]]
   **Medications:** [[wikis/health/shared/medications/slug-one]]
   ```
   This is required — frontmatter fields alone do not create graph edges in GBrain. Also add inline wikilinks in the body whenever referencing a prior clinical record (e.g., `see [[wikis/health/clinical/wiki/records/YYYY-MM-DD-description]]`).

Entity page locations (never mix):
- Providers → `wikis/health/shared/providers/`
- Conditions → `wikis/health/shared/conditions/`
- Medications → `wikis/health/shared/medications/`
- Biomarkers → `wikis/health/shared/biomarkers/`
- Personal (non-clinical) people → `wikis/shared/people/`

For large document collections: process each document individually. If the collection is too large to finish in one session, record the last file processed in `AGENT-HANDOFF.md` and continue next session. Never leave a collection "filed but unread."

## Step 4 — Update GBrain index

After all files are processed and wiki pages are written, update the search index. GBrain's sync job runs only daily (03:00) and only picks up **committed** changes — since ingest sessions don't auto-commit, you must run this manually:

```bash
gbrain import ~/life-wiki/wikis/ --no-embed \
  && gbrain embed --stale \
  && gbrain extract links --source db
```

This typically takes 2–5 minutes depending on how many new pages were created. Wait for it to complete before ending the session.

## Step 4.5 — Batch / parallel-ingest verification (REQUIRED for batches)

> **Why this step exists:** single-file ingests are reliable, but **parallel
> multi-agent batches are the one path that has regressed twice** — they have
> re-introduced real PHI (the 66-file batch re-added the patient name ×429 across
> 147 files) and left duplicate `-source.md` artifacts and unrecorded files.
> Structural lint catches neither. See `AGENT-HANDOFF.md` "Last Session".

**Whenever this ingest fanned out across multiple agents/contexts, or processed
more than a handful of files, run before close-out:**

```bash
bash .claude/scripts/post-ingest-verify.sh
```

It checks four things and **exits non-zero if any fail** — do not close out on a
non-zero result:

1. **PHI re-introduction** — distinctive redaction targets (DOB/phone/MRN/Medicaid
   + full names/addresses) reappearing anywhere in `wikis/`. It prints only
   filenames, never values. *This is a fast tripwire;* for a confirmed-clean
   result run the sanitizer repo's full fuzzy battery as well.
2. **Stray `-source.md` artifacts** — the duplicate-page residue parallel batches
   produce. Merge into the canonical page and delete.
3. **Orphaned `.meta.json`** in `ingest/`.
4. **Bracket-wrapped `[[REDACTED-*]]` placeholders** — these create phantom GBrain
   graph nodes; unwrap them.

If PHI is flagged, re-run the sanitizer pass on the named files and **stop to
flag the curator** — a batch that re-introduced PHI means the upstream sanitizer
let it through.

## Step 5 — Close out

After processing, verify the coordination contract:
- `wikis/sources.md` has a new row for every file moved out of `ingest/`
- The domain's `wiki/log.md` has a new entry
- `AGENT-HANDOFF.md` updated: `Last Session`, ingest queue cleared, lint result recorded
- If processing was partial: record exactly which file to continue from next session
- **`ingest/` contains no orphaned `.meta.json` files.** Run `ls ~/life-wiki/ingest/*.meta.json 2>/dev/null` — if anything prints, move those sidecars to the same destination as their paired transcripts before ending the session.
- **For batch/parallel ingests:** `bash .claude/scripts/post-ingest-verify.sh` exited 0 (Step 4.5).
