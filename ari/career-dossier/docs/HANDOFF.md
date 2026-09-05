# Handoff: Career dossier

**Prepared:** 2026-09-04; updated 2026-09-05
**Immediate owner:** Ari
**Next domain owner:** Ari
**Current state:** Phases 1–8 complete. `https://agent.johndifini.com` is live,
audited, and serving the approved 70-claim corpus. Phase 9 — cross-assistant
retrieval evaluation — is the only remaining phase and is now unblocked.

## Outcome

Create an AI-first, evidence-backed career corpus under
`ari/career-dossier/`. A recruiter gives `https://agent.johndifini.com` and a
job description to an AI assistant, which evaluates John DiFini's strong
matches, partial matches, and gaps and cites dossier evidence.

The substantive site is for AI retrieval. A recruiter who opens the URL
directly sees only a simple, sleek landing page explaining that the page is for
an AI assistant and providing a copyable prompt.

## Start here — 2026-09-05

Production is live. Everything below this section is implementation history,
retained because it records why decisions were made; read it only when a
specific question sends you there.

### What is true right now

- `https://agent.johndifini.com` serves the dossier from a Git-connected Vercel
  production deployment built from `main`.
- All six routes — `/`, `/agent`, `/career.json`, `/career.md`,
  `/evidence.json`, `/llms.txt` — return 200 with their declared media types and
  the full `vercel.json` header contract (CSP, `Referrer-Policy: no-referrer`,
  `nosniff`, HSTS, bounded caching).
- All six served files are byte-identical to local `dist/`. The preview's
  platform feedback-script injection does not occur on production, so `/` and
  `/agent` are identical.
- Served `career.json` carries the John DiFini profile, exactly 70 claims, zero
  `EX-*` ids, and zero evidence records. No private marker appears in any served
  byte.
- Thirteen source and repository paths return 404, including
  `/content/claims/RB-002.json`, `/.git/config`, and `/AGENTS.md`.
- TLS: Let's Encrypt `CN=agent.johndifini.com`, valid to 2026-12-03. `http://`
  returns 308 to `https://`. The CNAME TTL is 600, GoDaddy's floor.
- Sibling commits outside `ari/career-dossier/` produce no deployment; the
  `ignoreCommand` skip path is proven, not assumed.

`npm run verify` passes 29/29 with typecheck, build, privacy, and byte-for-byte
determinism. `npm run verify-deployment` passes 6/6.

### The next session's job: Phase 9

Phase 9 is the cross-assistant retrieval evaluation, specified in
[IMPLEMENTATION-PLAN.md](IMPLEMENTATION-PLAN.md). In short: select 10
representative job descriptions spanning strong, partial, and weak fits; run the
canonical recruiter prompt against at least three major AI assistants; and
record retrieval success, factual accuracy, citation correctness, honest gap
reporting, unsupported inference, and failures.

Constraints that are easy to get wrong:

- Job descriptions and raw evaluation inputs are private. They live under
  `ari/.private/`, never in this tracked directory.
- The recruiter prompt is canonical and shared with the resume. Do not reword it
  for the evaluation; that would measure a different artifact than the one
  recruiters will use.
- Fix measured corpus, schema, or retrieval problems before proposing any new
  infrastructure. ADR-0001 requires that a proposal for MCP, WebMCP, embeddings,
  or an API cite a measured failure from this evaluation.
- Nine sensitive current-employer claims are intentionally held and RB-065 is
  retired. An assistant reporting a gap in those areas is behaving correctly,
  not failing.

### Two traps this deployment already fell into

Both are fixed and recorded in [DEPLOYMENT.md](DEPLOYMENT.md); they are repeated
here because both cost a failed production build and neither is obvious.

1. **`.vercelignore` resolves against different roots on different deploy
   paths.** Against the deployment root for a CLI deploy, but against the
   repository root for a Git-connected build. An allowlist written for the former
   swept the whole checkout including `.git` on the latter, and the build died in
   one second. The file is now removed and ADR-0001 §8 is amended; do not
   reintroduce it. Source exposure is controlled by Vercel serving
   `outputDirectory` alone, which is the control the audits actually exercise.
2. **`npm run verify` cannot catch a missing empty directory.**
   `content/evidence/` is legitimately empty, Git does not track empty
   directories, and so the local tree passed while the clone had no such path
   and the build crashed in `assertDeployableSourcesSafe`. A tracked `.gitkeep`
   fixes it. If a corpus directory is ever emptied again, add the placeholder in
   the same commit.

### Operational notes

- The Vercel CLI is not installed. `npx vercel@latest` works and authenticates
  from `~/Library/Application Support/com.vercel.cli/auth.json`.
- `~/theborg` is a shared checkout with concurrent sessions. Stage by explicit
  path (`git add -A -- ari/career-dossier`) and check what is left unstaged
  before every commit; see `.claude/rules/shared-checkout-git-safety.md`.
- Re-running the production audit is cheap and worth doing after any deployment
  change: the six routes, the header contract, the source-exposure probes, and a
  byte comparison against local `dist/`.

## Phase 7 browser gate complete

The complete local browser acceptance gate passed on 2026-09-04 against the
repaired 70-claim build. Desktop and mobile layout, logical keyboard order and
visible focus, clipboard success and fault-injected failure fallback,
JavaScript-disabled rendering, and runtime reduced-motion behavior all passed.
Activating “Skip to main content” now moves `document.activeElement` to
`main#main-content`. With macOS Reduce Motion temporarily enabled, the live
`prefers-reduced-motion: reduce` query matched, transitions were capped at
`.01ms`, no animations ran, and the page remained usable. The original system
motion preference was restored after the check.

### Verified starting state

- The publication manifest records 70 of 70 claims as `published`.
- All 79 active private provenance mappings resolve; nine sensitive current-
  employer claims remain intentionally held and RB-065 remains retired.
- `dist/career.json` contains the approved John DiFini profile, exactly 70
  `RB-*` claims, zero `EX-*` claims, and zero public evidence records.
- Synthetic test records live only under `examples/synthetic/`.
- `npm run verify` passes all 28 dossier tests, typecheck, build, privacy, and
  byte-for-byte generated-output checks.
- The five publication-workflow tests pass.
- The approved visual direction is already implemented: simple and sleek,
  `#1ec503ff` brand accent, accessible light/dark pairings, `.015em` headline
  letter spacing, and `.14em` headline word spacing.
- The private runtime checklist is `ari/.private/Dossier Proposals/PHASE-7-QA.md`.

### Completed browser procedure

1. Confirm an in-app or connected browser is available before starting. If none
   is available, stop and report the browser gate still pending; do not
   substitute source inspection for rendered acceptance.
2. Serve the existing build locally without modifying content:
   `python3 -m http.server 4173 --directory dist` from `ari/career-dossier/`.
3. Review `/` at a representative desktop viewport and confirm the two-step
   recruiter flow is understandable without scrolling, with no clipping,
   overlap, or unintended horizontal overflow.
4. Review `/` at a representative narrow mobile viewport and confirm readable
   hierarchy, single-column layout, full-width copy button, usable prompt, and
   machine-resource links without clipping or horizontal overflow.
5. Traverse the page using only the keyboard. Verify the skip link, prompt,
   copy button, and resource links receive visible focus in logical order and
   that activating the skip link moves focus to main content.
6. Activate the copy button and verify both the clipboard-success state and the
   clipboard-failure fallback that selects the visible prompt for manual copy.
7. Emulate `prefers-reduced-motion: reduce` and verify the page remains usable
   with transitions and animations effectively suppressed.
8. Disable JavaScript and verify the complete prompt, two-step instructions,
   and machine-resource links remain visible and usable; only one-click copying
   may be unavailable.
9. Stop the local server. Run `npm run verify`, the five publication-workflow
   tests, `dossier_publication.py audit`, and `dossier_publication.py status`.

All nine steps above passed. Phase 7 is complete. No public content, schema,
deployment, DNS, or privacy-control changes were made during acceptance.

## Authoritative artifacts

Read these before acting:

1. `ari/career-dossier/docs/adr/0001-ari-career-dossier-publication-boundary.md`
2. `ari/career-dossier/docs/IMPLEMENTATION-PLAN.md`
3. Workspace-root `AGENTS.md`
4. `ari/AGENTS.md`
5. `ari/.private/AGENTS.md` only when Ari begins private-provenance work

ADR-0001 is accepted and the Phase 0 gate is closed. The continuation section
above is the current operational entry point; the foundation sections below are
retained as implementation history.

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
- `https://agent.johndifini.com` is the direct public entry; no Squarespace URL
  mapping is part of the current release.
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
6. Confirm `agent.johndifini.com` as the direct public and production URL.

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
- no production deployment or DNS change has occurred; and
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

Phase 6 completed on 2026-09-04. The candidate approved 12 reviewable batches,
and the workflow published 70 real claims with explicit evidence levels and
limitations before regenerating and verifying `dist/`. All 79 active private
claims were adjudicated: nine sensitive current-employer claims remain
intentionally held, and retired RB-065 remains omitted. The approved Phase 7
content cutover replaced the synthetic profile and removed both synthetic
production claims plus their orphaned evidence record. No public evidence record
has been migrated, and nothing has been deployed or published to a remote
service.

Phase 7 is implemented locally under Jony Vibe's documented simple-and-sleek
direction: semantic HTML, a responsive two-column first viewport, visible
two-step instructions, a progressively enhanced copy control, canonical and
alternate-resource metadata, light/dark contrast tokens, explicit focus states,
reduced-motion handling, and a visible machine-resource footer. Automated
structure and WCAG contrast checks pass with the full dossier suite. Browser
acceptance now passes at desktop and mobile sizes, including the keyboard-only
walkthrough, skip-link destination focus, clipboard states, JavaScript-disabled
rendering, and reduced-motion runtime behavior. The page renders the
candidate-approved real public profile and exactly 70 approved claims.

The résumé and landing page use `https://agent.johndifini.com` directly, while
the canonical copied prompt targets `/career.json` on the same host for machine
retrieval. No `johndifini.com/agent` redirect is required in the current release.
`content/recruiter-prompt.txt` owns the exact prompt; any résumé prompt must use
that file verbatim so the two surfaces cannot drift.

Phase 8 now has an account-owned, deployment-protected Vercel preview. Its six
public routes return 200 with the declared media types, security headers, and
bounded cache policies; representative source and package paths return 404; and
the generated artifacts match the local build. Vercel injects its own feedback
script into the preview root only, so that response differs from `dist/index.html`
by the platform-owned tag; `/agent` remains byte-identical. The audit corrected
an initial `.vercelignore` directory-pattern defect before the successful
preview. GitHub linking remains pending because the Vercel account has no GitHub
login connection. No custom domain, DNS record, or successful production
deployment exists; the one failed production-classified build record
created during project initialization was removed.

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

The landing-page visual and browser acceptance review under Jony Vibe's
direction is complete. Initial Vercel Git and domain setup can return to
Architetto; C4PO owns any changes to workspace privacy-audit configuration.

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
> production, or change DNS. Stop at the documented handoff to Ari.

## Subsequent Ari prompt

> Take over the career dossier from `ari/career-dossier/docs/HANDOFF.md` after
> Architetto's foundation stop condition is met. Verify the foundation tests,
> then implement the private provenance and approval workflow and prepare the
> real public claims in user-approved batches. Preserve the documented privacy
> boundary and do not deploy until content and design review are complete.
