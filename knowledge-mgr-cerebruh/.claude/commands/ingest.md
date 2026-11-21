---
description: Compile the knowledge base — file docs/to-organize/, then turn every added, updated, moved, or deleted doc into generated-wiki changes, following INGESTING.md.
argument-hint: "[optional: a note about what you just added or changed]"
---

# /ingest

Run the ingest procedure in `knowledge-mgr-cerebruh/INGESTING.md` over the whole of
`knowledge-base/docs/`. Read that file in full first; it is not in context until you do.

Run it from `knowledge-mgr-cerebruh/`. If this session's working directory is anywhere
else, stop and say so: other agents' settings deny writes to the generated wikis, and an
ingest that cannot write its pages stops halfway.

`$ARGUMENTS`, if given, tells you what the user just changed. Treat it as a hint about
where to look first, not as the scope: `ruby docs-changes.rb` decides the scope.

End with what each sub-wiki gained, changed, or lost, and anything waiting on the user
(placements you asked about, duplicates, skipped clippings).
