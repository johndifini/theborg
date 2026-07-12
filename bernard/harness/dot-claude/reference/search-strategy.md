# Search Strategy Reference

Which tool to use for which kind of question. Picking wrong costs 30 seconds (grep) vs. 5 minutes (cold GBrain).

---

## Decision Tree

| Question type | Best tool | Why |
|---|---|---|
| "Where is this exact string?" | `grep` via Bash | Exact match, instant, zero false negatives |
| "Which files mention X or Y?" | `grep` via Bash | Pattern matching; works even if GBrain is cold |
| "Summarize all records about X across 5+ files" | Explore agent | Reads full file content; no embedding loss |
| "What happened to X over time?" | Explore agent → direct reads | Timeline assembly needs full context per file |
| "What's semantically related to X?" | `gbrain query "..."` | The one case where semantic similarity adds value |
| "What's linked to/from entity X?" | `gbrain graph-query <slug> --depth 2` | This is what GBrain is actually good at |
| "What entities connect A to B?" | `gbrain graph-query <slug> --depth 2` | Graph traversal; impossible with grep |
| "I know exactly which file I need" | `Read` tool directly | No search needed |

---

## When NOT to use GBrain for content queries

GBrain returns chunks ranked by embedding similarity, not by exact match or clinical relevance. In a medical wiki:
- "lupus anticoagulant" and "dRVVT" aren't close in nomic-embed-text embedding space despite being the same test
- Lab values, ICD codes, and medication names won't rank well semantically
- GBrain cold-start is 2–5 min; grep is <1 sec

**Use grep or Explore agents for content. Use GBrain for relationships.**

---

## GBrain graph-query is underused — examples that actually benefit from it

```bash
# Everything linked to a specific condition
gbrain graph-query lupus-anticoagulant-aps --depth 2

# All providers who have records pointing to a condition
gbrain graph-query dermatomyositis-mda5 --depth 1

# Relationship path between two entities
gbrain graph-query dr-patel-neurologist --depth 2
```

Graph traversal is the unique capability GBrain offers that grep cannot replicate. This is where to invest GBrain queries.

---

## Explore agent pattern (for large content searches)

```
Spawn an Explore agent with: "Read files X through Y in [path]. For each, return one-line summary: date | provider | key finding."
```

- Cap batches at ~25 files to avoid token limits
- Works in parallel (multiple agents reading different slices)
- Agent reads full file content — no embedding distortion
- Results come back as structured summaries you can synthesize in the main loop

This is the standard pattern for batch ingest processing and for "survey everything about topic X."

---

## Warm vs. cold GBrain

- **Warm** (Ollama active ≤60 min): queries ~5–10 sec — acceptable
- **Cold** (>60 min idle): queries 2–5 min — use grep instead, queue GBrain for after

Check if Ollama is running before queuing GBrain: `pgrep -x ollama`

---

## Summary

> GBrain is a graph engine, not a search engine. Use it to traverse relationships. Use grep and Explore agents to read content.
