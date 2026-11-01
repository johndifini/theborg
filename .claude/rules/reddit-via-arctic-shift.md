---
name: reddit-via-arctic-shift
description: "When reading, quoting, or verifying a specific Reddit thread or comment, or resolving a reddit.com/r/<sub>/s/<id> share link: read content through the Arctic Shift API (reddit's .json API returns 403), resolve share links with plain curl, and cite the reddit.com permalink."
---
# Read Reddit through Arctic Shift, not reddit.com

The host is not blocked. reddit.com returns 403 to its `.json` API, which needs
OAuth, and to a hand-set browser user agent such as `-A 'Mozilla/5.0'`, which
it flags as a fake browser. Claude-in-Chrome blocks the site. Don't retry those
routes, and never spoof a user agent. Plain curl, with its default agent, gets
normal answers (verified 2026-11-01).

A share link (`/r/<sub>/s/<id>`) has no post ID until it is resolved. Read the
redirect without following it:

```sh
curl -s -o /dev/null -w '%{redirect_url}\n' 'https://www.reddit.com/r/<sub>/s/<id>'
```

The post ID is the segment after `/comments/`. To read or verify a thread or
comment, use the Arctic Shift API:

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
