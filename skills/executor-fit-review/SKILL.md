---
name: executor-fit-review
description: Agent 3 in the pipeline — an LLM second-opinion fit review that gates dispatch to external apps (Gmail/Sheets/Calendar/Drive) alongside the rule-based guardrail. Use when deciding whether a tailored application should proceed or be flagged for human review.
---

# Executor — independent fit review (Agent 3)

Third and final agent. The Researcher extracted the JD's requirements, the
Tailor rewrote the resume against them; the Executor reviews the match
quality itself before the application is dispatched to external apps.

## Function

```python
from agent.executor import execute_review

verdict, used_live_llm = execute_review(resume_text, requirements, guardrail)
```

- `resume_text: str` — candidate's tailored resume
- `requirements: dict` — output of `extract_requirements` (Agent 1)
- `guardrail: dict` — output of `score_overlap` (the rule-based gate)

Returns `(verdict, used_live_llm)` where

```json
{
  "recommendation": "proceed" | "review",
  "confidence": 0.0,
  "reason": "one short sentence"
}
```

## Semantics

- **Advisory, not authoritative.** The rule-based guardrail (`score_overlap`,
  thresholds 0.40 / 0.70) remains the hard reliability gate that short-circuits
  Gmail/Sheets/Calendar/Drive. The Executor's verdict is surfaced in the UI and
  eval log as a human-readable second opinion.
- `recommendation: "review"` with the rule gate also flagging the run means the
  candidate is never dispatched anywhere (only Slack is notified).
- On LLM failure (rate limit, model pulled, network), the mock fallback mirrors
  the rule gate's outcome so offline demos behave identically to live ones.

## System prompt

Each agent holds a distinct persona; the Executor's prompt (`agent/llm.py`
`_AGENT_SYSTEM_PROMPTS["executor"]`) frames it as the final quality gate and
strictly limits output to the JSON shape above.