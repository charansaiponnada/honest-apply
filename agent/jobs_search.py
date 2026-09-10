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
import re

import requests

_TIMEOUT_SECONDS = 15
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


def search_jobs(keyword: str, remote_only: bool = False, limit: int = 8) -> tuple[list[dict], str | None]:
    """
    Searches all three sources and merges the results (best-effort — a
    failure in one source doesn't block the others).

    Returns (jobs, error). jobs is a list of dicts with:
    {source, title, company_name, location, remote, description, url, tags}
    error is None if at least one source returned results; otherwise a
    short human-readable summary of what went wrong.
    """
    keyword_lower = keyword.strip().lower()
    per_source_limit = max(2, limit // len(_SOURCES) + 1)

    all_jobs: list[dict] = []
    failures: list[str] = []

    for name, fn in _SOURCES.items():
        try:
            all_jobs.extend(fn(keyword_lower, remote_only, per_source_limit))
        except Exception as exc:  # noqa: BLE001 - one bad source shouldn't sink the search
            failures.append(f"{name}: {exc}")

    all_jobs = all_jobs[:limit]

    if not all_jobs:
        if failures:
            return [], f"All job sources failed or returned nothing: {'; '.join(failures)}"
        return [], f"No live listings matched '{keyword}' right now — try a broader keyword, or paste a JD manually."

    error = f"Some sources unavailable ({'; '.join(failures)})" if failures else None
    return all_jobs, error
