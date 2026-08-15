---
name: yahoo-chart-daily-return
description: When computing a daily return from Yahoo Finance chart data: divide adjacent valid closes; meta.chartPreviousClose turns a multi-day move into a false daily move.
---
# Do not use chartPreviousClose as yesterday's close on multi-day queries

For a same-day move from Yahoo Finance chart data, divide the latest regular-market close by the immediately preceding non-null close in the timestamp/indicator series. `meta.chartPreviousClose` is the close before the requested chart range and can turn a multi-day move into a false daily move. If the result materially affects a trade or opportunity recommendation, cross-check it against an independent live source before emailing.
