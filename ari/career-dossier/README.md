# Career dossier

A small, offline TypeScript generator for an AI-readable public career corpus.
The checked-in content is synthetic: it demonstrates the contracts without
publishing private resume sources or application history.

## Requirements

- Node.js `24.x`
- npm `11.x`

Install with `npm ci`, then run `npm run verify`. The build emits only:

```text
dist/
├── index.html
├── agent.html
├── career.json
├── career.md
├── evidence.json
└── llms.txt
```

The canonical inputs are `content/profile.json`, `content/claims/*.json`, and
`content/evidence/*.json`. All are validated before rendering. Generation is
offline and stable: records sort by ID, object keys use lexical order,
JSON uses two-space indentation and a trailing newline, and Markdown/HTML use
fixed templates.

`npm run check-generated` rebuilds into a temporary directory and compares
every path and byte with `dist/`. Privacy checks scan deployable inputs and the
final output inventory. Path guards reject any build input or output outside the
project root.

Architecture and phase boundaries are recorded in
`docs/adr/0001-ari-career-dossier-publication-boundary.md` and
`docs/IMPLEMENTATION-PLAN.md`.
