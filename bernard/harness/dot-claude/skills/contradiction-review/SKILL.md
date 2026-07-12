---
name: contradiction-review
description: Surface and document conflicting claims across health records, sources, or pages for a given topic.
---

# /contradiction-review

## When to use
- When two or more health sources disagree about a diagnosis, lab value, medication history, or clinical fact.
- After a batch ingest, to catch new contradictions.
- When preparing for an appointment where conflicting records need to be reconciled.

## Usage

```
/contradiction-review <topic>
```

Topic can be a condition, biomarker, medication, provider, or free-text description.

Examples:
- `/contradiction-review hypertension`
- `/contradiction-review hs-crp`
- `/contradiction-review pulmonary-embolism timeline`

## Workflow

### 1. Gather all relevant pages

- Read the shared entity page in `wikis/health/shared/` for the topic.
- Read all clinical records in `wikis/health/clinical/wiki/records/` that cite this entity.
- Read all research and treatment pages that reference this entity.
- Read all personal tracking pages that mention it.

### 2. Extract claims

For each page, extract all factual claims about the topic with:
- The claim text
- The date of the source (not the wiki page creation date)
- The source path
- The source type (clinician record, research, personal tracking, etc.)

### 3. Identify contradictions

Compare claims across sources. Flag any pair where:
- Two sources state different values for the same measurement at overlapping times
- Two sources disagree on diagnosis, status, or history
- A newer source appears to supersede an older claim without the older page being updated
- A clinician record conflicts with patient-reported history

### 4. Apply source hierarchy

For each contradiction:
1. Clinician records and formal results
2. Peer-reviewed research or clinical guidelines
3. Reputable medical references
4. Patient tracking and human memory
5. Forums or anecdotes

Do not resolve contradictions automatically. Present the hierarchy ranking.

### 5. Report

---

## Contradiction Review — [Topic] — [Date]

### Contradiction 1
**Claim A:** [text] [[source-A]] (date: YYYY-MM-DD, type: clinician record)
**Claim B:** [text] [[source-B]] (date: YYYY-MM-DD, type: patient tracking)
**Hierarchy:** Claim A ranks higher (clinician record > patient tracking).
**Status:** Unresolved — curator review needed.
**Suggested action:** [e.g. "Update condition page to note the discrepancy with explicit dates."]

---

### 6. Update pages

For each contradiction, offer to add a `## Contradictions` section to the entity page:
```markdown
> Contradiction: [Claim A] [[source-A]] conflicts with [Claim B] [[source-B]]. Source hierarchy favors [A/B]. Unresolved as of YYYY-MM-DD.
```
Do not delete or overwrite either claim.

### 7. File back (optional)

Offer to save as a query page at:
`wikis/health/shared/queries/YYYY-MM-DD-contradiction-<topic>.md`
