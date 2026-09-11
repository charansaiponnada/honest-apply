---
name: gmail-draft
description: >
  Creates a Gmail draft (and optionally sends it if the guardrail
  score clears a second, stricter threshold). Attaches the tailored
  resume as a PDF-like text body. Never auto-sends in MVP unless both
  thresholds are cleared.
---

# Gmail Draft Skill

Composes a job application email and saves it as a Gmail draft.
The draft can be auto-sent if the guardrail score clears
`AUTO_SEND_THRESHOLD` (default 70%) — otherwise left for human review.

## When to use

Only when the guardrail check passes (`needs_review == False`).

## Function

```python
from agent.gmail_action import create_draft

result = create_draft(
    company="Acme Corp",
    role="Backend Engineer",
    cover_note="...",
    tailored_resume="...",
    auto_send=False,
)
# result: {"status": "ok"|"error"|"mocked", "detail": str, "live": bool, "sent": bool}
```

### Input

| Arg | Type | Default | Description |
|-----|------|---------|-------------|
| `company` | `str` | required | Target company name |
| `role` | `str` | required | Target role title |
| `cover_note` | `str` | required | Body text of the email |
| `tailored_resume` | `str` | required | Resume content (attached/body) |
| `auto_send` | `bool` | `False` | Send immediately vs leave as draft |

### Output

```json
{
  "status": "ok",
  "detail": "Draft created for Backend Engineer @ Acme Corp",
  "live": true,
  "sent": false
}
```

- `status`: `"ok"` = success, `"error"` = failed, `"mocked"` = offline fallback
- `sent`: `True` only when `auto_send=True` AND the email was actually sent

## Error handling

Google API failures (auth expired, quota) return `"error"` status.
Stale OAuth token triggers automatic re-auth on next run.

## Scopes required

`https://www.googleapis.com/auth/gmail.compose`
