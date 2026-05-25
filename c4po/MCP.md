# MCP Server Registry

Authoritative list of MCP servers approved for use in The Borg. Maintained by C4PO. See `../CLAUDE.md` → Lint → MCP servers for the governing rules.

## Approved servers

| Server | Scope | Source | Loaded by | Justification |
|---|---|---|---|---|
| `telegram` | user (plugin) | `telegram@claude-plugins-official` v0.0.6 | c4po, mrs-beast, warren-bot-fett | Provides the inbound/outbound channel each agent uses to receive prompts and reply to John from his phone. Required by the `telegram:configure` / `telegram:access` skills. |

## Out of scope

Servers loaded by the Claude Code harness, FleetView, or claude.ai connectors (e.g., session management, browser automation, scheduled tasks, claude.ai Gmail/Calendar/Drive) are not configured by The Borg and are not governed by this registry. If one of those starts being relied on as part of an agent's workflow, promote it to a Borg-level dependency and add an entry here.
