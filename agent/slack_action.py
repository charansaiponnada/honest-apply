"""
Skill 10 (5th app): Slack notification.

Posts a short message to a Slack channel via an Incoming Webhook whenever a
run completes — proceeded automatically or flagged for review. This is the
"tell a human what happened" step real job-application tooling needs: the
guardrail already decides *whether* to act, Slack is how a person finds out
either way without babysitting the app.

Incoming Webhooks are the simplest possible Slack integration: no OAuth
app review, no bot token scopes to manage, just a URL you paste into
.env. Falls back to a local log file if SLACK_WEBHOOK_URL isn't set.
"""
import json
import os

import requests

from agent.utils import retry_with_backoff

_MOCK_LOG = os.path.join("eval", "logs", "slack_mock.log")
_TIMEOUT_SECONDS = 10


def _webhook_url() -> str:
    return os.getenv("SLACK_WEBHOOK_URL", "").strip()


def is_live() -> bool:
    return bool(_webhook_url())


def _append_mock_log(text: str) -> None:
    os.makedirs(os.path.dirname(_MOCK_LOG), exist_ok=True)
    with open(_MOCK_LOG, "a") as f:
        f.write(text + "\n")


def notify_run_result(company: str, role: str, needs_review: bool, overlap_score: float,
                       actions: dict | None = None) -> dict:
    """Returns {"status": "ok"|"error"|"mocked", "detail": str, "live": bool}"""
    actions = actions or {}
    gmail_sent = actions.get("gmail", {}).get("sent", False)

    if needs_review:
        headline = f":warning: *Flagged for review* — {role} @ {company} (overlap {overlap_score*100:.0f}%)"
    elif gmail_sent:
        headline = (
            f":rocket: *Auto-sent* — {role} @ {company} (overlap {overlap_score*100:.0f}%, "
            f"cleared the auto-send threshold — no review needed)"
        )
    else:
        ok_actions = [k for k, v in actions.items() if v.get("status") in ("ok", "mocked")]
        headline = (
            f":memo: *Drafted, awaiting your send* — {role} @ {company} "
            f"(overlap {overlap_score*100:.0f}%). Actions: {', '.join(ok_actions) or 'none'}"
        )

    if not is_live():
        _append_mock_log(headline)
        return {
            "status": "mocked",
            "detail": f"[mock] Logged to eval/logs/slack_mock.log (no SLACK_WEBHOOK_URL configured).",
            "live": False,
        }

    try:
        def _post():
            resp = requests.post(
                _webhook_url(), data=json.dumps({"text": headline}),
                headers={"Content-Type": "application/json"}, timeout=_TIMEOUT_SECONDS,
            )
            resp.raise_for_status()
            return resp

        retry_with_backoff(
            _post,
            retryable_check=lambda exc: isinstance(exc, (requests.Timeout, requests.ConnectionError)),
        )
        return {"status": "ok", "detail": "Slack notification sent.", "live": True}
    except Exception as exc:  # noqa: BLE001 - isolate action failures
        return {"status": "error", "detail": f"Slack notification failed: {exc}", "live": True}
