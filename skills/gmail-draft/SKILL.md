---
name: gmail-draft
description: >
  Creates the application email in Gmail (cover note body, tailored resume
  attached) as a draft. Sends it only when a Google account is connected, the
  user enabled sending, a recipient is set, and every gate passed. Undo deletes
  the draft.
---

# Gmail Draft Skill

## Function

```python
from agent.gmail_action import create_draft, undo_draft

result = create_draft(company, role, cover_note, tailored_resume, to_addr="", auto_send=False)
# {"status": "ok"|"error"|"mocked", "detail", "live", "sent", "ref", "link"}
undo_draft(result["ref"])
```

## When it sends

`pipeline.py` passes `auto_send=True` only if **all** hold: Google credentials live, the user
turned on *Allow sending*, `to_addr` is set, overlap ≥ `AUTO_SEND_THRESHOLD`, receipts check
faithful, Executor recommends proceed. `drafts.send` is not retried (not idempotent). Mock mode
never reports `sent: true`.

## Chaining

`link` (the draft or sent message in Gmail) is passed to the Calendar event, the CRM deal and
Slack. `ref` is stored in the run log for undo. A sent email can't be recalled; undo says so.

## Scopes

`gmail.compose` (drafts + send). The reply tracker additionally uses `gmail.readonly`.
