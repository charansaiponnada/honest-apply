"""
Orchestrates the 3-agent pipeline and logs every run for evaluation.

  Researcher -> Tailor -> Executor
                          ├─ review: receipts check (code) + fit review (LLM)
                          └─ act:    gates in code, then the LLM picks app tools

Apps the agent acts in: Gmail, Google Calendar, HubSpot CRM, Slack.
Hard gates (code, never the LLM): keyword guardrail, receipts/faithfulness,
seniority mismatch, duplicate application. Any gate failing -> no Gmail/Calendar/CRM, and
Slack is told why (with the skills gap). Slack fires on every run.

progress_cb(event: dict) receives live events for the UI stream:
  {"type": "step", "step": "researcher"|"tailor"|"executor", "status": ...}
  {"type": "tool", "app": "gmail"|..., "status": ..., "detail": ...}
  {"type": "fault", "names": [...]}
"""
import json
import os
import re
import uuid
from datetime import datetime

from agent.calendar_action import create_followup_event
from agent.composio_client import connected_apps
from agent.crm_action import candidate_from_resume, log_application
from agent.executor import choose_tools, execute_review
from agent.extract import extract_requirements
from agent.github_profile import evidence_section, fetch_profile, verified_skills
from agent.gmail_action import create_draft
from agent.google_auth import is_live as google_is_live
from agent.guardrail import score_overlap
from agent.slack_action import notify_run_result
from agent.tailor import resume_lines, tailor_application
from agent.utils import FAULTS

EVAL_LOG_PATH = os.path.join("eval", "logs", "eval_log.json")


def load_eval_log() -> list[dict]:
    if not os.path.exists(EVAL_LOG_PATH):
        return []
    try:
        return json.loads(open(EVAL_LOG_PATH, encoding="utf-8").read())
    except json.JSONDecodeError:
        return []


def save_eval_log(entries: list[dict]) -> None:
    os.makedirs(os.path.dirname(EVAL_LOG_PATH), exist_ok=True)
    with open(EVAL_LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)


def _norm(text: str) -> str:
    return re.sub(r"\W+", " ", text).strip().lower()


def already_applied(company: str, role: str, entries: list[dict]) -> bool:
    # ponytail: dedup against the local run log; read the tracking Sheet when used from several machines
    key = (_norm(company), _norm(role))
    return any(
        (_norm(e.get("company", "")), _norm(e.get("role", ""))) == key
        and e.get("outcome") in ("sent", "drafted")
        and not e.get("undone")
        for e in entries
    )


def _gap_report(resume_text: str, requirements: dict, guardrail: dict, verdict: dict) -> dict:
    resume_lower = resume_text.lower()
    # ponytail: exact-phrase check on short must-haves only; long sentence-style must-haves need LLM matching
    missing_must_haves = [
        m for m in requirements.get("must_haves", [])
        if len(m.split()) <= 4 and m.lower() not in resume_lower
    ]
    return {
        "missing_must_haves": missing_must_haves,
        "missing_keywords": guardrail.get("missing", []),
        "unsupported_claims": verdict.get("unsupported_claims", []),
    }


_EARLY_CAREER = re.compile(r"\b(student|intern|internship|new grad|undergraduate|expected (19|20)\d\d)\b", re.I)


def _seniority_gap(resume_text: str, requirements: dict) -> str | None:
    # ponytail: regex read of the candidate's level; LLM-judged experience if it misfires on career changers
    if requirements.get("seniority") == "Senior" and _EARLY_CAREER.search(resume_text):
        return "This job is senior-level and the resume reads as student / early-career"
    return None


def run_pipeline(resume_text: str, jd_text: str, company: str, role: str,
                 jd_source: str = "pasted text", recipient: str = "", allow_send: bool = False, dedup: bool = True,
                 user_id: str = "", slack_channel: str = "", github_username: str = "",
                 progress_cb=None) -> dict:
    def emit(**event):
        if progress_cb:
            progress_cb(event)

    run_id = uuid.uuid4().hex[:8]
    candidate = candidate_from_resume(resume_text)
    # Apps this user connected through Composio run on their own accounts; the rest use .env or mock.
    connected = connected_apps(user_id)

    def via(app: str) -> str:
        return user_id if app in connected else ""
    started_at = datetime.now().isoformat(timespec="seconds")
    faults = sorted(FAULTS)
    if faults:
        emit(type="fault", names=faults)

    # Agent 1: Researcher
    emit(type="step", step="researcher", status="running")
    requirements, extract_live = extract_requirements(jd_text)
    emit(type="step", step="researcher", status="done")

    # GitHub as a second source of proof: job skills the resume lacks but public repos show are
    # added as a labeled section naming the repos, so receipts treat them as backed, never invented.
    github = {"username": github_username, "verified": [], "error": None}
    if github_username:
        profile = fetch_profile(github_username)
        github["error"] = profile["error"]
        github["verified"] = verified_skills(requirements.get("keywords", []) + requirements.get("skills", []),
                                             resume_text, profile)
        section = evidence_section(github["verified"])
        if section:
            resume_text = f"{resume_text.rstrip()}\n\n{section}"
        emit(type="github", verified=[v["skill"] for v in github["verified"]], error=github["error"])

    # Agent 2: Tailor
    emit(type="step", step="tailor", status="running")
    tailoring, tailor_live = tailor_application(resume_text, requirements)
    emit(type="step", step="tailor", status="done")

    # Agent 3: Executor — review
    emit(type="step", step="executor", status="reviewing")
    guardrail = score_overlap(resume_text, requirements)
    verdict, review_live = execute_review(resume_text, tailoring, requirements, guardrail, company, role)
    dedup_hit = dedup and already_applied(company, role, load_eval_log())
    seniority_gap = _seniority_gap(resume_text, requirements)
    blocked = guardrail["needs_review"] or not verdict["faithful"] or dedup_hit or bool(seniority_gap)
    gap_report = _gap_report(resume_text, requirements, guardrail, verdict)
    gap_report["seniority"] = seniority_gap

    # Agent 3: Executor — act
    emit(type="step", step="executor", status="acting")
    if blocked:
        chosen, executor_mode = [], "gated"
    else:
        chosen, by_llm = choose_tools(requirements, guardrail, verdict, company, role)
        executor_mode = "tool-calling" if by_llm else "deterministic"

    can_send = (
        allow_send and bool(recipient) and ("gmail" in connected or google_is_live())
        and guardrail["auto_send_eligible"] and verdict["faithful"]
        and verdict["recommendation"] == "proceed"
    )

    actions, refs = {}, {}

    def act(app: str, fn) -> None:
        emit(type="tool", app=app, status="running")
        res = fn()
        actions[app], refs[app] = res, res.get("ref")
        emit(type="tool", app=app, status=res["status"], detail=res["detail"])

    # The apps chain: Gmail's link goes into the Calendar reminder, both links go
    # onto the CRM deal, and Slack gets all three — one hand-off, not four silos.
    if "create_gmail_draft" in chosen:
        act("gmail", lambda: create_draft(company, role, tailoring["cover_note"], tailoring["tailored_resume"],
                                          to_addr=recipient, auto_send=can_send, user_id=via("gmail")))
    email_link = actions.get("gmail", {}).get("link")
    if "schedule_followup" in chosen:
        act("calendar", lambda: create_followup_event(company, role, email_link=email_link, user_id=via("calendar")))
    if "log_crm_deal" in chosen:
        stage = "sent" if actions.get("gmail", {}).get("sent") else "drafted"
        links = {"email": email_link, "follow_up": actions.get("calendar", {}).get("link")}
        act("crm", lambda: log_application(company, role, candidate, jd_source, stage, links=links, user_id=via("crm")))

    if dedup_hit:
        outcome = "duplicate"
    elif blocked:
        outcome = "flagged"
    elif any(a["status"] == "error" for a in actions.values()):
        outcome = "partial"  # not counted by dedup, so the user can simply re-run
    else:
        outcome = "sent" if actions.get("gmail", {}).get("sent") else "drafted"

    gaps = [f"unsupported claim: {c}" for c in gap_report["unsupported_claims"]]
    gaps = ([seniority_gap] if seniority_gap else []) + gaps + gap_report["missing_must_haves"] + gap_report["missing_keywords"]
    act("slack", lambda: notify_run_result(company, role, outcome, guardrail["score"], actions, gaps=gaps,
                                           user_id=via("slack"), channel=slack_channel))
    emit(type="step", step="executor", status=outcome)

    passed = outcome in ("flagged", "duplicate") or all(
        a["status"] in ("ok", "mocked") for k, a in actions.items() if k != "slack"
    )
    used_live_llm = extract_live and tailor_live and review_live
    llm_live = {"researcher": extract_live, "tailor": tailor_live, "executor": review_live}

    result = {
        "run_id": run_id,
        "started_at": started_at,
        "company": company,
        "role": role,
        "jd_source": jd_source,
        "requirements": requirements,
        "candidate": candidate["name"],
        "resume_lines": resume_lines(resume_text),
        "github": github,
        "llm_live": llm_live,
        "composio_apps": sorted(connected),
        "tailored_resume": tailoring["tailored_resume"],
        "cover_note": tailoring["cover_note"],
        "guardrail": guardrail,
        "executor_verdict": verdict,
        "executor_mode": executor_mode,
        "gap_report": gap_report,
        "dedup_hit": dedup_hit,
        "outcome": outcome,
        "actions": actions,
        "faults": faults,
        "used_live_llm": used_live_llm,
        "passed": passed,
    }

    entries = load_eval_log()
    entries.append({
        "run_id": run_id,
        "started_at": started_at,
        "company": company,
        "role": role,
        "jd_source": jd_source,
        "recipient": recipient,
        "user_id": user_id,
        "slack_channel": slack_channel,
        "github": github,
        "llm_live": llm_live,
        "composio_apps": sorted(connected),
        "candidate": candidate["name"],
        "requirements": requirements,
        "guardrail": guardrail,
        "executor_verdict": {k: v for k, v in verdict.items() if k != "receipts"},
        "executor_mode": executor_mode,
        "gap_report": gap_report,
        "dedup_hit": dedup_hit,
        "outcome": outcome,
        "actions": {k: {"status": v["status"], "detail": v["detail"], "sent": v.get("sent", False)} for k, v in actions.items()},
        "refs": refs,
        "faults": faults,
        "used_live_llm": used_live_llm,
        "passed": passed,
        "undone": False,
    })
    save_eval_log(entries)
    return result
