---
name: eval-logging
description: >
  Every pipeline run is logged to eval/logs/eval_log.json (gates, verdict, actions,
  refs for undo). The batch runner scores 10 job descriptions on four checks,
  optionally with injected faults, and writes eval/logs/eval_summary.json.
---

# Eval Logging Skill

## Per-run log (automatic)

`run_pipeline()` appends one entry per run:

```json
{
  "run_id": "b581317d",
  "started_at": "2026-09-13T10:00:00",
  "company": "Acme Corp", "role": "Backend Engineer", "candidate": "Jordan Rivera",
  "jd_source": "pasted text", "recipient": "",
  "requirements": {"skills": ["..."], "seniority": "Mid-level"},
  "guardrail": {"score": 0.625, "needs_review": false},
  "executor_verdict": {"recommendation": "proceed", "faithful": true, "unsupported_claims": []},
  "executor_mode": "tool-calling | deterministic | gated",
  "gap_report": {"missing_must_haves": [], "missing_keywords": [], "unsupported_claims": [], "seniority": null},
  "outcome": "sent | drafted | partial | flagged | duplicate",
  "actions": {"gmail": {"status": "ok", "detail": "..."}, "calendar": {}, "crm": {}, "slack": {}},
  "refs": {"gmail": {"draft_id": "..."}, "calendar": {"event_id": "..."}, "crm": {"deal_id": "..."}},
  "faults": [], "used_live_llm": true, "passed": true, "undone": false
}
```

Undo and the reply tracker update the same entry (`undone`, `replied`, `reply_link`).

## Batch eval

```bash
python -m eval.run_eval
python -m eval.run_eval --faults gmail,llm_429
```

Scores each job in `eval/sample_jds/` against `eval/expected.json` on: extraction, faithfulness,
decision, actions (under faults: every failure reported with a reason, no crash). Results go to
`eval/logs/eval_summary.json` under `normal` / `faults`, which the app's Reliability tab and the
landing page read.
