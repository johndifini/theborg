---
description: Verify a Word-exported PDF, harvest, and record a private resume artifact.
argument-hint: <DOCX path or unambiguous resume name>
private: true
---

Finalize one private resume identified by `$ARGUMENTS`. This is an interactive,
local workflow. Never apply, upload, email, publish, or otherwise transmit the
resume.

Treat the repository root as `${BORG_ROOT}`; derive it with
`git rev-parse --show-toplevel`. Candidate-specific facts and artifact metadata
must remain under `${BORG_ROOT}/ari/.private/`. The tracked command carries only
the method.

## Resolve and preflight

1. Re-read `${BORG_ROOT}/ari/.private/AGENTS.md` and the private manifest schema
   documentation before handling candidate files.
2. Resolve the source with:

       python3 "${BORG_ROOT}/ari/.bin/resume_corpus.py" resolve \
         --resume-dir "${BORG_ROOT}/ari/.private/Resumes" \
         "$ARGUMENTS"

3. Stop on a missing or ambiguous match. Never accept an archive, directory,
   Office lock file, backup, temporary file, non-DOCX artifact, or path outside
   the private resume directory.
4. Validate the existing manifest before doing any work:

       python3 "${BORG_ROOT}/ari/.bin/resume_corpus.py" validate \
         --manifest "${BORG_ROOT}/ari/.private/Resume Corpus Manifest.json"

## Require a current Word PDF and verify it

5. Preserve the DOCX as the editable source and derive its required same-stem
   PDF path beside it. The final PDF must be exported by the candidate from
   Microsoft Word. Never create or replace the final PDF with LibreOffice,
   Pages, Pandoc, a headless converter, `render_docx.py`, or any other
   non-Word renderer. Do not automate Word export as part of this command.
   Rendering an existing PDF to images for inspection is allowed.
6. Require explicit evidence that the PDF is the current Word export:
   - If the user already said they exported it from Word after the latest DOCX
     edit, treat that statement as provenance.
   - If the same-stem PDF is missing, tell the user to open the DOCX in Word,
     export or save it as the required same-stem PDF, and then reply to continue.
     Pause the workflow; do not harvest or update the manifest.
   - If the PDF exists but the user has not confirmed its origin and currency,
     ask whether it is the Word export of the current DOCX. Treat a PDF older
     than the DOCX as stale unless the user explicitly confirms that the DOCX
     content did not change after export. Pause when confirmation is needed.
   - Before asking for a new export, record in working notes whether the PDF
     existed and, if so, its SHA-256. On continuation, require the PDF to be new
     or its hash to have changed. If it did not, ask the user to export again.
   PDF metadata alone is not sufficient proof of Word origin or currency.
7. Extract text from both the DOCX and the Word-generated PDF and compare their
   substantive content. Stop and request a fresh Word export if headings,
   bullets, metrics, dates, or other material are missing or changed.
   Also inspect the DOCX core properties and Word PDF metadata. Tailored-resume
   builders must overwrite inherited template properties. Require a stable,
   role-neutral title (for example, `<Candidate Name> Resume`), the correct
   author, and blank subject, keywords, category, and comments unless a
   candidate-specific private policy says otherwise. Stop on stale employer,
   role, client, or target names.
8. Render every page of the Word-generated PDF to images with the available PDF
   tooling and visually inspect every page for clipping, overflow, unexpected
   page breaks, missing glyphs, broken bullets, spacing or alignment problems,
   and inconsistent headers, footers, or margins.
   When a full-page render suggests overlap or crowding, inspect the affected
   region at native resolution or with a lossless crop before failing it; never
   infer a layout defect from a downscaled preview alone.
9. If content comparison, rendering, or visual inspection fails, stop before
   harvesting or recording. Report the affected page or content, ask the user
   to correct the DOCX if necessary, and require another manual Word export.
   Never repair or replace the final PDF with a third-party conversion.

## Harvest

10. Re-read `${BORG_ROOT}/ari/.private/Resume Bullet Bank.md` immediately before
   editing it. Compare the final resume with that evidence bank and its cited
   source records.
11. Record the existing `RB-NNN` entries used by the final resume. Add materially
    improved wording as approved variants under the corresponding entries.
12. Add genuinely new claims as `needs-confirmation` unless an authoritative
    source supports them or the candidate confirms them interactively. Never
    silently promote a new claim to `verified`. Preserve retired or superseded
    wording for provenance, and never change factual meaning, ownership, scale,
    dates, or metrics.
13. If any claim remains unresolved, complete the safe portions of the harvest,
    report the pending confirmations, and do not record the resume as harvested
    until the evidence-bank state accurately reflects what can be reused.

## Record

14. Revalidate the manifest. Reuse the artifact's existing stable ID when its
    DOCX path is already recorded; otherwise generate one with
    `resume_corpus.py new-id`.
15. Only after Word-export provenance, content comparison, visual verification,
    and harvest all succeed, record the result atomically with
    `resume_corpus.py record`. Pass the relative DOCX and PDF paths, status
    (`final` unless the user explicitly says it was submitted), every used
    `--bullet-id`, and any known baseline or superseded artifact identifiers.
    Never infer `submitted` merely from PDF export.
16. Run `resume_corpus.py validate` again, then run the scanner in dry-run mode.
    The finalized artifact must no longer appear as pending.

Report the resolved DOCX, exported PDF, page-verification result, harvested
bullet IDs and variants, any claims awaiting confirmation, manifest artifact
ID/status, and the final dry-run result.
