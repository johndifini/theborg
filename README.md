# The Borg

Welcome to **The Borg** — a personal AI workspace for turning prompts, notes, tools, agents, and repeatable workflows into something that feels a little more like an operating environment.

Yes, it is yet another ClaudeOS-style setup.

"Resistance" is probably unnecessary.

This repo is my personal AI workspace, shared in case the patterns, structure, or terrible naming choices are useful to someone else.

## Directory Structure

- `cerebruh/` — The shared second-brain wiki template. Personal knowledge, reusable context, and other things Future Me will definitely forget.
- `c4po/` — The workspace administrator agent. Handles things like uptime, config, security, monitoring, and general “please don’t let this catch fire” duties.
- `mrs-beast/` — The social media manager agent. Helps with posts, ideas, drafts, and occasionally making me sound more clever than I am.
- `warren-bot-fett/` — The investment portfolio manager agent. Tracks portfolio ideas, market context, and other financially flavored stuff.
- `bones/` — The family medical assistant agent. Tracks health context, surfaces medical information, and helps the family stay on top of care decisions.

## Scheduled Jobs

Each agent runs background tasks via macOS launchd. Plists live in `~/Library/LaunchAgents/` under the `com.theborg.*` namespace. All jobs are driven by `.bin/run-scheduled-task.sh` and log to `<agent>/.claude/scheduled/logs/launchd.{out,err}`.

### c4po

| Label | Schedule | What it does |
|---|---|---|
| `c4po-security-audit` | Daily at 10:00 AM | Audits all agent settings files, hooks, permission rules, Telegram access lists, and MCP servers for security issues. Notifies via Telegram if anything critical is found; silent if clean. |
| `c4po-lint-audit-monthly` | 1st–5th of each month at 9:00 AM¹ | Audits the entire workspace against the lint rules in the root CLAUDE.md. Reports violations grouped by rule section via Telegram; silent if clean. Runs once per month (state tracked in `c4po/.claude/scheduled/state/`). |
| `c4po-assumptions-audit-monthly` | 1st–5th of each month at 9:00 AM¹ | Re-evaluates ephemeral best-practice assumptions (CLAUDE.md line ceiling, launchd as scheduler, slash-command relevance) against current Anthropic guidance and tooling. Also scans CLAUDE.md sizes against the current ceiling. Reports anything flagged via Telegram; silent if clean. Runs once per month (state tracked in `c4po/.claude/scheduled/state/`). |

### mrs-beast

| Label | Schedule | What it does |
|---|---|---|
| `mrs-beast-social-media-drafts` | Sun–Wed at 4:00 PM | Scans AI/tech podcast and YouTube sources for new content, then delivers 3 best X (Twitter) post drafts via Telegram. |

### warren-bot-fett

| Label | Schedule | What it does |
|---|---|---|
| `warren-bot-fett-daily-market-scan` | Mon–Fri at 9:00 AM | Fetches market data (indices, yields, VIX), checks portfolio allocations against targets, and alerts via Telegram only when a genuine buying opportunity exists. Silent otherwise. |
| `warren-bot-fett-ai-sleeve-monthly` | 1st–5th of each month at 9:00 AM¹ | Runs the AI Sleeve rebalance on the first trading day of the month: ranks candidates by market cap, enforces category minimums, computes floor-adjusted weights, and delivers a target-weights report via Telegram. Writes `ai-sleeve/last-rebalance.json` for month-over-month diffs. |
¹ Fired on days 1–5 as a retry window in case the machine was asleep on day 1. The prompt enforces once-per-month execution via a state file.

## Slash Commands

Project-scoped slash commands live in `.claude/commands/` (workspace-wide) or `<agent>/.claude/commands/` (agent-scoped, only visible from that agent's directory).

| Command | Scope | What it does |
|---|---|---|
| `/retro` | workspace | End-of-session retrospective. Asks "is there anything here worth saving?" — scans the session (or a user-supplied note about where Claude's default diverged from what was actually wanted) for lessons worth persisting to a memory file or `CLAUDE.md`. High bar for writing anything; per-item approval before any change. Optional free-text argument: `/retro I went with this version XYZ`. |
| `/audit-assumptions` | c4po | Test harness for the `c4po-assumptions-audit-monthly` scheduled job — runs the same audit logic on demand without touching the once-per-month state file. Use it to verify the audit and Telegram pipeline. |

## Status

This is one person’s working setup, not a polished product.

There is no roadmap, no SLA, and no sacred architecture. Things may move, disappear, mutate, or get renamed because I thought of a better pun at 11:47 PM.

That said, if you find something useful, please borrow it. Remix it. Fork it. Assimilate it into your own workflow.

Feedback, ideas, and “hey, this could be cleaner” notes are very welcome.

## Forking it

Before you make this your own:

1. Clone the repo.
1. Install the pre-commit hook: `git config core.hooksPath .githooks`
1. Read [SECURITY.md](./SECURITY.md) before your first commit — There’s a short forker checklist in there that may save you from accidentally publishing secrets, personal notes, API keys, or other spicy artifacts.
