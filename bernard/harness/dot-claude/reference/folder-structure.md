# Folder Structure Reference

```text
life-wiki/
├── CLAUDE.md
├── AGENTS.md -> CLAUDE.md   (symlink)
├── GEMINI.md -> CLAUDE.md   (symlink)
├── AGENT-HANDOFF.md
├── .gitignore
├── .obsidian/
├── .claude/
│   ├── skills/              ← /ingest, /lint, /wiki-query, etc.
│   ├── templates/
│   ├── scripts/             ← wiki-lint-structural.sh, gbrain wrapper
│   └── reference/           ← this file + ingest-routing.md
├── ingest/                  ← flat holding pen; sanitizer drops all output here
│                              each .md carries a paired .meta.json sidecar
└── wikis/
    ├── index.md
    ├── sources.md
    ├── tags.md
    ├── graph-rules.md
    ├── shared/              ← cross-domain entities (no raw/)
    │   ├── people/
    │   ├── organizations/
    │   ├── places/
    │   ├── goals/
    │   ├── decisions/
    │   └── queries/
    ├── journal/             ← default landing zone for all new material
    │   ├── raw/
    │   │   ├── audio/       ← local-only, never git-tracked
    │   │   └── transcripts/
    │   └── wiki/
    │       ├── index.md
    │       ├── log.md
    │       ├── entries/
    │       ├── themes/
    │       └── queries/
    └── health/
        ├── clinical/
        │   ├── raw/
        │   └── wiki/  (index.md, log.md, records/, appointments/, queries/)
        ├── research/
        │   ├── raw/
        │   └── wiki/  (index.md, log.md, papers/, articles/, treatments/, queries/)
        ├── personal-tracking/
        │   ├── raw/
        │   └── wiki/  (index.md, log.md, symptoms/, journals/, queries/)
        └── shared/
            ├── index.md, overview.md
            ├── conditions/, medications/, providers/, biomarkers/
            └── queries/
```

New sub-wikis (finance/, housing/, work/, travel/, etc.) are created inside `wikis/` with the same `raw/ + wiki/` structure when approved by curator.
