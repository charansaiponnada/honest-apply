---
name: crm-deal
description: >
  Records each application in HubSpot CRM: finds or creates the employer
  Company and the candidate Contact, creates a Deal associated with both,
  and moves its stage as the application progresses (drafted, sent, replied,
  closed-lost on undo). Makes the agent usable by career centers and agencies.
---

# CRM Deal Skill (HubSpot)

## Functions

```python
from agent.crm_action import candidate_from_resume, log_application, set_deal_stage, undo_deal

candidate = candidate_from_resume(resume_text)          # {"name", "firstname", "lastname", "email"}
result = log_application(company, role, candidate, jd_source, stage="drafted",
                         links={"email": gmail_link, "follow_up": calendar_link})
# {"status": "ok"|"error"|"mocked", "detail", "live", "ref": {"deal_id"}, "link"}

set_deal_stage(result["ref"], "replied")                 # used by the reply tracker
undo_deal(result["ref"])                                  # closed-lost, kept for history
```

## Stages

`drafted → appointmentscheduled`, `sent → qualifiedtobuy`, `replied → presentationscheduled`,
`undone → closedlost` (HubSpot default pipeline IDs). Rename labels in HubSpot, or override with
`HUBSPOT_STAGE_DRAFTED` / `_SENT` / `_REPLIED` / `_UNDONE`.

## Setup

Free HubSpot account → Private App token in `HUBSPOT_TOKEN` with
`crm.objects.companies`, `crm.objects.contacts`, `crm.objects.deals` (read + write).
Without a token, deals go to `eval/logs/crm_mock.json`.

## Reliability

429/5xx and network errors are retried with backoff; 401/403 fail fast with a readable reason.
The `crm` chaos fault simulates an outage.

## Self-check

`python -m agent.crm_action`
