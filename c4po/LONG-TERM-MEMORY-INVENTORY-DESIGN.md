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
semantic review is bounded and eventually covers the entire inventory. A
`critical` artifact can override the class cadence with a shorter interval.

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
4. Add the memory-inventory coverage rule to `LINT.md` only after the initial
   inventory reaches 100%, avoiding a knowingly red audit during migration.
5. Refactor the assumptions prompt into the ten-stage orchestrator while keeping
   the existing schedule, command name, state semantics, and email behavior.
6. Dry-run monthly and interactive modes; verify private data never enters the
   tracked snapshot, logs, or email.
7. Enable `--apply` only after deterministic actions have fixtures, idempotence
   tests, diff checks, and rollback verification.

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
