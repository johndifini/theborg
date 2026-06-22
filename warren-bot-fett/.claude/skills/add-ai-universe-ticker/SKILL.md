---
name: "add-ai-universe-ticker"
description: "Add a company/ticker to the AI sleeve investable universe (ai-sleeve/universe.md) — resolve the ticker, place it in the right category, handle pre-IPO placeholders, and add a parallel inclusion thesis. Use when asked to 'add <company/ticker> to the AI (sleeve) universe'."
---
# Add a ticker to the AI universe

Recurring workflow for adding a company to the AI sleeve investable universe. Most of the file format is self-documenting from `ai-sleeve/universe.md`, but two steps below are easy to skip and were the source of past mistakes (a near-duplicate entry, and inconsistent formatting). Do not skip them.

## Steps

1. **Read `ai-sleeve/universe.md`.** Note the `categories` lists, the `soft_excludes` section, and the `## Inclusion theses` format used by sibling entries.

2. **Resolve the company → real US ticker + listing status** via WebSearch. If the company is still private / pre-IPO, do **not** add it to `categories`. Instead add or keep a `soft_excludes` placeholder line with the embedded "at listing, do X" note.

3. **Before adding, grep `soft_excludes` for an existing placeholder** for this name. If one exists, follow its embedded instructions: replace the placeholder with the resolved ticker, add it to the named category, and delete the placeholder line. (Skipping this check is how a duplicate entry gets created.)

4. **Add the ticker to the single best-fit `categories` member list.** Pick one category, not several.

5. **Add a parallel `## Inclusion theses` bullet** matching sibling format:
   `- **TICKER** — <one-line thesis>; Reevaluate if <condition>.`

6. **Report** the category placement and note that the name competes on market cap at the next rebalance.
