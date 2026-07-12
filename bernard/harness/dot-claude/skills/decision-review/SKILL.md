---
name: decision-review
description: Surface open, stale, and undocumented decisions across the life wiki.
---

# /decision-review

## When to use
Monthly, or when the curator wants to clear the decision backlog. Surfaces decisions that need action or documentation.

## Workflow

### 1. Read all decision pages

Read every page in `wikis/shared/decisions/` and any domain-specific decision pages.

### 2. Categorize

For each decision:
- **Open**: status is staged/active but no outcome is documented
- **Stale**: open decision with `date_created` more than 30 days ago
- **Missing outcome**: a decision was made but the outcome field is blank
- **Linked to stalled goal**: the decision is tied to a goal that has had no activity in 30+ days

### 3. Report

Format:

---

## Decision Review — YYYY-MM-DD

### Stale open decisions (>30 days, no outcome)
1. [Decision title] — opened YYYY-MM-DD — [domain] — Suggested action: follow up or close

### Decisions missing outcomes
1. [Decision title] — marked decided on YYYY-MM-DD — Suggested action: document the outcome

### Decisions linked to stalled goals
1. [Decision title] — linked to goal [goal name] — goal last active YYYY-MM-DD

### Recently resolved (for awareness)
1. [Decision title] — resolved YYYY-MM-DD

---

### 4. Offer to update

Offer to mark stale decisions as `archived` with a note, or to prompt the curator for outcomes on pending decisions. Do not auto-update without confirmation.
