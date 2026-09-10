# Long-term memory inventory and audit design

Status: proposed  
Owner: C4PO  
Date: 2026-08-22

## Objective

Give every durable memory artifact in The Borg an inspectable reason for
existing, an accountable owner, a known context cost, and an explicit review
and retirement policy. Expand the assumptions audit from a hand-maintained list
of platform assumptions into a memory-governance audit that can discover new
artifacts, identify context rot, review current best practice, and recommend or
apply appropriately bounded remediation.

“Every artifact” means every file deliberately persisted to influence future
agent reasoning or behavior as instruction, procedure, knowledge, policy, or a
model-executed workflow. Ordinary application code, transient session logs,
caches, generated reports, and scheduler state are not memory artifacts unless
they are explicitly promoted into one of those roles.

## Design principles

1. **Inventory individually; review progressively.** Every artifact gets a
   record, but the audit opens full contents only when the record is new,
   changed, due, high-risk, conflicting, unused, or mechanically unhealthy.
2. **Do not duplicate content.** The inventory stores governance metadata and
   pointers, not copies of instructions or knowledge. Existing wiki frontmatter
   supplies metadata where it is already authoritative.
3. **Separate declared intent from observed facts.** Humans declare why an
   artifact exists and when it should retire; a deterministic scanner computes
   paths, hashes, sizes, token estimates, links, mirrors, and observed use.
4. **Audit canonical artifacts semantically.** Generated bridges, symlinks, and
   compatibility wrappers are inventoried individually but reviewed for drift
   against their canonical source rather than judged as independent memories.
5. **Keep private memory private.** The tracked inventory contains no private
   facts. Gitignored per-agent overlays hold records whose paths or rationales
   are themselves sensitive; only redacted aggregate findings may enter the
   public report.
6. **Preserve domain boundaries.** Cerebruh wiki content remains read-only from
   C4PO; changes are routed through its ingest workflow. Security-sensitive,
   destructive, and externally consequential changes remain approval-gated.

## Proposed files

| File | Purpose |
| --- | --- |
| `${BORG_ROOT}/MEMORY-INVENTORY.yaml` | Tracked canonical registry for public artifact intent, ownership, review policy, and remediation policy. |
| `${BORG_ROOT}/MEMORY-INVENTORY.schema.json` | Machine-readable schema and enumerations for registry validation. |
| `${BORG_ROOT}/<agent>/.private/memory-inventory.yaml` | Optional gitignored overlay for private artifacts; never merged into a tracked output. |
| `${BORG_ROOT}/.bin/build-memory-inventory.py` | Deterministic discovery, metadata join, coverage validation, dependency/link checks, token estimates, and snapshot generation. |
| `${BORG_ROOT}/c4po/.claude/scheduled/state/memory-inventory.json` | Gitignored generated snapshot containing computed facts and last-seen hashes; never an authoritative source. |
| `${BORG_ROOT}/c4po/.claude/scheduled/c4po-assumptions-audit-monthly.prompt` | Revised orchestrator: inventory integrity, mechanical health, due semantic reviews, then the existing external/platform assumptions. |
| `${BORG_ROOT}/c4po/.claude/commands/audit-assumptions.md` | Interactive entry point; add `--apply` for permitted repairs while retaining the existing command name and bridge. |
| `${BORG_ROOT}/LINT.md` | Require inventory coverage and valid governance metadata for newly added durable memory artifacts. |
| `${BORG_ROOT}/README.md` | Document scope, scheduled behavior, interactive apply behavior, and ownership. |

The registry is the canonical source for governance metadata, while the JSON
snapshot is disposable derived state. The registry may use concise defaults by
artifact class, but its `artifacts` map must resolve to one stable record per
artifact. Globs can discover candidates; they cannot replace individual
identity, rationale, or review history.

## Registry schema

```yaml
version: 1

defaults:
  scoped_rule:
    review_cadence: quarterly
    remediation_policy: propose_patch

artifacts:
  root-agent-instructions:
    path: AGENTS.md
    type: always_on_instruction
    owner: workspace
    scope: workspace
    visibility: public
    canonicality: canonical
    rationale: "Always-on routing, safety, and workspace operating context."
    introduced: 2026-05-01
    provenance:
      - kind: workspace_decision
        reference: "git history or ADR/reference path"
    load_mode: always
    consumers: [claude-code, codex, claude-desktop]
    risk: high
    review:
      cadence: monthly
      method: semantic_and_best_practice
      last_reviewed: 2026-08-01
    success_signals:
      - "Agents route work and knowledge consistently."
    retirement_triggers:
      - "A harness-native policy layer supersedes these instructions."
    remediation_policy: approval_required
    related: [lint-rules, cerebruh-routing]
```

### Record status: registered is not reviewed

A record additionally carries an optional `status` of `draft` or `reviewed`.
It describes the state of the **record**, not of the artifact, and it exists so
that inventory coverage can reach 100% without anyone being able to read that as
"every memory in The Borg has been justified".

- `draft` marks a stub emitted by `build-memory-inventory.py bootstrap`. Its
  identity, ownership, canonicality, and context cost were read off the tree; no
  human judgment has been applied. The validator therefore exempts it from the
  six **human judgment fields** — `rationale`, `provenance`, `risk`,
  `success_signals`, `retirement_triggers`, `remediation_policy` — each of which
  is a statement about consequence and intent that no scanner can derive.
- Absent `status` means `reviewed`, which is the strict state. The default has
  to be strict in both directions: every record written before drafts existed
  was hand-authored and complete, and a record must not be able to become
  unreviewed by dropping a field.
- A `draft` may not carry `review.last_reviewed`. A stub has not been reviewed,
  and a date there would be a false claim that survives into the review ledger.
- **Promotion gate.** Once a record declares a rationale, retirement triggers,
  and a remediation policy, it is no longer a stub: the validator requires it to
  be promoted to `reviewed`. This is what stops a half-filled record from
  sitting in the exempt tier indefinitely.
- `status` is deliberately **not** defaultable by class. Every other field in
  the `defaults:` block is a concision device; a class-wide `status: reviewed`
  would let one line declare several hundred artifacts reviewed at once, which
  is precisely the claim this flag exists to make impossible.
- `validate --require-reviewed` is the machine-checkable gate. It fails while
  any draft remains and names them, so the distinction is enforceable by a job
  rather than left to a reader's attention. Plain `validate` reports the split
  — reviewed, draft, and percent reviewed — on every run, including passing ones.

### Required declared fields

- `id`: stable, path-independent identifier (the map key).
- `path`: exact canonical path; generated artifacts additionally identify their
  own exact paths in separate records.
- `type`: artifact class from the taxonomy below.
- `owner`: accountable workspace agent, repository, or `workspace`.
- `scope`: workspace, agent, repository, sub-wiki, or private domain.
- `visibility`: `public`, `private`, or `redacted`.
- `canonicality`: `canonical`, `generated`, `mirror`, or `source`.
- `canonical_ref`: required for generated and mirror artifacts.
- `rationale`: why the artifact exists and what failure it prevents.
- `introduced`: date first adopted; recover from git history when possible.
- `provenance`: decision, source, incident, requirement, or upstream feature
  that justified adding it.
- `load_mode`: `always`, `path_triggered`, `explicit`, `scheduled`,
  `retrieved`, `source_only`, or `never_loaded`.
- `consumers`: harnesses, agents, jobs, or workflows that use it.
- `risk`: `low`, `medium`, `high`, or `critical`, based on the consequence of
  stale or incorrect memory rather than confidentiality alone.
- `review.cadence`: named cadence or event trigger.
- `review.method`: mechanical, semantic, best-practice, source-verification,
  usage, or a combination.
- `review.last_reviewed`: last completed substantive review.
- `success_signals`: observable evidence that the artifact earns its place.
- `retirement_triggers`: concrete conditions for relocation, consolidation,
  archival, or removal.
- `remediation_policy`: permission tier defined below.
- `related`: known dependencies, overlaps, replacements, or superseded items.

The six fields marked above as human judgment — `rationale`, `provenance`,
`risk`, `success_signals`, `retirement_triggers`, `remediation_policy` — are
required only of a `reviewed` record. Everything else is required of every
record, draft included, because it is mechanically derivable and a record that
cannot state its own path, class, owner, and load mode is not an inventory entry
at all.

### Computed snapshot fields

The scanner computes rather than hand-maintains:

- content hash, byte count, line count, and estimated tokens;
- current path, existence, modification time, and git status/history dates;
- canonical/mirror consistency and symlink targets;
- inbound and outbound references, broken links, and orphan status;
- overlap candidates based on titles, triggers, scopes, and semantic summaries;
- fixed context cost versus conditional/retrieval-only cost;
- observed invocation or retrieval counts where trustworthy logs exist;
- source age and source-resolution status;
- last-seen and materially-changed dates;
- next review date and reasons a deep review was selected.

Usage evidence is advisory: absence of a detectable invocation is not proof that
an always-on instruction or retrieved wiki page provided no value.

## Artifact taxonomy

| Type | Examples | Semantic audit unit |
| --- | --- | --- |
| `always_on_instruction` | Root and agent `AGENTS.md` | Canonical file and meaningful section when relocating content |
| `compatibility_wrapper` | `CLAUDE.md` imports and symlinks | Individual wrapper; drift only |
| `scoped_rule` | `.claude/rules/*.md` and local rules | Canonical rule |
| `generated_rule_bridge` | `.agents/skills/*/SKILL.md` generated from rules | Individual bridge; drift only |
| `procedural_skill` | Hand-authored `.claude/skills/*/SKILL.md`, personal skills | Canonical skill package |
| `command` | `.claude/commands/*.md` | Canonical command |
| `generated_command_bridge` | Codex skills generated from commands | Individual bridge; drift only |
| `scheduled_prompt` | `.claude/scheduled/*.prompt` | Prompt plus its configuration and runner dependency |
| `knowledge_page` | `cerebruh/wikis/*/wiki/*.md` | Individual page; substantive review can roll by cohort |
| `knowledge_source` | `cerebruh/wikis/*/raw/*` | Individual source; provenance and resolvability, not file-size guessing |
| `private_memory` | Agent Auto Memory and durable `.private/` notes | Individual private artifact in a private overlay |
| `policy_registry` | `LINT.md`, `MCP.md`, source-document procedures | Canonical policy file or registry entry |
| `retrieval_index` | Top-level and sub-wiki `index.md` files | Individual index plus coverage of its children |
| `design_decision` | Durable ADRs or explicit operating decisions | Individual decision record |

The scanner must support an explicit exclusion list for inert exhibits such as
`bernard/`, vendored packages, transient `tmp/`, caches, state, logs, and
independent repository content governed by that repository unless the workspace
registry intentionally imports it.

## Review cadence

| Artifact/risk class | Mechanical review | Substantive review |
| --- | --- | --- |
| Always-on instructions | Monthly | Monthly; immediately after harness changes |
| Security, permissions, scheduler, model, or privacy policy | Each relevant audit | Monthly and after incidents/upstream changes |
| Scoped rules | Monthly integrity/use check | Quarterly; immediately after a matching failure |
| Skills and commands | Monthly use/overlap check | Quarterly or after 90 days without observed use |
| Scheduled prompts | Every scheduled run plus monthly structure check | Quarterly; immediately after repeated failure or harness change |
| Generated bridges and wrappers | Every audit | Only their canonical source is reviewed semantically |
| Wiki pages and raw sources | Monthly structure, citations, and source-age check | Rolling annual review; earlier for changed, conflicting, high-stakes, or stale-source items |
| Retrieval indexes | Monthly coverage and size check | Quarterly or when retrieval quality/scale thresholds trip |
| Private memory | Monthly existence/metadata check privately | Quarterly, on contradiction, or at owner request |
| External/platform assumptions | Monthly | Monthly web/source verification, preserving current Assumptions A–H |

Every artifact therefore participates in every inventory scan, while expensive
semantic review is bounded and driven by risk, change, cadence, and a rotating
knowledge cohort. Complete first-review coverage is not an invariant: a draft
is an honest registered state, not a mechanical failure. A `critical` artifact
can override the class cadence with a shorter interval.

### Draft-record disposition

The one-off first-review bootstrap campaign was retired by user decision on
2026-09-09 after its first cohort. The remaining mechanically registered records
stay `status: draft`; they are not bulk-promoted and are not represented as
semantically reviewed. Ordinary audits may still select a draft when change,
risk, a finding, or the rotating knowledge cohort makes that artifact worth
reviewing. Cadence applies after substantive review. Existing review-ledger
entries and retained transactional receipts remain historical evidence and are
not deleted.

The `/remember` contract follows the same conservative rollback principle:
restore the prior canonical command and regenerate its managed bridge. Topic
files created under Auto Memory are user knowledge, not generated artifacts;
never delete or merge them automatically during a contract rollback.

## Findings and verdicts

Mechanical findings and semantic verdicts are separate so a valid idea with a
broken mirror is not mislabeled as obsolete.

Mechanical findings:

- `UNREGISTERED`, `MISSING_METADATA`, `MISSING_ARTIFACT`;
- `BROKEN_REFERENCE`, `ORPHANED`, `GENERATED_DRIFT`;
- `CONFLICT`, `DUPLICATE_SCOPE`, `OVER_BUDGET`;
- `REVIEW_OVERDUE`, `SOURCE_STALE`, `SOURCE_UNRESOLVED`;
- `UNUSED_SIGNAL` (never a deletion verdict by itself).

Semantic verdicts:

- `STILL_VALID` — earns its current place with no change.
- `WATCH` — valid now but approaching a stated threshold or upstream change.
- `RECONSIDER` — evidence is insufficient or tradeoffs require human judgment.
- `UPDATE` — retain purpose but change content, evidence, or implementation.
- `RELOCATE` — retain content in a better context layer.
- `CONSOLIDATE` — merge overlapping artifacts and preserve one canonical source.
- `SUPERSEDED` — a named replacement covers the purpose.
- `ARCHIVE` — preserve history but remove from active retrieval or loading.
- `REMOVE` — no longer useful and no historical retention requirement.
- `UNVERIFIABLE` — the required evidence cannot currently be obtained.

Every non-`STILL_VALID` verdict must include evidence, affected files, proposed
action, expected context or maintenance benefit, rollback path, and permission
tier. `WATCH` and `UNVERIFIABLE` must include the next trigger or evidence needed.

## Revised audit architecture

1. **Discover.** Enumerate all configured artifact classes, including hidden
   `.claude/` paths, symlinks, generated bridges, wiki pages, raw sources, and
   private overlays without printing confidential content.
2. **Join and validate metadata.** Resolve each discovered path to exactly one
   inventory record, validate the schema, and report missing or duplicate
   ownership. Flag registered paths that no longer exist.
3. **Build the snapshot.** Compute hashes, size/context estimates, references,
   canonical relationships, source age, and available use evidence.
4. **Run mechanical health checks.** Detect broken links, orphaned pages,
   generated drift, conflicting triggers, fixed-context growth, stale sources,
   missing provenance, and overdue reviews.
5. **Select deep-review candidates.** Select new, changed, due, high-risk,
   failing, conflicting, or apparently unused artifacts. Rotate lower-risk wiki
   pages so all receive substantive review within their maximum interval.
6. **Perform semantic review.** Judge relevance, correct layer, duplication,
   context contribution, evidence quality, and current best practice. Browse
   authoritative current sources when a claim is temporally unstable; do not
   web-search evergreen local intent merely to manufacture novelty.
7. **Run external assumptions modules.** Preserve the current Assumptions A–H,
   but represent each as an inventoried `policy_registry` decision with a named
   review procedure and update location. Future assumptions can be registered
   without rewriting the audit's orchestration logic.
8. **Plan remediation.** Group findings by permission tier, order dependent
   changes so canonical sources change before mirrors, and detect when a move
   would temporarily double-load content.
9. **Apply or report.** The monthly scheduled job is report-only. Interactive
   runs default to report-only; `--apply` performs only allowlisted automatic
   actions and prepares approval-gated patches without applying them.
10. **Record state.** Update the private/generated snapshot and review ledger
    only after a successful report. A failed or partial review does not falsely
    advance `last_reviewed`.

## Remediation permissions

| Tier | Allowed behavior | Examples |
| --- | --- | --- |
| `auto_safe` | May run under interactive `--apply` when deterministic, reversible, content-preserving, and confined to generated artifacts/state. | Refresh snapshot; regenerate an owned bridge from its unchanged canonical source; repair a generated index; update computed review state. |
| `propose_patch` | Generate an exact patch and impact/rollback note, but do not apply without approval. | Add missing rationale; tighten a trigger; consolidate duplicated instructions; relocate procedure text from `AGENTS.md` to a skill. |
| `approval_required` | Stop for explicit approval before mutation. | Change canonical instructions, rules, skills, wiki pages, schedules, models, permissions, security controls, private memory, or externally visible behavior. |
| `prohibited` | Never perform through this audit. | Delete unique knowledge automatically; copy private metadata into tracked files; rewrite raw sources; edit Cerebruh wiki content outside ingest; conceal provenance; weaken security to make the audit pass. |

Deletion, archival, and destructive consolidation are always
`approval_required`, even when the registry currently says `auto_safe`.
Restarts, permission changes, and scheduler activation remain subject to C4PO's
existing ask-first rules.

## Report contract

The monthly report should contain:

- coverage totals by artifact type, visibility, and load mode;
- fixed-context token estimate and change since the previous snapshot;
- discovered/unregistered/missing/overdue counts;
- mechanical findings with exact paths and canonical owners;
- semantic verdicts and evidence for deep-reviewed artifacts;
- existing Assumptions A–H results;
- proposed actions grouped by permission tier;
- private findings as redacted counts plus instructions to run the interactive
  private review, never private paths or facts in email;
- proof that all non-selected artifacts were still inventoried and the date by
  which each cohort will receive substantive review.

The current one-line clean report remains available when coverage is complete,
no health finding exists, no review is overdue, and every reviewed assumption is
`STILL_VALID`.

## Migration sequence

1. Define and validate the schema against a small representative set: root
   `AGENTS.md`, one rule and generated bridge, one command and generated bridge,
   one scheduled prompt, one wiki page/source/index, and one private placeholder.
2. Implement discovery in read-only mode and measure the complete artifact set;
   resolve exclusions and canonical/mirror pairs before enforcing coverage.
3. Bootstrap records mechanically, then require a human-quality rationale,
   retirement trigger, and remediation policy before marking each record valid.
   See **Step 3 in detail** below.
4. Add the memory-inventory coverage rule to `LINT.md` only after the initial
   inventory reaches 100%, avoiding a knowingly red audit during migration, and
   wire the existing lint audit to enforce it mechanically.
   See **Step 4 in detail** below.
5. Refactor the assumptions prompt into the ten-stage orchestrator while keeping
   the existing schedule, command name, state semantics, and email behavior.
6. Dry-run monthly and interactive modes; verify private data never enters the
   tracked snapshot, logs, or email.
7. Enable `--apply` only after deterministic actions have fixtures, idempotence
   tests, diff checks, and rollback verification.

### Step 7 in detail

Interactive `--apply` is implemented as a narrow transaction boundary in
`.bin/apply-memory-audit.py`; the model never receives generic write authority
from a permission-tier label. The helper recognizes exactly four action kinds:
rule bridges, command bridges, existing command-bridge manifest entries, and
the public generated snapshot (including its computed review ledger). Bridge
bytes are re-derived from a canonical source whose SHA-256 is pinned in the
plan. Each bridge target must resolve to a public generated registry record whose
effective `remediation_policy` is
`auto_safe` and whose `canonical_ref` identifies that source. A snapshot must
come from `tmp/`, parse as JSON, pass the existing snapshot privacy scan, and
target only `c4po/.claude/scheduled/state/memory-inventory.json`.

The command manifest action updates source/hash fields for existing managed
entries only; it refuses missing, duplicate, or malformed rows and never adds or
removes a skill. Apply refuses a command-skill repair unless its manifest action
is present later in the same transaction.

Planning records the exact before, source/candidate, and after hashes. Apply
re-derives every output and validates the whole plan before its first write,
prints unified diffs, atomically replaces existing targets while preserving
their modes, and verifies their bytes afterward. It refuses missing targets,
symlinks, path escapes, duplicate targets, mixed before/after state, changed
sources, non-`auto_safe` tiers, and every unknown action or field. The sole
missing-target exception is the first durable snapshot: planning and applying
it both require the exact `--approve-first-run-snapshot` opt-in, its plan records
an absent original instead of inventing a before hash, and apply uses an atomic
no-replace create so a concurrently appearing target is never clobbered. This
deliberately excludes retrieval indexes: no
owned deterministic index generator exists yet, and a generic replacement
primitive would be broader than the evidence for `auto_safe`.

An apply receipt under the run's unique `tmp/` directory holds the exact
original generated bytes and hashes, or records that the bootstrapped snapshot
was absent. Rollback restores only the same allowlisted generated targets,
refuses to clobber a post-apply edit, verifies the receipt's original hash
against the applied plan, and is idempotent. Removing a bootstrapped snapshot
requires `--approve-first-run-snapshot` again and succeeds only while its bytes
still match the applied hash. If apply fails after any replacement or creation,
the helper restores completed writes immediately and marks the receipt rolled
back.

The fixture at `.bin/tests/fixtures/memory-audit-auto-safe/` covers every
implemented deterministic action. `.bin/tests/test-apply-memory-audit.py`
asserts independently stored expected bytes, one exact diff per action, zero
actions on a second planning run, a no-op second apply, complete rollback, a
no-op second rollback, pre-write refusal of non-`auto_safe`/unknown/source-drift
plans, snapshot privacy rejection, and rollback conflict refusal. The broad
bridge sync commands remain outside this audit because they can remove orphans;
deletion remains `approval_required`. The scheduled prompt is unchanged and
report-only.

### Step 3 in detail

Step 2 measured the gap: 542 artifacts on disk against 9 declared records. Step 3
closes it mechanically, without pretending the resulting records are reviewed.

**What bootstrap derives, and what it refuses to.** `build-memory-inventory.py
bootstrap` emits one record per discovered-but-unregistered artifact, populating
only what the tree determines: path and path root, artifact class, canonicality
and the canonical it derives from, owner and scope from the directory layout,
visibility, how it enters context, and the date it first appeared. `introduced`
comes from YAML frontmatter `created:` where a page carries one, else the
earliest `git log --diff-filter=A` date, else file mtime — and each record
records in a trailing comment which of the three produced it, so a reviewer can
tell a history fact from a filesystem guess. Nothing else is written. Inventing
plausible-looking rationales would destroy the distinction `status` exists to
preserve, and a scanner has no access to the intent that a rationale states.

**Every emitted record is `status: draft`,** the machine-checkable marking
defined under *Record status* above. Coverage and review are printed as separate
numbers on every `validate` run, and `--require-reviewed` fails while any draft
remains, so 100% registration cannot be mistaken for 100% review.

**Routing is by visibility, and it is one-way.** A public artifact's record goes
to the tracked `MEMORY-INVENTORY.yaml`; a private artifact's record goes to the
gitignored `<owner>/.private/memory-inventory.yaml` overlay and never to a
tracked file — not its path, not its rationale, not a redacted stand-in. This is
design principle 5 and it is verified rather than asserted: the test suite
discovers this workspace's private artifacts and checks each path's absence from
the tracked registry. Workspace-scoped private records — shared Auto Memory,
which belongs to no single agent — go to C4PO's overlay, because C4PO owns this
inventory and `AGENTS.md` places durable confidential material under an owning
agent's `.private/`, not at the workspace root. Overlays are created `0600` and
carry no `defaults:` block, so a class-wide policy can never end up written down
only in a gitignored file.

**Concision without a second source of truth.** A drafted field whose value the
registry's own class `defaults:` block already supplies is omitted from the
emitted record; `apply_defaults` puts the identical value back before
validation. This applies only to tracked records, for the overlay reason above.

**Two safety properties the writer must have.** The tool ships its own YAML
reader, so it also ships a matching writer, and the two are checked against each
other: every file bootstrap is about to write is parsed back and compared record
by record before anything touches disk, and the writer raises on any shape it
cannot express rather than stringifying it. The whole would-be registry —
tracked file and every overlay together, so cross-file `canonical_ref`s resolve
— is validated in memory first. A registry that would not validate never exists
on disk, even momentarily. Bootstrap is a dry run unless `--write` is passed,
and it is idempotent: a second run finds nothing to do.

**What bootstrap will not guess.** An orphaned generated bridge or wrapper —
one whose canonical source is gone — has no honest mechanical record, because
`canonical_ref` is required precisely so that a derived artifact without one
reads as a finding rather than as a memory. Whether to restore the source or
delete the bridge is a judgment call. Those artifacts are reported by path with
a reason and left `UNREGISTERED`, so coverage stays honest about them.

The remaining half of step 3 is human and is not code: a draft may be promoted
to `reviewed` only by supplying the six judgment fields after substantive
review. Promotion is independent of step 4 — the coverage rule is gated on
registration reaching 100%, not on eventual review coverage.

### Step 4 in detail

Step 4 turns full registration into a rule the workspace is held to, so that the
next durable artifact someone adds cannot quietly escape the inventory.

**Gate.** The rule lands only when `discover` reports zero `UNREGISTERED` and
zero `MISSING_ARTIFACT` and `validate` passes, so it is green the day it is
written. It is deliberately *not* gated on step 3's human review: registration
and review are different numbers, and requiring review would leave the audit
knowingly red for as long as the cohorts take. `validate --require-reviewed`
stays the separate gate and stays red until the last draft is promoted; the lint
audit must not run it.

**The rule.** `LINT.md` gains a `Memory inventory` section, workspace-specific
like the README and MCP rules, since `repos/*` govern their own memory. It
requires exactly one record per durable artifact — tracked registry for public,
gitignored overlay for private — and treats three conditions as violations: an
unregistered artifact, a record whose path is gone, and a file in a
memory-bearing location that matches no artifact class. The third matters
because such a file never becomes an artifact at all and so could never be
reported as unregistered: without it the rule would have a silent hole exactly
where a new kind of memory would appear.

**Failing loudly is the acceptance criterion.** `discover --require-coverage`
exits non-zero and prints, for each offender, its path, its class, the owner the
directory layout makes accountable, the file its record belongs in, and the
metadata that record must carry — the last read out of the schema rather than
restated, so the message cannot drift from what the validator will demand. The
audit prompt emits one finding per named artifact rather than a count, because a
count names nobody. Enforcement refuses to run at all if the schema cannot state
its requirements, rather than reporting a violation while guessing what would
fix it. Private paths stay withheld, as everywhere else in this design: the
failure text is as emailable as the report it follows.

**What it does not do.** Enforcement is opt-in: plain `discover` still measures
and exits 0, and nothing about the check writes. Coverage is not review, a
`status: draft` record satisfies the rule, and an orphaned bridge with no
canonical source stays unregistered by design — the honest finding — rather than
being papered over with a record pointing nowhere.

### Step 6 in detail

Step 5 made the audit capable of reading every private overlay. Step 6 is the
step that checks it never says what it read. The privacy rule has been an
assertion since principle 5 was written; here it becomes a measurement, taken
against this workspace's real private material rather than a fixture.

**Two modes, because the two modes have different rules.** A scheduled run
emails a report and writes durable state, and must never open a private
artifact's contents. An interactive run reports into a session the user is
already looking at, may open private contents, and writes no state at all.
Proving one proves nothing about the other, so both are exercised:
`.bin/dry-run-memory-audit.sh` drives the scheduled path headlessly, and
`/audit-assumptions` in a session is the interactive path — run as itself rather
than simulated.

**What the harness keeps real, and what it redirects.** `BORG_ROOT` stays the
live workspace: a dry run against a synthetic tree would prove nothing about the
private data that is the whole question. Discovery, the join across every
overlay, coverage enforcement, validation, the candidate snapshot, the
mechanical checks, and both of the orchestrator's own privacy scans therefore
run against real artifacts. Only publication is redirected — the report goes to
a capture stub instead of `notify-email.sh`, and STAGE 10 writes its two files
into the run's output directory instead of `c4po/.claude/scheduled/state/`. The
network allowlist holds `api.anthropic.com` alone, so `smtp.gmail.com` is
unreachable and nothing can be sent even if the redirect were ignored; STAGE 7
still researches normally, because WebSearch is served through that same API
rather than by the client.

**The gate is tested by being obeyed, not bypassed.** `--mode full` seeds no
state file so the orchestrator runs; `--mode gate` seeds one dated this month
and the run must stop at STAGE 1 having produced nothing at all. Without the
second mode, the first mode's gate override would be the only evidence about a
guard whose entire job is to stop a second run in one month.

**The scanner derives its needles from the live overlays.**
`.bin/tests/audit-privacy-scan.py` reads every
`<owner>/.private/memory-inventory.yaml` through the inventory tool's own YAML
reader — the parser guaranteed to agree with the writer that produced them, and
one that needs no PyYAML — and builds seven categories of needle: private ids,
private paths in relative and absolute form, private judgment text, distinctive
content lines lifted from the private artifacts themselves, a concrete
`<owner>/.private/` marker, the `CLAUDE.local.md` wrapper name, and the
home-directory prefix. It never prints a needle: a finding is a category, a line
number, and twelve hex characters of the needle's SHA-256, so the failure report
cannot become the leak it is reporting.

Three profiles decide what is fatal, because the destinations differ. `email`
and `snapshot` fail on everything, including a home-directory fragment, matching
the orchestrator's own STAGE 9 and STAGE 10 scans. `log` demotes the
home-directory category to advisory, since every command line in an execution
trace contains the repository root, and keeps private material fatal.

**A scanner that cannot fail is not evidence.** `--self-test` builds a synthetic
tree with a fake overlay and a fake private artifact, confirms all seven
categories detect in a deliberately leaky file, and confirms none fires on a
clean report that legitimately names the generic `<owner>/.private/…` overlay
shape. That last case is why the marker category matches a concrete owner
directory rather than the bare string: the design and the report are both
required to describe where overlays live, and a scanner that failed on correct
documentation would get trained away instead of fixed. Live data supplies the
second control — `discover --show-private` produces output the scanner fails,
while the same command without the flag passes, so the default redaction is
doing work rather than having nothing to redact.

**The one channel live data cannot exercise.** Every private record here is
still `status: draft`, and a draft carries none of the six judgment fields by
design, so `private_judgment` has zero needles from real data. The synthetic
self-test covers the detector and the interactive run covers the behaviour, by
forming private verdicts in-session and confirming they reach no durable
artifact. The gap closes on its own as private drafts are promoted.

**What the dry run found.** Three defects, none of which an argument would have
caught.

The first was in the harness's own claim. Claude Code's sandbox
`filesystem.allowWrite` *adds* to the writable set rather than narrowing it —
the project root is writable by default — so listing only the output directory
and `tmp/` left the entire workspace writable while reading as though it did
not. The blanket repair fails too: `denyWrite` beats `allowWrite` even for a
subpath, so denying `$BORG_ROOT` and allowing `$BORG_ROOT/tmp` takes away the
one directory STAGE 2 needs. What works is denying every top-level entry except
`tmp/`, since deny is recursive. One gap survives by construction — a brand-new
top-level entry is on no deny list — which is why the harness treats its
before/after manifest, not the sandbox, as the proof that nothing changed.
`--mode probe` writes five disposable files, two inside the writable roots and
three outside, and reads its verdict from the filesystem rather than from the
model's account of what happened. The manifest earned its place on the second
run, which reported the workspace changed: the changed file was this design
document, edited from the session driving the run while the run was in flight
and denied to the run itself. A dry run in a shared checkout has to distinguish
what it did from what happened around it, and only the manifest can.

The second was a contradiction inside the orchestrator. Its per-assumption
"Where to update if flagged" pointers are written `${BORG_ROOT}/LINT.md` so the
run can open the file, and STAGE 9 then requires a pre-delivery scan for
home-directory fragments in the body. The first full dry run resolved that
conflict by copying the pointers verbatim and reporting its own scan clean; the
independent scanner found the fragment the run had missed. STAGE 9 now states
that report paths are workspace-relative and says why the two conventions
differ, since the model was not choosing carelessly — it was following the more
specific instruction.

The third was a false finding manufactured by the harness, and it took two
attempts to diagnose. `sync-codex-rule-skills.sh --check` compares a rendered
stub against the file on disk with `diff -q - FILE`, and `diff` spools stdin to
a temp file; with temp denied, every comparison failed `Operation not permitted`
and the script reported all 25 bridges stale. The run caught its own error and
re-derived the comparison by hand, but a dry run that fabricates a
`GENERATED_DRIFT` finding is worse than none, because the finding is
indistinguishable from a real one. The first repair added the outer `$TMPDIR`
and changed nothing, because the CLI sets its own `TMPDIR` for the sandboxed
run; allowing `/tmp` and `/private/tmp` as well is what fixed it. The lesson
generalises past this script: a sandbox tight enough to prove the report-only
invariant is also tight enough to make ordinary tools fail in ways that read as
audit findings, so a dry run has to be able to tell its own breakage from the
workspace's.

**What step 6 does not settle.** It exercises the report-only path only. Nothing
here validates `--apply`, which step 7 gates on fixtures, idempotence tests,
diff checks, and rollback verification, and the harness deliberately offers no
way to turn it on.

## Acceptance criteria

- Every in-scope durable memory artifact resolves to exactly one inventory
  record, including each generated mirror and private artifact via its private
  overlay.
- Adding an unregistered artifact causes a clear lint/audit failure naming its
  owner and required metadata.
- The audit can explain why each artifact exists, how it enters context, what it
  costs, when it was last reviewed, and what would justify retirement.
- The audit reads full contents only for selected candidates, not the entire
  memory corpus on every run.
- Generated artifacts cannot silently drift from canonical sources.
- Scheduled runs make no semantic or destructive changes.
- Interactive `--apply` cannot mutate canonical memory without approval.
- No private path, rationale, or content is written to tracked files or email.
- Existing Assumptions A–H retain their current checks and update pointers.
- The migration is documented and covered by the lint audit without creating a
  second manually maintained source of truth.
