"""
Agent 2 (Tailor): Resume + Cover Note Tailoring, with receipts.

HARD CONSTRAINT: this skill must only REORDER / REWORD facts already present
in the candidate's original resume. It must never invent skills, employers,
titles, metrics, or experience that isn't already there.

Receipts: every tailored line comes back with `source_line`, the index of
the original resume line it was derived from (indices over resume_lines()).
The Executor verifies those receipts in code before anything is sent, so
the no-fabrication rule is checked, not just prompted for.
"""
import re

from agent.llm import call_json


def resume_lines(text: str) -> list[str]:
    """Non-empty, stripped resume lines — the index space receipts refer to."""
    return [line.strip() for line in text.splitlines() if line.strip()]


def _mock_tailor(resume_text: str, requirements: dict) -> dict:
    """Rule-based fallback: reorder existing resume lines toward JD keywords."""
    keywords = [k.lower() for k in requirements.get("keywords", [])]
    lines = resume_lines(resume_text)

    def score(i: int) -> int:
        low = lines[i].lower()
        return sum(1 for k in keywords if k in low)

    order = sorted(range(len(lines)), key=score, reverse=True)
    resume_lower = resume_text.lower()
    # Only name skills the resume actually has — the cover note gets receipts-checked too.
    held = [
        s for s in requirements.get("skills", [])
        if re.search(rf"(?<![a-z0-9]){re.escape(s.lower())}(?![a-z0-9])", resume_lower)
    ][:4]
    focus = ", ".join(held) or "the areas this role focuses on"
    seniority = requirements.get("seniority", "the")
    cover_note = (
        f"I'm excited to apply for this {seniority.lower()} role. My background lines up "
        f"with what you're looking for, particularly around {focus}. "
        f"My resume shows hands-on experience in these areas and I would welcome the "
        f"chance to bring that to your team. Details of my background are in the attached resume."
    )
    return {
        "tailored_resume": "\n".join(lines[i] for i in order),
        "cover_note": cover_note,
        "evidence": [{"tailored": lines[i], "source_line": i} for i in order],
    }


def _unescape(text: str) -> str:
    """Some models double-escape JSON and return literal "\\n" instead of line breaks."""
    return text.replace("\\n", "\n") if text.count("\\n") > text.count("\n") else text


def tailor_application(resume_text: str, requirements: dict) -> tuple[dict, bool]:
    """Returns ({"tailored_resume", "cover_note", "evidence"}, used_live_llm)."""
    numbered = "\n".join(f"[{i}] {line}" for i, line in enumerate(resume_lines(resume_text)))
    prompt = f"""You will be given a candidate's ORIGINAL RESUME (one line per [index])
and a JOB REQUIREMENTS JSON extracted from a job description.

HARD CONSTRAINT — do not violate this under any circumstances:
Only reorder, re-emphasize, and reword content that is ALREADY present in the
original resume. NEVER invent, add, exaggerate, or imply any skill, employer,
title, project, certification, number, or metric that is not already in the
original resume text. If the JD wants something the resume doesn't have,
simply do not claim it.

Return ONLY a JSON object of this exact shape (no markdown, no commentary):
{{
  "tailored_resume": "the reworded/reordered resume as plain text, one item per line, using real line breaks",
  "cover_note": "a 120-180 word cover note in the FIRST PERSON ("I built..."), addressed to the hiring team, specific to this job, grounded only in the resume",
  "evidence": [
    {{"tailored": "one line of tailored_resume, verbatim", "source_line": 0}}
  ]
}}
"evidence" must have exactly one entry per line of tailored_resume, in order.
"source_line" is the [index] of the original line that tailored line was derived from.

ORIGINAL RESUME:
{numbered}

JOB REQUIREMENTS JSON:
{requirements}
"""
    result, live = call_json(
        prompt, mock_fn=lambda: _mock_tailor(resume_text, requirements), agent="tailor"
    )
    result["tailored_resume"] = _unescape(str(result.get("tailored_resume") or resume_text))
    result["cover_note"] = _unescape(str(result.get("cover_note") or ""))
    if not isinstance(result.get("evidence"), list):
        result["evidence"] = []
    for entry in result["evidence"]:
        if isinstance(entry, dict) and isinstance(entry.get("tailored"), str):
            entry["tailored"] = _unescape(entry["tailored"])
    return result, live


if __name__ == "__main__":
    assert _unescape("SUMMARY\\nBuilt APIs\\nSKILLS") == "SUMMARY\nBuilt APIs\nSKILLS"
    assert _unescape("real\nbreaks, one literal \\n kept") == "real\nbreaks, one literal \\n kept"
    print("tailor self-check passed")
