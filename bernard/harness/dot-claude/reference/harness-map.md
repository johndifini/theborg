# Harness map — every enforcement/automation layer, all agents, all hosts

> Canonical inventory. If you add/change a harness, update this file in the same session.
> "Covers" = which agents the layer mechanically binds. Instruction layers bind all agents
> that read them but enforce nothing; mechanical layers enforce regardless of agent.
> Last full audit: 2026-06-12.

## 1. Instruction layer (system prompts)

| Host/repo | Artifact | Covers |
|---|---|---|
| life-wiki | `CLAUDE.md` (= `AGENTS.md` = `GEMINI.md` symlinks) — hard rules, model policy, egress rules | all agents (instruction) |
| sanitizer | `CLAUDE.md` + `AGENTS.md` (canonical cross-tool policy) + `GEMINI.md` (tight summary) + `COORDINATION.md` | all agents (instruction) |
| VPS | `workspace/AGENTS.md`, `IDENTITY.md`, `SOUL.md`, `TOOLS.md` — **TOOLS.md is the operative file in sandbox mode** (codex harness drops AGENTS.md there) | Bernard |

## 2. Model policy (cost routing)

| Host/repo | Mechanism | Covers |
|---|---|---|
| life-wiki | CLAUDE.md "Model policy" tiers; `.claude/agents/wiki-search.md` (haiku), `wiki-maintenance.md` (sonnet); headless pins: `daily-ingest-check.sh` `--model opus`, `harness-health.sh` Tier-2 `--model sonnet`, `daily-synthesis.sh` `--model opus`. Codex: `.codex/config.toml` → `gpt-5.5`, cheap via `--profile wiki-cheap` (`~/.codex/wiki-cheap.config.toml`, `gpt-5.4-mini`). Gemini: `.gemini/settings.json` → `gemini-3.1-pro-preview`, cheap via `-m gemini-3.1-flash-lite` | mechanical for Claude Code + Codex (once repo trusted) + Gemini default-model |
| sanitizer | CLAUDE.md "Model policy"; `.claude/agents/repo-search.md` (haiku) | same split |
| VPS | openclaw.json model chain — curator rule: **codex + gemini models only**, anthropic plugin disabled. Chain is availability fallback, not cost tiering (OpenClaw has no per-task routing) | Bernard |

## 3. Permission / sandbox engines (mechanical, per-agent-runtime)

| Host/repo | Mechanism | Covers |
|---|---|---|
| life-wiki | `.claude/settings.json` hooks: `guard-wiki.py` (PreToolUse — ask on `ingest/`/`raw/` edits, deny audio writes, self-protect), `session-start.sh`, `stop-check.sh` | Claude Code only |
| life-wiki | `.codex/config.toml` — workspace-write sandbox, **network off**, web search disabled, `ingest/`+`raw/` read-only (moves escalate to approval = guard-wiki ask-parity), harness dirs read-only except logs/inbox/tmp | Codex (when project trusted) |
| life-wiki | `.gemini/settings.json` — `google_web_search`/`web_fetch` excluded (mechanical); per-path rules **instruction-only** (workspace policy tier non-functional) — backstopped by pre-commit + leak scan | Gemini |
| sanitizer | `.claude/settings.json` deny rules + `.claude/hooks/guard-sensitive.py`; `.codex/config.toml` (read-only sandbox + path denies); `.cursor/rules/security-boundary.mdc`; `GEMINI.md` instruction-only | per-runtime |
| VPS | Docker exec sandbox per agent (scope:agent), mirror mount-enforced read-only, openclaw.json invisible in container, WhatsApp allowlist = one person | Bernard, mechanical |

## 4. Commit-time gates (mechanical, agent-independent)

| Host/repo | Mechanism |
|---|---|
| life-wiki | `.git/hooks/pre-commit` (tracked: `.claude/scripts/pre-commit.sh`): staged audio (ext+magic), PHI tripwire incl. encoded variants (`phi-patterns.py`, 230 patterns), orphaned sidecars. Bypass curator-only |
| sanitizer | `scripts/check-secrets.sh` backstop; "never commit harness files / live data / .env" (instruction + review) |
| VPS | `backup-config.sh` scrubber (case-insensitive substring) redacts secrets before pushing config backup to private GitHub |

## 5. Egress gates (what is allowed to leave)

| Host/repo | Mechanism |
|---|---|
| life-wiki | **Local git only — no remote, ever** (curator 2026-06-12). Only sanctioned egress: VPS mirror, allowlist-scoped (`wikis/health/`, `wikis/shared/`, `wikis/journal/wiki/entries/`), one-way, **fail-closed on leak-scan status** (<48 h `clean` required). Egress rules in CLAUDE.md bind web tools |
| sanitizer | Models firewalled from all live data (landing/vault/ingest/state/credentials + `~/life-wiki/`); develop on `tests/fixtures/` only |
| VPS | Zero public surface: Tailscale Funnel off, briefs as WhatsApp attachments, no new tools until data flows vetted (curator rule 2026-06-12) |

## 6. Scheduled automation (Mac)

| When | Job | Mechanism |
|---|---|---|
| 02:30 | `nightly-leak-scan.sh` | launchd `com.life-wiki.scan` — 5-tier scan vs triaged baseline; writes mirror-gate status |
| 03:15 | `gbrain dream` | launchd `com.lashawsalta.gbrain-dream` |
| daily 03:00 | gbrain sync | launchd `com.lashawsalta.gbrain-sync` |
| 06:00 | `daily-synthesis.sh` | launchd `com.life-wiki.synthesis` — snapshot-gated, opus |
| 07:00 + login | `vps-mirror-sync.sh` | launchd `com.lashawsalta.wiki-mirror-sync` — push mirror + pull/drain question inbox |
| 08:00 | `harness-health.sh` | launchd `com.lashawsalta.harness-health` — the watchdog (§7) |
| 09:00 | `daily-transcribe.sh` | cron (sanitizer repo) |
| 09:15 (daily since 2026-07-02; was 3×/day) | `wiki-eval.sh` | launchd `com.life-wiki.eval` — golden-question eval (§11); failures feed the question inbox |
| 12:00 | `daily-ingest-check.sh` | cron — lint-gated auto-ingest, smart tier (no pin) |

## 7. Watchdog

- Mac: `harness-health.sh` — Tier 0 freshness on every job above, Tier 1 kickstart/lock-cleanup (stale `vps-mirror-sync.lock` **and `wiki-write.lock`** past their 2 h TTL), Tier 2 headless sonnet diagnosis, notify fallback.
- VPS: **none** — known gap; see `vps-companion/harness-parity.md`.

## 8. Feedback / curation loops

- Question inbox: VPS → pulled+drained by mirror sync → `.claude/inbox/wiki-question-inbox.md` → `/inbox-triage` → `inbox-archive.md`.
- `/synthesis-pass` (daily, gated) → Synthesis Log → mirror → Bernard.
- `AGENT-HANDOFF.md` — cross-session state; session-start hook injects it (Claude Code), hard rule binds everyone else.

## 9. MCP / middleware

- `gbrain serve` MCP (life-wiki `.claude/settings.json`) — Claude Code only. Other agents use the CLI: `bash .claude/scripts/wiki-query`, `gbrain graph-query`.

## 10. Skills (Claude-native; other agents read them as workflow docs per CLAUDE.md header)

`.claude/skills/<name>/SKILL.md` (directory-per-skill — the format Claude Code discovers): ingest, lint, wiki-query, gbrain-query, clinician-brief, contradiction-review, decision-review, weekly-review, synthesis-pass, session-wrap, inbox-triage. (The former `life-ingest` / `life-ingest-batch` were retired 2026-06-26 — folded into `/ingest`, whose flat/no-tier-blocking model supersedes their Tier-A/B staging.)

## 11. Verification battery

- `wiki-lint-structural.sh` (pre-ingest gate) · `post-ingest-verify.sh` (batch tripwire, 230 PHI patterns) · `nightly-leak-scan.sh` (deep, gates mirror) · `/lint` (semantic, Claude only) · sanitizer unit tests (`tests/fixtures/`, synthetic only).
- `wiki-eval.sh` (daily 09:15) — golden-question regression harness: `.claude/reference/eval-questions.tsv` (semantic wiki-query hits, graph-query edge presence, orphan-count delta). Deterministic bash, no model calls. New failures append to the question inbox tagged `[eval]` (deduped vs inbox+archive) → `/inbox-triage` fixes the graph → eval re-greens. Status: `.claude/logs/wiki-eval-status`; watchdog-checked.
