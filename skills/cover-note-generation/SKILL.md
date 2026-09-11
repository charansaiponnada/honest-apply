---
name: cover-note-generation
description: >
  Generates a short, JD-specific cover note grounded strictly in the
  candidate's real resume content. Bundled with the resume tailoring skill.
---

# Cover Note Generation Skill

Produces a 120-180 word cover note tailored to the specific job
description, grounded only in the candidate's actual experience.

## When to use

Generated together with the tailored resume by `tailor_application`.
Not a separate call — it's the second field in the tailoring output.

## Function

```python
from agent.tailor import tailor_application

result, _ = tailor_application(resume_text, requirements)
cover_note = result["cover_note"]
```

### Output

The `cover_note` field from the tailoring result: a short paragraph
specifically referencing the role's seniority level and top skills,
connected to the candidate's real experience from the resume.

## Anti-hallucination

The same hard constraint as resume tailoring applies: the cover note
must only reference experience already present in the original resume.

## Usage in pipeline

```python
cover_note = tailoring["cover_note"]  # drafted alongside tailored resume
```
