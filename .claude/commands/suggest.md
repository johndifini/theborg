---
description: Suggest the single most useful next prompt for this task, using the workspace's standard closing format.
argument-hint: "[optional: goal or area to focus the suggestion on]"
model: haiku
---

Review the current conversation and identify the single most useful follow-up.
Use `$ARGUMENTS`, when present, only to focus the suggestion.

When a useful follow-up exists, respond with exactly this shape:

```markdown
## Suggested Next Prompt

<a directly reusable prompt>
```

The prompt must be on a separate line and be ready for the user to paste without
editing. Do not preface it, explain it, offer alternatives, or execute it.

When the task is complete or no meaningful next step exists, omit the section
and reply only: `No meaningful next step.`
