"""
Job recommendations: rank live listings by how many of the candidate's proven
skills they ask for.

Proven skills = the resume's skills section (or its named tech terms when it
has none) plus GitHub languages and topics. Senior-level titles are ranked
down for early-career resumes, matching the pipeline's seniority gate. No LLM,
so recommendations work even when the model quota is used up.
"""
import re

from agent.executor import _claim_tokens
from agent.github_profile import profile_skills
from agent.pipeline import _EARLY_CAREER

_SECTION_HEADER = re.compile(r"^[A-Z][A-Z &/]{2,}$")
_SKILLS_HEADER = re.compile(r"^(technical\s+)?skills?\b[^:]*:?\s*(.*)$", re.I)
_QUALIFIER = re.compile(r"^(basic|advanced|intermediate|proficient in|familiar with|experienced in)\s+", re.I)
_SENIOR_TITLE = re.compile(r"\b(senior|sr\.?|staff|principal|lead|head|director|manager)\b", re.I)


def resume_skills(resume_text: str) -> list[str]:
    """Skills listed under a Skills heading (or inline "Skills: ..."), else the resume's named tech terms."""
    skills, in_section = [], False
    for raw in resume_text.splitlines():
        line = raw.strip()
        header = _SKILLS_HEADER.match(line)
        if header:
            in_section, line = True, header.group(2)
        elif _SECTION_HEADER.match(line):
            in_section = False
            continue
        if in_section and line:
            for part in re.split(r"[,;|•()]", line):
                skill = _QUALIFIER.sub("", part.strip())
                if 1 < len(skill) <= 30:
                    skills.append(skill)
    if not skills:
        skills = sorted(_claim_tokens(resume_text))
    return list(dict.fromkeys(skills))


def _mentions(skill: str, text_lower: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(skill.lower())}(?![a-z0-9])", text_lower) is not None


def recommend(resume_text: str, jobs: list[dict], github_profile: dict | None = None, limit: int = 10) -> list[dict]:
    skills = resume_skills(resume_text)
    known = {s.lower() for s in skills}
    github = [s for s in (profile_skills(github_profile) if github_profile else []) if s.lower() not in known]
    early_career = bool(_EARLY_CAREER.search(resume_text))

    ranked = []
    for job in jobs:
        text = f"{job.get('title', '')} {' '.join(job.get('tags') or [])} {job.get('description', '')}".lower()
        matched = [s for s in skills if _mentions(s, text)]
        from_github = [s for s in github if _mentions(s, text)]
        if not matched and not from_github:
            continue
        senior = early_career and bool(_SENIOR_TITLE.search(job.get("title", "")))
        # ponytail: skill-count score; weight by how central a skill is to the posting if rankings feel off
        score = (len(matched) + 0.5 * len(from_github)) * (0.4 if senior else 1.0)
        ranked.append({**job, "match_score": round(score, 2), "matched_skills": matched,
                       "github_skills": from_github, "senior_role": senior})
    ranked.sort(key=lambda j: -j["match_score"])
    return ranked[:limit]


if __name__ == "__main__":
    resume = "Jordan Rivera\nFinal-year student\nSKILLS\nPython, FastAPI, PostgreSQL, basic Kubernetes,\nAWS (EC2, S3)\nEDUCATION\nB.S. CS"
    assert resume_skills(resume) == ["Python", "FastAPI", "PostgreSQL", "Kubernetes", "AWS", "EC2", "S3"], resume_skills(resume)
    assert resume_skills("Skills: Go, Rust") == ["Go", "Rust"]
    jobs = [
        {"title": "Senior Backend Engineer", "tags": [], "description": "Python FastAPI PostgreSQL Kubernetes AWS"},
        {"title": "Backend Intern", "tags": ["python"], "description": "FastAPI and PostgreSQL, some Terraform"},
        {"title": "Designer", "tags": [], "description": "Figma"},
    ]
    gh = {"repos": [{"name": "infra", "url": "u", "language": "HCL", "topics": ["terraform"], "description": "", "readme": ""}]}
    ranked = recommend(resume, jobs, gh)
    assert [j["title"] for j in ranked] == ["Backend Intern", "Senior Backend Engineer"], ranked  # senior down-ranked, designer dropped
    assert ranked[0]["github_skills"] == ["terraform"] and ranked[1]["senior_role"]
    print("recommend self-check passed")
