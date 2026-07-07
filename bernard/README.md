# Bernard — how I built a health wiki with a family-facing companion agent

This folder is a **case study, not a live agent**. It's the sanitized harness of a
private personal-health wiki and of **Bernard**, the read-only companion agent that
answers the family's care questions over WhatsApp. The wiki's *content* (one person's
full health record) never leaves its home machine — what's shared here is every piece
of *machinery* wrapped around it, so you can see how it was built and what everything
does.

The wiki itself follows the same second-brain pattern as [`cerebruh/`](../cerebruh/) —
ingest → classify → cite → link — pushed to production-grade for the highest-stakes
domain: a real patient, real PHI, multiple AI agents writing to one record, and a
non-technical family reading from it.

## The shape of the system

Three places, two pipes:

```
① Mac — the record                      ② VPS — the reader
┌────────────────────────────┐          ┌──────────────────────────┐
│ life-wiki/  (markdown,     │  one-way │ Bernard (OpenClaw agent) │
│   local-git-only, no       │  rsync,  │  read-only mirror of     │
│   remote, ever)            │  leak-   │  health/ shared/ journal │
│ sanitizer repo (separate): │  scan    │  answers family over     │
│   PHI → pseudonyms BEFORE  │  gated   │  WhatsApp (allowlist),   │
│   anything reaches ingest/ │ ───────► │  builds PDF briefs,      │
│ GBrain: local embeddings   │          │  cites every claim       │
│   (Ollama, PGLite — no     │ ◄─ ─ ─ ─ │                          │
│   cloud, PHI stays home)   │ question │  logs what it could NOT  │
└────────────────────────────┘  inbox   │  answer                  │
                               (the only└──────────────────────────┘
                                reverse channel)
```

The north star: the family can ask Bernard any in-the-moment care question and get a
correct, cited, plain-language answer no single provider holds — and the record
**improves from what they ask**. Unanswerable questions flow back through the inbox,
each one is a wiki gap to fix, and a calibration loop learns which gap-detectors
produce real work vs noise.

## Design rules that shaped everything

1. **Pseudonymize at the door.** A separate sanitizer repo replaces names, DOBs,
   MRNs, addresses with codenames (`PATIENT-001`) before a document ever reaches the
   wiki's `ingest/`. The wiki is *already* pseudonymized; every later gate is
   defense-in-depth on top of that.
2. **Mechanical beats instructional.** Rules live in `wiki-CLAUDE.md`, but every rule
   that matters is also enforced by something that runs: git hooks bind *every*
   committer (Claude, Codex, Gemini, human), Claude-Code hooks guard tool calls,
   launchd jobs scan nightly. Instructions are the first layer, never the only one.
3. **Egress is a whitelist of exactly one.** The wiki repo has no git remote — a
   pre-push hook refuses every push, ever. The only sanctioned way content leaves the
   Mac is the mirror sync: allowlist-scoped, one-way, and **fail-closed** — it refuses
   to run unless the nightly 5-tier leak scan wrote a fresh `clean` status.
4. **Every health claim cites its source** (a wikilink to the ingested record), and
   sources that conflict are preserved as contradictions, never averaged. Agents
   organize and synthesize; they never diagnose, dose, or advise.
5. **Write for the downstream reader.** Entity pages keep compiled truth up top and
   an append-only timeline below; a backlink builder keeps every dated entry
   reachable by walking `[[wikilinks]]`, because Bernard traverses links in files —
   he has no embedding index.
6. **Route by cost.** Smart tier (default model) for anything requiring clinical or
   PHI judgment; Sonnet-class subagents for mechanical maintenance and building to a
   spec; Haiku-class for read-only search. Headless jobs deliberately omit `--model`
   so they inherit whatever the current best default is.
7. **The system watches itself.** A daily watchdog checks every scheduled job's
   freshness and fixes what it can; a golden-question eval regresses the wiki daily;
   a self-interrogation pass files structural gaps as questions; a weekly
   cross-model adversarial review attacks the top open hypothesis.

## What's in this snapshot

- `wiki-CLAUDE.md` — the wiki's rulebook (its real `CLAUDE.md`, renamed so no agent
  working in The Borg mistakes it for binding instructions). Read this first: it's
  the constitution everything below enforces.
- `harness/dot-claude/` — the wiki's `.claude/` directory, renamed for the same
  reason (so Claude Code never loads its hooks/settings here). Contents below.

### `dot-claude/hooks/` — Claude-Code tool-call guards

| File | What it does |
|---|---|
| `guard-wiki.py` | PreToolUse: asks before edits to `ingest/`/`raw/` (immutable sources), denies audio writes (voice biometrics), protects itself |
| `guard-git.py` | PreToolUse on Bash: **denies** `git push` / `git remote add` (egress), **asks** on blanket staging (`git add -A`) so parallel sessions can't sweep each other's files into a commit |
| `session-start.sh` | Injects in-flight state (handoff file, lint status, ingest queue, question inbox) at the top of every session |
| `stop-check.sh` | One reminder per session if wiki changed but the cross-session handoff file wasn't updated |

### `dot-claude/scripts/` — the operational layer (all agent-agnostic bash/python)

**Gates and verification**

| File | What it does |
|---|---|
| `pre-commit.sh` | Tracked copy of the git pre-commit hook: blocks staged audio (extension + magic bytes), PHI tripwire (~400 generated patterns incl. URL-encoded variants), orphaned sidecars. Binds every committer |
| `pre-push.sh` | Refuses **every** push — the mechanical form of "local git only" |
| `phi-patterns.py` | Generates the tripwire patterns at runtime from a git-ignored targets file (so no PHI, even encoded, is ever stored in a pattern list) |
| `wiki-lint-structural.sh` | Structural lint (frontmatter, statuses, orphaned sidecars); required before every ingest |
| `post-ingest-verify.sh` | Batch-ingest tripwire — exists because parallel multi-agent ingests twice re-introduced PHI that single-file ingests never did |
| `nightly-leak-scan.sh` | 02:30 deep scan using the sanitizer's 5-tier scanner, diffed against a curator-triaged baseline; writes the status that gates the mirror |
| `wiki-eval.sh` | Daily golden-question eval: semantic-search hits, graph edges present, orphan-count delta. New failures file inbox items. Deterministic, no model calls |

**The mirror (Bernard's feed)**

| File | What it does |
|---|---|
| `vps-mirror-sync.sh` | One-way scoped rsync to the VPS + pull-and-drain of the question inbox (the single reverse channel). Fail-closed on leak-scan status |
| `harness-health.sh` | Daily watchdog: freshness check on every job, deterministic fixes (kickstart, stale locks), headless-model diagnosis, notify fallback. Also SSH-checks the VPS |

**The self-improvement loop** (each idempotent, dry-run by default, `--apply` to write)

| File | What it does |
|---|---|
| `build-backlinks.sh` | ① Rebuilds "Mentioned In" backlinks + the master timeline so every dated entry is reachable by link-walking (critical for Bernard) |
| `calibration-capture.sh` | ⑤ Turns triaged inbox outcomes into per-detector precision stats, so future questions carry a "this detector is usually right/noise" note |
| `self-interrogate.sh` | ② Structural-gap detector: isolated conditions, untreated meds, missing entity pages, timeline gaps → files new inbox questions |
| `build-hypothesis-register.sh` | ③ Compiles inline `> Hypothesis:` / `Needs verification:` markers into one working-hypotheses register |
| `cross-model-review.sh` | ④ Weekly: runs the top open hypothesis through independent steelman vs skeptic passes; a verdict divergence files an inbox item |
| `bernard-learn.sh` | Distills Bernard's conversation logs into inbox items + a usage profile — the "record improves from what they ask" half |
| `self-improve.sh` | Runs the whole chain (①⑤②③, optionally ④) on demand and reindexes the graph |

**Support**

| File | What it does |
|---|---|
| `daily-ingest-check.sh` | Lint-gated auto-ingest of whatever landed in `ingest/` |
| `daily-synthesis.sh` | Delta-driven pattern mining into a holistic-synthesis page; snapshot-gated so it skips model calls when nothing changed |
| `build-daily-score.sh` | Deterministic daily symptom score from tracker exports |
| `build-graph-links.sh` | Turns declared-but-unlinked frontmatter relationships into traversable body wikilinks (now on-demand — ingest writes links up front) |
| `wiki-query` / `gbrain` / `gbrain-job.sh` | Semantic search with raw-source noise filtered / local-install wrapper / scheduled sync+dream runs |
| `wiki-lock.sh` + `lib/wiki-lock.sh` | Shared advisory write-lock: interactive agents hold it for write-heavy work; scheduled writers acquire-or-defer |
| `wiki-status.sh` | Read-only "is everything running, what did other agents change" dashboard |
| `rotate-logs.sh` | Caps append-only job logs by truncating in place (launchd holds the fd — `mv` would orphan it) |
| `lib/` | Python/bash implementations + unit tests (`test_*`) for the builders above; `wikilog.sh` gives every job newest-first dated log blocks |
| `*.plist` | launchd job definitions (the Mac's cron) |

### `dot-claude/skills/` — the judgment workflows (Claude-native; other agents read them as docs)

`ingest` (classify → extract entities → cite → link → index → log), `lint` (semantic
audit), `wiki-query`, `gbrain-query`, `clinician-brief` (appointment-ready summary
per provider), `contradiction-review`, `decision-review`, `weekly-review`,
`synthesis-pass`, `inbox-triage` (drain Bernard's unanswered questions), `session-wrap`.

### `dot-claude/agents/` — cost-routing subagents

`wiki-search.md` (pinned Haiku, read-only lookups) and `wiki-maintenance.md` (pinned
Sonnet, mechanical fixes to a spec). The session model keeps all PHI-judgment work.

### `dot-claude/reference/` — the design docs

`harness-map.md` (canonical inventory of every enforcement layer — start here),
`concurrency.md` (many writers, one working tree), `ingest-routing.md`,
`folder-structure.md`, `search-strategy.md` (which tool for which question),
`SYSTEM-BIBLE.html` (rendered architecture walkthrough).

### `dot-claude/templates/` — one frontmatter-typed template per page type

condition, medication, provider, biomarker, symptom, record, recording, journal,
person, place, organization, event, goal, decision, theme, query, question,
research, source-summary, plus the ingest sidecar schema.

### `dot-claude/vps-companion/` — Bernard's deploy bundle

| File | What it does |
|---|---|
| `README.md` / `deploy.sh` | One-command VPS setup for the OpenClaw agent |
| `workspace/` | Bernard's identity: `AGENTS.md`/`TOOLS.md` (operating rules), `IDENTITY.md`, `SOUL.md` (voice: warm, plain-language, always cites) |
| `workspace/skills/publish-brief/` | Markdown → low-glare, large-type PDF sent as a WhatsApp attachment — nothing hosted publicly |
| `infra/` | systemd units for the brief server + cleanup timer |
| `harness-parity.md` | Honest ledger of which Mac-side protections exist on the VPS and which don't |
| `openclaw-config-patch.md` | The OpenClaw config: WhatsApp allowlist, model chain, daily-brief and weekly-deep-dive crons |

## The daily rhythm

| When | What |
|---|---|
| 02:30 | Deep leak scan → writes the gate the mirror depends on |
| 03:00 / 03:15 | Graph reindex / entity-sweep ("dream") |
| 06:00 | Synthesis pass (skipped when nothing changed) |
| 07:00 | Mirror sync to Bernard + question-inbox pull |
| ~07:30 (VPS) | Bernard's daily brief to the family WhatsApp group |
| 08:00 | Watchdog + the self-improvement chain (cross-model review Mondays) |
| 09:15 | Golden-question eval |
| 12:00 | Lint-gated auto-ingest |

## What was sanitized for this snapshot

Everything here passed the wiki's own PHI tripwire (the ~400-pattern generator run
against real targets) plus manual review. Removed outright: logs, the question
inbox, machine-local settings, the golden-question set and leak-scan baseline (both
encode real clinical details), and one explainer HTML built from real graph data.
Genericized in place: the VPS hostname/user, and every doctor/condition/medication
name used as an example in templates, skills, and unit-test fixtures — the *shape*
is identical, the clinical fingerprint is gone.

That list is itself the lesson: if you share your own harness, the PHI isn't only in
the data — it hides in test fixtures, doc examples, filenames in code comments, and
diagrams.

## Borrowing it

Start small: the pre-commit gate (`pre-commit.sh` + `phi-patterns.py`), the
fail-closed mirror pattern (`nightly-leak-scan.sh` → `vps-mirror-sync.sh`), and the
question-inbox loop are each liftable on their own. The full rulebook is
`wiki-CLAUDE.md`; the full enforcement inventory is
`harness/dot-claude/reference/harness-map.md`.
