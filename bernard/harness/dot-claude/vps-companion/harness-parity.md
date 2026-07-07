# VPS harness parity — does OpenClaw match the Mac harnesses?

> Audit 2026-06-12. Companion to `.claude/reference/harness-map.md`.
> Per the curator data-flow rule (2026-06-12): nothing new runs on the VPS until its
> read/write/network surface is vetted. Everything in "Gaps" below is a PROPOSAL —
> deploying any of it is a curator decision executed via the vetting checklist at the end.

## Parity table

| Mac harness | VPS equivalent | Status |
|---|---|---|
| Model policy (tiered routing) | openclaw.json model chain `openai/gpt-5.5` → `gemini-3.1-pro-preview` → `gpt-5.5-pro`; anthropic plugin disabled (curator: codex+gemini only) | ⚠️ Partial — chain is *availability* fallback. OpenClaw has no per-task cost routing; Bernard's queries are uniform-difficulty retrieval, so one mid-tier default + fallback is acceptable. No action needed unless costs spike |
| Permission engine (hooks/denies) | Docker exec sandbox per agent (`scope:agent`), mirror mount-enforced **read-only**, openclaw.json invisible in container | ✅ Equivalent-or-stronger for exec; config in `openclaw-config-patch.md` §5 |
| Instruction layer | `workspace/` files; **TOOLS.md is operative in sandbox mode** (codex harness drops AGENTS.md) | ✅ Live; keep rules in TOOLS.md, not AGENTS.md |
| Commit-time PHI gate | N/A — Bernard never commits to the wiki; mirror is one-way inbound | ✅ By design |
| Egress gate (leak scan) | Runs Mac-side BEFORE content reaches the VPS (mirror gated on `clean` status) | ✅ Right place — do not duplicate scanner on VPS |
| Config-secret gate | `backup-config.sh` scrubber (fixed+verified 2026-06-12) before GitHub push | ✅ Live |
| Public surface | Funnel off; briefs as WhatsApp attachments; one allowlisted contact | ✅ Live (`tailscale serve reset` if ever re-enabled) |
| Watchdog | **none** | ❌ GAP — see below |
| Question-inbox loop | VPS writes; Mac mirror sync pulls-and-drains | ✅ Live |
| Handoff/state file | Bernard is stateless-by-design between sessions; `COORDINATION.md` exists for the main VPS agent | ✅ Acceptable |

## Gaps (proposals — curator-gated)

### 1. VPS watchdog (the one real gap)

Mirror of `harness-health.sh`, minimal surface. Data flows: reads systemd/launch state + local logs only; writes one local log; network = none (notification rides the existing WhatsApp channel or surfaces via the Mac watchdog, below).

**Implemented 2026-06-12 (Mac-side, zero new VPS code):** `harness-health.sh` now SSHes daily over the mirror's existing path, alerts on any *failed* systemd user unit or on unreachability, and logs the active-state of all `openclaw|briefs|bernard` units informationally. Conservative by design — it doesn't assert specific units are active because deployed unit names weren't verifiable from the Mac (live probe is classifier-blocked for agents). **Curator tightening step (optional):** after eyeballing one day's `harness-health.log` `vps:` line, promote the units that should always be active from informational to alerting.

Rejected alternative: a systemd timer on the VPS — more code on Bernard's box, needs the vetting checklist, no added signal.

### 2. Model-policy note in TOOLS.md

One paragraph telling Bernard the chain is availability-only and to answer from the mirror without escalating models. No data-flow change (text file already in scope). Safe to include in the next bundle render.

## Vetting checklist (run before ANY new VPS install/tool/service)

1. **Reads:** exactly which paths? Any outside `~/health-wiki-workspace/` + its own state dir?
2. **Writes:** exactly which paths? Anything inside the mirror? (must be no)
3. **Network:** which hosts does it phone home to? (updates, telemetry, registries) — capture with `strace`/docs before first run
4. **Provenance:** first-party (openclaw org) or vetted source? Pinned version, no auto-update?
5. **Surface:** does it open a port, socket, or public URL? (must be no — zero public surface)
6. **Sandbox:** can it run inside Bernard's existing docker jail instead of on the host?
7. Record the answers in `openclaw-config-patch.md` before installing.
