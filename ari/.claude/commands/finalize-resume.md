---
description: Export, visually verify, harvest, and record a private resume artifact.
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

## Export and verify

5. Preserve the DOCX as the editable source. Export to a temporary PDF under
   `${BORG_ROOT}/tmp/`, using the most reliable available local document-export
   mechanism. Prefer the native office application's PDF export when available;
   otherwise use a verified headless converter. If GUI automation or another
   privileged action needs approval, request it rather than routing around it.
6. Render every page of the temporary PDF to images with the available PDF
   tooling and visually inspect every page for clipping, overflow, unexpected
   page breaks, missing glyphs, broken bullets, spacing or alignment problems,
   and inconsistent headers, footers, or margins.
7. If export, rendering, or visual inspection fails, stop. Do not replace the
   same-stem PDF, harvest evidence, or update the manifest. Keep working
   artifacts only in the workspace-root `tmp/` and clean them up when safe.
8. After the PDF passes visual inspection, place it beside the DOCX with the
   same relative stem and a `.pdf` suffix. Re-render the placed PDF or verify
   its hash matches the inspected temporary PDF before continuing.

## Harvest

9. Re-read `${BORG_ROOT}/ari/.private/Resume Bullet Bank.md` immediately before
   editing it. Compare the final resume with that evidence bank and its cited
   source records.
10. Record the existing `RB-NNN` entries used by the final resume. Add materially
    improved wording as approved variants under the corresponding entries.
11. Add genuinely new claims as `needs-confirmation` unless an authoritative
    source supports them or the candidate confirms them interactively. Never
    silently promote a new claim to `verified`. Preserve retired or superseded
    wording for provenance, and never change factual meaning, ownership, scale,
    dates, or metrics.
12. If any claim remains unresolved, complete the safe portions of the harvest,
    report the pending confirmations, and do not record the resume as harvested
    until the evidence-bank state accurately reflects what can be reused.

## Record

13. Revalidate the manifest. Reuse the artifact's existing stable ID when its
    DOCX path is already recorded; otherwise generate one with
    `resume_corpus.py new-id`.
14. Only after export, placed-PDF verification, and harvest all succeed, record
    the result atomically with `resume_corpus.py record`. Pass the relative DOCX
    and PDF paths, status (`final` unless the user explicitly says it was
    submitted), every used `--bullet-id`, and any known baseline or superseded
    artifact identifiers. Never infer `submitted` merely from PDF export.
15. Run `resume_corpus.py validate` again, then run the scanner in dry-run mode.
    The finalized artifact must no longer appear as pending.

Report the resolved DOCX, exported PDF, page-verification result, harvested
bullet IDs and variants, any claims awaiting confirmation, manifest artifact
ID/status, and the final dry-run result.
