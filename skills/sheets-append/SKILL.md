---
name: sheets-append
description: >
  Appends a tracking row to a Google Sheet for every application run
  (company, role, JD source, date, status). Falls back to local CSV
  when no Google credentials are configured.
---

# Sheets Append Skill

Logs every application to a tracking spreadsheet so the candidate can
see their pipeline at a glance.

## When to use

After the guardrail passes, alongside Gmail and Calendar actions.

## Function

```python
from agent.sheets_action import append_row

result = append_row(
    company="Acme Corp",
    role="Backend Engineer",
    jd_source="pasted text",
    status="applied",
    spreadsheet_id="1AbC...",  # optional
)
# result: {"status": "ok"|"error"|"mocked", "detail": str, "live": bool}
```

### Input

| Arg | Type | Default | Description |
|-----|------|---------|-------------|
| `company` | `str` | required | Target company name |
| `role` | `str` | required | Target role title |
| `jd_source` | `str` | `"pasted text"` | Where the JD came from |
| `status` | `str` | `"applied"` | Application status |
| `spreadsheet_id` | `str` | `None` | Google Sheet ID (optional) |

### Output

```json
{
  "status": "ok",
  "detail": "Row appended to Sheet 1AbC...",
  "live": true
}
```

## Mock mode

Without Google credentials or a Sheet ID, rows are appended to
`eval/logs/tracking_mock.csv` as a local fallback.

## Scopes required

`https://www.googleapis.com/auth/spreadsheets`
