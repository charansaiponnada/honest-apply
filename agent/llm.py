"""
Thin wrapper around OpenRouter's OpenAI-compatible chat completions API.

Defaults to the best free model on OpenRouter as of Sept 2026 for structured
JSON output: NVIDIA Nemotron 3 Super 120B (validated live — extract/tailoring
JSON in ~5s, 262k context). If OPENROUTER_API_KEY is not set, or live calls
keep failing (free-tier rate limit, a model getting pulled from the free
tier, network hiccup, etc.), this falls back to a deterministic, rule-based
"mock LLM" so the rest of the pipeline still runs end-to-end.

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

_API_URL = "https://openrouter.ai/api/v1/chat/completions"
_DEFAULT_MODEL = "nvidia/nemotron-3-super-120b-a12b:free"
_TIMEOUT_SECONDS = 90
_MAX_RETRIES = 3

# Each named agent gets its own system prompt so the LLM holds a distinct
# persona per stage. "executor" is the orchestrator stage: it receives the
# artifacts from the first two agents and decides/acts on them.
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
        "that are not already in the original resume."
    ),
    "executor": (
        "You are the Executor agent of an AI job-application team. You receive a "
        "candidate's tailored application and decide whether it should proceed to "
        "external apps (Gmail/Sheets/Calendar/Drive) or be flagged for human review, "
        "based on how well the resume actually covers the job's requirements."
    ),
}

_ALWAYS_JSON = ". You return ONLY valid JSON. No markdown fences, no commentary, no preamble."


def _model_name() -> str:
    return os.getenv("OPENROUTER_MODEL") or _DEFAULT_MODEL


def _api_key() -> str:
    return os.getenv("OPENROUTER_API_KEY", "").strip()


def is_live() -> bool:
    """Whether calls will hit the real OpenRouter API (vs. the offline mock)."""
    key = _api_key()
    return bool(key) and key != "your_openrouter_api_key_here"


def call_json(prompt: str, mock_fn, agent: str = "researcher") -> tuple[dict, bool]:
    """
    Call OpenRouter asking for a strict JSON response. Falls back to
    mock_fn() (a zero-arg callable returning a dict) if no key is
    configured or all retries + the call/parse fail for any reason.

    `agent` selects the system prompt (researcher | tailor | executor) so
    each pipeline stage runs as a distinct named agent.

    Retries up to 3 times on 429 (free-tier rate limit) with exponential
    backoff, since free models are heavily rate-limited on OpenRouter.

    Returns (result_dict, used_live_llm: bool).
    """
    if not is_live():
        return mock_fn(), False

    system = _AGENT_SYSTEM_PROMPTS.get(agent, _AGENT_SYSTEM_PROMPTS["researcher"]) + _ALWAYS_JSON

    last_exc: Exception | None = None
    for attempt in range(_MAX_RETRIES):
        try:
            headers = {
                "Authorization": f"Bearer {_api_key()}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/ai-job-application-agent",
                "X-Title": "AI Job Application Agent",
            }
            body = {
                "model": _model_name(),
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.3,
            }
            resp = requests.post(_API_URL, headers=headers, json=body, timeout=_TIMEOUT_SECONDS)
            resp.raise_for_status()
            data = resp.json()
            text = data["choices"][0]["message"]["content"].strip()
            text = re.sub(r"^```json|```$", "", text, flags=re.MULTILINE).strip()
            return json.loads(text), True
        except requests.exceptions.HTTPError as exc:
            last_exc = exc
            status = getattr(exc.response, "status_code", None) if hasattr(exc, "response") else None
            if status == 429 and attempt < _MAX_RETRIES - 1:
                delay = 2.0 * (2 ** attempt)
                print(f"[llm] 429 rate-limited, retry {attempt+1}/{_MAX_RETRIES} in {delay:.0f}s...")
                time.sleep(delay)
                continue
            print(f"[llm] Live OpenRouter call failed, falling back to mock: {exc}")
            return mock_fn(), False
        except Exception as exc:
            last_exc = exc
            print(f"[llm] Live OpenRouter call failed, falling back to mock: {exc}")
            return mock_fn(), False

    print(f"[llm] All {_MAX_RETRIES} retries exhausted, falling back to mock: {last_exc}")
    return mock_fn(), False
