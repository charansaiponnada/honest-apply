---
name: resume-tailoring
description: >
  Rewrites a resume to emphasize JD-relevant experience without inventing
  any new skills, employers, titles, or metrics. Hard anti-hallucination
  constraint enforced in the prompt.
---

# Resume Tailoring Skill

Takes the candidate's original resume and the extracted JD requirements,
then rewrites the resume to emphasize the most relevant experience.

## Hard constraint

**Only reorder, re-emphasize, and reword content already present in the
original resume.** The LLM is explicitly forbidden from inventing skills,
employers, titles, projects, or metrics. This is the anti-hallucination
guarantee.

## When to use

After the JD parsing skill returns requirements. Run before the guardrail
check.

## Function

```python
from agent.tailor import tailor_application, diff_lines

result, used_live_llm = tailor_application(resume_text, requirements)
```

### Input

| Arg | Type | Description |
|-----|------|-------------|
| `resume_text` | `str` | Candidate's original resume as plain text |
| `requirements` | `dict` | Output of `extract_requirements` |

### Output

Returns `(tailor_dict, used_live_llm: bool)`.

```json
{
  "tailored_resume": "Full rewritten resume text...",
  "cover_note": "120-180 word JD-specific cover note..."
}
```

## Diff helper

```python
from agent.tailor import diff_lines
lines = diff_lines(original_resume, tailored_resume)
# Returns: [("same"|"reworded", line_text), ...]
```

## Error handling

Live LLM fallback reorders existing resume lines by keyword score
and generates a generic cover note. Never invents content.

## Usage in pipeline

```python
tailoring, tailor_live = tailor_application(resume_text, requirements)
```
