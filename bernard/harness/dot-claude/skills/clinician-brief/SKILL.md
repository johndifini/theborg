---
name: clinician-brief
description: Generate an appointment-ready brief for a specific provider or upcoming appointment.
---

# /clinician-brief

## When to use
Before any clinical appointment. Produces a structured one-page brief you can review, annotate, and bring into the visit.

## Usage

```
/clinician-brief <provider-or-appointment>
```

Examples:
- `/clinician-brief dr-lee-cardiologist`
- `/clinician-brief 2026-06-02-lee-cardiology-followup`

## Workflow

### 1. Orient

- Read the provider page at `wikis/health/shared/providers/<provider>.md` for specialty, role, and history.
- If an upcoming appointment page exists (`wikis/health/clinical/wiki/appointments/<date>-<name>.md`), read it.
- Identify the conditions and medications most relevant to this provider's specialty.

### 2. Gather current status

Read the following, in order of recency:
- The most recent 3–5 clinical records for this provider or specialty from `wikis/health/clinical/wiki/records/`.
- All shared condition pages relevant to this provider's specialty.
- All shared medication pages for medications managed by or relevant to this provider.
- Relevant biomarker pages, especially those with recent values.

### 3. Gather open questions

- Read `wikis/health/shared/queries/` for any open questions tagged to this provider or specialty.
- Scan recent clinical records for flagged items, deferred decisions, or "follow up" notes.

### 4. Synthesize the brief

Produce a structured brief in this format:

---

## Appointment Brief — [Provider Name] — [Date]

**Specialty:** [specialty]
**Appointment type:** [follow-up | new consult | procedure | telehealth]

### Current status
*2–4 bullet points summarizing where things stand for conditions in this provider's scope. Cite sources.*

### Since last visit
*Changes since the most recent record with this provider: new symptoms, new labs, medication changes, new diagnoses. Cite sources.*

### Active medications (relevant to this visit)
*List with dose if known. Flag any recent changes or concerns.*

### Recent labs / objective data
*Most recent relevant values with dates. Flag anything abnormal or trending.*

### Open questions for this visit
*Numbered list of questions to raise.*

### Hypotheses / unresolved threads
*Any active hypotheses or unresolved contradictions relevant to this provider's scope.*

---

### 5. File back (optional)

Offer to save the brief as a query page at:
`wikis/health/clinical/wiki/queries/YYYY-MM-DD-<provider>-brief.md`

## Notes

- Synthesizes from the wiki only. Does not access raw source files directly unless a specific fact needs verification.
- Do not recommend medication changes, doses, or diagnoses. Present what the records say.
- If information is missing or uncertain, say so rather than filling gaps with general knowledge.
