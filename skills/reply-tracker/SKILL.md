---
name: reply-tracker
description: >
  Closes the loop across all four apps: finds replies in Gmail for sent
  applications, moves the HubSpot deal to "replied", cancels the Calendar
  follow-up, and notifies Slack with a link to the reply.
---

# Reply Tracker Skill

## Functions

```python
from agent.reply_tracker import sync_replies, simulate_reply

sync_replies()
# {"mode": "live"|"mock", "checked": 3, "replies": [{"run_id", "company", "role", "link", "results"}]}

simulate_reply(run_id)   # mock mode only: mark a run as replied-to, then call sync_replies()
```

## What happens on a reply

| App | Change |
|-----|--------|
| Gmail | search `from:<recipient> after:<run date>` finds the reply |
| HubSpot | deal stage → `replied` |
| Calendar | follow-up event deleted (no need to chase) |
| Slack | "Reply received" with a link to the reply |

The run log entry gets `replied: true` and `reply_link`, so undo skips the already-cancelled
reminder.

## Live vs. mock

Live mode only checks *sent* applications with a recipient (a draft can't be replied to) and
needs the `gmail.readonly` scope. Mock mode uses `eval/logs/mock_replies.json`, written by the
app's *Simulate reply* button, so the loop can be demoed with no accounts.

In the app: **Tracker → Sync replies**, or `POST /api/replies/sync`.
