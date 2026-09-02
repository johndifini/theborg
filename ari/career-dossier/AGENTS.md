# Career dossier operating contract

This capability is a child of `ari/` and inherits `../AGENTS.md`.

## Purpose

This directory builds a public, AI-first career dossier from approved tracked
JSON. It is a static generator, not a portfolio, application tracker, private
resume store, matching service, database, scraper, MCP server, or deployment
controller.

## Public/private boundary

- Build and test only files below this directory. Never read, import, link, or
  copy from `ari/.private/` or any absolute local path.
- Use synthetic data in examples and tests. Real career facts require Ari's
  private-provenance workflow and explicit candidate approval before a tracked
  write.
- Public content belongs in `content/`. Private-sidecar schemas and synthetic
  examples may describe the private contract but never contain real provenance.
- Do not add contact details, secrets, source filenames, application history,
  hashes, confirmation notes, or unapproved employer details.

## Commands

- `npm test` — run schema, reference, privacy, rendering, publication-state,
  and determinism tests offline.
- `npm run typecheck` — check TypeScript without emitting files.
- `npm run build` — validate and generate the public `dist/` tree.
- `npm run check-generated` — regenerate into a temporary directory and require
  byte-for-byte equality with `dist/`.
- `npm run verify` — run typecheck, tests, build, and generated-output checks.

## Structure and generated files

- `docs/HANDOFF.md`, `docs/IMPLEMENTATION-PLAN.md`, and `docs/adr/` are the
  authoritative handoff, phase plan, and architectural decisions.
- `schemas/` defines every versioned public and private-sidecar contract and
  rejects unknown properties.
- `content/` is the only production corpus input; load records in stable ID
  order, not filesystem enumeration order.
- `examples/synthetic/` and `tests/fixtures/` contain invented data only.
- `src/` must remain offline and must resolve every read/write beneath the
  project root.
- `dist/` is generated. Never hand-edit it. Its allowed inventory is exactly
  `index.html`, `agent.html`, `career.json`, `career.md`, `evidence.json`, and
  `llms.txt`.

## Change control

Ask before changing schemas, dependencies, public routes, deployment topology,
or the privacy allowlist. Record an architectural change in an ADR before
implementation. Do not deploy, alter Squarespace, migrate real claims, or begin
Phases 5–9 as foundation work.
