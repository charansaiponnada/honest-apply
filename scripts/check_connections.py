"""
Preflight check for every integration this agent uses. Run this first thing
on demo day (matches the PRD's 9:00-9:30 "confirm OAuth/API keys work end
to end before building" step) so a broken credential surfaces before
judging, not during it.

Usage:
    python -m scripts.check_connections            # status only, no side effects
    python -m scripts.check_connections --ping      # also sends a real Slack
                                                      # test message and a real
                                                      # Arbeitnow search (both
                                                      # safe/read-mostly); does
                                                      # NOT create a Gmail draft,
                                                      # Sheet row, Calendar event,
                                                      # or Drive file, since those
                                                      # would leave real artifacts
                                                      # behind just from a check.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from agent.llm import is_live as llm_is_live  # noqa: E402
from agent.google_auth import get_credentials  # noqa: E402
from agent.slack_action import is_live as slack_is_live, notify_run_result  # noqa: E402
from agent.jobs_search import search_jobs  # noqa: E402


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
        "API key configured" if llm_is_live() else "no OPENROUTER_API_KEY — extraction/tailoring will use offline mock",
    )

    # 2. Google APIs (Gmail, Sheets, Calendar, Drive share one OAuth client)
    creds = get_credentials()
    _status_line(
        "Google APIs (4 apps)",
        creds is not None,
        "OAuth credentials valid (Gmail, Sheets, Calendar, Drive)"
        if creds is not None
        else "no credentials.json / OAuth not completed — actions will use local mock files",
    )

    # 3. Slack
    _status_line(
        "Slack webhook",
        slack_is_live(),
        "SLACK_WEBHOOK_URL configured" if slack_is_live() else "no SLACK_WEBHOOK_URL — notifications logged locally",
    )
    if ping and slack_is_live():
        result = notify_run_result("Preflight Check", "N/A", needs_review=False, overlap_score=1.0, actions={})
        print(f"         -> test message: {result['status']} — {result['detail']}")

    # 4. Job boards (Arbeitnow, Remotive, RemoteOK — public, no auth)
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
