---
name: guardrail
description: >
  Scores keyword overlap between the candidate's resume and the extracted
  JD requirements. Below GUARDRAIL_THRESHOLD (40%) → flags for review
  and skips all app actions. Above AUTO_SEND_THRESHOLD (70%) → eligible
  for automatic email send. Two independent gates, not one.
---

# Confidence / Guardrail Skill

A transparent, explainable guard between the tailoring step and the
action layer. Uses keyword-overlap scoring (not opaque LLM judgment)
so the reasoning is fully auditable.

## Two thresholds

| Threshold | Default | Meaning |
|-----------|---------|---------|
| `GUARDRAIL_THRESHOLD` | 40% | Below this → `needs_review=True`, all actions skipped except Slack notification |
| `AUTO_SEND_THRESHOLD` | 70% | At/above this → Gmail draft is auto-sent immediately |

Both thresholds are configurable via `.env`.

## Function

```python
from agent.guardrail import score_overlap

result = score_overlap(resume_text, requirements)
```

### Input

| Arg | Type | Description |
|-----|------|-------------|
| `resume_text` | `str` | Candidate's original resume |
| `requirements` | `dict` | Output of `extract_requirements` |

### Output

```json
{
  "score": 0.625,
  "needs_review": false,
  "threshold": 0.4,
  "auto_send_threshold": 0.7,
  "auto_send_eligible": false,
  "matched": ["Python", "FastAPI", "SQL"],
  "missing": ["Kubernetes", "CI/CD"]
}
```

- `needs_review`: `True` = skip Gmail/Sheets/Calendar/Drive, notify Slack
- `auto_send_eligible`: `True` = Gmail can auto-send (never in MVP demo)
- `matched` / `missing`: full lists of which keywords matched/didn't

## Why keyword overlap

Transparent and explainable to judges. A future improvement is an
embedding-similarity or LLM-scored second opinion alongside this one.
