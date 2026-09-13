---
name: calendar-followup
description: >
  Creates an all-day Google Calendar follow-up 7 days out for every application
  that clears the gates, with a link to the application email. Deleted by undo,
  and cancelled automatically when the reply tracker sees a reply.
---

# Calendar Follow-up Skill

## Function

```python
from agent.calendar_action import create_followup_event, undo_event

result = create_followup_event("Acme Corp", "Backend Engineer", email_link="https://mail.google.com/...")
# {"status": "ok"|"error"|"mocked", "detail": str, "live": bool, "ref": {"event_id": ...}, "link": htmlLink}

undo_event(result["ref"])   # deletes the event (or removes the mock entry)
```

## Chaining

Runs after Gmail: the event description carries the email link, and the event's own link is
passed on to the CRM deal and the Slack message.

## Mock mode

Without Google credentials, events go to `eval/logs/calendar_mock.json`.

## Chaos

The `calendar` fault makes this skill fail like a 503 outage (retried, then reported).

## Scope

`https://www.googleapis.com/auth/calendar.events`
