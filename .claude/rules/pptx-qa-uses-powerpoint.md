---
name: pptx-qa-uses-powerpoint
description: "When visually checking a .pptx deck on the Mac Studio: render it with Microsoft PowerPoint, not Keynote, Quick Look, or LibreOffice (not installed). The lenient renderers pass decks PowerPoint repairs or refuses."
---
# Check .pptx decks in PowerPoint, not Keynote

The `pptx` skill's visual QA assumes LibreOffice. The Mac Studio has no
LibreOffice, but it has **Microsoft PowerPoint** — the app the deck is for. When
`soffice` is missing, render with PowerPoint. Do not improvise with Keynote or
Quick Look: both open files PowerPoint repairs or refuses, so a clean Keynote
render proves nothing. `repos/atm` commit `28eab53` ("Fix deck table cells that
made PowerPoint offer repair") shipped after passing Keynote QA.

Export to PDF, then rasterize the pages to inspect them:

```sh
S=<scratch dir>; cp deck.pptx "$S/qa.pptx"
osascript <<EOF
tell application "Microsoft PowerPoint"
  open POSIX file "$S/qa.pptx"
  set p to active presentation
  save p in POSIX file "$S/qa.pdf" as save as PDF
  close p saving no
end tell
EOF
```

- Run it unsandboxed; Claude's sandbox blocks Apple Events to PowerPoint.
- Allow up to ten minutes: wrap the script in `with timeout of 600 seconds`
  … `end timeout`. The first export on 2026-09-26 took two minutes; one on
  2026-09-27 took five and outlived a 240-second AppleEvent timeout. macOS
  has no `timeout` command.
- Close only the reference captured right after `open`. **Never** close by
  `whose name is …`: on 2026-09-26 that filter closed the user's open
  `atm-deck.pptx` window instead of the QA copy.
- If the AppleEvent times out anyway, the captured reference is gone. Close
  the QA copy by matching both its `path` and its `name` to the scratch copy —
  never by name alone (`full name` returned error -2763 on 2026-09-27).
- An export that hangs with no file means PowerPoint is showing a dialog on the
  Studio (a repair prompt or a sandbox file-access grant). A repair prompt is
  itself a QA failure: fix the generator.
- PowerPoint is sandboxed and asks for file access once per folder. Over SSH
  that Grant Access dialog appears on the Studio's screen, where nobody sees
  it, and the export just hangs. Export from one stable QA folder (for
  example `${BORG_ROOT}/tmp/pptx-qa/`) so the grant is given once, via Screen
  Sharing to the Studio. Do not try PowerPoint's container folders
  (`~/Library/Containers/com.microsoft.Powerpoint/…`): the sandbox refuses
  them. Four sessions each lost turns retrying them on 2026-09-26/27.
- Rasterize the PDF with the Swift PDFKit recipe in `SOURCE-DOCUMENTS.md` →
  "Rendering a page as an image". The Studio has no `pdftoppm`, ImageMagick,
  PyMuPDF, or Python Quartz, and `qlmanage` renders only page 1.
- Computer use, `screencapture`, and System Events are not a fallback. The app
  has no Screen Recording or Accessibility permission (five sessions,
  2026-09-26/27).

If PowerPoint cannot run (no GUI session, or no permission to run unsandboxed),
report the visual check as **blocked**. Do not substitute Keynote or a
source-only review and call it passed.
