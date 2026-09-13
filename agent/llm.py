"""
Thin wrapper around OpenRouter's OpenAI-compatible chat completions API.

Defaults to the best free model on OpenRouter as of Sept 2026 for structured
JSON output: NVIDIA Nemotron 3 Super 120B (validated live — extract/tailoring
JSON in ~5s, 262k context). If OPENROUTER_API_KEY is not set, or live calls
keep failing (free-tier rate limit, a model getting pulled from the free
tier, network hiccup, etc.), this falls back to a deterministic, rule-based
"mock LLM" so the rest of the pipeline still runs end-to-end.

Two entry points:
  call_json  — strict JSON answer (Researcher, Tailor, Executor review)
  call_tools — function calling (Executor choosing which apps to act in)

Free-tier models rotate on OpenRouter as providers retire them. If
_DEFAULT_MODEL stops working, check
https://openrouter.ai/models?max_price=0 and set OPENROUTER_MODEL to a new
free ID. The 429 retry loop below cushions transient rate limits before any
mock fallback.
"""
import json
import os
import re
import time

import requests

from agent.utils import FAULTS

_API_URL = "https://openrouter.ai/api/v1/chat/completions"
_DEFAULT_MODEL = "nvidia/nemotron-3-super-120b-a12b:free"
_TIMEOUT_SECONDS = 90
_MAX_RETRIES = 4  # waits 5s, 15s, 30s: free-tier limits reset per minute, so short backoffs just fail again

# One persona per agent in the 3-agent team.
_AGENT_SYSTEM_PROMPTS = {
    "researcher": (
        "You are the Researcher agent of an AI job-application team. Your only job "
        "is to read a job description and produce a precise, structured requirements "
        "profile. Be literal: extract only what the posting actually asks for."
    ),
    "tailor": (
        "You are the Tailor agent of an AI job-application team. You rewrite a "
        "candidate's resume and write a cover note against a requirements profile. "
        "HARD RULE: never invent or add experience, skills, employers, or metrics "
        "that are not already in the original resume, and cite the original line "
        "every tailored line came from."
    ),
    "executor": (
        "You are the Executor agent of an AI job-application team. First you review "
        "the tailored application: does it cover the job's requirements, and is every "
        "claim backed by the original resume? Then you decide which external app tools "
        "(Gmail, Google Calendar, HubSpot CRM, Slack) to use for it."
    ),
}

_ALWAYS_JSON = ". You return ONLY valid JSON. No markdown fences, no commentary, no preamble."
_TEXT_TOOL_NAME = re.compile(r'"name"\s*:\s*"([A-Za-z0-9_]+)"')
_QUEUED = json.dumps({"status": "queued", "note": "runs after planning; call any other tools that apply, or stop"})


def _model_name() -> str:
    return os.getenv("OPENROUTER_MODEL") or _DEFAULT_MODEL


def _api_key() -> str:
    return os.getenv("OPENROUTER_API_KEY", "").strip()


def is_live() -> bool:
    """Whether calls will hit the real OpenRouter API (vs. the offline mock)."""
    key = _api_key()
    return bool(key) and key != "your_openrouter_api_key_here"


def _chat(agent: str, messages: list[dict], system_suffix: str = "", **extra) -> dict:
    """One chat completion, retrying 429s with exponential backoff. Returns the
    assistant message dict; raises on any other failure."""
    system = _AGENT_SYSTEM_PROMPTS.get(agent, _AGENT_SYSTEM_PROMPTS["researcher"]) + system_suffix
    headers = {
        "Authorization": f"Bearer {_api_key()}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/ai-job-application-agent",
        "X-Title": "AI Job Application Agent",
    }
    body = {
        "model": _model_name(),
        "messages": [{"role": "system", "content": system}, *messages],
        "temperature": 0.3,
        **extra,
    }
    for attempt in range(_MAX_RETRIES):
        last = attempt == _MAX_RETRIES - 1
        resp = requests.post(_API_URL, headers=headers, json=body, timeout=_TIMEOUT_SECONDS)
        if (resp.status_code == 429 or resp.status_code >= 500) and not last:
            delay = _retry_delay(resp, attempt)
            print(f"[llm] HTTP {resp.status_code}, retry {attempt+1}/{_MAX_RETRIES - 1} in {delay:.0f}s...")
            time.sleep(delay)
            continue
        resp.raise_for_status()
        data = resp.json()
        if data.get("choices"):
            return data["choices"][0]["message"]
        # Free providers sometimes answer 200 with an error body instead of a completion.
        reason = str(data.get("error") or data)[:200]
        if last:
            raise RuntimeError(f"no completion returned: {reason}")
        delay = _retry_delay(resp, attempt)
        print(f"[llm] no completion ({reason}), retry {attempt+1}/{_MAX_RETRIES - 1} in {delay:.0f}s...")
        time.sleep(delay)
    raise RuntimeError("unreachable")  # pragma: no cover - the last attempt returns or raises


def _retry_delay(resp, attempt: int) -> float:
    """Honor Retry-After when the provider sends it, else 5s, 15s, 30s."""
    try:
        return min(60.0, float(resp.headers.get("Retry-After", "")))
    except ValueError:
        return min(30.0, 5.0 * 3 ** attempt)


def _fault_active() -> bool:
    if "llm_429" in FAULTS:
        print("[llm] injected fault: 429 rate limit, retries exhausted — falling back to rule-based mock")
        return True
    return False


def call_json(prompt: str, mock_fn, agent: str = "researcher") -> tuple[dict, bool]:
    """
    Ask for a strict JSON response. Falls back to mock_fn() (a zero-arg
    callable returning a dict) if no key is configured, the chaos panel has
    the LLM rate-limited, or the call/parse fails for any reason.

    Returns (result_dict, used_live_llm: bool).
    """
    if _fault_active() or not is_live():
        return mock_fn(), False
    try:
        message = _chat(agent, [{"role": "user", "content": prompt}], system_suffix=_ALWAYS_JSON,
                        response_format={"type": "json_object"})
        text = (message.get("content") or "").strip()
        text = re.sub(r"^```json|```$", "", text, flags=re.MULTILINE).strip()
        return json.loads(text), True
    except Exception as exc:  # noqa: BLE001 - demo-safe fallback
        print(f"[llm] Live OpenRouter call failed, falling back to mock: {exc}")
        return mock_fn(), False


def call_tools(prompt: str, tools: list[dict], agent: str = "executor") -> tuple[list[dict], bool]:
    """
    Function-calling request. Returns ([{"name": str, "args": dict}], used_live_llm).
    An empty list with used_live_llm=False means "no live decision" — the
    caller falls back to its deterministic plan.
    """
    if _fault_active() or not is_live():
        return [], False

    # Many models emit one tool call per turn, so keep the conversation going: acknowledge each call
    # (the pipeline runs the tools after planning) and ask again until the model stops choosing.
    messages = [{"role": "user", "content": prompt}]
    calls: list[dict] = []
    for turn in range(len(tools) + 1):
        try:
            # First turn must pick a tool (the gates already decided to act); later turns may stop.
            message = _chat(agent, messages, tools=tools, tool_choice="required" if turn == 0 else "auto")
        except Exception as exc:  # noqa: BLE001 - demo-safe fallback
            print(f"[llm] Tool-calling request failed on turn {turn + 1}: {exc}")
            return (calls, True) if calls else ([], False)

        chosen = {c["name"] for c in calls}
        tool_calls = message.get("tool_calls") or []
        if tool_calls:
            if all((tc.get("function") or {}).get("name") in chosen for tc in tool_calls):
                break
            messages.append({"role": "assistant", "content": message.get("content") or "", "tool_calls": tool_calls})
            for tool_call in tool_calls:
                fn = tool_call.get("function") or {}
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                except json.JSONDecodeError:
                    args = {}
                if fn.get("name") not in chosen:
                    calls.append({"name": fn.get("name", ""), "args": args})
                    chosen.add(fn.get("name"))
                messages.append({"role": "tool", "tool_call_id": tool_call.get("id", ""), "content": _QUEUED})
            continue

        # Some free providers return the model's tool call as JSON text in `content` instead of
        # `tool_calls`. Read the names back, accepting only tools that were actually offered.
        # ponytail: names only (our tools take no arguments); parse arguments too if a tool ever needs them
        offered = {t["function"]["name"] for t in tools}
        text = message.get("content") or ""
        new = [n for n in dict.fromkeys(_TEXT_TOOL_NAME.findall(text)) if n in offered and n not in chosen]
        if not new:
            break
        calls.extend({"name": n, "args": {}} for n in new)
        messages.append({"role": "assistant", "content": text})
        messages.append({"role": "user", "content": f"Queued: {', '.join(new)}. Call any other tools that apply, or reply DONE."})
    return calls, True


if __name__ == "__main__":
    observed = '[[\n\n{\n  "name": "create_gmail_draft",\n  "parameters": {}\n}\n]'  # real reply from a free provider
    assert _TEXT_TOOL_NAME.findall(observed) == ["create_gmail_draft"]
    assert _TEXT_TOOL_NAME.findall('DONE') == []
    print("llm text tool-call parser self-check passed")
