"""
Shared reliability helpers used across every external integration
(Google APIs, Slack, the job-board search). Two things live here:

1. retry_with_backoff — retries a call on transient failures (rate limits,
   5xx errors, network hiccups) with exponential backoff + jitter, and
   gives up immediately on non-retryable failures (bad auth, bad request)
   so a broken integration fails fast instead of stalling a live demo.
2. classify_google_error — turns a raw googleapiclient HttpError into a
   short, judge-readable reason ("auth expired", "quota exceeded", etc.)
   instead of a raw stack trace, for the eval log and the UI.
"""
import random
import time


def retry_with_backoff(fn, retries: int = 2, base_delay: float = 0.6, retryable_check=None):
    """
    Call fn() (a zero-arg callable) with retries on transient failures.

    retryable_check(exc) -> bool decides whether a given exception is worth
    retrying. If None, every exception is treated as retryable until the
    last attempt. Re-raises the final exception if all attempts fail.
    """
    last_exc = None
    for attempt in range(retries + 1):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - re-raised below if not retryable
            last_exc = exc
            is_retryable = retryable_check(exc) if retryable_check else True
            if attempt == retries or not is_retryable:
                raise
            delay = base_delay * (2 ** attempt) + random.uniform(0, 0.25)
            time.sleep(delay)
    raise last_exc  # pragma: no cover - unreachable, satisfies type checkers


def is_retryable_google_error(exc: Exception) -> bool:
    """Rate limits and server-side 5xx errors are worth a retry; auth/permission/bad-request are not."""
    try:
        from googleapiclient.errors import HttpError
    except ImportError:
        return isinstance(exc, (TimeoutError, ConnectionError))

    if isinstance(exc, HttpError):
        status = getattr(getattr(exc, "resp", None), "status", None)
        return status in (429, 500, 502, 503)
    return isinstance(exc, (TimeoutError, ConnectionError))


def classify_google_error(exc: Exception) -> str:
    """Human-readable classification of a Google API failure, for logs/UI."""
    try:
        from googleapiclient.errors import HttpError
    except ImportError:
        return str(exc)

    if isinstance(exc, HttpError):
        status = getattr(getattr(exc, "resp", None), "status", None)
        if status == 401:
            return "auth expired — re-run OAuth (delete token.json and retry)"
        if status == 403:
            return "permission denied or quota exceeded for this scope"
        if status == 429:
            return "rate limited — too many requests, retries exhausted"
        if status and status >= 500:
            return f"Google API server error (HTTP {status})"
        if status == 404:
            return "target resource not found (check the ID you passed in)"
        return f"Google API error (HTTP {status}): {exc}"
    return str(exc)
