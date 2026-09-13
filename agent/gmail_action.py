"""
Gmail skill: application email with the tailored resume.

Always creates a DRAFT first. It is sent only when pipeline.py passes
auto_send=True, which it does only if ALL of these hold: a Gmail account is
connected (Composio or .env), the user turned on "Allow send", a recipient was
given, overlap cleared AUTO_SEND_THRESHOLD, and the Executor's receipts check
found no unsupported claims. Mock mode never reports an email as sent.

Paths, in order: the user's Composio connection (user_id given) -> .env OAuth
credentials -> mock. Every result carries a `ref` so the run can be undone.
"""
import base64
import re
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from agent import composio_client as composio
from agent.google_auth import get_credentials
from agent.utils import classify_google_error, is_retryable_google_error, maybe_fail, retry_with_backoff

_DRAFTS_URL = "https://mail.google.com/mail/u/0/#drafts"


def _create_via_composio(user_id: str, company: str, role: str, cover_note: str, tailored_resume: str,
                         to_addr: str, auto_send: bool) -> dict:
    # ponytail: resume goes inline under the cover note; Composio's attachment param wants a file path/URL, attach once files are hosted
    args = {"subject": f"Application: {role} at {company}", "body": f"{cover_note}\n\n---\n\n{tailored_resume}"}
    if to_addr:
        args["recipient_email"] = to_addr
    try:
        draft_id = composio.find(composio.execute(user_id, "GMAIL_CREATE_EMAIL_DRAFT", args), "draft_id", "id")
        if auto_send and to_addr and draft_id:
            message_id = composio.find(composio.execute(user_id, "GMAIL_SEND_DRAFT", {"draft_id": draft_id}), "message_id", "id")
            return {"status": "ok", "detail": f"Application email sent to {to_addr} via your connected Gmail.",
                    "live": True, "sent": True, "ref": {"composio_user": user_id, "message_id": message_id},
                    "link": f"https://mail.google.com/mail/u/0/#sent/{message_id}" if message_id else None}
        return {"status": "ok", "detail": f"Gmail draft created in your connected account (id: {draft_id}).",
                "live": True, "sent": False, "ref": {"composio_user": user_id, "draft_id": draft_id}, "link": _DRAFTS_URL}
    except Exception as exc:  # noqa: BLE001 - isolate action failures
        return {"status": "error", "detail": f"Gmail draft/send failed (Composio): {exc}", "live": True, "sent": False, "ref": None}


def create_draft(company: str, role: str, cover_note: str, tailored_resume: str,
                 to_addr: str = "", auto_send: bool = False, user_id: str = "") -> dict:
    """Returns {"status": "ok"|"error"|"mocked", "detail", "live", "sent", "ref", "link"?}"""
    try:
        retry_with_backoff(lambda: maybe_fail("gmail"), retryable_check=is_retryable_google_error)
    except Exception as exc:  # noqa: BLE001 - chaos panel outage
        return {"status": "error", "detail": f"Gmail draft failed: {classify_google_error(exc)}",
                "live": False, "sent": False, "ref": None}

    if user_id:
        return _create_via_composio(user_id, company, role, cover_note, tailored_resume, to_addr, auto_send)

    creds = get_credentials()
    if creds is None:
        return {
            "status": "mocked",
            "detail": f"[mock] Gmail draft created for {role} @ {company} "
                      f"(no Gmail account connected, so nothing is sent).",
            "live": False,
            "sent": False,
            "ref": {"mock": True},
        }

    try:
        from googleapiclient.discovery import build

        service = build("gmail", "v1", credentials=creds)

        message = MIMEMultipart()
        if to_addr:
            message["to"] = to_addr
        message["subject"] = f"Application: {role} at {company}"
        message.attach(MIMEText(cover_note))

        attachment = MIMEApplication(tailored_resume.encode("utf-8"), _subtype="plain")
        filename = re.sub(r"[^\w.-]+", "_", f"resume_{company}_{role}") + ".txt"
        attachment.add_header("Content-Disposition", "attachment", filename=filename)
        message.attach(attachment)

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        draft = retry_with_backoff(
            lambda: service.users().drafts().create(userId="me", body={"message": {"raw": raw}}).execute(),
            retryable_check=is_retryable_google_error,
        )

        if auto_send and to_addr:
            # No retry: drafts.send is not idempotent, a retry after a timeout could double-send.
            sent = service.users().drafts().send(userId="me", body={"id": draft.get("id")}).execute()
            return {
                "status": "ok",
                "detail": f"Application email sent to {to_addr} (message id: {sent.get('id')})",
                "live": True,
                "sent": True,
                "ref": {"message_id": sent.get("id")},
                "link": f"https://mail.google.com/mail/u/0/#sent/{sent.get('id')}",
            }

        return {
            "status": "ok",
            "detail": f"Gmail draft created (id: {draft.get('id')})",
            "live": True,
            "sent": False,
            "ref": {"draft_id": draft.get("id")},
            "link": f"{_DRAFTS_URL}?compose={draft.get('message', {}).get('id')}",
        }
    except Exception as exc:  # noqa: BLE001 - isolate action failures
        return {"status": "error", "detail": f"Gmail draft/send failed: {classify_google_error(exc)}",
                "live": True, "sent": False, "ref": None}


def undo_draft(ref: dict) -> dict:
    if ref.get("mock"):
        return {"status": "mocked", "detail": "[mock] Draft discarded."}
    if ref.get("message_id"):
        return {"status": "skipped", "detail": "Email was already sent, so it can't be recalled."}
    if ref.get("composio_user"):
        composio.execute(ref["composio_user"], "GMAIL_DELETE_DRAFT", {"draft_id": ref["draft_id"]})
        return {"status": "ok", "detail": f"Gmail draft {ref['draft_id']} deleted from your connected account."}
    creds = get_credentials()
    if creds is None:
        return {"status": "error", "detail": "Google account not connected, can't delete the live draft."}
    from googleapiclient.discovery import build

    build("gmail", "v1", credentials=creds).users().drafts().delete(userId="me", id=ref["draft_id"]).execute()
    return {"status": "ok", "detail": f"Gmail draft {ref['draft_id']} deleted."}
