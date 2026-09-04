# Career dossier

A small, offline TypeScript generator for an AI-readable public career corpus.
The checked-in production corpus contains a candidate-approved public profile
and public claims. Synthetic records remain isolated under `examples/synthetic/`
for tests and documentation. Private resume sources, provenance, and application
history remain outside the project.

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

The canonical inputs are `content/profile.json`,
`content/recruiter-prompt.txt`, `content/claims/*.json`, and
`content/evidence/*.json`. All are privacy-checked before rendering, and the
JSON records are schema-validated. The recruiter prompt is shared public copy:
any prompt printed on a résumé must match it exactly. Generation is offline and
stable: records sort by ID, object keys use lexical order, JSON uses two-space
indentation and a trailing newline, and Markdown/HTML use fixed templates.

`npm run check-generated` rebuilds into a temporary directory and compares
every path and byte with `dist/`. Privacy checks scan deployable inputs and the
final output inventory. Path guards reject any build input or output outside the
project root. `npm run verify-deployment` rebuilds the site and checks the local
Vercel route, header, cache, ignored-build, upload-allowlist, and served-inventory
contract. Remote preview and production steps are documented in
`docs/DEPLOYMENT.md`; running the local gate does not deploy or change DNS.

Architecture and phase boundaries are recorded in
`docs/adr/0001-ari-career-dossier-publication-boundary.md` and
`docs/IMPLEMENTATION-PLAN.md`.
