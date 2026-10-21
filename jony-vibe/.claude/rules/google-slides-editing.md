---
name: google-slides-editing
description: "When editing or visually checking a native Google Slides deck through the connector: render slides with read_slide_page_thumbnail (the skill's PDF path needs pdftoppm, absent here), and rewrite text with replaceAllText so run style survives."
---
# Editing and checking a native Google Slides deck

- **Visual QA.** The google-workspace skill's Verify step (Drive PDF export,
  then `render_export.py`) needs `pdftoppm`, which the Mac Studio does not have.
  Render each slide with `read_slide_page_thumbnail` (MEDIUM or LARGE) instead;
  its `contentUrl` downloads with plain `curl`. Save under
  `${BORG_ROOT}/tmp/<deck>-qa/`. Request about 10 at a time: on 2026-10-19,
  ~30 parallel calls drew a connector rate-limit error. System `python3` has no
  Pillow, so build contact sheets with `sips`, Swift, or a venv under `tmp/`.
  After a font or size change, render every slide, not a sample. Slides never
  shrinks text to fit.
- **Rewriting text keeps style only with `replaceAllText`.** In a deck imported
  from .pptx, font, size and color live on each run. `deleteText` ALL followed
  by `insertText` drops them, whatever the skill reference says (2026-10-19:
  the new text came out nearly invisible). When you must delete and reinsert,
  read the old run's `style` first and re-apply it with `updateTextStyle` in
  the same batch, then check the thumbnail.
