# Handoff: Career dossier foundation and Ari transition

**Prepared:** 2026-09-01
**Immediate owner:** Architetto
**Next domain owner:** Ari
**Current state:** Phase 0 accepted; synthetic foundation complete; ready for Ari

## Outcome

Create an AI-first, evidence-backed career corpus under
`ari/career-dossier/`. A recruiter gives `https://johndifini.com/agent` and a
job description to an AI assistant, which evaluates John DiFini's strong
matches, partial matches, and gaps and cites dossier evidence.

The substantive site is for AI retrieval. A recruiter who opens the URL
directly sees only a simple, sleek landing page explaining that the page is for
an AI assistant and providing a copyable prompt.

## Authoritative artifacts

Read these before acting:

1. `ari/career-dossier/docs/adr/0001-ari-career-dossier-publication-boundary.md`
2. `ari/career-dossier/docs/IMPLEMENTATION-PLAN.md`
3. Workspace-root `AGENTS.md`
4. `ari/AGENTS.md`
5. `ari/.private/AGENTS.md` only when Ari begins private-provenance work

ADR-0001 is **Proposed**, not accepted. The implementation plan is gated on
Phase 0 approval.

## Decisions already reached

- The tracked capability lives at `ari/career-dossier/`, inside The Borg's
  public repository.
- The public claim corpus owns publishable claim wording.
- Ari's private files retain source lineage, application history, confirmations,
  and publication digests without duplicating public claim prose.
- Private material never enters Git, Vercel, generated files, fixtures, or
  environment variables.
- The machine routes are `/career.json`, `/career.md`, `/evidence.json`, and
  `/llms.txt`.
- `/` and `/agent` serve the minimal recruiter landing page.
- Vercel hosts `agent.johndifini.com` from the `ari/career-dossier` project root.
- Squarespace redirects `johndifini.com/agent` to the Vercel landing page.
- The MVP uses static HTML/CSS, TypeScript generation, JSON files, JSON Schema,
  Node's built-in test runner, and no production database.
- Remote MCP, WebMCP, embeddings, vector search, authentication, analytics,
  server-side job matching, and live external ingestion are deferred.
- Visual decisions for the landing page route through Jony Vibe.

## Why the immediate session belongs to Architetto

The next unfinished work is architectural foundation rather than recruiting:

- close the Phase 0 contract decisions;
- scaffold the tracked application and its scoped instructions;
- pin the runtime and package choices;
- implement public/private schemas using synthetic fixtures;
- build privacy and referential-integrity gates; and
- implement deterministic static generation.

These are foundation choices and repository-structure work. They fit
Architetto's decide-record-scaffold-handoff role. Ari should not have to invent
the software architecture while also adjudicating private career evidence.

## Architetto session scope

### First: close Phase 0 with the user

Review these choices before implementation:

1. Accept or amend ADR-0001.
2. Approve the exact landing-page message and recruiter prompt.
3. Approve the public claim/profile/evidence fields and enums.
4. Decide whether exact current-employer staffing metrics and the flagged
   current-employer AI/control claims are eligible for later publication.
5. Verify and pin the Vercel-supported Node.js LTS version.
6. Confirm `agent.johndifini.com` plus the Squarespace 301 redirect.

Record every accepted or amended decision in ADR-0001. Change its status to
Accepted only after the user approves the complete Phase 0 contract.

### Then: implement only foundation phases

Implement Phases 1 through 4 of the implementation plan:

1. Scaffold `ari/career-dossier/`.
2. Add scoped `AGENTS.md` and exact `CLAUDE.md` wrapper.
3. Add package/runtime configuration and documented commands.
4. Implement the public and private-sidecar schemas using synthetic examples.
5. Implement schema, reference, privacy, and adversarial tests.
6. Implement deterministic renderers for every public route.
7. Render the landing page with provisional structure and copy; do not make
   unreviewed visual-taste decisions.
8. Verify offline tests, deterministic builds, and the served-file inventory.

### Architetto stop condition

Stop and hand off to Ari when all of the following are true:

- the accepted architecture and exact commands are recorded;
- the synthetic application builds all required outputs;
- schema, privacy, references, and determinism tests pass;
- no code or fixture reads outside `ari/career-dossier/`;
- no real private résumé fact has been migrated;
- no production deployment or Squarespace change has occurred; and
- the next task would require reading `ari/.private/` or approving real career
  content.

Do not implement Phases 5 or 6 in the Architetto session.

## Foundation completion — 2026-09-01

Architetto completed Phases 1–4 using synthetic data only:

- accepted ADR-0001 and pinned Node.js `24.x`;
- recorded the exact provisional landing message and recruiter prompt;
- scaffolded the scoped instructions, package/runtime configuration, schemas,
  generator, fixtures, and tests;
- generated the six-file `dist/` inventory from one validated corpus;
- verified 20 schema, reference, privacy, rendering, publication-state, and
  determinism tests;
- verified TypeScript, a clean build, and byte-identical regeneration with
  `npm run typecheck`, `npm test`, `npm run build`, and
  `npm run check-generated`; and
- confirmed no real career source, deployment, redirect, database, remote
  fetch, or Phase 5–9 workflow was introduced.

The landing structure and copy are contract-approved but visually provisional;
Jony Vibe review remains a later Phase 7 gate. Ari is now the next owner for the
private provenance and real-content phases described below.

## Ari implementation progress — 2026-09-01

Ari verified the foundation and implemented the local Phase 5 workflow outside
the deployment root:

- owner-only private provenance and publication-manifest sidecars are
  initialized from the evidence bank and resume-corpus manifest;
- all active claim IDs resolve to private sources, while retired entries remain
  excluded;
- unsealed proposals can be checked in a temporary project copy without
  changing tracked content or generated output;
- exact public diffs receive content digests before the separate explicit
  approval phrase can authorize a write;
- source or public-record changes mark an existing publication stale without
  rewriting public content; and
- failed validation is no-write, while an approved publication runs the full
  typecheck, test, build, privacy, and determinism suite.

Phase 6 is in progress. The candidate approved the first batch of seven
lower-risk historical claims, and the workflow wrote those public records plus
their private approval digests before regenerating and verifying `dist/`. No
real profile value or evidence record has been migrated yet. Current-employer
claims, incomplete metrics, future activities, and public-evidence URLs remain
outside the approved first batch. Nothing has been deployed or published to a
remote service.

## Ari session scope after the foundation handoff

Ari then owns Phases 5, 6, and 9 because they involve candidate evidence and job
alignment:

1. Read `ari/.private/AGENTS.md` before private files.
2. Create the private provenance and publication-manifest sidecars from tracked
   synthetic schemas.
3. Map stable public claim IDs to private source artifacts without duplicating
   public claim prose.
4. Implement and exercise the approval-gated publication workflow.
5. Convert active evidence-bank entries into public proposals in reviewable
   batches.
6. Exclude private provenance, application history, retired wording, and
   unapproved details.
7. Ask the user to approve every public batch before writing it.
8. Use private job descriptions only for the cross-assistant retrieval
   evaluation; never add them to tracked tests or fixtures.

Ari must route the final landing-page visual review to Jony Vibe. Initial Vercel
and Squarespace setup can return to Architetto after content and design approval;
C4PO owns any changes to workspace privacy-audit configuration.

## Privacy boundary

The tracked project may contain approved identity and career facts. It must not
contain:

- private résumé or job-description filenames;
- application targets or application history;
- `.private/` or absolute local paths;
- document hashes or harvest metadata;
- candidate-confirmation history, rejected language, or tailoring notes;
- unapproved contact information;
- secrets, tokens, credentials, or private Vercel configuration; or
- current-employer internal detail beyond the user's approved public wording.

Never symlink `ari/.private/` into the tracked project. Vercel builds must be
reproducible from tracked files inside `ari/career-dossier/` alone.

## Working-tree caution

This is a shared checkout. Before editing, re-read every target file and inspect
the current state narrowly. Preserve unrelated work. Do not use tree-wide stash,
reset, checkout, or cleanup commands. Do not assume the two planning documents
remain unchanged simply because this handoff summarizes them.

## Immediate verification target

The first implementation milestone is a synthetic, offline build that produces:

```text
dist/
├── index.html
├── agent.html or an equivalent route mapping
├── career.json
├── career.md
├── evidence.json
└── llms.txt
```

It must pass:

```text
npm test
npm run build
npm run check-generated
```

Exact commands may change during Phase 0, but any change must be recorded in the
accepted ADR, scoped `AGENTS.md`, and README.

## Reusable prompt for the next Architetto session

> Continue the career-dossier foundation from
> `ari/career-dossier/docs/HANDOFF.md`. Read ADR-0001 and the implementation plan
> first. Close the Phase 0 decisions with me, then implement Phases 1–4 using
> synthetic data only. Do not read or migrate Ari's private corpus, deploy to
> production, or change Squarespace. Stop at the documented handoff to Ari.

## Subsequent Ari prompt

> Take over the career dossier from `ari/career-dossier/docs/HANDOFF.md` after
> Architetto's foundation stop condition is met. Verify the foundation tests,
> then implement the private provenance and approval workflow and prepare the
> real public claims in user-approved batches. Preserve the documented privacy
> boundary and do not deploy until content and design review are complete.
