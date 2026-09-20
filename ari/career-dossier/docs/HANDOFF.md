# Handoff: Career dossier

**Prepared:** 2026-09-04; updated 2026-09-20
**Immediate owner:** Ari
**Next domain owner:** Ari
**Current state:** Phases 1–9 complete and the MVP is closed.
`https://agent.johndifini.com` is live, audited, and serving the approved
70-claim corpus. Gemini retrieval is a documented product-specific limitation;
the original strict Phase 9 acceptance gate remains failed rather than being
revised after measurement.

**Prompt update — 2026-09-19:** The candidate approved a shorter production
recruiter prompt. `content/recruiter-prompt.txt` remains the canonical source.
The Phase 9 evaluation records retain the longer prompt verbatim because it was
the fixed input used for those completed measurements.

## Active handoff: synthetic interop indexing experiment — 2026-09-19

The same-origin HTML-versus-JSON experiment is live. Commit `d7e8e6a` published
the fictional experiment; commit `9d37523` added the Bing site-verification
meta tag. Vercel reported both production deployments successful. The complete
post-deployment audit passed: all public routes returned their declared media
types and security/cache headers, all nine served artifacts were byte-identical
to local `dist/`, representative source paths returned 404, the real dossier
remained at 70 claims, and the production recruiter prompt was unchanged.

Public experiment routes:

- `https://agent.johndifini.com/interop-test`
- `https://agent.johndifini.com/interop-test.json`

The fictional disclaimer refers only to "the site owner"; the source and both
generated artifacts contain no real candidate name. Desktop (1440 × 900),
mobile (390 × 844), light/dark, keyboard, JavaScript-disabled, and horizontal
overflow checks passed. `npm run verify` passes 31/31 tests and
`npm run verify-deployment` passes 6/6.

### Bing state at handoff

The candidate verified the `https://agent.johndifini.com` Bing Webmaster Tools
site property with the `msvalidate.01` meta tag. Keep that tag live throughout
the experiment. The candidate submitted both experiment URLs for indexing on
2026-09-19 and inspected them at approximately 19:46 (`/interop-test`) and 19:49
(`/interop-test.json`) in the Bing UI.

The latest captured HTML status is **Discovered but not crawled**, discovered
on 2026-09-19. Bing currently says the URL cannot appear because it has not
reached the crawl/index stages. No specific HTTP, robots, `noindex`, canonical,
or fetch error is reported. This is currently treated as a pending crawl state,
not a proven site defect, because the production audit independently confirmed
HTTP 200, `index,follow`, a self-referential canonical URL, and no crawl-blocking
headers. The JSON route's detailed Bing status has not yet been captured.

**Day-1 observation — 2026-09-20.** The Bing Index tab still reported
**Discovered but not crawled** for both routes, with the generic red-flagged
copy "The inspected URL is known to Bing but has some issues which are
preventing indexation." That string is Bing's catch-all for the pre-crawl
state and names no specific defect; every field Bing populates for a real
blocker was empty. The **Live URL** test for `/interop-test`, run at 07:42,
returned **"URL can be indexed by Bing"** with **no SEO/GEO issues found**,
which resolves next action 1 in favour of the pending-crawl reading. ("No
markup found" is informational: the page carries no structured data, which
was never a requirement.) An independent re-check the same day confirmed both
routes at HTTP 200 with their declared media types to a bingbot user-agent,
`index,follow`, a self-referential canonical, an `http` → `https` 308, an
`/interop-test.html` → `/interop-test` 308, and an absent (permissive)
`robots.txt`. The alarming wording is therefore not a site defect and needs no
remediation; the constraint is Bing's crawl queue for a new origin with no
inbound links, consistent with the `site:` query returning nothing for any
route on this host. Minor, non-causal: `/interop-test/` serves 200 rather than
redirecting, a trailing-slash duplicate the canonical already resolves.

**IndexNow submission — 2026-09-20.** Commit `e6263ba` added the public key
file (`src/indexnow.ts`; 32 hex characters, leading digit — the constraints are
explained in that file) to the build, `expectedDistFiles`, `vercel.json`, and
`tests/deployment.test.ts`; `npm run verify` passed 32/32 before the push. The
Git-connected Vercel production deployment served the key URL within 30 seconds
of the push: HTTP 200, `text/plain; charset=utf-8`, body exactly the 32-byte
key with no trailing newline, and the full security/cache header contract. The
post-deploy spot check found all eight other public routes at HTTP 200 with
their declared media types and `/career.json` still at 70 claims. A single
POST to `https://api.indexnow.org/indexnow` then submitted `/`, `/career.json`,
`/career.md`, `/llms.txt`, `/interop-test`, and `/interop-test.json`; the
response was **HTTP 202 — accepted, key validation pending**, the normal
first-submission state while Bing fetches the key file. 202 confirms receipt
only; it is not a crawl and not an index entry. IndexNow reaches Bing, Yandex,
Seznam, and Naver and does nothing for Google. Continue the daily Bing URL
Inspection through 2026-09-26 to see whether the crawl date moves.

### Google Search Console state — 2026-09-20

The URL-prefix property `https://agent.johndifini.com/` is active, and Google
Search Console reports the candidate as a verified owner through the domain
name provider method. Search Console automatically accepted the existing
domain-provider verification; no dossier or DNS change was required.

The candidate submitted `/`, `/career.json`, `/career.md`, and `/llms.txt`.
Google's URL Inspection results captured on 2026-09-20 were:

- `/` — **URL is on Google / Page is indexed**. Last crawl: 11:39:38 AM by
  Googlebot smartphone; crawl allowed, fetch successful, and indexing allowed.
  The user-declared canonical is the inspected root URL, which Google selected.
- `/career.json` — **URL is not on Google / Crawled - currently not indexed**.
  Last crawl: 11:41:48 AM by Googlebot smartphone; crawl allowed and fetch
  successful. Indexing allowed and both canonical fields display `N/A`.
- `/career.md` — the same non-indexed result and crawl details as
  `/career.json`, including the 11:41:48 AM crawl.
- `/llms.txt` — **URL is not on Google / Crawled - currently not indexed**.
  Last crawl: 11:41:49 AM by Googlebot smartphone; crawl allowed and fetch
  successful. Indexing allowed and both canonical fields display `N/A`.

The three machine-readable resources have been fetched successfully, so their
current state is an indexing-selection outcome rather than a crawl failure. Do
not repeatedly resubmit them. Recheck later if their inclusion in human search
results becomes operationally important; the indexed HTML homepage is the
primary Google Search discovery surface.

### Download fallback release — 2026-09-20

Commit `34cb684` is live in production. The candidate-approved, Jony
Vibe-reviewed prompt-card fallback offers native downloads of `/career.json`
and `/career.md`; the canonical recruiter prompt now accepts an attached
dossier and otherwise retrieves the JSON URL. The release passed 32/32 source
tests, 7/7 deployment-contract tests, desktop and mobile rendered QA, and a
post-deployment audit of all ten public artifacts. Every artifact returned 200
with the expected media type, security and cache headers, and exact local byte
parity; thirteen source-exposure probes returned 404; the real corpus remained
70 claims with no `EX-*` IDs or public evidence records.

**Simplified follow-up — 2026-09-20.** Commit `8509433` is live in Vercel
production deployment `career-dossier-kzc8icbmd`. It restores the original
concise recruiter prompt, removes the aspect-ratio-dependent "prompt below"
copy, moves the fallback beneath Copy Prompt, and offers Markdown as the single
attachment fallback. JSON and `llms.txt` remain in the technical footer;
Evidence JSON and the synthetic retrieval-test link do not. The underlying
evidence and experiment routes remain public. `llms.txt` is semantically, not
textually, aligned with the homepage prompt, with test coverage for their core
evaluation and non-inference guidance. The release passed 32/32 source tests,
7/7 deployment tests, desktop/mobile rendered QA, the ten-artifact production
audit, all thirteen source-exposure probes, and the 70-claim corpus-integrity
check.

### Immediate next actions

1. ~~Run the HTML route's **Live URL** test.~~ Done 2026-09-20: passed, see the
   day-1 observation above. Only the crawl queue remains.
2. Capture the detailed Bing Index and Live URL results for the JSON route as
   an observation. JSON indexing is not an acceptance requirement, and Bing
   largely does not index bare `application/json` URLs, so that route holding
   at Discovered-but-not-crawled is close to its expected steady state.
3. Reinspect the HTML route once daily through 2026-09-26. Do not repeatedly
   resubmit it, and do not read the generic "some issues" copy as a new fault.
4. Treat the Bing gate as passed when `/interop-test` has been successfully
   crawled and is index-eligible or indexed with no blocking issue. "URL is
   indexed" or "URL is on Bing" is the strongest completion state. A `site:`
   search is secondary evidence only.
5. ~~Wait seven days before raising IndexNow.~~ Done 2026-09-20: the candidate
   approved IndexNow because of a live application send date, commit `e6263ba`
   shipped the key file, and the submission returned **HTTP 202** — see the
   IndexNow record above. Nothing further to do here unless the JSON route's
   Bing status or the next daily reinspection shows a regression.

### Pre-index Copilot baseline

Run the direct-retrieval baseline while Bing indexing is pending. Use fresh
chats and change only the URL between the HTML and JSON conditions:

```text
Retrieve the synthetic career dossier at [URL]. Using only that source:

1. Give the profile name.
2. List all six claim IDs.
3. Report the rollback-detection metric and telemetry-pipeline name.
4. Report the completed and deferred migration counts.
5. Summarize the limitations concerning Rust experience and SOC 2 ownership.
6. Cite the URL you actually used.

If you cannot retrieve the source, state the exact failure and do not infer or
substitute information.
```

Run both route conditions in fresh chats on each available account:

- personal Microsoft 365 Copilot;
- work Microsoft 365 Copilot with the add-on license; and
- work Microsoft 365 Copilot without the add-on license.

For every run, preserve the date/time, account and license state, route, exact
prompt, exact response, citations, and whether Copilot substituted another
source. Do not put work-account identifiers or private responses in tracked
files; store those records in Ari's private area if a durable record is needed.

Synthetic grading truth:

- profile: Avery Northstar;
- claim IDs: `TEST-Q7M-101` through `TEST-Q7M-106`;
- rollback detection: 47 minutes to 11 minutes via Cobalt Kestrel;
- migration: 26 completed and 2 deferred;
- Rust: no production Rust experience is claimed; and
- SOC 2: supported evidence collection but did not own the compliance program.

### Baseline status — 2026-09-19 22:00 UTC

HTML route, pre-index: **0/3 accounts retrieved it.** Personal Copilot, the
work account with the add-on, and the work account without the add-on all
failed in fresh chats on 2026-09-19. The exact tool failure was "No relevant
content could be retrieved"; Copilot stated the failure and declined to infer,
substitute, or fabricate, so sentinel accuracy is not applicable. No citation
was displayed and no alternate source was substituted. The JSON route has not
been run yet on any account. Per-run records, including the verbatim response,
live in Ari's private evaluation area (`Dossier Evaluation/`), not here.

Independent checks in the same session: both routes still return HTTP 200 with
the declared media types to a browser user-agent and to a bingbot user-agent;
`/robots.txt` is absent (permissive); the HTML canonical and `index,follow`
directives are unchanged. A Bing `site:agent.johndifini.com` query returned no
results for any route on this origin, including the real dossier — the domain
is new to Bing's index as a whole. The failure is therefore consistent with
Copilot's web tool depending on Bing's index for URL retrieval rather than
fetching live, but that is a hypothesis until the JSON-route baseline and the
post-index repeat are in. The Bing Live URL test (next action 1) has not been
run; it needs the Bing Webmaster Tools UI, which this session could not reach.

Two controls would sharpen the pre-index reading and cost one fresh chat each:
run the same prompt on one account against a page that is known to be in
Bing's index (proves the tool works at all), and against the real dossier
route `/career.json` (shows whether the whole unindexed origin fails, not just
the experiment routes). Neither changes the experiment routes or prompt.

After the HTML Bing gate passes, repeat the identical fresh-chat matrix. The
pre/post comparison is intended to separate direct URL retrieval, representation
effects, and Bing-index availability. Do not change the synthetic routes,
prompt, sentinels, real dossier, or recruiter prompt during the comparison.

The full release, audit, and observation procedure remains in
`docs/DEPLOYMENT.md`.

## Outcome

Create an AI-first, evidence-backed career corpus under
`ari/career-dossier/`. A recruiter gives `https://agent.johndifini.com` and a
job description to an AI assistant, which evaluates John DiFini's strong
matches, partial matches, and gaps and cites dossier evidence.

The substantive site is for AI retrieval. A recruiter who opens the URL
directly sees only a simple, sleek landing page explaining that the page is for
an AI assistant and providing a copyable prompt.

## Start here — 2026-09-07

Production is live. Everything below this section is implementation history,
retained because it records why decisions were made; read it only when a
specific question sends you there.

### What is true right now

- `https://agent.johndifini.com` serves the dossier from a Git-connected Vercel
  production deployment built from `main`.
- All eight routed resources — `/`, `/agent`, `/career.json`, `/career.md`,
  `/evidence.json`, `/llms.txt`, `/interop-test`, and `/interop-test.json` —
  return 200 with their declared media types and the full `vercel.json` header
  contract (CSP, `Referrer-Policy: no-referrer`, `nosniff`, HSTS, bounded
  caching).
- All nine served artifacts, including the favicon, are byte-identical to local
  `dist/`. The preview's platform feedback-script injection does not occur on
  production, so `/` and `/agent` are identical.
- Served `career.json` carries the John DiFini profile, exactly 70 claims, zero
  `EX-*` ids, and zero evidence records. No private marker appears in any served
  byte.
- Thirteen source and repository paths return 404, including
  `/content/claims/RB-002.json`, `/.git/config`, and `/AGENTS.md`.
- TLS: Let's Encrypt `CN=agent.johndifini.com`, valid to 2026-12-03. `http://`
  returns 308 to `https://`. The CNAME TTL is 600, GoDaddy's floor.
- Sibling commits outside `ari/career-dossier/` produce no deployment; the
  `ignoreCommand` skip path is proven, not assumed.

`npm run verify` passes 31/31 with typecheck, build, privacy, and byte-for-byte
determinism. `npm run verify-deployment` passes 6/6.

### Phase 9 closeout

The cross-assistant retrieval evaluation is complete. Thirty canonical-prompt
runs covered ten representative job descriptions in ChatGPT, Claude, and
Gemini. ChatGPT and Claude retrieved the canonical JSON in all 20 of their
runs; Gemini retrieved it in 0 of 10. The strict per-run score was 12/30.
All cited `RB-*` IDs were valid, no evidence ID was fabricated, and no
unsupported inference was recorded. The strict acceptance gate failed on
retrieval, material-gap reporting, and unresolved high-severity failures.

Twenty-seven supplemental route probes then tested `/`, `/career.md`, and
`/career.json` across the three assistants. ChatGPT and Claude succeeded in
18/18; Gemini failed in 9/9. A supplemental Grok check succeeded on all three
routes. Read-only inspection of the Vercel project found no active or draft WAF
configuration, no custom rules or IP blocks, no Bot Protection or AI Bots
managed ruleset, no attack anomalies, and no recorded firewall actions.

The candidate approved closing the MVP with Gemini documented as a known
product-specific interoperability limitation. This is an exception disposition,
not a retroactive pass or a change to the measured threshold. Do not add
`robots.txt`, change the canonical route, or propose MCP, WebMCP, embeddings, or
an API unless a future evaluation establishes a reproducible need that the
existing static routes can solve.

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
