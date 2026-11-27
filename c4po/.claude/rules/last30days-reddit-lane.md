---
name: last30days-reddit-lane
description: "When last30days shows Reddit 0 items, 'HTTP 403: Blocked', or 'site search skipped (skipped-cached)': reddit.com refuses this host's unauthenticated search. Reddit is accepted as degraded (user decision, 2026-11-27); don't retry, tune the rate, or spoof a user agent."
---
# last30days Reddit is accepted as degraded here

last30days' keyless Reddit lane searches reddit.com without OAuth, and
reddit.com refuses this host with 403 (plain curl to `search.json`, rechecked
2026-11-27; see the workspace `reddit-via-arctic-shift` rule). It has
returned 0 items on every weekly run since 2026-11-10, on 3.31.0 and on
4.6.0. In 4.6.0 it looks like this:

- `[RedditSearch] global page 1 failed: HTTP 403: Blocked`
- `[RedditHealth] search refused this network (HTTP 403: Blocked); skipping it for 6 h`
- `[RedditKeyless] site search skipped (skipped-cached)` on later runs in that window
- `[RedditWeb] 0 threads ... (brave throttled, ...)`: the web-search fallback found nothing
- footer `Reddit: 0 items (auth-failed: HTTP 403: Blocked (run doctor for fixes))`

`--diagnose` can still list reddit as available. Trust the live per-source
footer, not the diagnose output.

**The user accepted Reddit as degraded on 2026-11-27** rather than buy a
ScrapeCreators key (`SCRAPECREATORS_API_KEY`, a paid third-party service).
So:

- Don't retry, tune `LAST30DAYS_REDDIT_KEYLESS_RATE`, clear the 6-hour skip
  cache, or set a browser user agent. None of them is a fix.
- Scheduled jobs still say Reddit is degraded, in one line, never as a
  quiet week. Their suggested next prompt must not ask anyone to fix the 403.
- When a deliverable needs a specific Reddit thread, read it through Arctic
  Shift per `reddit-via-arctic-shift`.
- Reopen this only if Reddit starts returning items again, or the user
  decides to buy a key.
