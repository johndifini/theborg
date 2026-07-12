---
name: wiki-query
description: Answer a question from the life wiki and optionally file the answer back as a durable query page.
---

# /wiki-query

## When to use
Any time you ask a question that can be answered from wiki content — synthesis across domains, pattern analysis, timeline reviews, cross-domain connections, or decision support.

## Workflow

1. Read `wikis/index.md` to locate relevant sub-wikis and domains.
2. Read the relevant sub-wiki `index.md` files to find candidate pages.
3. Read those pages and synthesize an answer with inline `[[wikilink]]` citations.
4. If the answer is durable (non-trivial synthesis, worth revisiting), offer to file it back.

**Note on health questions**: Health domain questions are answered from `wikis/health/`. Do not use general knowledge for health facts — only what the wiki sources say.

**Note on relationship/graph questions**: If the question is asking for cross-domain patterns or relationship graph traversal ("who appears in both my health and work domains?", "what housing factors correlate with symptoms?"), note that GBrain is better suited for these queries once it is set up. Answer from the wiki as best you can, and flag that GBrain would give a richer answer.

## Filing a query answer back

When filing:

1. Pick the sub-wiki that best owns the question.
2. Write the page in `wiki/queries/` with a descriptive kebab-case name.
3. Use this frontmatter:
   ```yaml
   ---
   type: query
   status: staged
   domain: <domain>
   date_created: YYYY-MM-DD
   date_updated: YYYY-MM-DD
   source_paths: []
   confidence: high | medium | low
   tags: []
   ---
   ```
4. List all wiki pages and raw sources cited in a `## Sources` section at the bottom.
5. Link the query page from any relevant entity pages.
6. Add it to the sub-wiki `index.md` under a `Queries` section.
7. Append one entry to the sub-wiki `log.md`.

## Good candidates for filing back
- Synthesis across multiple domains
- Pattern analyses
- Cross-domain connections found manually
- Any answer that took non-trivial cross-referencing to produce
- Appointment prep notes (health domain: use `/clinician-brief` instead)
