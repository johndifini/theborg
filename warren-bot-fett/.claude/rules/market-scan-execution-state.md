---
description: Prevent daily market-scan recommendations from stacking when prior trades were not executed
globs: [".claude/scheduled/warren-bot-fett-daily-market-scan.prompt", "PORTFOLIO.md"]
---
# A recommendation is not an execution

Before issuing a daily trade recommendation, compare current share counts and
cash balances with the latest prior scan or recommendation.

- Never infer that a recommended trade was executed merely because it appeared
  in a prior report.
- If the relevant holdings and cash are unchanged, label today's recommendation
  as a replacement or reaffirmation, not an additional trade.
- Apply the "about one trade per week per portfolio" cadence to executed trades,
  while avoiding a daily stream of cosmetically different recommendations for
  the same unresolved drift.
- If execution cannot be determined, say so and avoid stacking recommendations.
