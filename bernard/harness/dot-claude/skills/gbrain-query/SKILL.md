---
name: gbrain-query
description: Run a semantic + graph query against the gbrain index over the wiki. Use for any cross-domain question where wikilink traversal or vector recall would beat reading folders.
---

# /gbrain-query

## When to use

- The question requires connecting evidence across sub-wikis ("how does housing environment correlate with health symptoms?")
- The curator wants entity-centric recall ("everything that touches Dr. Smith")
- A query needs both vector similarity AND graph traversal — the default `wiki-query` skill does grep+read; this skill leverages the indexed brain.

If a question is purely structural ("what conditions are active?") or scoped to one sub-wiki, prefer `/wiki-query` — no need to hit the brain.

## Pre-flight

```bash
gbrain --version           # must succeed; if not, run .claude/scripts/gbrain-setup.md install steps
gbrain stats               # links > 0 and chunks > 0; if 0, run gbrain extract links --source db
```

## Step 1 — Pick the query mode

| Question shape | Command |
|---|---|
| Open-ended semantic | `gbrain query "<question>"` |
| Entity-centric (one anchor) | `gbrain graph-query <slug> --depth 2` |
| "What connects A and B" | `gbrain query "<A> and <B>"` then `gbrain graph-query <a-slug> --depth 3` for overlap |
| Recall everything about X | `gbrain query "<X>" --limit 50` |

## Step 2 — Run and read

Run the chosen command. Read the returned chunks AND the citation wikilinks. Open the cited pages if needed before answering — don't paraphrase from chunks alone for any health-domain claim.

## Step 3 — Cite, don't synthesize

When reporting back to the curator:
- Quote the exact wikilinks gbrain surfaced (its citations).
- If health-domain: every factual claim still needs a wikilink to its raw source per CLAUDE.md, regardless of what gbrain returned.
- If two cited sources conflict, surface the contradiction — do not average. Apply the health source hierarchy from CLAUDE.md.

## Step 4 — Optionally file back

If the query revealed a new connection worth preserving (a theme, a contradiction, a decision-relevant pattern), create a `query` page in the relevant `queries/` folder following the `query` template. Cite both the gbrain query string and the source pages.

## Notes

- Local Ollama embeddings: queries do not leave the machine. Cloud swap would change this — see `.claude/scripts/gbrain-setup.md`.
- Gbrain ranks compiled-truth chunks above timeline chunks. For pages still using the old single-zone layout, all content ranks equally.
- If gbrain returns no results for an obvious term, run `gbrain sync --repo ~/life-wiki/wikis && gbrain embed --stale` — the index may be behind.
