"""Data breach monitoring via Have I Been Pwned API."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional

from constants import CONFIG_DIR

HIBP_API_BASE = "https://haveibeenpwned.com/api/v3/breachedaccount"
WATCHLIST_FILE = CONFIG_DIR / "breach_watchlist.json"
DEFAULT_USER_AGENT = "mac-cleaner/1.2.0"
DEFAULT_MIN_DELAY = 1.6


@dataclass
class BreachResult:
    """Result for one email address."""
    email: str
    breached: bool
    breaches: List[dict] = field(default_factory=list)
    error: Optional[str] = None
    checked_at: str = field(default_factory=lambda: datetime.now().isoformat())
    status_code: Optional[int] = None
    retry_after: Optional[int] = None


def _build_request(email: str, api_key: str) -> urllib.request.Request:
    url = f"{HIBP_API_BASE}/{urllib.parse.quote(email)}?truncateResponse=true"
    return urllib.request.Request(
        url,
        headers={
            "hibp-api-key": api_key,
            "user-agent": DEFAULT_USER_AGENT,
        },
    )


def parse_breach_response(payload: str) -> List[dict]:
    """Parse HIBP response JSON into a list."""
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return []
    if isinstance(data, list):
        return data
    return []


def check_email(email: str, api_key: str) -> BreachResult:
    """Check a single email using the HIBP API."""
    if not api_key:
        return BreachResult(email=email, breached=False, error="HIBP API key missing")

    req = _build_request(email, api_key)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8")
            breaches = parse_breach_response(body)
            return BreachResult(email=email, breached=bool(breaches), breaches=breaches, status_code=resp.status)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return BreachResult(email=email, breached=False, status_code=exc.code)
        if exc.code in (401, 403):
            return BreachResult(email=email, breached=False, error="Invalid API key", status_code=exc.code)
        if exc.code == 429:
            retry = exc.headers.get("Retry-After") if exc.headers else None
            retry_after = int(retry) if retry and retry.isdigit() else None
            message = "Rate limited by HIBP"
            if retry_after is not None:
                message = f"Rate limited by HIBP (retry after {retry_after}s)"
            return BreachResult(
                email=email,
                breached=False,
                error=message,
                status_code=exc.code,
                retry_after=retry_after,
            )
        return BreachResult(email=email, breached=False, error=f"HTTP {exc.code}", status_code=exc.code)
    except (urllib.error.URLError, OSError) as exc:
        return BreachResult(email=email, breached=False, error=str(exc))


def check_emails(
    emails: Iterable[str],
    api_key: str,
    min_delay: float = DEFAULT_MIN_DELAY,
) -> List[BreachResult]:
    """Check multiple emails with basic rate limiting."""
    results: List[BreachResult] = []
    email_list = list(emails)
    for idx, email in enumerate(email_list):
        results.append(check_email(email, api_key))
        if idx >= len(email_list) - 1:
            continue
        delay = max(min_delay, 0)
        last = results[-1]
        if last.status_code == 429 and last.retry_after:
            delay = max(delay, float(last.retry_after))
        if delay > 0:
            time.sleep(delay)
    return results


def load_watchlist(path: Path = WATCHLIST_FILE) -> List[str]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return []
    emails = data.get("emails", [])
    return [str(e) for e in emails if isinstance(e, str)]


def save_watchlist(emails: List[str], path: Path = WATCHLIST_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at": datetime.now().isoformat(),
        "emails": sorted(set(emails)),
    }
    path.write_text(json.dumps(payload, indent=2))


def resolve_api_key(explicit: Optional[str] = None) -> Optional[str]:
    return explicit or os.environ.get("HIBP_API_KEY")
