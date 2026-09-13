"""
Preflight check for every integration this agent uses. Run this first thing
on demo day so a broken credential surfaces before judging, not during it.

Usage:
    python -m scripts.check_connections            # status only, no side effects
    python -m scripts.check_connections --ping      # also sends a real Slack test
                                                    # message, a real job-board
                                                    # search, a HubSpot read, and
                                                    # a tool-calling probe to the
                                                    # LLM. Never creates a Gmail
                                                    # draft, Calendar event or deal.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from agent.composio_client import check_tools, is_enabled as composio_enabled  # noqa: E402
from agent.crm_action import _call as hubspot_call, _classify as hubspot_error, is_live as crm_is_live  # noqa: E402
from agent.google_auth import get_credentials  # noqa: E402
from agent.jobs_search import search_jobs  # noqa: E402
from agent.llm import _model_name, call_tools, is_live as llm_is_live  # noqa: E402
from agent.slack_action import is_live as slack_is_live, send_text  # noqa: E402

_PROBE_TOOL = [{
    "type": "function",
    "function": {"name": "ping", "description": "Call this tool to confirm tool calling works.",
                 "parameters": {"type": "object", "properties": {}}},
}]


def _status_line(name: str, ok: bool, detail: str) -> None:
    tag = "LIVE" if ok else "MOCK"
    print(f"[{tag:4}] {name:22} {detail}")


def main() -> None:
    ping = "--ping" in sys.argv

    print("Checking integrations...\n")

    # 1. LLM (OpenRouter)
    _status_line(
        "OpenRouter LLM",
        llm_is_live(),
        f"API key configured, model {_model_name()}" if llm_is_live() else "no OPENROUTER_API_KEY — agents will use offline rule-based mock",
    )
    if ping and llm_is_live():
        calls, _ = call_tools("Call the ping tool now.", _PROBE_TOOL)
        ok = any(c["name"] == "ping" for c in calls)
        print(f"         -> tool calling: {'supported' if ok else 'NOT returned — Executor will use deterministic dispatch; try another OPENROUTER_MODEL'}")

    # 2. Google APIs (Gmail + Calendar share one OAuth client)
    creds = get_credentials()
    _status_line(
        "Google (Gmail/Calendar)",
        creds is not None,
        "OAuth credentials valid" if creds is not None
        else "no credentials.json / GOOGLE_TOKEN_JSON — actions will use local mock files",
    )

    # 3. HubSpot CRM
    _status_line("HubSpot CRM", crm_is_live(), "HUBSPOT_TOKEN configured" if crm_is_live() else "no HUBSPOT_TOKEN — deals go to eval/logs/crm_mock.json")
    if ping and crm_is_live():
        try:
            hubspot_call("GET", "/crm/v3/objects/deals?limit=1")
            print("         -> deals API reachable with this token")
        except Exception as exc:  # noqa: BLE001
            print(f"         -> deals API FAILED: {hubspot_error(exc)}")

    # 4. Slack
    _status_line(
        "Slack webhook",
        slack_is_live(),
        "SLACK_WEBHOOK_URL configured" if slack_is_live() else "no SLACK_WEBHOOK_URL — notifications logged locally",
    )
    if ping and slack_is_live():
        result = send_text(":white_check_mark: Preflight check from the job application agent.")
        print(f"         -> test message: {result['status']} — {result['detail']}")

    # 5. Composio (one-click Connect for each user's own apps)
    _status_line(
        "Composio",
        composio_enabled(),
        "COMPOSIO_API_KEY configured — users can Connect their own apps in the app"
        if composio_enabled() else "no COMPOSIO_API_KEY — apps use .env credentials or mock",
    )
    if ping and composio_enabled():
        for slug, state, params, required in check_tools():
            print(f"         -> {slug:30} {state}" + (f"  required={required}  params={params}" if state == "ok" else ""))

    # 6. Job boards (Arbeitnow, Remotive, RemoteOK — public, no auth)
    if ping:
        jobs, error = search_jobs("engineer", limit=1)
        _status_line("Job board search", error is None, error or f"reachable, sample: {jobs[0]['title']!r} [{jobs[0]['source']}]")
    else:
        _status_line("Job board search", True, "public APIs, no auth needed (pass --ping to test reachability)")

    print(
        "\nA MOCK line means that integration runs in offline/local mode — the "
        "pipeline still works end to end, it just won't touch real accounts."
    )


if __name__ == "__main__":
    main()
