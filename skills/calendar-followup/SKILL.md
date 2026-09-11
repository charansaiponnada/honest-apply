---
name: calendar-followup
description: >
  Creates a 7-day follow-up reminder event on Google Calendar for every
  application that clears the guardrail.
---

# Calendar Follow-up Skill

Schedules a calendar reminder 7 days after application so the candidate
remembers to follow up.

## When to use

After the guardrail passes, alongside Gmail and Sheets actions.

## Function

```python
from agent.calendar_action import create_followup_event

result = create_followup_event("Acme Corp", "Backend Engineer")
# result: {"status": "ok"|"error"|"mocked", "detail": str, "live": bool}
```

### Input

| Arg | Type | Description |
|-----|------|-------------|
| `company` | `str` | Target company name |
| `role` | `str` | Target role title |

### Output

```json
{
  "status": "ok",
  "detail": "Follow-up event created for Backend Engineer @ Acme Corp (2026-09-20)",
  "live": true
}
```

The event is created for 7 days from now at 10:00 AM local time.

## Mock mode

Without Google credentials, events are logged to
`eval/logs/calendar_mock.json` as a local fallback.

## Scopes required

`https://www.googleapis.com/auth/calendar.events`
