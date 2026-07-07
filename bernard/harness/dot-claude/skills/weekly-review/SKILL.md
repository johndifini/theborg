---
name: weekly-review
description: Synthesize the past week's journal entries, recordings, and cross-domain activity into a weekly summary.
---

# /weekly-review

## When to use
Once a week, typically at the end of the week or beginning of the next. Produces a synthesis of activity, patterns, and open items across all domains.

## Workflow

### 1. Gather this week's activity

Read all pages with `date_created` or `date_updated` in the past 7 days:
- `wikis/journal/wiki/entries/` — journal entries and recordings
- `wikis/shared/decisions/` — any new or updated decisions
- `wikis/shared/goals/` — any goal updates
- Any other sub-wikis with recent activity (check `wikis/index.md` for sub-wikis that exist)

### 2. Identify patterns

- Recurring themes across journal entries and recordings
- Decisions made or deferred this week
- Goals with activity or momentum
- Cross-domain connections that appeared (e.g., a financial event mentioned in a journal entry that connects to a housing decision)

### 3. Surface open items

- Decisions that were raised but not resolved
- Questions that came up but weren't answered
- Goals that had no activity this week

### 4. Produce the weekly review

Format:

---

## Weekly Review — Week of YYYY-MM-DD

### Activity this week
- X journal entries / recordings ingested
- Key topics: [list themes]

### Patterns and connections
[Cross-domain connections, recurring themes, notable observations]

### Open decisions
[Decisions raised this week that need follow-up]

### Goal updates
[Goals with activity; goals with no activity that may be stalling]

### Next week
[Suggested focus areas based on open items]

---

### 5. File back (optional)

Offer to save as a query page at:
`wikis/journal/wiki/queries/YYYY-MM-DD-weekly-review.md`

Use `type: query, domain: journal`.
