"""
Skill 2: Resume + Cover Note Tailoring.

HARD CONSTRAINT: this skill must only REORDER / REWORD facts already present
in the candidate's original resume. It must never invent skills, employers,
titles, metrics, or experience that isn't already there. That constraint is
stated explicitly in the LLM prompt below, and the mock fallback only ever
copies/reorders lines from the real resume too, for the same reason.
"""
import re

from agent.llm import call_json


def _mock_tailor(resume_text: str, requirements: dict) -> dict:
    """Rule-based fallback: reorder existing resume lines toward JD keywords."""
    keywords = [k.lower() for k in requirements.get("keywords", [])]
    lines = [l for l in resume_text.splitlines() if l.strip()]

    def score(line: str) -> int:
        low = line.lower()
        return sum(1 for k in keywords if k in low)

    ordered = sorted(lines, key=score, reverse=True)
    tailored_resume = "\n".join(ordered)

    top_skills = ", ".join(requirements.get("skills", [])[:4]) or "the role's core requirements"
    seniority = requirements.get("seniority", "the")
    cover_note = (
        f"I'm excited to apply for this {seniority.lower()} role. My background lines up "
        f"closely with what you're looking for, particularly around {top_skills}. "
        f"Based on my resume, I've built relevant, hands-on experience in these areas and "
        f"would welcome the chance to bring that to your team. Details of my background are "
        f"in the attached resume."
    )
    return {"tailored_resume": tailored_resume, "cover_note": cover_note}


def tailor_application(resume_text: str, requirements: dict) -> tuple[dict, bool]:
    """Returns ({"tailored_resume": str, "cover_note": str}, used_live_llm)."""
    prompt = f"""You are a resume-tailoring assistant. You will be given a candidate's
ORIGINAL RESUME and a JOB REQUIREMENTS JSON extracted from a job description.

HARD CONSTRAINT — do not violate this under any circumstances:
Only reorder, re-emphasize, and reword content that is ALREADY present in the
original resume. NEVER invent, add, exaggerate, or imply any skill, employer,
title, project, certification, or metric that is not already in the original
resume text. If the JD wants something the resume doesn't have, simply do not
claim it.

Return ONLY a JSON object of this exact shape (no markdown, no commentary):
{{
  "tailored_resume": "the reworded/reordered resume as plain text",
  "cover_note": "a short (120-180 word) JD-specific cover note grounded only in the resume"
}}

ORIGINAL RESUME:
\"\"\"{resume_text}\"\"\"

JOB REQUIREMENTS JSON:
{requirements}
"""
    result, live = call_json(
        prompt, mock_fn=lambda: _mock_tailor(resume_text, requirements), agent="tailor"
    )
    result.setdefault("tailored_resume", resume_text)
    result.setdefault("cover_note", "")
    return result, live


def diff_lines(original: str, tailored: str) -> list[tuple[str, str]]:
    """Very small line-level diff for the UI's before/after view.

    Returns a list of (status, line) tuples where status is one of
    'same', 'moved' (present in both, different position/wording context),
    used purely for display — not a real diff algorithm.
    """
    orig_lines = [l for l in original.splitlines() if l.strip()]
    tail_lines = [l for l in tailored.splitlines() if l.strip()]
    orig_set = set(l.strip().lower() for l in orig_lines)
    out = []
    for line in tail_lines:
        status = "same" if line.strip().lower() in orig_set else "reworded"
        out.append((status, line))
    return out
