"""
Google Calendar skill: follow-up reminder 7 days out.

Creates one event titled "Follow up: [company] – [role]" with a link to the
application email. Paths, in order: the user's Composio connection -> .env
OAuth credentials -> local JSON mock. Every result carries a `ref` (event id)
so the run can be undone.
"""
import json
import os
from datetime import datetime, timedelta

from agent import composio_client as composio
from agent.google_auth import get_credentials
from agent.utils import classify_google_error, is_retryable_google_error, maybe_fail, retry_with_backoff

_MOCK_JSON = os.path.join("eval", "logs", "calendar_mock.json")


def _read_mock_events() -> list[dict]:
    if not os.path.exists(_MOCK_JSON):
        return []
    try:
        return json.loads(open(_MOCK_JSON, encoding="utf-8").read())
    except json.JSONDecodeError:
        return []


def _write_mock_events(events: list[dict]) -> None:
    os.makedirs(os.path.dirname(_MOCK_JSON), exist_ok=True)
    with open(_MOCK_JSON, "w", encoding="utf-8") as f:
        json.dump(events, f, indent=2)


def create_followup_event(company: str, role: str, email_link: str | None = None, user_id: str = "") -> dict:
    """Returns {"status": "ok"|"error"|"mocked", "detail", "live", "ref", "link"?}.
    email_link (from the Gmail step) goes in the event, so the reminder opens the application."""
    try:
        retry_with_backoff(lambda: maybe_fail("calendar"), retryable_check=is_retryable_google_error)
    except Exception as exc:  # noqa: BLE001 - chaos panel outage
        return {"status": "error", "detail": f"Calendar event failed: {classify_google_error(exc)}",
                "live": False, "ref": None}

    follow_up_date = (datetime.now() + timedelta(days=7)).date().isoformat()
    title = f"Follow up: {company} – {role}"
    description = f"Follow up on application to {role} at {company}." + (
        f"\nYour application email: {email_link}" if email_link else ""
    )

    if user_id:
        try:
            data = composio.execute(user_id, "GOOGLECALENDAR_CREATE_EVENT", {
                "summary": title,
                "description": description,
                "start_datetime": f"{follow_up_date}T09:00:00",
                "event_duration_hour": 0,
                "event_duration_minutes": 30,
            })
        except Exception as exc:  # noqa: BLE001 - isolate action failures
            return {"status": "error", "detail": f"Calendar event failed (Composio): {exc}", "live": True, "ref": None}
        event_id = composio.find(data, "id")
        return {"status": "ok", "detail": f"Follow-up added to your connected calendar for {follow_up_date}.",
                "live": True, "ref": {"composio_user": user_id, "event_id": event_id}, "link": composio.find(data, "htmlLink")}

    creds = get_credentials()
    if creds is None:
        events = _read_mock_events()
        events.append({"title": title, "date": follow_up_date, "email_link": email_link})
        _write_mock_events(events)
        return {
            "status": "mocked",
            "detail": f"[mock] '{title}' logged for {follow_up_date} (no calendar connected).",
            "live": False,
            "ref": {"mock_title": title, "date": follow_up_date},
        }

    try:
        from googleapiclient.discovery import build

        service = build("calendar", "v3", credentials=creds)
        event = {
            "summary": title,
            "description": description,
            "start": {"date": follow_up_date},
            "end": {"date": follow_up_date},
        }
        created = retry_with_backoff(
            lambda: service.events().insert(calendarId="primary", body=event).execute(),
            retryable_check=is_retryable_google_error,
        )
        return {
            "status": "ok",
            "detail": f"Calendar event created for {follow_up_date} (id: {created.get('id')})",
            "live": True,
            "ref": {"event_id": created.get("id")},
            "link": created.get("htmlLink"),
        }
    except Exception as exc:  # noqa: BLE001 - isolate action failures
        return {"status": "error", "detail": f"Calendar event failed: {classify_google_error(exc)}",
                "live": True, "ref": None}


def undo_event(ref: dict) -> dict:
    if "mock_title" in ref:
        events = _read_mock_events()
        for i, e in enumerate(events):
            if e.get("title") == ref["mock_title"] and e.get("date") == ref["date"]:
                del events[i]
                _write_mock_events(events)
                return {"status": "mocked", "detail": "[mock] Follow-up event removed."}
        return {"status": "error", "detail": "Mock follow-up event not found."}
    if ref.get("composio_user"):
        composio.execute(ref["composio_user"], "GOOGLECALENDAR_DELETE_EVENT", {"event_id": ref["event_id"]})
        return {"status": "ok", "detail": f"Calendar event {ref['event_id']} deleted from your connected calendar."}
    creds = get_credentials()
    if creds is None:
        return {"status": "error", "detail": "Google account not connected, can't delete the live event."}
    from googleapiclient.discovery import build

    build("calendar", "v3", credentials=creds).events().delete(calendarId="primary", eventId=ref["event_id"]).execute()
    return {"status": "ok", "detail": f"Calendar event {ref['event_id']} deleted."}
