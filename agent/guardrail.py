"""
Skill 3 (Reliability Layer): Confidence / Guardrail check.

Simple, transparent keyword-overlap scoring between the resume and the
extracted JD requirements, with two thresholds:

  GUARDRAIL_THRESHOLD (default 0.40)   below this -> needs_review=True,
      which short-circuits the multi-app action layer entirely (no draft,
      no tracking row, no calendar event, no Drive save — just a Slack
      notification so a human knows it was flagged).

  AUTO_SEND_THRESHOLD (default 0.70)   at or above this -> auto_send_eligible
      = True, meaning the Gmail skill is allowed to actually SEND the
      drafted application instead of leaving it as a draft for a human to
      review and send themselves. This is intentionally a stricter, second
      gate on top of GUARDRAIL_THRESHOLD, not a replacement for it: every
      auto-sent application already cleared the normal guardrail AND a
      materially higher bar on top of it.
"""
import os
import re

DEFAULT_THRESHOLD = 0.40
DEFAULT_AUTO_SEND_THRESHOLD = 0.70


def _threshold() -> float:
    try:
        return float(os.getenv("GUARDRAIL_THRESHOLD", DEFAULT_THRESHOLD))
    except ValueError:
        return DEFAULT_THRESHOLD


def _auto_send_threshold() -> float:
    try:
        return float(os.getenv("AUTO_SEND_THRESHOLD", DEFAULT_AUTO_SEND_THRESHOLD))
    except ValueError:
        return DEFAULT_AUTO_SEND_THRESHOLD


def score_overlap(resume_text: str, requirements: dict) -> dict:
    """
    Returns {score, needs_review, threshold, auto_send_threshold,
    auto_send_eligible, matched, missing}.
    """
    resume_lower = resume_text.lower()
    keywords = [k.strip().lower() for k in requirements.get("keywords", []) if k.strip()]
    if not keywords:
        keywords = [k.strip().lower() for k in requirements.get("skills", []) if k.strip()]

    threshold = _threshold()
    auto_send_threshold = _auto_send_threshold()

    if not keywords:
        return {
            "score": 0.0,
            "needs_review": True,
            "threshold": threshold,
            "auto_send_threshold": auto_send_threshold,
            "auto_send_eligible": False,
            "matched": [],
            "missing": [],
        }

    matched, missing = [], []
    for kw in keywords:
        # word-boundary-ish match so "go" doesn't match "going"
        pattern = re.escape(kw)
        if re.search(rf"\b{pattern}\b", resume_lower):
            matched.append(kw)
        else:
            missing.append(kw)

    score = round(len(matched) / len(keywords), 3)
    needs_review = score < threshold
    auto_send_eligible = (not needs_review) and score >= auto_send_threshold

    return {
        "score": score,
        "needs_review": needs_review,
        "threshold": threshold,
        "auto_send_threshold": auto_send_threshold,
        "auto_send_eligible": auto_send_eligible,
        "matched": matched,
        "missing": missing,
    }
