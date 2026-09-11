---
name: jd-parsing
description: >
  Extracts structured requirements (skills, seniority, must-haves, keywords)
  from raw job description text. Returns JSON for the downstream tailoring
  agent. Fallback: rule-based keyword extractor.
---

# JD Parsing Skill

Turns unstructured job-description text into structured JSON that the
tailoring agent uses to ground resume rewriting.

## When to use

Run this first for every new application. The output drives resume
tailoring, cover-note generation, and the guardrail check.

## Function

```python
from agent.extract import extract_requirements

requirements, used_live_llm = extract_requirements(jd_text)
```

### Input

| Arg | Type | Description |
|-----|------|-------------|
| `jd_text` | `str` | Raw job description text (pasted or scraped) |

### Output

Returns `(requirements_dict, used_live_llm: bool)`.

```json
{
  "skills": ["Python", "FastAPI", "PostgreSQL", "..."],
  "seniority": "Mid-level",
  "must_haves": ["3+ years backend experience", "..."],
  "keywords": ["Python", "FastAPI", "SQL", "..."]
}
```

- `seniority`: one of `"Entry-level"`, `"Mid-level"`, `"Senior"`
- `must_haves`: non-negotiable qualifications (short list)
- `keywords`: broader matchable keywords, ranked by importance

## Error handling

If the live LLM call fails (429, timeout, network), a deterministic
rule-based fallback extracts keywords by frequency and seniority by
keyword scan. The function always returns valid output.

## Usage in pipeline

```python
# pipeline.py
requirements, extract_live = extract_requirements(jd_text)
```
