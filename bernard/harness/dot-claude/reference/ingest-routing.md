# Ingest Routing & Sidecar Reference

## Routing table

| Content type | Wiki destination |
|---|---|
| Medical appointment recording | `wikis/journal/raw/transcripts/` + journal entry (PATIENT-001's appointments → journal domain, not health/clinical) |
| Health research / articles | `wikis/health/research/raw/` |
| Clinical documents (labs, imaging, visit notes) | `wikis/health/clinical/raw/` |
| Finance / banking | `wikis/finance/raw/` (propose sub-wiki if it doesn't exist) |
| Journal / personal | `wikis/journal/raw/transcripts/` |
| Uncertain | `wikis/journal/raw/transcripts/` — over-land rather than misclassify |

Routing is determined by reading the content, not the sidecar. The sidecar `suggested_domain` is a hint only.

## Sidecar `.meta.json` fields

Every sanitized file carries a `<filename>.meta.json` sidecar. Fields are **hints only** — all files are pre-sanitized; process regardless of tier or flags.

| Field | Description |
|---|---|
| `source_class` | `voice \| email \| secure \| web \| biometric \| location \| finance \| ai-chat` |
| `suggested_domain` | Routing hint; override by reading content |
| `suggested_template` | `recording` or `source-summary` |
| `tier` / `flags` | Informational only — **do not block on Tier B or health/finance/decision flags** |
| `speakers[]` | Often null — determine speaker roles from transcript content |
| `opener_parse` | Extracted date/context from recording opener; use when populated |
| `entities_detected` / `themes` | Low-quality NLP hints; treat as starting points, not facts |
| `sanitization_log` | What redactions the sanitizer applied |

## Speaker identification

Identify speakers from: self-identification in transcript, clinical context (who is asking clinical questions vs. answering), farewell cues, conversational role. Do not rely on `speakers[]` — it is frequently null or wrong.

## For recordings/transcripts

- Use the `recording` template (not `source-summary`)
- Place audio binary in `wikis/journal/raw/audio/` — local-only, not committed to git
- Place transcript in `wikis/journal/raw/transcripts/`
- Register audio as local-only asset in `wikis/sources.md` (path note, not a wikilink)
