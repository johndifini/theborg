---
name: generated-deck-hand-edits
description: "Before regenerating a .pptx (or any document) from its generator script over an existing built file: the user may have edited the built file by hand. Back it up, diff it against a fresh build, and port the edits into the generator before overwriting."
---
# A generated deck may carry the user's hand edits

The user edits built decks directly, in PowerPoint or Google Slides, even when
the repository says the generator is the source of truth. Rebuilding in place
silently discards that work.

Before any rebuild that writes over the existing file:

1. Copy the current file to a timestamped backup (a gitignored path beside it,
   or the workspace `tmp/`).
2. Build to a scratch path, not over the original. Diff the two files slide by
   slide:
   - slide and speaker-note text, after normalizing whitespace and XML entities;
   - shape geometry (`<a:off>` and `<a:ext>`);
   - run properties, including typeface (`<a:latin typeface=…>`) and letter
     spacing (`spc`).
   A Google Slides round trip silently replaced Avenir Next with Avenir and
   dropped the letter spacing, twice on 2026-09-27. A diff of text and
   positions alone missed it.
3. Port every difference into the generator. Rebuild to scratch and diff again,
   until only re-save noise remains. Only then replace the original.
4. Do the check, the backup, and the overwrite in one `set -euo pipefail`
   script that uses absolute paths. On 2026-09-27 a guard with a relative path
   failed after the working directory reset, and the rebuild overwrote the
   deck anyway.

If the diff shows an edit you cannot port faithfully, stop and ask. Do not
choose between the two versions yourself.
