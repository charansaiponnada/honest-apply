"""
Skill 5: Google Sheets append.

Appends a single tracking row (company, role, JD source, date, status) to a
tracking spreadsheet. Falls back to appending the same row to a local CSV
(eval/logs/tracking_mock.csv) when no live Google credentials are available,
so the tracker still works out of the box.
"""
import csv
import os
from datetime import date

from agent.google_auth import get_credentials
from agent.utils import classify_google_error, is_retryable_google_error, retry_with_backoff

_MOCK_CSV = os.path.join("eval", "logs", "tracking_mock.csv")
_HEADER = ["company", "role", "jd_source", "date", "status"]


def _append_mock_csv(row: list[str]) -> None:
    os.makedirs(os.path.dirname(_MOCK_CSV), exist_ok=True)
    is_new = not os.path.exists(_MOCK_CSV)
    with open(_MOCK_CSV, "a", newline="") as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(_HEADER)
        writer.writerow(row)


def append_row(company: str, role: str, jd_source: str, status: str,
                spreadsheet_id: str | None = None) -> dict:
    """Returns {"status": "ok"|"error"|"mocked", "detail": str, "live": bool}"""
    row = [company, role, jd_source, date.today().isoformat(), status]
    creds = get_credentials()

    if creds is None or not spreadsheet_id:
        _append_mock_csv(row)
        reason = "no credentials.json" if creds is None else "no SHEET_ID configured"
        return {
            "status": "mocked",
            "detail": f"[mock] Row appended to eval/logs/tracking_mock.csv ({reason}).",
            "live": False,
        }

    try:
        from googleapiclient.discovery import build

        service = build("sheets", "v4", credentials=creds)
        retry_with_backoff(
            lambda: service.spreadsheets().values().append(
                spreadsheetId=spreadsheet_id,
                range="Sheet1!A1",
                valueInputOption="USER_ENTERED",
                body={"values": [row]},
            ).execute(),
            retryable_check=is_retryable_google_error,
        )
        return {"status": "ok", "detail": "Row appended to Google Sheet.", "live": True}
    except Exception as exc:  # noqa: BLE001 - isolate action failures
        return {
            "status": "error",
            "detail": f"Sheets append failed: {classify_google_error(exc)}",
            "live": True,
        }
