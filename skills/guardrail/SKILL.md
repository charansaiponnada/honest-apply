---
name: guardrail
description: >
  Scores keyword overlap between the candidate's resume and the extracted
  job requirements. Below GUARDRAIL_THRESHOLD (40%) the run is flagged and no
  app acts; at/above AUTO_SEND_THRESHOLD (70%) the application is eligible
  to be sent — one of several conditions, never enough on its own.
---

# Confidence / Guardrail Skill

A transparent, explainable gate between tailoring and the action layer. Keyword overlap is
auditable (you can see exactly which keywords matched), which is why it is a hard gate while
the LLM fit review stays advisory.

## Thresholds

| Threshold | Default | Meaning |
|-----------|---------|---------|
| `GUARDRAIL_THRESHOLD` | 40% | Below → `needs_review=True`: Gmail, Calendar and CRM skipped, Slack gets the gap report |
| `AUTO_SEND_THRESHOLD` | 70% | At/above → `auto_send_eligible=True` |

## Function

```python
from agent.guardrail import score_overlap
result = score_overlap(resume_text, requirements)
```

```json
{
  "score": 0.625,
  "needs_review": false,
  "threshold": 0.4,
  "auto_send_threshold": 0.7,
  "auto_send_eligible": false,
  "matched": ["python", "fastapi", "sql"],
  "missing": ["kubernetes", "ci/cd"]
}
```

## How it combines with the other gates (in `agent/pipeline.py`)

Nothing is dispatched unless **all** pass: overlap ≥ `GUARDRAIL_THRESHOLD`, Executor receipts
check `faithful`, no seniority mismatch (senior job + student resume), not a duplicate.
Gmail *sends* only if additionally: Google account connected, user enabled *Allow sending*,
recipient set, `auto_send_eligible`, Executor recommends proceed.

## Known limit

Overlap can't tell a differently worded strong match from a weak one. The seniority gate covers
the most common miss (a strong-keyword student applying to a staff role).
