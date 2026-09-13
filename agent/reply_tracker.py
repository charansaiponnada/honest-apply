"""
Reply tracker: the loop that makes the four apps work as one system.

For every application still waiting on an answer, look in Gmail for a reply
from the recipient. When one has arrived:
  CRM      -> the HubSpot deal moves to the "replied" stage
  Calendar -> the 7-day follow-up reminder is deleted (no need to chase)
  Slack    -> heads-up with a link straight to the reply

Each run is checked through the Gmail it was sent from: the user's Composio
connection, else the .env OAuth credentials. A live check needs a sent email
with a recipient (a draft can't be replied to). Simulated runs, and runs marked
with "Simulate reply" (eval/logs/mock_replies.json), complete the loop without
Gmail, and a simulated run's updates stay simulated.
"""
import json
import os
from datetime import datetime

from agent import composio_client as composio
from agent.calendar_action import undo_event
from agent.crm_action import set_deal_stage
from agent.google_auth import get_credentials
from agent.pipeline import load_eval_log, save_eval_log
from agent.slack_action import send_text
from agent.utils import SIMULATED, classify_google_error, is_retryable_google_error, retry_with_backoff

_MOCK_REPLIES = os.path.join("eval", "logs", "mock_replies.json")


def _mock_replied() -> set[str]:
    if not os.path.exists(_MOCK_REPLIES):
        return set()
    try:
        return set(json.loads(open(_MOCK_REPLIES, encoding="utf-8").read()))
    except json.JSONDecodeError:
        return set()


def simulate_reply(run_id: str) -> bool:
    """Mark a run as replied-to in mock mode. Returns False if the run doesn't exist."""
    if not any(e.get("run_id") == run_id for e in load_eval_log()):
        return False
    replied = _mock_replied() | {run_id}
    os.makedirs(os.path.dirname(_MOCK_REPLIES), exist_ok=True)
    with open(_MOCK_REPLIES, "w", encoding="utf-8") as f:
        json.dump(sorted(replied), f)
    return True


def _query(entry: dict) -> str:
    after = datetime.fromisoformat(entry["started_at"]).strftime("%Y/%m/%d")
    return f"from:{entry['recipient']} after:{after}"


def _reply_link(message_id) -> str | None:
    return f"https://mail.google.com/mail/u/0/#inbox/{message_id}" if message_id else None


def _find_composio_reply(user_id: str, entry: dict) -> str | None:
    data = composio.execute(user_id, "GMAIL_FETCH_EMAILS", {"query": _query(entry), "max_results": 1})
    return _reply_link(composio.find(data, "messageId", "id"))


def _find_oauth_reply(service, entry: dict) -> str | None:
    resp = retry_with_backoff(
        lambda: service.users().messages().list(userId="me", q=_query(entry), maxResults=1).execute(),
        retryable_check=is_retryable_google_error,
    )
    messages = resp.get("messages") or []
    return _reply_link(messages[0]["id"] if messages else None)


def _close_loop(entry: dict, link: str | None) -> dict:
    """CRM -> replied, cancel the follow-up, tell Slack. Each app isolated, like undo."""
    refs = entry.get("refs") or {}
    results = {}
    for app, step in (("crm", lambda ref: set_deal_stage(ref, "replied")), ("calendar", undo_event)):
        if not refs.get(app):
            continue
        try:
            results[app] = step(refs[app])
        except Exception as exc:  # noqa: BLE001 - one app failing shouldn't stop the reply loop
            results[app] = {"status": "error", "detail": f"Reply update failed: {classify_google_error(exc)}"}
    text = f":tada: *Reply received* — {entry['role']} @ {entry['company']}. Follow-up reminder cancelled, CRM deal moved to replied."
    if link:
        text += f"\n<{link}|Open the reply>"
    slack_user = entry.get("user_id", "") if "slack" in (entry.get("composio_apps") or []) else ""
    results["slack"] = send_text(text, user_id=slack_user, channel=entry.get("slack_channel", ""))
    return results


def sync_replies(run_id: str | None = None) -> dict:
    """Returns {"mode", "checked", "replies": [{run_id, company, role, link, results} | {run_id, error}]}.
    With run_id, only that run is processed: "Simulate reply" on one run must never act on other pending runs."""
    entries = load_eval_log()
    creds = get_credentials()
    mock_replied = _mock_replied()
    service = None
    checked, any_live, replies = 0, False, []

    for entry in entries:
        if not entry.get("run_id") or entry.get("undone") or entry.get("replied"):
            continue
        if run_id is not None and entry["run_id"] != run_id:
            continue
        simulated_run = bool(entry.get("simulated"))
        marked = entry["run_id"] in mock_replied  # an explicit "Simulate reply" always completes the loop
        gmail_user = entry.get("user_id", "") if "gmail" in (entry.get("composio_apps") or []) and not simulated_run else ""
        live = bool(gmail_user or (creds and not simulated_run)) and not marked
        if entry.get("outcome") not in (("sent",) if live else ("sent", "drafted")):
            continue
        if live and not entry.get("recipient"):
            continue
        checked += 1
        any_live = any_live or live

        try:
            if not live:
                if not marked:
                    continue
                link = None
            elif gmail_user:
                link = _find_composio_reply(gmail_user, entry)
            else:
                if service is None:
                    from googleapiclient.discovery import build

                    service = build("gmail", "v1", credentials=creds)
                link = _find_oauth_reply(service, entry)
            if live and not link:
                continue
        except Exception as exc:  # noqa: BLE001 - one lookup failing shouldn't stop the sync
            replies.append({"run_id": entry["run_id"], "error": classify_google_error(exc)})
            continue

        token = SIMULATED.set(simulated_run)
        try:
            results = _close_loop(entry, link)
        finally:
            SIMULATED.reset(token)

        entry.update(replied=True, reply_link=link, reply_results=results)
        replies.append({"run_id": entry["run_id"], "company": entry["company"], "role": entry["role"],
                        "link": link, "results": results})

    if any(not r.get("error") for r in replies):
        save_eval_log(entries)
    return {"mode": "live" if any_live else "mock", "checked": checked, "replies": replies}
