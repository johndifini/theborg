# theborg — design assets

Design deliverables for the `johndifini/theborg` repository itself. Owned by
`jony-vibe/`.

## GitHub social preview

`assets/social-preview-1280x640.png` — the Open Graph card GitHub serves when a
`theborg` link is shared (Settings → General → Social preview).

**Spec**

| Property | Value |
|---|---|
| Dimensions | 1280 × 640 (2:1, GitHub's required ratio) |
| Side margins | 120px — nothing load-bearing inside them |
| Vertical placement | Name, description and avatar share an optical centre at y=258 — the midpoint of the band *above* the GitHub mark, not of the full canvas |
| Background | `#10161f` → `#0d1117` → `#080b10` diagonal, with a teal radial lift behind the avatar |
| Repo name | GitHub default UI stack (`-apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial`), 80px, −0.025em |
| Owner segment | `#8b949e` regular · **Repo segment** `#f0f6fc` bold |
| Description | 38px, `#9aa7b4` — one short line, deliberately |
| Avatar | 208px, 30px radius, 1px `rgba(240,246,252,.14)` hairline |
| GitHub mark | 54px, `#6e7681`, 120px right / 70px bottom — holds its own baseline |
| Accent rule | 6px bottom edge, teal → deep slate; sampled from the avatar's sweater |

**Rationale.** Dark canvas matched to GitHub's own dark theme so the card sits in
the product rather than beside it. The content block is lifted off the vertical
centre so the GitHub mark reads as a signature in its own space rather than as a
fourth element competing with the type; the wide side margins keep the card calm
at full size and stop the type crowding the edge when a client crops it. Type is oversized on purpose: the repo name
clears legibility at 25% scale (320 × 160, the Slack/X inline size) and still
holds at 15%. Description is one line because long descriptions wrap and
truncate in this layout, which is what makes GitHub's auto-generated card look
unconsidered.

## Reproducing

`src/social-preview.html` is the source; the avatar is inlined as base64 so the
file renders standalone.

```
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --headless=new --disable-gpu --hide-scrollbars --force-device-scale-factor=1 \
  --window-size=1280,640 --screenshot=social-preview-1280x640.png \
  file://$PWD/src/social-preview.html
```

`src/avatar-source.jpg` is the 460 × 460 original from the GitHub profile,
kept so the card can be re-rendered if the live avatar changes.
