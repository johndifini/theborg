---
description: Suggest the single most useful next prompt for this task, using the workspace's standard closing format.
argument-hint: "[optional: goal or area to focus the suggestion on]"
model: haiku
---

Review the current conversation and identify the single most useful follow-up.
Use `$ARGUMENTS`, when present, only to focus the suggestion.

When a useful follow-up exists, respond with only the `## Suggested Next Prompt`
section, in the canonical shape fixed by the workspace `AGENTS.md` →
Communication style. The prompt must be ready for the user to paste without
editing. Do not execute it.

When the task is complete or no meaningful next step exists, omit the section
and reply only: `No meaningful next step.`
