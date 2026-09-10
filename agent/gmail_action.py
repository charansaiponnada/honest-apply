"""
Skill 4: Gmail draft-creation, with gated auto-send.

Always creates a Gmail DRAFT with the cover note as the body and the
tailored resume attached as a text file. If auto_send=True is passed in
(the caller — pipeline.py — only sets this when the guardrail's stricter
AUTO_SEND_THRESHOLD was cleared, on top of the normal guardrail already
having passed), the draft is immediately sent via drafts.send using the
same OAuth scope (gmail.compose covers both draft creation and sending
drafts — no extra scope needed). Otherwise the draft is left for a human
to review and send themselves, which remains the default behavior.

Wrapped so a failure here never crashes the rest of the pipeline — it just
reports failure in the log. The actual API calls are retried with backoff
on transient errors (rate limits, 5xx) but fail fast on auth/permission
errors, and the error message is classified rather than a raw exception dump.
"""
import base64
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart

from agent.google_auth import get_credentials
from agent.utils import classify_google_error, is_retryable_google_error, retry_with_backoff


def create_draft(company: str, role: str, cover_note: str, tailored_resume: str,
                  to_addr: str = "hiring@example.com", auto_send: bool = False) -> dict:
    """Returns {"status": "ok"|"error"|"mocked", "detail": str, "live": bool, "sent": bool}"""
    creds = get_credentials()
    if creds is None:
        detail = f"[mock] Gmail draft created for {role} @ {company}"
        detail += (
            " and auto-sent (mock — cleared the auto-send threshold; no credentials.json found)."
            if auto_send
            else " (no credentials.json found — see README to go live)."
        )
        return {"status": "mocked", "detail": detail, "live": False, "sent": auto_send}

    try:
        from googleapiclient.discovery import build

        service = build("gmail", "v1", credentials=creds)

        message = MIMEMultipart()
        message["to"] = to_addr
        message["subject"] = f"Application: {role} at {company}"
        message.attach(MIMEText(cover_note))

        attachment = MIMEApplication(tailored_resume.encode("utf-8"), _subtype="plain")
        attachment.add_header(
            "Content-Disposition", "attachment", filename=f"resume_{company}_{role}.txt"
        )
        message.attach(attachment)

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

        draft = retry_with_backoff(
            lambda: service.users().drafts().create(
                userId="me", body={"message": {"raw": raw}}
            ).execute(),
            retryable_check=is_retryable_google_error,
        )

        sent = False
        detail = f"Gmail draft created (id: {draft.get('id')})"
        if auto_send:
            retry_with_backoff(
                lambda: service.users().drafts().send(
                    userId="me", body={"id": draft.get("id")}
                ).execute(),
                retryable_check=is_retryable_google_error,
            )
            sent = True
            detail += " and auto-sent (overlap cleared the auto-send threshold)"

        return {"status": "ok", "detail": detail, "live": True, "sent": sent}
    except Exception as exc:  # noqa: BLE001 - isolate action failures
        return {
            "status": "error",
            "detail": f"Gmail draft/send failed: {classify_google_error(exc)}",
            "live": True,
            "sent": False,
        }
