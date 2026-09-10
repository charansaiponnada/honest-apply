"""
Skill 6: Google Calendar follow-up event creation.

Creates a single event 7 days from now titled "Follow up: [company] – [role]".
Falls back to writing the event to a local JSON file when no live Google
credentials are available.
"""
import json
import os
from datetime import datetime, timedelta

from agent.google_auth import get_credentials
from agent.utils import classify_google_error, is_retryable_google_error, retry_with_backoff

_MOCK_JSON = os.path.join("eval", "logs", "calendar_mock.json")


def _append_mock_event(event: dict) -> None:
    os.makedirs(os.path.dirname(_MOCK_JSON), exist_ok=True)
    events = []
    if os.path.exists(_MOCK_JSON):
        try:
            events = json.loads(open(_MOCK_JSON).read())
        except json.JSONDecodeError:
            events = []
    events.append(event)
    with open(_MOCK_JSON, "w") as f:
        json.dump(events, f, indent=2)


def create_followup_event(company: str, role: str) -> dict:
    """Returns {"status": "ok"|"error"|"mocked", "detail": str, "live": bool}"""
    follow_up_date = (datetime.now() + timedelta(days=7)).date().isoformat()
    title = f"Follow up: {company} – {role}"
    creds = get_credentials()

    if creds is None:
        _append_mock_event({"title": title, "date": follow_up_date})
        return {
            "status": "mocked",
            "detail": f"[mock] '{title}' logged for {follow_up_date} "
                      f"(no credentials.json found).",
            "live": False,
        }

    try:
        from googleapiclient.discovery import build

        service = build("calendar", "v3", credentials=creds)
        start = f"{follow_up_date}T09:00:00"
        end = f"{follow_up_date}T09:30:00"
        event = {
            "summary": title,
            "description": f"Follow up on application to {role} at {company}.",
            "start": {"dateTime": start},
            "end": {"dateTime": end},
        }
        created = retry_with_backoff(
            lambda: service.events().insert(calendarId="primary", body=event).execute(),
            retryable_check=is_retryable_google_error,
        )
        return {
            "status": "ok",
            "detail": f"Calendar event created for {follow_up_date} (id: {created.get('id')})",
            "live": True,
        }
    except Exception as exc:  # noqa: BLE001 - isolate action failures
        return {
            "status": "error",
            "detail": f"Calendar event failed: {classify_google_error(exc)}",
            "live": True,
        }
