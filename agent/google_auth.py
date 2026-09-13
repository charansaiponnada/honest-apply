"""
Shared Google OAuth helper used by the Gmail, Calendar and reply-tracker skills.
Scopes are intentionally narrow: gmail.compose (drafts, plus sending a draft
only when every gate in pipeline.py passes), gmail.readonly (spotting replies)
and calendar.events. Changing scopes means authorizing once more: delete
token.json and the next Google action opens the consent screen.

Where credentials come from, in order:
  1. GOOGLE_TOKEN_JSON env var — for hosted deploys, which have no browser
     for the OAuth flow. Authorize locally once, paste token.json's contents.
  2. credentials.json + token.json on disk — the local Desktop-app flow.
  3. Neither -> None, and every Google skill runs in labeled mock mode.

Hardening notes:
- A stale/corrupt token.json (revoked access, expired refresh token) is
  deleted and the flow retried once rather than caching a broken client.
- get_credentials() caches the *outcome* (including "unavailable") for the
  process lifetime so a broken setup doesn't retry OAuth on every call.
- The chaos panel's "google_auth" fault makes credentials unavailable, so the
  demo can show every Google skill degrading to labeled mock mode.
"""
import json
import os

from agent.utils import FAULTS

SCOPES = [
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.events",
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
    if "google_auth" in FAULTS:
        return None
    if _checked:
        return _creds_cache

    _checked = True

    token_env = os.getenv("GOOGLE_TOKEN_JSON", "").strip()
    if token_env:
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials

            creds = Credentials.from_authorized_user_info(json.loads(token_env), SCOPES)
            if not creds.valid and creds.refresh_token:
                creds.refresh(Request())
            _creds_cache = creds
        except Exception as exc:  # noqa: BLE001 - demo-safe fallback to mock mode
            print(f"[google_auth] GOOGLE_TOKEN_JSON unusable, using mock mode: {exc}")
        return _creds_cache

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
