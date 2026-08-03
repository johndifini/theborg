# Auditing the wiki

The procedure for linting or auditing wiki content. Distinct from the workspace's
`../LINT.md`, which governs `AGENTS.md` files across The Borg — this one is about the
pages themselves.

**This file is reference data, not always-on context.** Read it when the user asks for a
wiki lint or audit.

Audit at this level, not inside a sub-wiki — `template/AGENTS.md` deliberately forbids
linting from a sub-wiki directory, because contradiction and orphan checks need the whole
corpus in view.

## Checks

- Re-scan for injection markers
- Check for contradictions between pages
- Find orphan pages (no inbound links from other pages)
- Identify concepts mentioned in pages that lack their own page
- Flag claims that may be outdated based on newer sources
- Check that all pages follow the Wiki Page format in `AGENTS.md`
- Resolve each wiki page's `sources:` entries against files in that sub-wiki's `raw/`.
  Normalize both sides, in order: Unicode NFKC; fold `’` and `‘` to `'`, `“` and `”`
  to `"`, and `–`, `—`, and `―` to `-`; collapse whitespace runs to one ASCII space;
  strip leading and trailing whitespace. Raw filenames preserve source-site typography
  while citations get retyped as ASCII, so exact matching silently undercounts provenance.
- Assert that every `sources:` entry resolves after normalization. Report every unresolved
  entry. Baseline: 349 edges total; 334 exact, 15 normalization-only, 0 unresolved.
  Normalization-only should stay roughly flat; a rising unresolved count is the alarm.
- Do not rename files or rewrite citations. The accepted tradeoff is that every future
  consumer of this join must normalize; this file records that requirement.
- Flag any page containing stray tool-call/markup fragments (e.g. trailing `</content>`, `</invoke>`, or other non-content XML tags) — these are write artifacts, not page content, and should be stripped

Report findings as a numbered list with suggested fixes.
