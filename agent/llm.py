"""
Thin wrapper around OpenRouter's OpenAI-compatible chat completions API.

Defaults to a free, open-source model (Llama 3.3 70B Instruct — OpenRouter's
most established free pick, stable since Dec 2024). If OPENROUTER_API_KEY
is not set, or a live call fails for any reason (free-tier rate limit hit
mid-demo, a model getting pulled from the free tier, network hiccup, etc.),
this falls back to a deterministic, rule-based "mock LLM" so the rest of
the pipeline still runs end-to-end. This makes the app runnable out of the
box with zero setup, and gives you an offline safety net during judging.
"""
import json
import os
import re

import requests

_API_URL = "https://openrouter.ai/api/v1/chat/completions"
_DEFAULT_MODEL = "meta-llama/llama-3.3-70b-instruct:free"
_TIMEOUT_SECONDS = 45


def _model_name() -> str:
    return os.getenv("OPENROUTER_MODEL", _DEFAULT_MODEL)


def _api_key() -> str:
    return os.getenv("OPENROUTER_API_KEY", "").strip()


def is_live() -> bool:
    """Whether calls will hit the real OpenRouter API (vs. the offline mock)."""
    key = _api_key()
    return bool(key) and key != "your_openrouter_api_key_here"


def call_json(prompt: str, mock_fn) -> tuple[dict, bool]:
    """
    Call OpenRouter asking for a strict JSON response. Falls back to
    mock_fn() (a zero-arg callable returning a dict) if no key is
    configured or the call/parse fails for any reason.

    Returns (result_dict, used_live_llm: bool).
    """
    if not is_live():
        return mock_fn(), False

    try:
        headers = {
            "Authorization": f"Bearer {_api_key()}",
            "Content-Type": "application/json",
            # OpenRouter asks apps to identify themselves; any value is fine.
            "HTTP-Referer": "https://github.com/ai-job-application-agent",
            "X-Title": "AI Job Application Agent",
        }
        body = {
            "model": _model_name(),
            "messages": [
                {
                    "role": "system",
                    "content": "You return ONLY valid JSON. No markdown fences, no commentary, no preamble.",
                },
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
    except Exception as exc:  # noqa: BLE001 - demo-safe fallback
        print(f"[llm] Live OpenRouter call failed, falling back to mock: {exc}")
        return mock_fn(), False
