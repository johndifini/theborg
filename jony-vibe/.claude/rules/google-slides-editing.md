---
name: google-slides-editing
description: "When editing or visually checking a native Google Slides deck through the connector: render slides with the thumbnail tool (read_slide_page_thumbnail in Claude, google_drive_get_slide_thumbnail in Codex; the skill's PDF path needs pdftoppm, absent here), rewrite text with replaceAllText so run style survives, scope notes edits to the notes page, keep bold and link runs through deck-wide font or color changes, change palette colors in the theme, order replaceAllText requests so a later pattern can't match an earlier one's output, read long Google Docs as text with read_file_content, and unwrap a saved read_doc with jq '.content' before docs_index.py."
---
# Editing and checking a native Google Slides deck

- **Visual QA.** The google-workspace skill's Verify step (Drive PDF export,
  then `render_export.py`) needs `pdftoppm`, which the Mac Studio does not have.
  Render each slide with the connector's thumbnail tool (MEDIUM or LARGE)
  instead: `read_slide_page_thumbnail` in Claude,
  `google_drive_get_slide_thumbnail` (Google Drive plugin) in Codex. Download
  its `contentUrl` with `curl`. Codex's sandbox cannot resolve
  `lh7-us.googleusercontent.com` (`curl: (6)`), so request escalated network
  for that curl on the first try. Don't substitute a Chrome screenshot or skip
  the check (2026-10-25: 11 Codex slide runs hit this; the ones that escalated
  got a render). Save under
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
  the same batch, then check the thumbnail. Requests in one batch apply in
  order, so a later `replaceAllText` also matches text an earlier request in
  the same batch just wrote (2026-10-29, twice). Order the replacements so no
  later pattern occurs in an earlier one's output, or split the batch, and
  check `occurrencesChanged`.
- **Speaker notes live on the notes page.** `replaceAllText` limited with
  `pageObjectIds: ["<slide id>"]` skips that slide's speaker notes and returns
  an empty reply, not an error (2026-10-25 and 2026-10-27). To change notes,
  scope it to `"<slide id>:notes"` or omit `pageObjectIds`. Treat any reply
  without `occurrencesChanged` as a miss.
- **A font or color change over whole text erases run exceptions.**
  `updateTextStyle` with `fontFamily` resets each run's weight to 400, so bold
  goes plain, and `foregroundColor` over `ALL` recolors links and accent runs
  too. Read each run's `bold`, `weightedFontFamily`, `link` and
  `foregroundColor` first. Then split the request around the exceptions, or
  re-apply them in the same batch (`bold: true`; `themeColor: HYPERLINK` on
  links). On 2026-10-27 a notes-font change stripped bold from about 129
  phrases and a black-text pass turned 24 links black.
- **Change palette colors in the theme.** When runs and shapes use theme slots
  (`ACCENT1`–`ACCENT6`, `LIGHT2`, `HYPERLINK`), change a deck color with one
  `updatePageProperties` on the master's `colorScheme`, sending the full list
  you just read. Recolor a run with `themeColor`, never `rgbColor`: a
  hard-coded run stops following later palette changes (2026-10-25).
- **Inserting an image behind text.** `createImage`, then
  `updatePageElementsZOrder` (plural *Elements*) with `SEND_TO_BACK`; the
  singular `updatePageElementZOrder` is rejected as an unknown field. Several
  sessions may edit one deck at once, so read `revisionId` immediately before
  each `batchUpdate` that uses `writeControl`.
- **Reading a long Google Doc (the speaking script).** For plain text
  (wording, word counts, timing), use Drive `read_file_content`; Drive
  `download_file_content` with `text/plain` returns the file inline as
  base64. Use `read_doc` only for edit indices. On a long doc it
  overflows, and the app saves it as `{"content": {…}}`, which the
  google-workspace skill's `docs_index.py` rejects ("not a read_doc
  result: found no 'tabs' or 'body'"). Run `jq '.content' <saved file> >
  ${BORG_ROOT}/tmp/<deck>-qa/doc.json` and point the script at that.
  Ten sessions re-derived this between 2026-10-29 and 2026-11-03.
