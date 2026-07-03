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
- `architetto/` — The software architect agent. Bootstraps greenfield repos — picking the stack, automated-testing framework, repo structure, and database — then hands them off with the decisions written down.
- `repos/` — Where `architetto` parks the repos it initializes. Each is its own independent git repo; the workspace git-ignores the contents (structure only, via `.gitkeep`) so product code stays out of The Borg's history.

## Scheduled Jobs

Each agent runs background tasks via macOS launchd. Plists live in `~/Library/LaunchAgents/` under the `com.theborg.*` namespace. All jobs are driven by `.bin/run-scheduled-task.sh` and log to `<agent>/.claude/scheduled/logs/launchd.{out,err}`. The plists embed absolute paths and aren't committed verbatim — regenerate them from your checkout with `.bin/install-scheduled-tasks.sh` (which holds the schedule table as the single source of truth; add `--load` to (re)register them with launchd).

Jobs notify the user by **email** via `.bin/notify-email.sh` (outbound Gmail SMTP; creds in `~/.claude/channels/email-shared/.env`). `run-scheduled-task.sh` pins each run to a fixed `--session-id`, so the notification email includes a `claude --resume <id>` command to continue that exact session on the Mac Studio. `.bin/notify-telegram.sh` remains in the tree as a manual/backup channel but is no longer wired into any scheduled job.

For more info about each job, see `<agent>/.claude/scheduled/<label>.prompt`.

### c4po

| Label | Schedule | What it does |
|---|---|---|
| `c4po-security-audit` | Daily at 10:00 AM | Audits all agent settings files, hooks, permission rules, Telegram access lists, and MCP servers for security issues. Emails the result every run — findings with recommended fixes, or an all-clear if clean. |
| `c4po-lint-audit-monthly` | 1st–5th of each month at 9:00 AM¹ | Audits the entire workspace against the lint rules in the root CLAUDE.md. Emails the result every run — violations grouped by rule section, or an all-clear if clean. Runs once per month (state tracked in `c4po/.claude/scheduled/state/`). |
| `c4po-assumptions-audit-monthly` | 1st–5th of each month at 9:00 AM¹ | Re-evaluates ephemeral best-practice assumptions (CLAUDE.md line ceiling, launchd as scheduler, slash-command relevance, cerebruh raw-source ceiling, whether native "dreaming" has superseded the custom dream/consolidate jobs) against current Anthropic guidance and tooling. Also scans CLAUDE.md sizes against the current ceiling. Emails the result every run — anything flagged, or an all-clear if clean. Runs once per month (state tracked in `c4po/.claude/scheduled/state/`). |
| `c4po-dream` | Sat at 10:00 PM (Sun retry)² | Harvests durable lessons from the user's Claude sessions machine-wide since its last run and routes them to the right home — proposed rules, CLAUDE.md additions, and skills are emailed as a digest; durable shared knowledge is staged into `cerebruh/ingest/` for the user to ingest. Propose/stage-only — never writes Auto Memory or the cerebruh wiki. Emails every run — the digest, or a one-liner if nothing clears the bar. Runs once per week (state tracked in `c4po/.claude/scheduled/state/`). |
| `c4po-consolidate-memory` | Sun at 11:00 PM (Mon retry)² | Tidies every Auto Memory store in the workspace (the shared store plus any `repos/*` repo store) in place: merges duplicates, fixes/prunes stale facts, repairs the index. Emails a digest every run — what changed, or a one-liner if all stores are already tidy. Runs once per week (state tracked in `c4po/.claude/scheduled/state/`). |

### mrs-beast

| Label | Schedule | What it does |
|---|---|---|
| `mrs-beast-social-media-drafts` | Sun–Wed at 4:00 PM | Scans AI/tech podcast and YouTube sources for new content, then delivers 3 best X (Twitter) post drafts via email. |

### warren-bot-fett

| Label | Schedule | What it does |
|---|---|---|
| `warren-bot-fett-daily-market-scan` | Mon–Fri at 9:00 AM | Fetches market data (indices, yields, VIX), checks portfolio allocations against targets, and emails the result every run — a specific trade alert when a genuine buying opportunity exists, otherwise a brief no-action summary (one-liner on market holidays). |
| `warren-bot-fett-ai-sleeve-monthly` | 1st–5th of each month at 9:00 AM¹ | Runs the AI Sleeve rebalance on the first trading day of the month: ranks candidates by market cap, enforces category minimums, computes floor-adjusted weights, and delivers a target-weights report via email. Writes `ai-sleeve/last-rebalance.json` for month-over-month diffs. |
¹ Fired on days 1–5 as a retry window in case the machine was asleep on day 1. The prompt enforces once-per-month execution via a state file.
² Fired on the primary day plus the next day as a retry window in case the machine was asleep. The prompt enforces once-per-ISO-week execution via a state file.

## Slash Commands

Project-scoped slash commands live in `.claude/commands/` (workspace-wide) or `<agent>/.claude/commands/` (agent-scoped, only visible from that agent's directory).

Every scheduled task has a matching interactive command (named after the task, minus the agent prefix). Each delegates to the same `.prompt` the launchd job runs — no duplicated logic — applying only the overrides needed for interactive use: skip once-per-month state gates and state/data-file writes, and report to the session instead of email.

| Command | Scope | What it does |
|---|---|---|
| `/remember` | workspace | Save durable context to the current agent's Auto Memory file (`~/.claude/projects/<project>/memory/MEMORY.md`) so it persists across sessions. With no argument, writes a concise gist of the current conversation; with an argument, saves that specific item as a standing fact or rule. Shows the proposed addition for approval before writing unless the request is unambiguous. |
| `/retro` | workspace | End-of-session retrospective. Asks "is there anything here worth saving?" — scans the session (or a user-supplied note about where Claude's default diverged from what was actually wanted) for lessons worth persisting to a memory file or `CLAUDE.md`. High bar for writing anything; per-item approval before any change. Optional free-text argument: `/retro I went with this version XYZ`. |
| `/audit-assumptions` | c4po | Runs the `c4po-assumptions-audit-monthly` audit logic interactively, reporting the full result (all verdicts, not just flagged) to the session instead of email. Skips the once-per-month state file so it never blocks the scheduled run. |
| `/dream` | c4po | Runs the `c4po-dream` harvest logic interactively, reporting all proposals (rules, CLAUDE.md, skills, cerebruh candidates) to the session instead of email. Defaults to a 7-day window (override via argument, e.g. `/dream last 14 days`); asks before staging any cerebruh candidate. Skips the once-per-week state file so it never moves the scheduled run's harvest boundary. |
| `/consolidate-memory` | c4po | Runs the `c4po-consolidate-memory` logic interactively, consolidating the Auto Memory stores for real and reporting what changed (including "no changes") to the session instead of email. Skips the once-per-week state file so it never blocks the scheduled run. |
| `/security-audit` | c4po | Runs the `c4po-security-audit` logic interactively, reporting what was checked and the verdict (including a clean bill of health) to the session instead of email. |
| `/lint-audit` | c4po | Runs the `c4po-lint-audit-monthly` logic interactively, reporting the full result (including a clean audit) to the session instead of email. Skips the once-per-month state file so it never blocks the scheduled run. |
| `/social-media-drafts` | mrs-beast | Runs the `mrs-beast-social-media-drafts` logic interactively, outputting the post drafts to the session instead of email. |
| `/market-scan` | warren-bot-fett | Runs the `warren-bot-fett-daily-market-scan` logic interactively, reporting the full scan (allocations vs. targets, deviations, opportunity verdict) to the session instead of email. Skips the market-holiday gate so it always runs. |
| `/ai-sleeve-rebalance` | warren-bot-fett | Runs the `warren-bot-fett-ai-sleeve-monthly` logic interactively, reporting target weights and the month-over-month diff to the session instead of email. Skips the once-per-month gate and does not write `last-rebalance.json`, so it never clobbers the scheduled run's diff baseline. |

## Status

This is one person’s working setup, not a polished product.

There is no roadmap, no SLA, and no sacred architecture. Things may move, disappear, mutate, or get renamed because I thought of a better pun at 11:47 PM.

That said, if you find something useful, please borrow it. Remix it. Fork it. Assimilate it into your own workflow.

Feedback, ideas, and “hey, this could be cleaner” notes are very welcome.

## Forking it

Before you make this your own:

1. Clone the repo.
1. Install the pre-commit hook: `git config core.hooksPath .githooks`
1. Set up email notifications: `cp .bin/email-shared.env.example ~/.claude/channels/email-shared/.env`, `chmod 600` it, then fill in a Gmail App Password (see the file's header).
1. Install the scheduled tasks: `.bin/install-scheduled-tasks.sh --load` — generates the launchd plists from your checkout path and registers them.
1. Read [SECURITY.md](./SECURITY.md) before your first commit — There’s a short forker checklist in there that may save you from accidentally publishing secrets, personal notes, API keys, or other spicy artifacts.
