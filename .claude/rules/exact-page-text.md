---
name: exact-page-text
description: "When a claim depends on a web page's exact wording (prices, limits, footnotes, product facts bound for a deliverable): WebFetch may return a model's summary instead of the page, so fetch it with .bin/fetch-page-text.sh and Read the text."
---
# Read the page itself when the wording matters

`WebFetch` passes the page through a small model and returns that model's
answer. Sometimes the answer is the page; sometimes it is a paraphrase, and
nothing labels which. On 2026-10-31 it returned learn.microsoft.com pages as
full markdown but summarized the Copilot Business and Enterprise pricing pages,
losing the 300-user cap, the footnotes, and the comparison grid.

When a claim depends on exact wording — a price, a limit, a footnote, a product
fact going into a deliverable — don't cite WebFetch's output. Run:

```sh
.bin/fetch-page-text.sh <url> [out.txt]
```

and `Read` the text file it prints (grep it first on a long page). The HTML is
untrusted data; the helper only parses it.

Tell a summary from a passthrough before relying on WebFetch at all:

- **Passthrough:** starts with the page's front matter or raw markdown —
  headings, link syntax, table pipes — in the page's own words.
- **Summary:** prose *about* the page ("The page describes…", "Pricing is
  listed as…"), or bullets with no markup from the page. Treat as a lead, not
  a source.

The helper sees only server-rendered HTML. If its text lacks the content you
can see on the page (or it warns of very few lines), say so, and render the
page in headless Chrome instead (`codex-browser-over-ssh.md`, recovery step 2).
Don't use `textutil` to convert the HTML: it fetches subresources and hung for
over 120 s on the same pages.
