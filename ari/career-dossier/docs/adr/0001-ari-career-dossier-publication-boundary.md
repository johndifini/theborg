# ADR-0001: Ari owns an AI-first public career dossier with private provenance

**Status:** Accepted — 2026-09-01
**Decision owners:** John DiFini (product and publication), Ari (career-domain
ownership), Architetto (architecture), Jony Vibe (landing-page visual direction)

## Phase 0 accepted contract

The foundation implementation proceeds under these approved constraints:

- Node.js `24.x` is the pinned runtime. Vercel lists Node.js 24 as its default
  supported LTS major; Vercel supplies security and patch releases within that
  major.
- The public profile, claim, evidence, private-provenance, and publication-
  manifest contracts are the version 1 schemas described by this ADR and
  implemented under `schemas/`. Unknown properties are rejected.
- Exact current-employer staffing metrics and flagged current-employer AI or
  operational-control claims are **not eligible for publication** during the
  foundation phase. Each requires later, explicit candidate approval as part of
  a reviewable public-content batch.
- Vercel will eventually serve `agent.johndifini.com`; Squarespace will
  eventually own only the permanent redirect from `johndifini.com/agent`.
  Neither production change is authorized by this foundation phase.
- The provisional landing-page message is: “This career dossier is designed
  for an AI assistant. Give the assistant this URL and a job description to
  assess strong matches, partial matches, and gaps using cited evidence.”
- The approved example prompt is: “Using the career dossier at
  https://agent.johndifini.com/career.json and the attached job description,
  identify strong matches, partial matches, and gaps. Cite the dossier claim
  and evidence IDs for every conclusion. Do not infer missing qualifications;
  state uncertainty explicitly.”

Visual styling remains provisional until Jony Vibe reviews Phase 7.

## Context

The career dossier is an AI-readable, evidence-backed career corpus that a
recruiter can give to an AI assistant alongside a job description. Its canonical
entry URL is `https://johndifini.com/agent`. The assistant should be able to
identify strong matches, partial matches, and gaps, and cite dossier evidence for
each conclusion.

The dossier is not a conventional portfolio or resume website. All substantive
career content is optimized for machine retrieval. A recruiter who opens the URL
directly still needs a simple, sleek landing page explaining that the page is for
an AI assistant and supplying a copyable example prompt.

Ari already maintains confidential resume artifacts, a resume corpus manifest,
and a curated evidence bank. Most career claims are appropriate for publication,
but the private corpus also contains material that must not be deployed:

- target-employer resume filenames and application history;
- local filesystem paths, document hashes, and harvest timestamps;
- candidate-confirmation history, rejected wording, and tailoring notes;
- private job descriptions and source documents; and
- current-employer details that have not been expressly approved for publication.

Maintaining separate private and public copies of the same claim prose would
create drift. Deploying Ari's private corpus would collapse the privacy boundary.
The architecture needs one owner for public wording and a separate, non-deployed
chain of provenance.

The Borg is itself an open-source AI workspace. The reusable dossier schema,
generator, validation rules, publication workflow, tests, and synthetic example
are useful parts of Ari's open-source capability, so the dossier belongs inside
the tracked Borg repository rather than under the ignored `repos/` product area.

## Decision

### 1. Location and ownership

The tracked application SHALL live at:

```text
ari/career-dossier/
```

It is an Ari capability, not a new top-level Borg agent and not an independent
repository. It inherits Borg-wide rules and adds a scoped `AGENTS.md` plus an
adjacent `CLAUDE.md` containing exactly `@AGENTS.md`.

The directory SHALL contain only data and code safe to publish in The Borg's
public Git history. Ari's confidential records remain under `ari/.private/`,
which stays gitignored and outside the Vercel project root.

### 2. Audience and routes

The site is AI-first. It SHALL expose:

| Route | Purpose | Media type |
|---|---|---|
| `/` | Minimal recruiter landing page and machine-entry index | `text/html` |
| `/agent` | Alias for the same landing page | `text/html` |
| `/career.json` | Canonical structured public corpus | `application/json` |
| `/career.md` | Compact agent-readable rendering of the corpus | `text/markdown` |
| `/evidence.json` | Public evidence records referenced by claims | `application/json` |
| `/llms.txt` | Short machine-oriented index and retrieval instructions | `text/plain` |

The landing page SHALL contain no portfolio-style presentation. It SHALL contain:

- a clear statement that the page is intended for an AI assistant;
- three short steps: copy the URL, attach the job description, paste the prompt;
- a copyable prompt asking for strong matches, partial matches, gaps, and cited
  evidence; and
- discoverable links to all machine-readable routes.

The HTML head SHOULD advertise the Markdown and JSON alternatives with
`<link rel="alternate">` elements. Visual treatment is simple and sleek; final
type, spacing, color, and responsive-layout decisions route through Jony Vibe.

### 3. Public corpus is authoritative for public wording

The tracked `content/` directory is the single source of truth for wording that
may appear in the public dossier or a newly tailored resume. Ari SHALL consume
these public claim records rather than maintain a second private copy of their
claim text.

Every public claim SHALL conform to `schemas/public-claim.schema.json`. Version 1
has this conceptual shape:

```json
{
  "schemaVersion": 1,
  "id": "RB-079",
  "type": "project",
  "title": "Develop an AI-powered iOS application",
  "claim": "Developing a Swift iOS application using on-device and cloud AI models.",
  "status": "in-development",
  "asOf": "2026-08-29",
  "period": { "start": "2026", "end": null },
  "organizations": [],
  "skills": ["Swift", "iOS", "on-device AI"],
  "evidenceIds": [],
  "limitations": [
    "Not publicly launched",
    "No user-adoption or quantified-outcome claim"
  ],
  "evidenceLevel": "candidate-confirmed",
  "visibility": "public",
  "approvedAt": "2026-08-31T00:00:00Z"
}
```

Required fields SHALL be `schemaVersion`, `id`, `type`, `title`, `claim`,
`status`, `asOf`, `skills`, `evidenceIds`, `limitations`, `evidenceLevel`,
`visibility`, and `approvedAt`.

Allowed `type` values SHALL initially be `experience`, `project`, `leadership`,
`writing`, `speaking`, `award`, and `education`.

Allowed `status` values SHALL initially be `completed`, `historical`,
`in-development`, and `scheduled`. Time-sensitive claims require `asOf`.

Allowed `evidenceLevel` values SHALL initially be:

- `publicly-documented` — supported by at least one public evidence URL;
- `resume-sourced` — present in a candidate-provided resume but not independently
  documented; and
- `candidate-confirmed` — confirmed by the candidate without a public source.

The schema SHALL reject unknown properties. Claims SHALL state limitations
directly rather than rely on private editorial warnings.

Public evidence SHALL conform to `schemas/public-evidence.schema.json` and SHALL
contain only public HTTP(S) references. A version 1 evidence record SHALL include
an ID, type, title, URL, publisher or owner, optional publication date, access
date, and a short statement of what the source supports. It SHALL NOT contain a
local file path or imply independent verification when the source is
candidate-controlled.

`content/profile.json` SHALL contain only the public identity and stable summary
fields required to assemble the corpus. Contact details are excluded by default.

### 4. Private provenance is a sidecar, not a second corpus

Ari SHALL keep private source lineage in:

```text
ari/.private/Career Claim Provenance.json
ari/.private/Dossier Publication Manifest.json
```

`Career Claim Provenance.json` maps each public claim ID to private sources and
editorial history. It may contain resume artifact IDs, local paths, private notes,
candidate-confirmation records, and supersession history. It SHALL NOT duplicate
the canonical public `claim` text.

`Dossier Publication Manifest.json` records the approval boundary. Each entry
SHALL contain:

```json
{
  "claimId": "RB-079",
  "privateSourceDigest": "sha256:...",
  "publicContentDigest": "sha256:...",
  "approvedAt": "2026-08-31T00:00:00Z",
  "exportedAt": "2026-08-31T00:00:00Z",
  "status": "published"
}
```

The existing private `Resume Corpus Manifest.json` remains authoritative for
finalized DOCX/PDF artifacts and their selected claim IDs. It is not repurposed
as a dossier database.

### 5. Publication is explicit and one-way

Publication SHALL follow this state transition:

```text
private source -> harvested -> public proposal -> candidate approved
               -> tracked public claim -> generated artifacts -> deployed
```

An Ari publication command MAY read both private and public data locally. The
Vercel build SHALL read only tracked files below `ari/career-dossier/`.

The publication command SHALL:

1. resolve the selected private source claims;
2. create or update a proposed public record;
3. show the candidate the exact public diff;
4. stop for explicit approval;
5. write the approved public record and update the private publication manifest;
6. generate all derived artifacts; and
7. run schema, privacy, determinism, and content tests.

Changes to private evidence SHALL mark a published mapping `stale`; they SHALL
NOT silently rewrite or redeploy the public claim. Changes made directly to a
public record require a new approval digest before publication.

### 6. Privacy is enforced mechanically

The project SHALL contain tests that reject:

- `.private/` references or any absolute local filesystem path;
- `.docx` or `.pdf` source paths and private artifact hashes;
- email addresses, phone numbers, credentials, tokens, and secrets unless a
  specifically approved public-profile schema field later permits them;
- evidence URLs using schemes other than HTTPS, except an explicitly approved
  HTTP development fixture;
- records whose `visibility` is not exactly `public`;
- unapproved or undated public records;
- fields outside the public schemas;
- duplicate claim or evidence IDs;
- references to missing evidence IDs;
- generated files that differ from a clean regeneration; and
- imports, reads, or build inputs outside the project root.

The project SHALL include synthetic fixtures for open-source users. Tests SHALL
not depend on John DiFini's real claims. C4PO's privacy audit SHALL continue to
scan the directory; it SHALL receive only narrow allowlist entries for identity
fields intentionally published, never a directory-wide exclusion.

### 7. Generation is deterministic

`career.json`, `career.md`, `evidence.json`, `llms.txt`, and the landing page are
generated from versioned public inputs. Generated output SHALL be byte-stable for
identical inputs and SHALL use a documented deterministic sort order.

The build SHALL be offline and SHALL not fetch LinkedIn, GitHub, resume files, or
any other remote/private source. External evidence is represented by reviewed
URLs and metadata already present in `content/`.

### 8. Vercel hosts the public build

The Vercel project SHALL use The Borg GitHub repository with:

```text
Root Directory:   ari/career-dossier
Framework Preset: Other
Build Command:    npm run build
Output Directory: dist
Production branch: the Borg repository's default branch
Custom domain:    agent.johndifini.com
```

`vercel.json` SHALL live in the project root and SHALL define the output
directory, clean URL behavior, the `/agent` alias, explicit content types for
Markdown/JSON/text artifacts, and conservative cache/security headers.

The project SHALL deploy from tracked Git content only. `.vercelignore` SHALL
exclude non-build inputs such as documentation, adversarial fixtures, and local
Vercel metadata while retaining the package manifests, public content, schemas,
templates, and generator source required by the remote build. Only `dist/` is
served as deployment output.

Vercel SHALL be configured to skip deployments when the project directory has no
relevant change. No Vercel environment variable may contain private corpus data.

Squarespace SHALL retain `johndifini.com` and configure:

```text
/agent -> https://agent.johndifini.com/ 301
```

The URL printed on the resume remains `https://johndifini.com/agent`; agents and
human visitors follow the redirect to the Vercel-hosted landing page. The Vercel
project SHALL also serve `/agent` as an alias so either form remains intelligible.

Remote MCP and WebMCP are explicitly deferred. The MVP proves URL-based agent
retrieval before adding a protocol-specific interface.

## Consequences

- The open-source Borg repository gains a reusable dossier schema, generator,
  privacy gates, publication workflow, and synthetic example.
- The public claim corpus becomes reusable by Ari for future resume tailoring,
  eliminating duplicate public wording.
- Confidential source lineage remains available locally without entering Git or
  Vercel.
- Dossier changes share The Borg's Git history and review process.
- The public corpus intentionally identifies John and describes his approved
  career history. Those fields require narrow privacy-audit allowlisting.
- A private-source correction does not automatically reach production; explicit
  reapproval is the cost of preserving candidate control.
- The first release has no search API, semantic index, database, authentication,
  MCP endpoint, or live external ingestion.

## Alternatives considered

### Independent `repos/career-dossier/` repository

Rejected for this phase. It preserves deployment independence but withholds the
reusable dossier capability from The Borg's open-source history and creates a
second integration surface for Ari.

### Publish Ari's private corpus directly

Rejected. The private files mix publishable claims with application history,
source paths, hashes, confirmations, and editorial notes.

### Maintain separate private and public claim prose

Rejected. Two manually edited corpora would drift. Public wording has one tracked
owner; private files retain provenance by ID and digest.

### Keep the landing page in Squarespace

Rejected. It would split the entry page from generated artifacts and require
manual synchronization. A Squarespace redirect preserves the resume URL while
Vercel owns the complete dossier deployment.

### Build MCP or WebMCP in the MVP

Rejected. Ordinary URL retrieval is universally available and must be evaluated
before protocol-specific infrastructure is justified.

## Verification required before implementation is complete

- The user approves the exact landing-page copy and public schema.
- Jony Vibe approves the rendered landing page at desktop and mobile widths.
- Every public artifact returns HTTP 200 with the expected media type.
- At least three major AI assistants can retrieve the canonical URL, follow the
  redirect, use the corpus, distinguish matches from gaps, and cite evidence.
- Privacy tests pass against both real public content and adversarial fixtures.
- A deliberately changed private source marks its publication stale without
  changing public output.
- A clean rebuild produces no diff.
- The deployed file inventory contains no private or source-only file.

## References

- [Vercel monorepos](https://vercel.com/docs/monorepos)
- [Vercel project settings](https://vercel.com/docs/project-configuration/project-settings)
- [Vercel static configuration](https://vercel.com/docs/project-configuration/vercel-json)
- [Vercel custom domains](https://vercel.com/docs/domains/set-up-custom-domain)
- [Vercel deployment exclusions](https://vercel.com/docs/deployments/vercel-ignore)
- [Squarespace URL mappings](https://support.squarespace.com/hc/en-us/articles/205815308-URL-mappings)
- `cerebruh/wikis/spec-driven-development/wiki/persistence-artifacts.md`
- `cerebruh/wikis/spec-driven-development/wiki/seven-information-layers.md`
