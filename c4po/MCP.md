# MCP Server Registry

Authoritative list of MCP servers approved for use in The Borg. Maintained by C4PO. See `../CLAUDE.md` → Lint → MCP servers for the governing rules.

## Approved servers

| Server | Scope | Source | Loaded by | Justification |
|---|---|---|---|---|
| `telegram` | user (plugin) | `telegram@claude-plugins-official` v0.0.6 | c4po, mrs-beast, warren-bot-fett | Provides the inbound/outbound channel each agent uses to receive prompts and reply to the user from their phone. Required by the `telegram:configure` / `telegram:access` skills. |

## Bundled but not loaded

Third-party plugins that ship an MCP server which is **not currently registered** (no `mcpServers` entry in the plugin manifest or `~/.claude.json`), so it does not run. Recorded here so a future audit can diff it and catch the day it goes live.

| Plugin | Bundled server | Reviewed version | Notes |
|---|---|---|---|
| `last30days@last30days-skill` (GitHub `mvanhorn/last30days-skill`) | `last30days-pp-mcp` (Go binary, outbound web search) | skill 3.8.3 / mcp manifest 3.6.0 (reviewed 2026-07-05) | Installed intentionally by the user. Currently inert — the skill runs via CLI, not the MCP server. Also ships a **SessionStart hook** (`hooks/scripts/check-config.sh`) that runs in every session: inspected 2026-07-05, non-malicious (status banner, Keychain presence check, chmod-600 of loose config). Promote to **Approved servers** if the MCP server is ever registered. |

## Out of scope

Servers loaded by the Claude Code harness, FleetView, or claude.ai connectors (e.g., session management, browser automation, scheduled tasks, claude.ai Gmail/Calendar/Drive) are not configured by The Borg and are not governed by this registry. If one of those starts being relied on as part of an agent's workflow, promote it to a Borg-level dependency and add an entry here.
