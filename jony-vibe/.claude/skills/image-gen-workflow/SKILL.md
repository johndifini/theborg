---
name: image-gen-workflow
description: Proven workflow for AI image generation — write a Midjourney-style prompt first, then run it through image-gen tools in a specific priority order. Use whenever creating or iterating on AI-generated images, logos, or graphics.
---

# Image Generation Workflow

Field-tested process for getting the best AI image results.

## Step 1 — Write a Midjourney-style prompt first

Draft (or have an LLM draft) a **Midjourney prompt** for the desired image, even though Midjourney won't necessarily be the tool used. The Midjourney prompt format produces the best results across all tools.

When the deliverable is a transformation of an existing image, attach the source image and describe the transformation as explicit, numbered instructions. Good instructions are concrete and constraint-based, e.g.:

1. Replace the buzzard with a robot with the same expression.
2. Use these colors in priority order: `#00F604`, `#F67F00`, `#0077F6`
3. Use a flat design (no shading).
4. Keep the star shape as-is.
5. The robot is wearing headphones, and it has a radio transmitter on its head.
6. Incorporate negative space in the robot's face.

Instruction patterns that work well:

- **Element swaps** that preserve attributes ("same expression")
- **Color palettes in priority order**, as hex codes
- **Style constraints** ("flat design, no shading")
- **Preservation rules** ("keep the star shape as-is")
- **Specific added details** (headphones, radio transmitter)
- **Design techniques** ("incorporate negative space")

## Step 2 — Run the prompt through tools in priority order

Despite the prompt being Midjourney-formatted, the best results come from these tools, in order:

1. **ChatGPT** (image generation)
2. **Gemini Pro**
3. **[ideogram.ai](https://ideogram.ai/)**
4. **Midjourney**

Start with ChatGPT; fall through the list only if results are unsatisfactory.
