---
name: docx-editing
description: "Before writing, reporting on, or delivering a .docx: never rewrite one while a ~$<name>.docx Word lock exists (ask the user to close it); report page count only from Word or a Word-exported PDF; use Avenir Next (never a default Microsoft font) in style defaults and theme fonts; keep sections from splitting across pages with keepNext and cantSplit; send a Word-exported PDF, checking its embedded fonts and re-exporting with Best for printing if it embeds Calibri."
paths:
  - "**/*.docx"
  - "**/*.dotx"
---
# Writing and checking a .docx

- **Check for a Word lock before writing a document.** A sibling file named
  `~$<name>.docx` means Microsoft Word currently has `<name>.docx` open. Never
  rewrite a `.docx` in that state — Word's next save will silently overwrite
  the change, and a concurrent OOXML rewrite can corrupt the file. Say the
  document is open and ask the user to close it first. A stale lock file left
  behind by a crash looks identical, so ask rather than assume. Reading the
  document is always safe.
- **Never report a `.docx` page count from a non-Word renderer.** Quick Look,
  Pages, and headless DOCX→PDF helpers ignore `w:pageBreakBefore`, so they
  confidently disagree with Word in both directions. Page count and page-break
  position are authoritative only from Word, or from a PDF Word exported. When
  neither is available, say the page count is unverified and give the one thing
  you can check: the number of forced breaks in `word/document.xml`. A document
  that spills onto a *mostly empty* extra page has a forced break, not an
  overflow — find and remove the break rather than trimming content.
- **Every generated or edited `.docx` follows two standing rules from the user
  (2026-10-12).**
  - Never a default Microsoft font (Calibri, Aptos, Cambria, Arial, Times New
    Roman): use Avenir Next unless jony-vibe says otherwise, and set it in the
    style defaults *and* the theme's major/minor fonts, because Word drops
    per-run fonts on re-save and falls back to the theme.
  - Never let a page break split a section: `keepNext` on each heading and on
    every table-row paragraph but the last, and `cantSplit` on rows.

  Avenir Next is not on Windows, so send a PDF exported from Word. Check the
  PDF's embedded fonts first, because a Word export on 2026-10-12 still came
  out in Calibri. If the PDF embeds Calibri, re-export with Save As → PDF →
  **Best for printing**: "Best for electronic distribution and accessibility"
  converts on Microsoft's server, which lacks Avenir Next (confirmed
  2026-10-18).
