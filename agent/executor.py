"""
Agent 3: Executor — reviews the tailored application, then acts on it.

Step 1, review:
  - Receipts check (code, authoritative): every tailored line must trace to
    a line of the original resume, and every named thing in it (tools,
    employers, numbers) must appear in the original resume. Same token check
    on the cover note. Any failure -> faithful=False, which blocks all app
    actions.
  - Fit review (LLM, advisory): proceed vs. review with a short reason, plus
    any unsupported claims the model spots on its own (shown, not gating).

Step 2, act:
  - choose_tools() lets the LLM pick which app tools to call via function
    calling. It is only offered tools once every hard gate (guardrail,
    receipts, dedup) has already passed in pipeline.py, so the model can do
    less, never bypass a gate. No live decision -> deterministic dispatch.
"""
import json
import re
from difflib import SequenceMatcher, get_close_matches

from agent.llm import call_json, call_tools
from agent.tailor import resume_lines

# ponytail: difflib line similarity; embeddings if legit paraphrases get falsely blocked
_LINE_CUTOFF = 0.3
# "/" and "-" split words, so "FastAPI-powered" and "React/TypeScript" are checked as their parts
_WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9+#.%&]*")
_SENTENCE_BREAKS = {"", ".", "!", "?", ":", ";", "-", "•", "–", "—", "(", "|", '"'}


def _claim_tokens(text: str) -> set[str]:
    """Named things a line asserts: numbers, mid-sentence capitalized words, and
    mixed-case tech names (FastAPI, PostgreSQL) — the stuff fabrication adds."""
    tokens = set()
    for match in _WORD.finditer(text):
        word = match.group().rstrip(".&")
        if len(word) < 2:
            continue
        sentence_start = text[: match.start()].rstrip()[-1:] in _SENTENCE_BREAKS
        if (
            any(c.isdigit() for c in word)
            or any(c.isupper() for c in word[1:])
            or (word[0].isupper() and not sentence_start)
        ):
            tokens.add(word.lower())
    return tokens


def _in_text(token: str, text_lower: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])", text_lower) is not None


def check_receipts(original_resume: str, tailoring: dict, exclude=()) -> tuple[list[dict], list[str]]:
    """
    Returns (receipts, unsupported).
    receipts: one {"tailored", "source_line", "supported", "reason"} per tailored line.
    unsupported: human-readable descriptions of every claim that failed.
    `exclude` holds phrases allowed to appear without a receipt (company, role).
    """
    src = resume_lines(original_resume)
    src_lower = [s.lower() for s in src]  # match case-insensitively: "Education" is the "EDUCATION" line
    original_lower = original_resume.lower()
    excluded = {w.lower() for phrase in exclude for w in _WORD.findall(phrase or "")}

    cited = {}
    for entry in tailoring.get("evidence") or []:
        if not isinstance(entry, dict):
            continue
        idx = entry.get("source_line")
        if isinstance(idx, int) and 0 <= idx < len(src):
            cited[str(entry.get("tailored", "")).strip()] = idx

    def missing_tokens(text: str) -> list[str]:
        return sorted(t for t in _claim_tokens(text) if t not in excluded and not _in_text(t, original_lower))

    receipts, unsupported = [], []
    for line in resume_lines(tailoring.get("tailored_resume", "")):
        idx = cited.get(line)
        if idx is None or SequenceMatcher(None, line.lower(), src_lower[idx]).ratio() < _LINE_CUTOFF:
            close = get_close_matches(line.lower(), src_lower, n=1, cutoff=_LINE_CUTOFF)
            idx = src_lower.index(close[0]) if close else None
        missing = missing_tokens(line)
        if idx is None:
            reason = "no matching line in the original resume"
        elif missing:
            reason = "not in original resume: " + ", ".join(missing)
        else:
            reason = ""
        receipts.append({"tailored": line, "source_line": idx, "supported": not reason, "reason": reason})
        if reason:
            unsupported.append(f"{line} ({reason})")

    cover_missing = missing_tokens(tailoring.get("cover_note", ""))
    if cover_missing:
        unsupported.append("Cover note mentions " + ", ".join(cover_missing) + " (not in original resume)")
    return receipts, unsupported


def _mock_review(guardrail: dict) -> dict:
    if guardrail.get("needs_review"):
        return {
            "recommendation": "review",
            "confidence": min(0.3, guardrail.get("score", 0.0)),
            "reason": "Rule guardrail flagged low keyword overlap.",
        }
    return {
        "recommendation": "proceed",
        "confidence": guardrail.get("score", 0.0),
        "reason": "Rule guardrail cleared; match on extracted requirements.",
    }


def execute_review(original_resume: str, tailoring: dict, requirements: dict, guardrail: dict,
                   company: str = "", role: str = "") -> tuple[dict, bool]:
    """Returns (verdict, used_live_llm). verdict = {recommendation, confidence,
    reason, faithful, unsupported_claims, receipts, llm_flags}."""
    receipts, unsupported = check_receipts(original_resume, tailoring, exclude=(company, role))

    prompt = f"""Review this tailored job application before it is dispatched to external apps.
Return ONLY a JSON object of this exact shape:
{{
  "recommendation": "proceed" | "review",
  "confidence": 0.0,
  "reason": "one short sentence",
  "unsupported_claims": ["claims in the tailored resume or cover note the original resume does not support"]
}}
- "proceed" only if the tailored resume covers the core requirements AND every claim is backed by the original resume.
- "review" if core requirements are missing, the fit is weak, or anything was invented.
- confidence is a 0.0-1.0 number reflecting how sure you are.

JOB REQUIREMENTS:
{json.dumps(requirements)}

ORIGINAL RESUME:
\"\"\"{original_resume}\"\"\"

TAILORED RESUME:
\"\"\"{tailoring.get("tailored_resume", "")}\"\"\"

COVER NOTE:
\"\"\"{tailoring.get("cover_note", "")}\"\"\"
"""
    result, live = call_json(prompt, mock_fn=lambda: _mock_review(guardrail), agent="executor")

    recommendation = result.get("recommendation")
    if recommendation not in ("proceed", "review"):
        recommendation = "review" if guardrail.get("needs_review") else "proceed"
    try:
        confidence = float(result.get("confidence", guardrail.get("score", 0.0)))
    except (TypeError, ValueError):
        confidence = guardrail.get("score", 0.0)
    reason = str(result.get("reason", ""))
    if unsupported:
        recommendation = "review"
        reason = f"Receipts check blocked {len(unsupported)} unsupported claim(s). {reason}".strip()
    llm_flags = result.get("unsupported_claims")

    return {
        "recommendation": recommendation,
        "confidence": confidence,
        "reason": reason,
        "faithful": not unsupported,
        "unsupported_claims": unsupported,
        "receipts": receipts,
        "llm_flags": llm_flags if isinstance(llm_flags, list) else [],
    }, live


DISPATCH_TOOLS = ("create_gmail_draft", "schedule_followup", "log_crm_deal")

_TOOLS = [
    {
        "type": "function",
        "function": {"name": name, "description": desc, "parameters": {"type": "object", "properties": {}}},
    }
    for name, desc in (
        ("create_gmail_draft", "Gmail: create the application email with the cover note and tailored resume attached."),
        ("log_crm_deal", "HubSpot CRM: record this application as a deal linked to the employer and the candidate."),
        ("schedule_followup", "Google Calendar: schedule a follow-up reminder 7 days from today."),
    )
]


def choose_tools(requirements: dict, guardrail: dict, verdict: dict, company: str, role: str) -> tuple[list[str], bool]:
    """Only called after every hard gate passed. Returns (tool names, chosen_by_llm).
    Slack is not offered — pipeline.py always notifies Slack itself."""
    prompt = f"""This application passed every safety gate. Decide which app tools to call for it.
Call every tool that should run (one at a time is fine; keep going until all that apply are called, then stop).
Skip a tool only if the job details make it pointless
(for example, no follow-up reminder if the posting says not to contact the team).

Company: {company}
Role: {role}
Seniority: {requirements.get("seniority", "?")}
Keyword overlap: {guardrail.get("score", 0.0) * 100:.0f}%
Your review: {verdict.get("recommendation")} — {verdict.get("reason")}
Must-haves: {json.dumps(requirements.get("must_haves", []))}
"""
    calls, live = call_tools(prompt, _TOOLS, agent="executor")
    names = [c["name"] for c in calls if c["name"] in DISPATCH_TOOLS]
    if not names:  # not live, tools unsupported, or the model called nothing
        return list(DISPATCH_TOOLS), False
    return [n for n in DISPATCH_TOOLS if n in names], True


if __name__ == "__main__":
    original = (
        "Jordan Rivera\nSKILLS\nPython, FastAPI, basic Kubernetes\n"
        "- Built REST APIs in Python using FastAPI"
    )
    honest = {
        "tailored_resume": "- Built REST APIs using Python and FastAPI\nSKILLS\nPython, FastAPI, basic Kubernetes",
        "evidence": [],
        "cover_note": "I build APIs with FastAPI and Python for Northstar.",
    }
    _, bad = check_receipts(original, honest, exclude=("Northstar", "Backend Engineer"))
    assert not bad, bad

    fabricated = dict(honest, tailored_resume=honest["tailored_resume"] + "\n- Led a Terraform migration at Google, cutting costs 40%")
    _, bad = check_receipts(original, fabricated)
    assert bad and "terraform" in bad[0].lower(), bad

    padded_note = dict(honest, cover_note="I have 5 years of AWS experience.")
    _, bad = check_receipts(original, padded_note)
    assert bad and "aws" in bad[-1].lower(), bad

    # a heading that only changed case still has a receipt
    _, bad = check_receipts("SUMMARY\nEDUCATION\nB.S. Computer Science", {"tailored_resume": "Education\nSummary", "evidence": [], "cover_note": ""})
    assert not bad, bad

    # compound words are checked by their parts: real skills pass, an invented part still fails
    stack = "Campus Marketplace (React, TypeScript, Node.js)\nStudy Buddy Bot (Python, FastAPI)\nCI/CD (GitHub Actions)"
    joined = {"tailored_resume": stack, "evidence": [], "cover_note": "My FastAPI-powered bot and React/TypeScript app use CI/CD."}
    _, bad = check_receipts(stack, joined)
    assert not bad, bad
    _, bad = check_receipts(stack, dict(joined, cover_note="My FastAPI-powered Kafka/React pipeline."))
    assert bad and "kafka" in bad[-1].lower(), bad
    print("executor receipts self-check passed")
