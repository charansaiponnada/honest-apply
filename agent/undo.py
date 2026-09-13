"""
One-click undo: reverse everything a run did across the apps.

Uses the refs each action stored in the run log: deletes the Gmail draft,
deletes the Calendar follow-up, moves the CRM deal to closed-lost (kept, not
deleted, so the pipeline history stays honest), and tells Slack. A sent email
can't be recalled, and undo says so rather than pretending. Each app is undone
independently, so one failure doesn't stop the others.
"""
from agent.calendar_action import undo_event
from agent.crm_action import undo_deal
from agent.gmail_action import undo_draft
from agent.pipeline import load_eval_log, save_eval_log
from agent.slack_action import send_text
from agent.utils import classify_google_error

_UNDOERS = (("gmail", undo_draft), ("calendar", undo_event), ("crm", undo_deal))


def undo_run(run_id: str) -> dict | None:
    """Returns {"run_id", "already_undone", "results"}, or None if the run doesn't exist."""
    entries = load_eval_log()
    entry = next((e for e in entries if e.get("run_id") == run_id), None)
    if entry is None:
        return None
    if entry.get("undone"):
        return {"run_id": run_id, "already_undone": True, "results": entry.get("undo_results", {})}

    refs = entry.get("refs") or {}
    results = {}
    for app, undo in _UNDOERS:
        if not refs.get(app):
            continue
        if app == "calendar" and entry.get("replied"):
            results[app] = {"status": "skipped", "detail": "Follow-up was already cancelled when the reply came in."}
            continue
        try:
            results[app] = undo(refs[app])
        except Exception as exc:  # noqa: BLE001 - one app's undo failing shouldn't stop the rest
            results[app] = {"status": "error", "detail": f"Undo failed: {classify_google_error(exc)}"}

    summary = "; ".join(f"{app}: {r['status']}" for app, r in results.items()) or "nothing to undo"
    slack_user = entry.get("user_id", "") if "slack" in (entry.get("composio_apps") or []) else ""
    results["slack"] = send_text(f":leftwards_arrow_with_hook: *Undone* — {entry['role']} @ {entry['company']} ({summary})",
                                 user_id=slack_user, channel=entry.get("slack_channel", ""))

    entry["undone"] = True
    entry["undo_results"] = results
    save_eval_log(entries)
    return {"run_id": run_id, "already_undone": False, "results": results}
