---
name: reddit-via-arctic-shift
description: "When reading, quoting, or verifying a specific Reddit thread or comment: reddit.com refuses this host (curl 403, Claude-in-Chrome blocked), so use the Arctic Shift API and cite the reddit.com permalink."
---
# Read Reddit through Arctic Shift, not reddit.com

reddit.com refuses this host: curl gets 403 and `.json` endpoints fail, and
Claude-in-Chrome blocks the site. Don't retry either route. To read or verify a
thread or comment, use the Arctic Shift API:

- `https://arctic-shift.photon-reddit.com/api/comments/search?link_id=<post id>&limit=100`
- `/api/posts/ids?ids=<id>`
- `/api/comments/ids?ids=<c1>,<c2>`
- `/api/comments/tree`

Pause a few seconds between calls; "Timeout. Maybe slow down a bit" is a rate
limit, not an outage. Cite the reddit.com permalink
(`https://www.reddit.com/r/<sub>/comments/<post>/comment/<comment>/`), and say a
link was checked against the archive, not opened.

Observed in four jony-vibe deck-research sessions on 2026-10-18/19; two lost
turns on reddit.com before falling back to the archive.
