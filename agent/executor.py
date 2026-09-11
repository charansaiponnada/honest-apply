"""
Agent 3: Executor — independent fit review before dispatching to external apps.

The rule-based guardrail (guardrail.py) stays the hard reliability gate;
the Executor is an LLM second opinion that reviews the tailored application
against the extracted requirements and decides proceed vs. human review.
Its verdict is advisory and surfaced in the UI / eval log.

Mock fallback mirrors the rule gate's outcome so an offline demo behaves
identically to the live path.
"""
from agent.llm import call_json


def _mock_execute(resume_text: str, requirements: dict, guardrail: dict) -> dict:
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


def execute_review(resume_text: str, requirements: dict, guardrail: dict) -> tuple[dict, bool]:
    """Returns (verdict, used_live_llm). verdict = {recommendation,
    confidence, reason}."""
    prompt = f"""You are the final quality gate before an application is dispatched to
external apps (Gmail, Sheets, Calendar, Drive). The two agents before you have:
  1) extracted the job's true requirements from its description, and
  2) tailored the candidate's resume against them.

Review the match quality yourself and return ONLY a JSON object (no markdown,
no commentary) of this exact shape:
{{
  "recommendation": "proceed" | "review",
  "confidence": 0.0,
  "reason": "one short sentence"
}}
- "proceed" only if the tailored resume actually covers the core requirements.
- "review" if core requirements are missing or the fit is weak.
- confidence is a 0.0-1.0 number reflecting how sure you are.

JOB REQUIREMENTS:
{requirements}

CANDIDATE RESUME:
\"\"\"{resume_text}\"\"\"
"""
    result, live = call_json(
        prompt,
        mock_fn=lambda: _mock_execute(resume_text, requirements, guardrail),
        agent="executor",
    )
    result.setdefault("recommendation", "review" if guardrail.get("needs_review") else "proceed")
    result.setdefault("confidence", guardrail.get("score", 0.0))
    result.setdefault("reason", "")
    return result, live