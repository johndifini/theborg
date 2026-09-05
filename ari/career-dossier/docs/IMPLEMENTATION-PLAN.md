# Career dossier implementation plan

**Architecture:** [ADR-0001](adr/0001-ari-career-dossier-publication-boundary.md)
**Target:** `ari/career-dossier/`
**Deployment:** Vercel at `agent.johndifini.com`
**Status:** Phases 1–8 complete; production is live at
`https://agent.johndifini.com`. Phase 9 (cross-assistant retrieval
evaluation) is the only remaining phase.

## Objective

Build an AI-first, public career corpus that a recruiter can give to an AI
assistant alongside a job description. The system must return grounded,
citable career information through ordinary web retrieval while keeping Ari's
resume sources, application history, and private provenance outside Git and
Vercel.

## MVP success criteria

The MVP is complete only when all of the following are true:

1. `https://agent.johndifini.com` reaches a simple, sleek recruiter landing page.
2. The landing page explains the AI-only purpose and provides a copyable prompt.
3. `/career.json`, `/career.md`, `/evidence.json`, and `/llms.txt` are generated
   from one validated public corpus.
4. Every published claim declares its evidence level, limitations, status, and
   `asOf` date.
5. No deployed or tracked dossier file contains private source paths, resume
   filenames, artifact hashes, application history, or unapproved contact data.
6. Private provenance can identify the source and approved version of every
   public claim without duplicating public claim prose.
7. A private-source change marks a publication stale rather than silently
   changing public output.
8. Identical inputs produce byte-identical generated output.
9. At least three representative AI assistants can retrieve the URL and produce
   a job-alignment assessment with evidence citations and explicit gaps.
10. No MCP server, vector database, authentication system, or live scraper is
    required for the MVP.

## Target structure

```text
ari/career-dossier/
├── AGENTS.md
├── CLAUDE.md
├── README.md
├── package.json
├── package-lock.json
├── tsconfig.json
├── vercel.json
├── .vercelignore
├── content/
│   ├── profile.json
│   ├── claims/
│   │   └── RB-001.json
│   └── evidence/
│       └── evidence-example.json
├── schemas/
│   ├── public-profile.schema.json
│   ├── public-claim.schema.json
│   ├── public-evidence.schema.json
│   ├── private-provenance.schema.json
│   └── publication-manifest.schema.json
├── src/
│   ├── build.ts
│   ├── validate.ts
│   ├── privacy.ts
│   ├── render-career-json.ts
│   ├── render-career-markdown.ts
│   ├── render-evidence.ts
│   ├── render-llms-txt.ts
│   └── render-landing-page.ts
├── templates/
│   └── landing-page.html
├── examples/
│   └── synthetic/
├── tests/
│   ├── schema.test.ts
│   ├── privacy.test.ts
│   ├── references.test.ts
│   ├── determinism.test.ts
│   ├── rendering.test.ts
│   ├── publication-state.test.ts
│   └── fixtures/adversarial/
├── dist/                         # generated; deployment output
└── docs/
    ├── IMPLEMENTATION-PLAN.md
    └── adr/
        └── 0001-ari-career-dossier-publication-boundary.md

ari/.private/
├── Career Claim Provenance.json
├── Dossier Publication Manifest.json
├── Resume Corpus Manifest.json
└── Resumes/
```

## Foundation choices

| Concern | Choice | Reason |
|---|---|---|
| Runtime | Current Vercel-supported Node.js LTS, pinned at implementation | Native fit for Vercel and local Borg tooling |
| Language | TypeScript | One small typed generator can later support an HTTP/MCP interface |
| UI | Static semantic HTML and CSS | One explanatory page does not justify a frontend framework |
| Persistence | Versioned JSON files | Corpus is small, reviewable, diffable, and read-heavy |
| Validation | JSON Schema plus a standards-compliant validator | Public/private contracts need mechanical enforcement |
| Tests | Node's built-in test runner | Avoid a test-framework dependency for a small deterministic tool |
| Deployment | Vercel static output | Git preview deployments, custom domain, and later functions if justified |

No production database is selected. Adding a database, framework, semantic
index, or MCP transport requires a new ADR.

## Phase 0 — approve contracts before scaffolding

### Tasks

1. Review and accept ADR-0001.
2. Approve the exact recruiter landing-page message and example prompt.
3. Approve the public field list and enums.
4. Decide whether exact current-employer staffing metrics and the reviewed
   current-employer AI/control claims may be published.
5. Confirm the Node.js LTS version supported by Vercel at implementation time.
6. Confirm that `agent.johndifini.com` is the direct public and Vercel production
   domain, with no `johndifini.com/agent` redirect in the current release.

### Gate

No code or public claim migration begins until the user approves the visible
landing copy, schema, and current-employer publication choices.

## Phase 1 — scaffold the tracked Ari capability

### Tasks

1. Create `ari/career-dossier/` with the target structure.
2. Add a scoped `AGENTS.md` covering:
   - AI-first purpose and non-goals;
   - public/private boundary;
   - exact validation and build commands;
   - generated-file rules; and
   - the requirement for explicit candidate approval before public writes.
3. Add `CLAUDE.md` containing exactly `@AGENTS.md`.
4. Configure TypeScript, package scripts, and the Node test runner.
5. Add synthetic content sufficient to build every output format.
6. Add README instructions for forkers that never refer to John's private data.

### Acceptance criteria

- `npm test` runs without network access.
- `npm run build` creates the complete synthetic `dist/` tree.
- No test or build reads outside `ari/career-dossier/`.
- The scoped instructions pass the workspace lint rules.

## Phase 2 — implement schemas and referential validation

### Tasks

1. Write JSON Schemas for public profile, claims, and evidence.
2. Write JSON Schemas for the private provenance and publication-manifest
   sidecars; publish only synthetic examples of private schemas.
3. Reject unknown properties in every schema.
4. Validate enum values, ISO dates/timestamps, stable IDs, HTTPS URLs, and
   required limitations/evidence classifications.
5. Validate cross-record references:
   - claim IDs are unique;
   - evidence IDs are unique;
   - every `evidenceId` resolves;
   - no evidence points at a local path; and
   - every record is explicitly `public` and approved.
6. Produce concise, path-specific validation errors.

### Acceptance criteria

- Valid synthetic fixtures pass.
- One adversarial fixture exists for every rejected condition.
- A missing evidence record and duplicate ID both fail with actionable messages.
- Current/in-development/scheduled claims without `asOf` fail.

## Phase 3 — implement the privacy boundary

### Tasks

1. Add a deny-by-default scanner over tracked source and generated output.
2. Detect private paths, absolute paths, resume filenames, hashes, credentials,
   tokens, email addresses, phone numbers, and unexpected URL schemes.
3. Add an explicit, field-level allowlist for intentionally public identity
   values; do not allowlist an entire file or directory.
4. Scan the final `dist/` inventory and fail on unexpected files.
5. Add a test that attempts to import or read `../.private/` and proves the build
   rejects the dependency.
6. Add a repository-level check ensuring `.private/` remains ignored.
7. Coordinate a narrow update to C4PO's privacy-audit allowlist only after the
   real public corpus is approved.

### Acceptance criteria

- Every adversarial privacy fixture fails.
- No absolute path or private filename survives in generated output or source
  maps.
- No blanket privacy-audit exclusion exists for `ari/career-dossier/`.
- A deployment archive inspection contains only expected public artifacts.

## Phase 4 — implement deterministic generation

### Tasks

1. Load profile, claim, and evidence files in a documented stable order.
2. Normalize dates, arrays, whitespace, and JSON indentation deterministically.
3. Generate `career.json` as the canonical aggregate corpus.
4. Generate `career.md` as a compact retrieval-oriented rendering, not a visual
   resume.
5. Generate `evidence.json` with explicit claim support and ownership labels.
6. Generate `llms.txt` as a short index that tells assistants which artifact to
   use and requires evidence-backed, gap-honest answers.
7. Generate the landing HTML and minimal CSS.
8. Add `npm run check-generated`, which rebuilds into a temporary directory and
   fails on any diff.

### Acceptance criteria

- Two clean builds produce byte-identical trees and hashes.
- Reordering source files without changing records does not change output.
- Every claim appears once in JSON and Markdown.
- Candidate-controlled evidence is labeled as such.
- Output does not instruct an assistant to ignore other instructions or behave
  as an authority beyond the dossier; it is data and retrieval guidance, not
  prompt injection.

## Phase 5 — implement private provenance and publication workflow

### Tasks

1. Create private sidecar files from synthetic templates with owner-only file
   permissions.
2. Map existing `RB-*` IDs to private resume artifacts without copying public
   claim prose into the sidecar.
3. Implement a local publication command under Ari that:
   - resolves private sources;
   - produces a candidate public record;
   - validates it;
   - prints the exact tracked diff;
   - stops for explicit approval;
   - writes the tracked public record;
   - updates the private digest manifest atomically; and
   - runs the full test/build suite.
4. Implement stale detection by hashing normalized private source facts and
   approved public records.
5. Integrate claim selection with the existing resume corpus manifest.
6. Make the public claim corpus Ari's source for future resume wording.

### Acceptance criteria

- A publication cannot complete without approval.
- Private changes produce `stale` status and no tracked or generated changes.
- Direct edits to a public claim invalidate its approval digest.
- Failed validation leaves both public and private files unchanged.
- Re-publication updates both digests and returns the state to `published`.

## Phase 6 — migrate the initial public corpus

**Completed 2026-09-04.** The approval-gated workflow published 70 real claims
across 12 reviewed batches. All 79 active private claims were adjudicated: nine
sensitive current-employer claims remain intentionally held and RB-065 remains
retired rather than forming an unfinished publication queue. The approved
production-content cutover removed the two synthetic foundation claims and their
orphaned evidence record from production inputs.

### Tasks

1. Transform active private evidence-bank entries into public claim proposals.
2. Exclude the retired entry and all private provenance/editorial metadata.
3. Review these claims separately before publication:
   - current-employer AI strategy and adoption;
   - current-employer operational control details;
   - metrics with incomplete baselines or dates;
   - future speaking engagements and in-development products; and
   - current staffing/team/geography figures.
4. Attach public evidence URLs where available.
5. Mark the remaining claims accurately as `resume-sourced` or
   `candidate-confirmed`.
6. Review the complete public diff in manageable batches.

### Acceptance criteria

- Every migrated claim has an explicit evidence level and limitations list.
- No private source path, confirmation note, or target-employer filename enters
  Git.
- The candidate explicitly approves every migrated batch.
- The generated corpus passes privacy and determinism tests.

## Phase 7 — landing-page design and accessibility

**Complete 2026-09-04.** The real public profile and 70-claim corpus generate
without synthetic production records. Browser review at 1440×900 and 390×844
passed layout, overflow, prompt, two-step flow, and resource-link checks.
Keyboard focus order and visible focus, clipboard success and fault-injected
failure fallback, and JavaScript-disabled rendering passed. Activating the skip
link moved focus to `main#main-content`. Runtime reduced-motion verification
matched `prefers-reduced-motion: reduce`, capped transitions at `.01ms`, ran no
animations, and preserved page usability. The original system preference was
restored after verification.

### Tasks

1. Route visual direction through Jony Vibe.
2. Implement the approved copy with semantic HTML and minimal CSS.
3. Include a copy-prompt control that works without a framework and leaves the
   prompt visible if JavaScript is unavailable.
4. Add alternate-format links, canonical URL metadata, descriptive title and
   summary metadata, and a visible machine-resource footer.
5. Verify keyboard operation, focus visibility, color contrast, reduced-motion
   behavior, and narrow/mobile layouts.

### Acceptance criteria

- The page is usable with JavaScript disabled except for one-click copying.
- Recruiters can understand the two-step instruction without scrolling on a
  typical desktop viewport.
- Mobile and desktop renders receive Jony Vibe approval.
- Automated accessibility checks pass, followed by a keyboard-only review.

## Phase 8 — Vercel domain configuration

**Complete 2026-09-05.** `https://agent.johndifini.com` serves the dossier over
HTTPS from a Git-connected production deployment. All six routes return 200 with
their declared media types and the full header contract; thirteen source and
repository paths return 404; all six served files are byte-identical to local
`dist/`; and two sibling commits outside the project directory produced no
deployment, closing the skip criterion. Two defects were fixed to get there — a
`.vercelignore` allowlist that stripped `.git` on Git-connected builds, and an
untracked empty `content/evidence/`. See [DEPLOYMENT.md](DEPLOYMENT.md).

### Tasks

1. Create one Vercel project from The Borg GitHub repository.
2. Set Root Directory to `ari/career-dossier` and Framework Preset to `Other`.
3. Configure `npm run build` and `dist` as the output directory.
4. Add `vercel.json` with:
   - schema declaration;
   - output directory;
   - clean URLs;
   - `/agent` alias;
   - explicit content types;
   - `X-Content-Type-Options: nosniff`;
   - a restrictive Content Security Policy for the static landing page; and
   - cache rules that allow short HTML caching and longer immutable data caching
     only when releases are content-addressed or otherwise invalidated safely.
5. Add `.vercelignore` without excluding remote-build inputs, then inspect the
   actual served `dist/` inventory.
6. Configure Vercel to skip deployments for unrelated Borg changes.
7. Add `agent.johndifini.com` and copy the exact CNAME value Vercel provides to
   the domain's authoritative DNS provider.
8. Verify TLS, canonical URLs, status codes, content types, and headers.

### Acceptance criteria

- `agent.johndifini.com` serves the landing page directly over HTTPS.
- Every documented route returns 200 over HTTPS.
- There is no directory listing or accidental source-file route.
- Preview deployments contain synthetic or approved public data only.
- Unrelated Borg commits do not produce a dossier deployment.

## Phase 9 — agent retrieval evaluation

### Tasks

1. Select 10 representative job descriptions spanning strong, partial, and weak
   fits. Keep private job descriptions outside the tracked repository.
2. Test the resume prompt against at least three major AI assistants.
3. Record structured results for:
   - URL retrieval success;
   - redirect and alternate-artifact discovery;
   - factual accuracy;
   - evidence citation correctness;
   - distinction among strong, partial, and missing qualifications;
   - unsupported inference rate; and
   - latency or retrieval failures.
4. Compare HTML-only, Markdown, and JSON retrieval where the assistant allows it.
5. Fix corpus/schema/retrieval issues before considering new infrastructure.

### Acceptance criteria

- All tested assistants can retrieve the canonical URL.
- Every reported match is traceable to a dossier claim.
- Gaps are reported honestly rather than inferred away.
- Citation checks meet the review threshold chosen in Phase 0.
- Any proposal for MCP, WebMCP, embeddings, or an API cites a measured failure in
  this evaluation.

## Delivery order

Implementation SHOULD proceed as these independently verifiable batches:

1. Scaffold plus synthetic build.
2. Public schemas and referential validator.
3. Privacy tests and adversarial fixtures.
4. Deterministic renderers.
5. Private sidecars and approval-gated publication command.
6. First reviewed public-claim batch.
7. Landing page and design review.
8. Vercel preview and deployment audit.
9. Custom domain and production release.
10. Cross-assistant evaluation report.

Each batch should be committed separately. Any implementation choice not covered
by ADR-0001 must update the ADR or add a new ADR before the batch is considered
complete.

## Explicitly deferred

- Remote MCP
- WebMCP
- Embeddings or vector search
- Database persistence
- Live LinkedIn or GitHub ingestion
- Server-side job-description comparison
- Authentication, recruiter accounts, analytics, or tracking pixels
- A human-facing portfolio or resume experience

## Handoff checklist

- [x] ADR accepted and present beside the implementation
- [x] Phase 0 choices recorded
- [x] Scoped `AGENTS.md` and exact `CLAUDE.md` wrapper created
- [x] Public/private schemas implemented
- [x] Privacy and determinism gates passing
- [x] Publication command approval-gated and atomic
- [x] Initial claims reviewed in batches
- [x] Jony Vibe landing-page review complete
- [x] Vercel preview deployment inventory inspected
- [x] Custom domain and production TLS verified
- [ ] Three-assistant retrieval evaluation complete
- [x] Deferred features remain absent
