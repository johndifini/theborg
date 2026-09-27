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
- Allow about three minutes. The first export on 2026-09-26 took two, and a
  60-second watchdog killed the script before PowerPoint finished writing.
- Close only the reference captured right after `open`. **Never** close by
  `whose name is …`: on 2026-09-26 that filter closed the user's open
  `atm-deck.pptx` window instead of the QA copy.
- An export that hangs with no file means PowerPoint is showing a dialog on the
  Studio (a repair prompt or a sandbox file-access grant). A repair prompt is
  itself a QA failure: fix the generator.

If PowerPoint cannot run (no GUI session, or no permission to run unsandboxed),
report the visual check as **blocked**. Do not substitute Keynote or a
source-only review and call it passed.
