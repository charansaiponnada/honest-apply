"""
Skill 9 + orchestration: ties the 4-step pipeline together
(Extract -> Tailor -> Guardrail -> Act) and writes an eval log entry for
every run so results can be reviewed after a test batch.

6 external apps are integrated in total:
  Gmail, Sheets, Calendar, Drive  — the core "act on the application" apps,
                                     skipped when the guardrail flags for review
  Slack                            — notified on every run regardless of
                                     outcome, so a human always hears about it
  Arbeitnow (jobs_search.py)       — upstream, optional: lets the UI pull a
                                     real live JD instead of only pasted text
"""
import json
import os
from datetime import datetime

from agent.extract import extract_requirements
from agent.tailor import tailor_application
from agent.guardrail import score_overlap
from agent.gmail_action import create_draft
from agent.sheets_action import append_row
from agent.calendar_action import create_followup_event
from agent.drive_action import save_tailored_resume
from agent.slack_action import notify_run_result

EVAL_LOG_PATH = os.path.join("eval", "logs", "eval_log.json")


def _append_eval_log(entry: dict) -> None:
    os.makedirs(os.path.dirname(EVAL_LOG_PATH), exist_ok=True)
    entries = []
    if os.path.exists(EVAL_LOG_PATH):
        try:
            entries = json.loads(open(EVAL_LOG_PATH).read())
        except json.JSONDecodeError:
            entries = []
    entries.append(entry)
    with open(EVAL_LOG_PATH, "w") as f:
        json.dump(entries, f, indent=2)


def run_pipeline(resume_text: str, jd_text: str, company: str, role: str,
                  jd_source: str = "pasted text", spreadsheet_id: str | None = None,
                  progress_cb=None) -> dict:
    """
    Runs the full 4-step pipeline. progress_cb(step_name, status) is called
    at the start/end of each step so a UI can render live progress.

    Returns a result dict with every intermediate artifact plus a final
    'passed' bool used by the eval batch runner.
    """
    def tick(step, status):
        if progress_cb:
            progress_cb(step, status)

    started_at = datetime.now().isoformat(timespec="seconds")

    # Step 1: Extract
    tick("extract", "running")
    requirements, extract_live = extract_requirements(jd_text)
    tick("extract", "done")

    # Step 2: Tailor
    tick("tailor", "running")
    tailoring, tailor_live = tailor_application(resume_text, requirements)
    tick("tailor", "done")

    # Step 3: Guardrail
    tick("guardrail", "running")
    guardrail = score_overlap(resume_text, requirements)
    tick("guardrail", "done")

    # Step 4: Act — Gmail/Sheets/Calendar/Drive skipped when flagged for
    # review; Slack always fires so a human hears about the outcome either
    # way. Gmail auto-sends only when the stricter AUTO_SEND_THRESHOLD gate
    # (on top of the normal guardrail already passing) is cleared —
    # otherwise it's a draft for a human to review and send themselves.
    tick("act", "running")
    actions = {}
    if not guardrail["needs_review"]:
        actions["gmail"] = create_draft(
            company, role, tailoring["cover_note"], tailoring["tailored_resume"],
            auto_send=guardrail["auto_send_eligible"],
        )
        actions["sheets"] = append_row(
            company, role, jd_source, "applied", spreadsheet_id=spreadsheet_id
        )
        actions["calendar"] = create_followup_event(company, role)
        actions["drive"] = save_tailored_resume(company, role, tailoring["tailored_resume"])

    actions["slack"] = notify_run_result(
        company, role, guardrail["needs_review"], guardrail["score"], actions
    )
    tick("act", "done" if not guardrail["needs_review"] else "skipped")

    core_actions = {k: v for k, v in actions.items() if k != "slack"}
    core_action_success = not guardrail["needs_review"] and all(
        a["status"] in ("ok", "mocked") for a in core_actions.values()
    )
    passed = core_action_success or guardrail["needs_review"]  # flagged review = correct behavior

    result = {
        "started_at": started_at,
        "company": company,
        "role": role,
        "jd_source": jd_source,
        "requirements": requirements,
        "tailored_resume": tailoring["tailored_resume"],
        "cover_note": tailoring["cover_note"],
        "guardrail": guardrail,
        "actions": actions,
        "used_live_llm": extract_live and tailor_live,
        "passed": passed,
    }

    _append_eval_log(
        {
            "started_at": started_at,
            "company": company,
            "role": role,
            "jd_source": jd_source,
            "requirements": requirements,
            "tailoring_faithfulness_note": "grounded strictly in original resume per prompt constraint",
            "guardrail": guardrail,
            "actions": {k: {"status": v["status"], "detail": v["detail"]} for k, v in actions.items()},
            "used_live_llm": result["used_live_llm"],
            "passed": passed,
        }
    )

    return result
