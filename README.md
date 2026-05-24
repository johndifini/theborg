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
