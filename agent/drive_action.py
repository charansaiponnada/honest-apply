"""
Skill 7: Google Drive read/write.

Saves the tailored resume as a new file in Drive. Falls back to saving it
locally under eval/logs/tailored_resumes/ when no live Google credentials
are available.
"""
import io
import os
import re

from agent.google_auth import get_credentials
from agent.utils import classify_google_error, is_retryable_google_error, retry_with_backoff

_MOCK_DIR = os.path.join("eval", "logs", "tailored_resumes")


def _safe_filename(company: str, role: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", f"{company}_{role}").strip("_")
    return f"resume_{slug or 'application'}.txt"


def save_tailored_resume(company: str, role: str, tailored_resume: str) -> dict:
    """Returns {"status": "ok"|"error"|"mocked", "detail": str, "live": bool}"""
    filename = _safe_filename(company, role)
    creds = get_credentials()

    if creds is None:
        os.makedirs(_MOCK_DIR, exist_ok=True)
        path = os.path.join(_MOCK_DIR, filename)
        with open(path, "w") as f:
            f.write(tailored_resume)
        return {
            "status": "mocked",
            "detail": f"[mock] Saved to {path} (no credentials.json found).",
            "live": False,
        }

    try:
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaIoBaseUpload

        service = build("drive", "v3", credentials=creds)
        media = MediaIoBaseUpload(
            io.BytesIO(tailored_resume.encode("utf-8")), mimetype="text/plain"
        )
        file = retry_with_backoff(
            lambda: service.files().create(
                body={"name": filename}, media_body=media, fields="id"
            ).execute(),
            retryable_check=is_retryable_google_error,
        )
        return {
            "status": "ok",
            "detail": f"Saved to Drive as {filename} (id: {file.get('id')})",
            "live": True,
        }
    except Exception as exc:  # noqa: BLE001 - isolate action failures
        return {
            "status": "error",
            "detail": f"Drive save failed: {classify_google_error(exc)}",
            "live": True,
        }
