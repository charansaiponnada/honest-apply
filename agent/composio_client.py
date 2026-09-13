"""
Composio: one-click "Connect" for each user's own Gmail, Google Calendar,
HubSpot and Slack, inside the app.

Composio runs the OAuth flow, stores and refreshes each user's tokens, and
executes app actions on that user's behalf, so a new user connects apps with
a button instead of creating a Google Cloud project or a HubSpot token.
Enabled when COMPOSIO_API_KEY is set.

Precedence per app, per user: Composio connection -> .env credentials -> mock.
"""
import hashlib
import json
import os
import re
from functools import lru_cache

from agent.utils import SIMULATED

APP_TOOLKITS = {"gmail": "gmail", "calendar": "googlecalendar", "crm": "hubspot", "slack": "slack"}
TOOL_SLUGS = (
    "GMAIL_CREATE_EMAIL_DRAFT", "GMAIL_SEND_DRAFT", "GMAIL_DELETE_DRAFT", "GMAIL_FETCH_EMAILS",
    "GOOGLECALENDAR_CREATE_EVENT", "GOOGLECALENDAR_DELETE_EVENT",
    "HUBSPOT_CREATE_DEAL", "HUBSPOT_UPDATE_DEAL",
    "SLACK_FIND_CHANNELS", "SLACK_SEND_MESSAGE",
)
_AUTH_CONFIG_CACHE = os.path.join("eval", "logs", "composio_auth_configs.json")
_USER_ID = re.compile(r"^[\w.@+-]{1,200}$")


class ComposioToolError(Exception):
    pass


def _api_key() -> str:
    return os.getenv("COMPOSIO_API_KEY", "").strip()


def is_enabled() -> bool:
    return bool(_api_key())


def valid_user_id(user_id: str) -> bool:
    return bool(user_id) and _USER_ID.fullmatch(user_id) is not None


@lru_cache(maxsize=1)
def _client():
    from composio import Composio

    # ponytail: "latest" toolkit versions + skipped version check; pin per-toolkit versions before production
    return Composio(api_key=_api_key(), toolkit_versions={t: "latest" for t in APP_TOOLKITS.values()})


def _auth_config_id(toolkit: str) -> str:
    """Composio-managed auth config per toolkit: env override, else created once and cached per API key."""
    override = os.getenv(f"COMPOSIO_AUTH_CONFIG_{toolkit.upper()}", "").strip()
    if override:
        return override
    key = f"{hashlib.sha256(_api_key().encode()).hexdigest()[:12]}:{toolkit}"
    cache = {}
    if os.path.exists(_AUTH_CONFIG_CACHE):
        try:
            cache = json.loads(open(_AUTH_CONFIG_CACHE, encoding="utf-8").read())
        except json.JSONDecodeError:
            cache = {}
    if key not in cache:
        cache[key] = _client().auth_configs.create(toolkit, {"type": "use_composio_managed_auth"}).id
        os.makedirs(os.path.dirname(_AUTH_CONFIG_CACHE), exist_ok=True)
        with open(_AUTH_CONFIG_CACHE, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2)
    return cache[key]


def connect_link(user_id: str, app: str, callback_url: str) -> str:
    """Hosted Composio page where the user signs in to the app. Returns its URL."""
    request = _client().connected_accounts.link(user_id, _auth_config_id(APP_TOOLKITS[app]), callback_url=callback_url)
    return request.redirect_url


def connected_apps(user_id: str) -> set[str]:
    """Which of our apps this user has an ACTIVE Composio connection for."""
    if SIMULATED.get() or not (is_enabled() and valid_user_id(user_id)):
        return set()
    try:
        resp = _client().connected_accounts.list(
            user_ids=[user_id], statuses=["ACTIVE"], toolkit_slugs=list(APP_TOOLKITS.values())
        )
    except Exception as exc:  # noqa: BLE001 - fall back to .env / mock rather than failing the run
        print(f"[composio] listing connections failed, falling back: {exc}")
        return set()
    slugs = {item.toolkit.slug for item in resp.items}
    return {app for app, toolkit in APP_TOOLKITS.items() if toolkit in slugs}


def execute(user_id: str, slug: str, arguments: dict) -> dict:
    """Run one app action as this user. Returns the tool's data; raises on failure.
    Not retried: create/send tools aren't idempotent."""
    # ponytail: direct execution of a fixed allowlist on purpose: the gates and the Executor's tool choice
    # stay in our code. Composio recommends sessions for agents that discover tools; migrate if the
    # agent ever needs open-ended app access.
    result = _client().tools.execute(slug, arguments, user_id=user_id, dangerously_skip_version_check=True)
    if not result.get("successful"):
        raise ComposioToolError(f"{slug}: {result.get('error') or 'failed without an error message'}")
    return result.get("data") or {}


def find(data, *keys):
    """First non-empty value for any of `keys`, searching nested dicts/lists breadth-first.
    Tool responses nest ids at different depths, so callers ask for the key, not the path."""
    queue = [data]
    while queue:
        node = queue.pop(0)
        if isinstance(node, dict):
            for key in keys:
                if node.get(key) not in (None, ""):
                    return node[key]
            queue.extend(node.values())
        elif isinstance(node, list):
            queue.extend(node)
    return None


def check_tools() -> list[tuple[str, str, list, list]]:
    """Preflight: (slug, "ok" | problem, parameter names, required parameter names) per tool we call."""
    rows = []
    for slug in TOOL_SLUGS:
        try:
            params = getattr(_client().tools.get_raw_composio_tool_by_slug(slug), "input_parameters", None) or {}
            rows.append((slug, "ok", sorted(params.get("properties", {})), params.get("required", [])))
        except Exception as exc:  # noqa: BLE001 - report, don't stop the preflight
            if "401" in str(exc) or "InvalidAPIKey" in str(exc):
                return [("COMPOSIO_API_KEY", "REJECTED by Composio (401): copy the project API key again", [], [])]
            rows.append((slug, f"NOT FOUND: {exc}", [], []))
    return rows


if __name__ == "__main__":
    sample = {"response_data": {"id": "evt1", "htmlLink": "https://calendar.google.com/x"}, "extra": [{"draft_id": "d9"}]}
    assert find(sample, "htmlLink") == "https://calendar.google.com/x"
    assert find(sample, "draft_id", "id") == "evt1"  # breadth-first: shallower "id" wins over deeper draft_id
    assert find({"items": [{"id": ""}, {"id": "m2"}]}, "id") == "m2"
    assert find({}, "id") is None
    assert valid_user_id("jordan.rivera@email.com") and not valid_user_id("bad id") and not valid_user_id("")
    print("composio client self-check passed")
