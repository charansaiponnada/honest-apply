"""
Skill 0 (multi-board search, feeding the pipeline upstream): live job search
across three free, unauthenticated public job-board APIs — no scraping, no
ToS circumvention, nothing that needs a key:

  - Arbeitnow  (https://arbeitnow.com/api/job-board-api)
  - Remotive   (https://remotive.com/api/remote-jobs)
  - RemoteOK   (https://remoteok.com/api)

This deliberately does NOT cover LinkedIn, Indeed, or Glassdoor — all three
explicitly prohibit scraping in their Terms of Service and run active
anti-bot protection to enforce it, so there's no legitimate free/no-key way
to search them programmatically. If a person wants those boards covered,
the honest options are each site's own (paid, approval-gated) partner API,
or applying manually.

Each source is queried independently and wrapped so one source failing
(rate limit, outage, schema change) never blocks the other two — you just
get results from whichever sources answered, plus a note about which
failed, rather than the whole search silently returning nothing.
"""
import json
import os
import re

import requests

from agent import DATA_DIR

_TIMEOUT_SECONDS = 15
# Local record of job URLs already seen, so refreshes can flag genuinely new
# postings (the "scraper picks up new listings" behavior) instead of re-showing
# the whole pool as new every time.
_SEEN_CACHE = os.path.join(DATA_DIR, "job_seen.json")
_TAG_RE = re.compile(r"<[^>]+>")
# RemoteOK blocks generic default User-Agents; a normal-looking browser UA is
# required to get real results back instead of an empty/blocked response.
_REMOTEOK_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; AIJobApplicationAgent/1.0; "
        "+https://github.com/ai-job-application-agent)"
    )
}


def _strip_html(text: str) -> str:
    """Job-board descriptions are HTML; extraction/tailoring prompts want plain text."""
    text = _TAG_RE.sub(" ", text or "")
    return re.sub(r"\s+", " ", text).strip()


def _load_seen() -> set[str]:
    if not os.path.exists(_SEEN_CACHE):
        return set()
    try:
        with open(_SEEN_CACHE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    except (json.JSONDecodeError, ValueError, OSError):
        return set()


def _save_seen(urls: set[str]) -> None:
    os.makedirs(os.path.dirname(_SEEN_CACHE), exist_ok=True)
    with open(_SEEN_CACHE, "w", encoding="utf-8") as f:
        json.dump(sorted(urls), f, indent=2)


def _posted(job: dict) -> str:
    """Best-effort posting date as %Y-%m-%d ('' if the source doesn't provide one)."""
    for key in ("created_at", "publication_date", "date"):
        raw = job.get(key)
        if raw:
            return str(raw)[:10]
    return ""


def _matches(keyword_lower: str, *fields: str) -> bool:
    if not keyword_lower:
        return True
    haystack = " ".join(f or "" for f in fields).lower()
    return keyword_lower in haystack


def _search_arbeitnow(keyword_lower: str, remote_only: bool, limit: int) -> list[dict]:
    resp = requests.get("https://arbeitnow.com/api/job-board-api", timeout=_TIMEOUT_SECONDS)
    resp.raise_for_status()
    listings = resp.json().get("data", [])

    out = []
    for job in listings:
        if remote_only and not job.get("remote"):
            continue
        if not _matches(keyword_lower, job.get("title", ""), job.get("company_name", ""), " ".join(job.get("tags", []) or [])):
            continue
        out.append(
            {
                "source": "Arbeitnow",
                "title": job.get("title", "Untitled role"),
                "company_name": job.get("company_name", "Unknown company"),
                "location": job.get("location", ""),
                "remote": bool(job.get("remote")),
                "posted": _posted(job),
                "description": _strip_html(job.get("description", "")),
                "url": job.get("url", ""),
                "tags": job.get("tags", []) or [],
            }
        )
        if len(out) >= limit:
            break
    return out


def _search_remotive(keyword_lower: str, remote_only: bool, limit: int) -> list[dict]:
    # Remotive is remote-only by nature; the API supports server-side search.
    resp = requests.get(
        "https://remotive.com/api/remote-jobs",
        params={"search": keyword_lower, "limit": limit} if keyword_lower else {"limit": limit},
        timeout=_TIMEOUT_SECONDS,
    )
    resp.raise_for_status()
    listings = resp.json().get("jobs", [])

    out = []
    for job in listings[:limit]:
        out.append(
            {
                "source": "Remotive",
                "title": job.get("title", "Untitled role"),
                "company_name": job.get("company_name", "Unknown company"),
                "location": job.get("candidate_required_location", "Remote"),
                "remote": True,
                "posted": _posted(job),
                "description": _strip_html(job.get("description", "")),
                "url": job.get("url", ""),
                "tags": job.get("tags", []) or [],
            }
        )
    return out


def _search_remoteok(keyword_lower: str, remote_only: bool, limit: int) -> list[dict]:
    resp = requests.get("https://remoteok.com/api", headers=_REMOTEOK_HEADERS, timeout=_TIMEOUT_SECONDS)
    resp.raise_for_status()
    listings = resp.json()
    # First element is a legal-notice record, not a job.
    listings = [j for j in listings if isinstance(j, dict) and j.get("position")]

    out = []
    for job in listings:
        if not _matches(keyword_lower, job.get("position", ""), job.get("company", ""), " ".join(job.get("tags", []) or [])):
            continue
        out.append(
            {
                "source": "RemoteOK",
                "title": job.get("position", "Untitled role"),
                "company_name": job.get("company", "Unknown company"),
                "location": job.get("location", "Remote"),
                "remote": True,
                "posted": _posted(job),
                "description": _strip_html(job.get("description", "")),
                "url": job.get("url") or job.get("apply_url", ""),
                "tags": job.get("tags", []) or [],
            }
        )
        if len(out) >= limit:
            break
    return out


_SOURCES = {
    "Arbeitnow": _search_arbeitnow,
    "Remotive": _search_remotive,
    "RemoteOK": _search_remoteok,
}


def fetch_pool(limit: int = 60, remote_only: bool = False, keyword: str = "") -> tuple[list[dict], str | None]:
    """
    Fetches a pooled batch of recent listings across all sources, dedupes by
    URL, sorts newest-first, and marks each listing with `is_new` = True if its
    URL hasn't been seen before (tracked in _SEEN_CACHE). This is the
    "scraper" behavior: calling it again later surfaces freshly-posted jobs.

    Returns (jobs, error) with the same error semantics as search_jobs.
    """
    keyword_lower = keyword.strip().lower()
    per_source_limit = max(10, limit // len(_SOURCES))

    all_jobs: list[dict] = []
    failures: list[str] = []

    for name, fn in _SOURCES.items():
        try:
            all_jobs.extend(fn(keyword_lower, remote_only, per_source_limit))
        except Exception as exc:  # noqa: BLE001 - one bad source shouldn't sink the search
            failures.append(f"{name}: {exc}")

    seen = _load_seen()
    by_url: dict[str, dict] = {}
    for job in all_jobs:
        key = job.get("url") and f"{job['source']}@{job['url']}"
        if not key or key in by_url:
            continue
        job["is_new"] = job["url"] not in seen
        by_url[key] = job

    jobs = sorted(by_url.values(), key=lambda j: j.get("posted") or "", reverse=True)[:limit]

    if not jobs:
        if failures:
            return [], f"All job sources failed or returned nothing: {'; '.join(failures)}"
        return [], "No live listings matched right now — try a broader keyword, or paste a JD manually."

    error = f"Some sources unavailable ({'; '.join(failures)})" if failures else None
    return jobs, error


def mark_seen(jobs: list[dict]) -> None:
    """Records the given listings' URLs as seen, so future pools flag them as old."""
    if not jobs:
        return
    seen = _load_seen()
    seen.update(j["url"] for j in jobs if j.get("url"))
    _save_seen(seen)


def search_jobs(keyword: str, remote_only: bool = False, limit: int = 8) -> tuple[list[dict], str | None]:
    """
    Thin wrapper over fetch_pool kept for scripts/tests compatibility.
    Returns (jobs, error) — see fetch_pool.
    """
    return fetch_pool(limit=limit, remote_only=remote_only, keyword=keyword)
