---
name: eval-logging
description: >
  Records every pipeline run's inputs, outputs, guardrail decisions, and
  action results to eval/logs/eval_log.json for the reliability brief.
  The eval batch runner also uses this to produce pass/fail tables.
---

# Eval Logging Skill

Every run writes a structured log entry so results can be reviewed,
benchmarked, and screenshotted for the reliability brief.

## What gets logged

```json
{
  "started_at": "2026-09-13T10:00:00",
  "company": "Acme Corp",
  "role": "Backend Engineer",
  "jd_source": "pasted text",
  "requirements": {"skills": [...], "seniority": "..."},
  "guardrail": {"score": 0.625, "needs_review": false},
  "actions": {
    "gmail": {"status": "ok", "detail": "..."},
    "sheets": {"status": "mocked", "detail": "..."},
    "calendar": {"status": "ok", "detail": "..."},
    "drive": {"status": "mocked", "detail": "..."},
    "slack": {"status": "ok", "detail": "..."}
  },
  "used_live_llm": true,
  "passed": true
}
```

## Automatic logging

No manual call needed — `run_pipeline()` writes to
`eval/logs/eval_log.json` at the end of every run automatically.

## Batch eval

```bash
python -m eval.run_eval
```

Runs the pipeline against every JD in `eval/sample_jds/` using
`eval/sample_resume.txt`, prints a pass/fail table, and appends
results to the same log file.

## Log location

`eval/logs/eval_log.json` (git-ignored except `.gitkeep`).
