"""
Shared Google OAuth (Desktop app flow) helper used by the four *_action.py
skills. Scopes are intentionally narrow: Gmail is compose/draft-only
(no send), plus Sheets, Calendar, and Drive file access.

If credentials.json is not present, or the OAuth flow can't run (e.g. no
browser available in this environment), every action skill falls back to a
"mock mode" that simulates the action and returns a clearly-labeled mocked
result. This lets the whole pipeline run end-to-end with zero Google setup,
which matters for a fast hackathon demo and for anyone trying this repo
before wiring up their own credentials.

Hardening notes:
- A stale/corrupt token.json (revoked access, expired refresh token) is
  deleted and the flow retried once rather than caching a broken client
  for the rest of the run — this is the failure mode most likely to bite
  you mid-demo if you authorized on a different day.
- get_credentials() caches the *outcome* (including "unavailable") for the
  process lifetime so a broken setup doesn't retry the OAuth flow on every
  single action call.
"""
import os

SCOPES = [
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/drive.file",
]

_CREDENTIALS_PATH = "credentials.json"
_TOKEN_PATH = "token.json"

_creds_cache = None
_checked = False


def _run_flow():
    from google_auth_oauthlib.flow import InstalledAppFlow

    flow = InstalledAppFlow.from_client_secrets_file(_CREDENTIALS_PATH, SCOPES)
    creds = flow.run_local_server(port=0)
    with open(_TOKEN_PATH, "w") as f:
        f.write(creds.to_json())
    return creds


def get_credentials():
    """Return valid OAuth credentials, or None if unavailable (-> mock mode)."""
    global _creds_cache, _checked
    if _checked:
        return _creds_cache

    _checked = True

    if not os.path.exists(_CREDENTIALS_PATH):
        return None

    try:
        from google.auth.exceptions import RefreshError
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials

        creds = None
        if os.path.exists(_TOKEN_PATH):
            try:
                creds = Credentials.from_authorized_user_file(_TOKEN_PATH, SCOPES)
            except ValueError as exc:
                print(f"[google_auth] token.json unreadable ({exc}), re-authorizing.")
                os.remove(_TOKEN_PATH)
                creds = None

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    with open(_TOKEN_PATH, "w") as f:
                        f.write(creds.to_json())
                except RefreshError as exc:
                    print(f"[google_auth] Refresh token invalid ({exc}), re-authorizing.")
                    os.remove(_TOKEN_PATH)
                    creds = _run_flow()
            else:
                creds = _run_flow()

        _creds_cache = creds
        return creds
    except Exception as exc:  # noqa: BLE001 - demo-safe fallback to mock mode
        print(f"[google_auth] OAuth unavailable, using mock mode: {exc}")
        _creds_cache = None
        return None


def is_live() -> bool:
    return get_credentials() is not None


def reset_cache() -> None:
    """Force the next get_credentials() call to re-check from disk. Mainly for tests/CLI tools."""
    global _creds_cache, _checked
    _creds_cache = None
    _checked = False
