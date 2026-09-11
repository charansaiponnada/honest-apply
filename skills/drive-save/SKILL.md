---
name: drive-save
description: >
  Saves the tailored resume version to Google Drive under a folder
  named after the target company, for version tracking per application.
---

# Drive Save Skill

Stores the tailored resume as a new file on Google Drive, organized
by company name for easy lookup.

## When to use

After the guardrail passes, alongside Gmail, Sheets, and Calendar
actions.

## Function

```python
from agent.drive_action import save_tailored_resume

result = save_tailored_resume("Acme Corp", "Backend Engineer", "resume text...")
# result: {"status": "ok"|"error"|"mocked", "detail": str, "live": bool}
```

### Input

| Arg | Type | Description |
|-----|------|-------------|
| `company` | `str` | Target company name (used as folder name) |
| `role` | `str` | Target role title (used in filename) |
| `resume_text` | `str` | Full tailored resume content |

### Output

```json
{
  "status": "ok",
  "detail": "Saved to Acme Corp/backend_engineer.txt",
  "live": true
}
```

## Mock mode

Without Google credentials, files are saved to
`eval/logs/tailored_resumes/<company>_<role>.txt` locally.

## Scopes required

`https://www.googleapis.com/auth/drive.file`
