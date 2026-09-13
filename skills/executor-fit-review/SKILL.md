---
name: executor-fit-review
description: Agent 3 — reviews the tailored application (receipts check in code + LLM fit review), then uses LLM tool calling to choose which apps (Gmail, Calendar, HubSpot CRM) to act in once every hard gate has passed. Use when deciding whether an application may be dispatched and where.
---

# Executor — review, then act (Agent 3)

## Step 1: review

```python
from agent.executor import execute_review, check_receipts

verdict, used_live_llm = execute_review(original_resume, tailoring, requirements, guardrail, company, role)
```

- `tailoring` is the Tailor's output: `tailored_resume`, `cover_note`, `evidence` (`[{tailored, source_line}]`).
- **Receipts check (authoritative, code):** each tailored line must match its cited source line
  (difflib ≥ 0.3, falling back to the closest original line), and every named thing in it
  (numbers, mixed-case tech names, mid-sentence capitalized words) must appear in the original
  resume. The cover note gets the same token check; company and role words are allowed.
- **Fit review (advisory, LLM):** `proceed | review`, confidence, one-sentence reason, plus any
  unsupported claims the model notices (`llm_flags`, shown but not gating).

```json
{
  "recommendation": "proceed",
  "confidence": 0.72,
  "reason": "Covers Python, FastAPI and PostgreSQL requirements.",
  "faithful": true,
  "unsupported_claims": [],
  "receipts": [{"tailored": "...", "source_line": 11, "supported": true, "reason": ""}],
  "llm_flags": []
}
```

`faithful: false` blocks every app action and forces `recommendation: "review"`.

## Step 2: act

```python
from agent.executor import choose_tools
tool_names, chosen_by_llm = choose_tools(requirements, guardrail, verdict, company, role)
```

Only called after `pipeline.py` has cleared every hard gate (overlap, receipts, seniority,
duplicate). The model is offered `create_gmail_draft`, `schedule_followup`, `log_crm_deal` and
may call fewer — it can never reach a tool the gates didn't allow.

Tool selection is a multi-turn loop (`agent/llm.py` `call_tools`): the first turn requires a tool
call, each chosen tool is acknowledged as queued, and the model is asked again until it stops.
Structured `tool_calls` are used when the provider returns them; when a free provider returns the
call as JSON text instead, the tool names are read from the text, accepting only offered tools. Slack is not offered: the
pipeline always notifies Slack itself. No tool calls (mock mode, model without tool support,
rate limit) → deterministic dispatch of all three, and the run log records `executor_mode`.

## Self-check

`python -m agent.executor` — asserts an honest rewrite passes and an injected fabricated bullet
("Led a Terraform migration at Google, cutting costs 40%") and a padded cover note are caught.
