"""
Skill 1: JD Requirement Extraction.

Turns raw, unstructured job-description text into a structured JSON object:
  {skills: [...], seniority: str, must_haves: [...], keywords: [...]}
"""
import re

from agent.llm import call_json

_STOPWORDS = {
    "the", "and", "for", "with", "you", "your", "our", "are", "will",
    "this", "that", "have", "has", "from", "who", "job", "role", "team",
    "work", "years", "year", "experience", "a", "an", "to", "of", "in",
    "on", "as", "is", "we", "or", "at", "be", "including", "etc",
}


def _mock_extract(jd_text: str) -> dict:
    """Rule-based fallback extractor — no LLM call required."""
    words = re.findall(r"[A-Za-z][A-Za-z+.#]{1,}", jd_text)
    freq: dict[str, int] = {}
    for w in words:
        lw = w.lower()
        if lw in _STOPWORDS or len(lw) < 3:
            continue
        freq[lw] = freq.get(lw, 0) + 1
    keywords = [w for w, _ in sorted(freq.items(), key=lambda kv: -kv[1])][:15]

    seniority = "Mid-level"
    lowered = jd_text.lower()

    def has(*terms: str) -> bool:
        # whole words only: "intern" must not match "internal", "lead" was dropped ("lead user research")
        return any(re.search(rf"(?<![a-z]){re.escape(t)}(?![a-z])", lowered) for t in terms)

    if has("senior", "sr.", "staff", "principal", "5+ years", "8+ years"):
        seniority = "Senior"
    elif has("intern", "internship", "entry level", "entry-level", "new grad", "0-1 year", "junior"):
        seniority = "Entry-level"

    must_haves = []
    for line in jd_text.splitlines():
        line = line.strip("-• \t")
        if not line:
            continue
        if any(t in line.lower() for t in ("required", "must have", "must-have")):
            must_haves.append(line[:140])
    if not must_haves:
        must_haves = keywords[:5]

    return {
        "skills": keywords[:10],
        "seniority": seniority,
        "must_haves": must_haves[:6],
        "keywords": keywords,
    }


def extract_requirements(jd_text: str) -> tuple[dict, bool]:
    """Returns (requirements_json, used_live_llm)."""
    prompt = f"""You are an expert technical recruiter. Read the job description below
and return ONLY a JSON object (no markdown, no commentary) with this exact shape:

{{
  "skills": ["list of specific technical/professional skills mentioned or implied"],
  "seniority": "Entry-level | Mid-level | Senior (pick the single best fit)",
  "must_haves": ["short list of explicitly required, non-negotiable qualifications"],
  "keywords": ["concrete, resume-matchable terms (tools, languages, frameworks, methods, domains), ranked by importance; NO soft skills such as communication, teamwork or problem solving"]
}}

JOB DESCRIPTION:
\"\"\"{jd_text}\"\"\"
"""
    result, live = call_json(prompt, mock_fn=lambda: _mock_extract(jd_text), agent="researcher")
    result.setdefault("skills", [])
    result.setdefault("seniority", "Mid-level")
    result.setdefault("must_haves", [])
    result.setdefault("keywords", [])
    return result, live
