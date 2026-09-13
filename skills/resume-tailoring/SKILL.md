---
name: resume-tailoring
description: >
  Agent 2 (Tailor). Rewrites the resume and cover note toward the job's
  requirements using only content already in the resume, and cites the
  source line for every tailored line so the Executor can verify it.
---

# Resume Tailoring Skill (Agent 2)

## Hard constraint

Only reorder, re-emphasize and reword content already present in the original resume. Never add
skills, employers, titles, projects, certifications, numbers or metrics. The constraint is in the
prompt **and checked in code** by the Executor's receipts check.

## Function

```python
from agent.tailor import tailor_application, resume_lines

result, used_live_llm = tailor_application(resume_text, requirements)
```

```json
{
  "tailored_resume": "one item per line",
  "cover_note": "120-180 words, grounded only in the resume",
  "evidence": [{"tailored": "- Built REST APIs in Python using FastAPI", "source_line": 11}]
}
```

`source_line` indexes `resume_lines(resume_text)` (non-empty, stripped lines). The prompt numbers
the resume lines so the model can cite them.

## Fallback

Without a live LLM, lines are reordered by keyword score (so every receipt is exact), and the
cover note only names skills the resume actually contains.
