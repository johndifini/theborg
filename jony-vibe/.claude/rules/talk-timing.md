---
name: talk-timing
description: "Before giving timing advice on a scripted talk: measure two gauges, script words (130 wpm plus 10% for pauses, plus planned room time) and slide pace (seconds per content slide, about 15 per divider), against speaking time minus a tenth for unplanned questions; call a deck under 90 s per content slide crowded; recount the live script from a fresh plain-text read, never from summed edit deltas; report both gauges every time."
paths:
  - "**/*script*"
  - "**/*.gdoc"
  - "**/*.pptx"
---
# Check a talk's timing with two gauges

Measure both gauges, and say where they disagree:

- **Script words.** 130 words a minute, plus 10% for pauses, plus planned
  room time.
- **Slide pace.** Seconds per content slide, counting about 15 seconds per
  section divider.

Measure against **speaking time**: the slot minus Q&A. Hold back about a tenth
of it for unplanned questions mid-talk; planned show-of-hands moments don't
count toward that buffer.

While the pace is under 90 seconds per content slide, call the deck crowded
rather than suggesting more material. On 2026-11-01 a word count alone called a
37-slide, 45-minute talk 4.5 minutes short, when its slides had 76 seconds
each.

Before giving timing advice, recount the live script from a fresh plain-text
read (Drive `read_file_content`) instead of summing per-edit deltas, and report
both gauges every time. John edits the script by hand, so deltas drift: on
2026-11-02 a recount came in 133 words under the running total.

A planned outline's timing is the budget, not a measurement.
