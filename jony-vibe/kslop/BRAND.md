# KSLOP — Brand System

Rock-radio nostalgia, rewired. KSLOP takes the composition language of the classic
WMMS 101 FM "Buzzard" identity (arched burst logotype, mascot-with-attitude, ribbon
banners, cloud bank base) and re-skins it as a techno/terminal system. The mascot is
**The Bad Bot**. No hometown appears on any asset.

## Palette

| Token | Hex | Use |
|---|---|---|
| `terminal-green` | `#00FF41` | Primary. Type fills, eye glow, circuit traces, highlights |
| `bot-green` | `#17E85F` | Mascot body panels (slightly softer than pure terminal green) |
| `panel-green` | `#0FBF4C` | Secondary panels (snout, boots), shading on bot-green |
| `phosphor-dim` | `#0A3D1E` | Cloud bank, dark greens, muted fills |
| `void-black` | `#0A0E0A` | Backgrounds. Near-black with a green cast — never pure `#000` |
| `outline-ink` | `#05130A` | All cartoon outlines. Thick, consistent weight |
| `crt-amber` | `#FFB000` | Single warm accent: crest fin, antenna tips, bursts, banners |
| `amber-deep` | `#E85D04` | Amber shading / burst outer edge |
| `glint-white` | `#EAFFF2` | Eye glints, teeth, specular hits (green-tinted white) |

Rule: green does the work, amber does the punch. Amber never exceeds ~15% of any
composition. No other hues.

## Typography

Techno geometric display — squared letterforms with 45° corner bevels, in the
Eurostile/Orbitron family. In the shipped SVGs, letterforms are **drawn as
stroke-based paths** (square caps, miter joins) so there is no font dependency.
For live text in the app UI, use **Orbitron** (headers) and **JetBrains Mono**
(body/terminal text) — both open (OFL).

Treatments: double-stroke letters (dark keyline under green fill), optional amber
inner glow on hero lockups, horizontal scanlines at 4–6% opacity over large fields.

## The Bad Bot — model sheet

Fixed features (keep on-model in every rendering):

- **Head**: rounded green dome, oversized relative to body (cartoon proportions).
- **Visor**: dark band with two angry angled terminal-green eyes; small white glints.
- **Snout**: big protruding rounded muzzle (the Buzzard-beak homage) with vent
  slots on top and a wide cocky grin with teeth below.
- **Crest**: swept-back amber fin blades (the pompadour homage).
- **Antennae**: two, splayed, amber glow tips.
- **Pose**: right fist raised high, left hand open at hip height, chest out.
- **Cape**: amber outside, deep-amber underside, always mid-billow.
- **Ground**: never stands on a floor — always a bank of circuit-trace clouds
  (phosphor-dim bumps with terminal-green trace lines and node dots).

## Do / Don't

- **Do** keep outlines thick and uniform (comic-cel weight, ~1/50 of asset width).
- **Do** put the mascot on `void-black`; glow effects stay subtle (blur, not bloom).
- **Don't** add a location/hometown to any asset.
- **Don't** introduce blues, reds, or purples — the WMMS palette is referenced in
  *composition*, not color.
- **Don't** pre-round the app icon or add transparency (Apple masks it).
- **Don't** use gradients as decoration; only for glow and burst depth.

## iOS shipping notes

- App Store icon: 1024×1024, full-bleed opaque square, no alpha channel, no
  pre-rounded corners. Export `assets/app-icon.svg` → PNG at 1024.
- Launch screen: `assets/launch-screen.svg` is drawn at 1320×2868 (iPhone Pro Max
  class); core lockup sits inside a centered safe area so it crops cleanly to
  smaller aspect ratios.
- In-app marks: `assets/bad-bot-head.svg` (avatar/empty states),
  `assets/wordmark.svg` (headers, about screen).

## Files

- `assets/app-icon.svg` — 1024×1024 App Store icon (head mark, no text)
- `assets/launch-screen.svg` — poster-style launch screen
- `assets/wordmark.svg` — arched KSLOP burst logotype
- `assets/bad-bot-head.svg` — head-only mark on starburst
- `prompts/chatgpt-images.md` — image-gen prompts for ChatGPT Images 2.0
- `prompts/nano-banana-pro.md` — image-gen prompts for Nano Banana Pro
