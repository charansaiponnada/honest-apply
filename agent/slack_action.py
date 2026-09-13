"""
Slack skill: tell a human what happened, on every run.

Posts sent, drafted, partial, flagged (with the top skill gaps), duplicate,
undone and reply messages. Paths, in order: the user's Composio-connected
Slack (posts to their chosen channel) -> the .env Incoming Webhook -> a local
log file.
"""
import json
import os
import re
from functools import lru_cache

import requests

from agent import composio_client as composio
from agent.utils import InjectedFault, maybe_fail, retry_with_backoff

_MOCK_LOG = os.path.join("eval", "logs", "slack_mock.log")
_TIMEOUT_SECONDS = 10
_SLACK_LINK = re.compile(r"<(https?://[^|>]+)\|([^>]+)>")


def _webhook_url() -> str:
    return os.getenv("SLACK_WEBHOOK_URL", "").strip()


def is_live() -> bool:
    return bool(_webhook_url())


@lru_cache(maxsize=64)
def _channel_id(user_id: str, channel: str) -> str:
    """Composio's Slack tools want channel IDs; resolve a name like #job-applications once."""
    name = channel.lstrip("#")
    if re.fullmatch(r"[CG][A-Z0-9]{6,}", name):
        return name
    data = composio.execute(user_id, "SLACK_FIND_CHANNELS", {"query": name, "exact_match": True, "limit": 1})
    return composio.find(data, "id") or name


def send_text(text: str, user_id: str = "", channel: str = "") -> dict:
    """Returns {"status": "ok"|"error"|"mocked", "detail", "live"}"""
    channel = channel or os.getenv("SLACK_CHANNEL", "").strip() or "general"

    def _post():
        maybe_fail("slack")
        if user_id:
            markdown = _SLACK_LINK.sub(r"[\2](\1)", text)  # Slack mrkdwn links -> markdown for markdown_text
            return composio.execute(user_id, "SLACK_SEND_MESSAGE", {"channel": _channel_id(user_id, channel), "markdown_text": markdown})
        if not is_live():
            return None
        resp = requests.post(
            _webhook_url(), data=json.dumps({"text": text}),
            headers={"Content-Type": "application/json"}, timeout=_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        return resp

    try:
        retry_with_backoff(
            _post,
            retryable_check=lambda exc: isinstance(exc, (requests.Timeout, requests.ConnectionError, InjectedFault)),
        )
    except Exception as exc:  # noqa: BLE001 - isolate action failures
        return {"status": "error", "detail": f"Slack notification failed: {exc} (retried, then gave up)", "live": bool(user_id) or is_live()}

    if user_id:
        return {"status": "ok", "detail": f"Posted to #{channel.lstrip('#')} in your connected Slack.", "live": True}
    if not is_live():
        os.makedirs(os.path.dirname(_MOCK_LOG), exist_ok=True)
        with open(_MOCK_LOG, "a", encoding="utf-8") as f:
            f.write(text + "\n")
        return {"status": "mocked", "detail": "[mock] Logged to eval/logs/slack_mock.log (no Slack connected).", "live": False}
    return {"status": "ok", "detail": "Slack notification sent.", "live": True}


def notify_run_result(company: str, role: str, outcome: str, overlap_score: float,
                      actions: dict | None = None, gaps: list[str] | None = None,
                      user_id: str = "", channel: str = "") -> dict:
    """outcome is one of sent | drafted | partial | flagged | duplicate."""
    pct = f"{overlap_score * 100:.0f}%"
    if outcome == "duplicate":
        text = f":repeat: *Duplicate skipped* — already applied to {role} @ {company}."
    elif outcome == "flagged":
        text = f":warning: *Flagged for review* — {role} @ {company} (overlap {pct})"
        if gaps:
            text += "\nWhat this job wants that your resume doesn't show: " + "; ".join(gaps[:5])
    elif outcome == "partial":
        failed = [k for k, v in (actions or {}).items() if v.get("status") == "error"]
        text = f":x: *Partly failed* — {role} @ {company}: {', '.join(failed)} failed after retries. Re-run it from the app."
    elif outcome == "sent":
        text = f":rocket: *Sent* — {role} @ {company} (overlap {pct}, cleared every gate)"
    else:
        done = [k for k, v in (actions or {}).items() if v.get("status") in ("ok", "mocked")]
        text = f":memo: *Drafted, awaiting your send* — {role} @ {company} (overlap {pct}). Done: {', '.join(done) or 'none'}"

    labels = {"gmail": "Email", "calendar": "Follow-up", "crm": "CRM deal"}
    links = [f"<{a['link']}|{labels[k]}>" for k, a in (actions or {}).items() if k in labels and a.get("link")]
    if links:
        text += "\n" + " · ".join(links)
    return send_text(text, user_id=user_id, channel=channel)
