# KSLOP — Image-Gen Prompts · Nano Banana Pro

Tuned for Nano Banana Pro: it renders exact in-image text reliably and follows
structured layout regions, so these prompts lock the lettering and spatial zones
explicitly. Set the aspect ratio parameter as noted per asset. Palette and mascot
spec: see [../BRAND.md](../BRAND.md).

Tip: Nano Banana Pro accepts reference images — attach the SVG exports from
`../assets/` as style references to keep the mascot on-model across generations.

---

## 1. Launch poster — aspect ratio 9:19.5 (or 9:16 if unavailable)

> Retro 1970s rock-radio promo poster, hand-inked cartoon mascot style with a
> techno/terminal palette.
>
> LAYOUT (top to bottom):
> - TOP THIRD: the exact text "KSLOP" in chunky beveled techno/Eurostile-style capital
>   letters, phosphor green (#00FF41) with thick near-black outlines, arched in a gentle
>   upward arc, sitting on a spiky amber (#FFB000) starburst panel with a darker orange
>   (#E85D04) edge.
> - MIDDLE: full-body cartoon robot mascot "The Bad Bot" standing heroically, right fist
>   raised into a small amber starburst, left hand open at hip, chest out. Features, all
>   required: rounded bright-green (#17E85F) metal head; dark visor with two angry
>   slanted glowing green eyes with white glints; large protruding rounded muzzle with
>   three vent slots on top and a wide cocky toothy grin below with a smirk corner;
>   swept-back amber crest fin (pompadour-like); one splayed antenna with glowing amber
>   ball tip; amber billowing cape with zigzag hem and darker orange underside; amber
>   utility belt; dark chest terminal screen showing a glowing green ">" prompt and block
>   cursor; chunky green boots with amber cuffs. A large dark-green sixteen-point
>   starburst with a thin bright-green keyline sits behind him.
> - BOTTOM: he stands on a bank of dark green (#0A3D1E) cartoon clouds overlaid with
>   glowing green circuit traces ending in node dots. Below the clouds, a folded amber
>   ribbon banner with the exact text "THE BAD BOT" in near-black squared techno capitals.
>
> STYLE: thick uniform black cartoon outlines, flat cel colors, soft airbrush highlights,
> subtle CRT scanlines over a near-black (#0A0E0A) background with a faint green radial
> glow. STRICT PALETTE: #00FF41, #17E85F, #0FBF4C, #0A3D1E, #0A0E0A, #FFB000, #E85D04,
> off-white — absolutely no blue, red, or purple. No text other than "KSLOP" and
> "THE BAD BOT".

## 2. App icon source art — aspect ratio 1:1

> Square app icon artwork, full bleed, opaque background, no rounded corners, no border.
>
> SUBJECT: head-only portrait of cartoon robot mascot "The Bad Bot", centered, filling
> ~75% of frame, over a sixteen-point dark-green starburst with a thin glowing
> #00FF41 keyline. Head spec: rounded bright-green (#17E85F) metal dome; dark visor
> band with two angry slanted glowing green (#00FF41) eyes with small white glints;
> large protruding muzzle (#0FBF4C) with three dark vent slots and a huge cocky toothy
> grin with a smirk at the right corner; swept-back amber (#FFB000) crest fin with
> darker orange (#E85D04) streaks; one antenna with glowing amber ball tip; two round
> side bolts.
>
> BACKGROUND: near-black (#0A0E0A) with faint green radial glow and subtle horizontal
> CRT scanlines.
>
> STYLE: 1970s hand-inked cartoon mascot, thick uniform black outlines, flat cel colors.
> NO TEXT of any kind. Strict palette as above — no blue, red, or purple.

## 3. Wordmark plate — aspect ratio 16:9

> Logo plate on near-black (#0A0E0A) background: the exact text "KSLOP" in chunky
> squared techno capital letters with 45-degree corner bevels (Eurostile/Orbitron
> character), phosphor green (#00FF41) fills with thick near-black keylines, letters
> arched in a gentle upward arc across a spiky amber (#FFB000) starburst panel edged
> in darker orange (#E85D04). Below the burst, smaller: the exact text "THE BAD BOT"
> in near-black techno capitals on a slim amber ribbon. Flat vector-style rendering,
> thick outlines, subtle green glow. No other text, no mascot, no blue/red/purple.

### Re-roll guidance

- Spelling is usually solid; if "KSLOP" garbles, shorten the prompt around the text
  clause and put the exact-text instruction first.
- If the palette drifts warm, repeat the hex list at the end of the prompt.
- For on-model consistency across assets, generate the icon first and feed it back as
  a reference image for the poster.
