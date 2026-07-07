---
type: reference
status: active
domain: shared
date_created: 2026-05-25
date_updated: 2026-05-25
source_paths: []
confidence: high
tags: [reference, sidecar, ingest, sanitizer]
---

# Sidecar (`.meta.json`) schema

The sanitizer at `~/Devops/life-wiki-sanitizer` emits a `<file>.meta.json` next to every sanitized output in `~/life-wiki/ingest/<class>/`. This file is a **hint** — `/ingest` consumes it but the curator (or curator's agent) retains final authority on classification.

This document is the canonical schema reference for agents reading or writing these files.

## Top-level shape

```json
{
  "source_class": "voice | email | secure | web | biometric | location | finance | ai-chat",
  "pipeline_version": "0.5.0",
  "original_filename": "...",
  "doc_date": "YYYY-MM-DD",
  "est_tokens": 3260,
  "suggested_domain": "journal | health/clinical | health/research | health/personal-tracking | finance | housing | work | shared",
  "suggested_template": "recording | source-summary",
  "tier": "A | B",
  "tier_reasons": ["short", "no-health-flag", ...],
  "flags": {
    "health": false,
    "finance": false,
    "decision": false,
    "cross_domain": false
  },
  "speakers": [...],
  "opener_parse": {...},
  "entities_detected": {
    "people": [...], "organizations": [...], "places": [...],
    "conditions": [...], "medications": [...], "providers": [...]
  },
  "themes": ["kebab-cased-tag", ...],
  "sanitization_log": {
    "redactions_applied": {"PHONE": 1, "MRN": 0, ...},
    "redaction_version": "0.4.0"
  }
}
```

Plus an optional **pipeline-specific block** keyed by source class:
`gmail`, `finance`, `ai_chat`, `biometric`, `location`, `extraction`.

## Tier A auto-promotion gates

All of these must hold for the batch skill to auto-stage:

- `tier == "A"`
- `est_tokens < 1500`
- No `flags.health` / `flags.finance` / `flags.decision`
- For voice: every entry in `speakers[]` has a non-null `label` AND `source ∈ {"voiceprint", "opener"}`
- Sidecar's `suggested_domain` matches the destination subdir (e.g. journal-class memo going to `wikis/journal/raw/transcripts/`)

Anything that doesn't gate Tier A is Tier B → curator review via `/ingest`.

## Per-class fields

### Voice (`source_class: "voice"`)

```json
{
  "speakers": [
    {"id": "SPEAKER_00", "label": "PARTNER-001",  "source": "voiceprint", "confidence": 0.91},
    {"id": "SPEAKER_01", "label": "abby",    "source": "voiceprint", "confidence": 0.87},
    {"id": "SPEAKER_02", "label": "dr-smith","source": "opener",     "confidence": 0.60}
  ],
  "opener_parse": {
    "stated_date": "2024-03-21",
    "stated_self": "PARTNER-001",
    "stated_context": "appointment with dr smith cardiology",
    "inferred_template": "recording",
    "inferred_domain": "health/clinical"
  }
}
```

`label` is `null` if the speaker wasn't matched to a voice print or named via opener. `source` indicates how the label was determined.

### Email (`source_class: "email"`)

```json
{
  "gmail": {
    "thread_id": "...",
    "from": "...",
    "subject": "...",
    "labels": ["INBOX", "wiki/clinical", ...]
  }
}
```

Gmail label `wiki/<domain>` drives `suggested_domain`. Sub-labels like `wiki/work-projectX` resolve to the parent domain.

### Secure document (`source_class: "secure"`)

```json
{
  "flags": {"...": "...", "legal": true, "insurance": false},
  "extraction": {
    "methods": ["pdfplumber", "ocr", "pdfplumber"],
    "ocr_confidence": 78.5
  }
}
```

`extraction.methods` is per-page when handling PDFs. OCR confidence below 60 surfaces as a `tier_reasons` entry.

### Web (`source_class: "web"`)

```json
{
  "web": {
    "title": "...",
    "url": "https://example.com/...",
    "author": "...",
    "date": "..."
  }
}
```

URLs in metadata and body text have tracking params (`utm_*`, `fbclid`, `gclid`, etc.) stripped before sidecar emit.

### Biometric (`source_class: "biometric"`)

```json
{
  "biometric": {"week": "2026-W22"}
}
```

Always Tier A. Always routes to `wikis/health/personal-tracking/raw/`. Never per-sample — only weekly aggregates.

### Location (`source_class: "location"`)

```json
{
  "location": {
    "week": "2026-W22",
    "place_count": 8,
    "distance_km": 142.5
  }
}
```

Always Tier A. Coordinates resolve to known-location labels or ~11km grid cells — full coordinates never retained.

### Finance (`source_class: "finance"`)

```json
{
  "finance": {
    "csv_kind": "transactions | positions | 1099 | statement-summary",
    "issuer": "chase | bank-of-america | schwab | ...",
    "row_count": 87
  }
}
```

Always Tier B. The sanitized CSV is preserved next to the summary `.md`.

### AI chat (`source_class: "ai-chat"`)

```json
{
  "ai_chat": {
    "title": "...",
    "source": "chatgpt | claude | claude-code | generic",
    "turn_count": 12,
    "topic": "code | writing | planning | null"
  }
}
```

Conversations with `turn_count ≤ 2` are `tier: "A"` and flagged for weekly-rollup aggregation by `/ingest`. Longer conversations are Tier B.

## What sidecars never contain

- Raw PII (sanitizer strips before sidecar emit)
- Full content of the source (sidecar is hints, the `.md` is content)
- Health-domain factual claims that should be cited (those belong in wiki pages with their wikilink citation)
- Voice-print biometric data (those live local-only at `~/Devops/life-wiki-sanitizer/voiceprints/`)

## Reading sidecars in code

Python:

```python
import json
from pathlib import Path

def load_sidecar(md_path: Path) -> dict | None:
    meta = md_path.with_suffix(".meta.json")
    if not meta.exists():
        return None
    return json.loads(meta.read_text())
```

## Sanitizer-side authoring

Per-class classifier functions in `~/Devops/life-wiki-sanitizer/classify.py`:

| Pipeline | Function |
|---|---|
| voice | `classify_voice_memo` |
| email | `classify_email` |
| secure | `classify_secure_document` |
| web | `classify_web` |
| biometric | `classify_biometric` |
| location | `classify_location` |
| finance | `classify_finance` |
| ai-chat | `classify_ai_chat` |

If extending sidecar with new fields, document them here first.
