"""Data breach monitoring via Have I Been Pwned API."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from constants import CONFIG_DIR

HIBP_API_BASE = "https://haveibeenpwned.com/api/v3/breachedaccount"
WATCHLIST_FILE = CONFIG_DIR / "breach_watchlist.json"
DEFAULT_USER_AGENT = "mac-cleaner/1.2.0"


@dataclass
class BreachResult:
    """Result for one email address."""
    email: str
    breached: bool
    breaches: List[dict] = field(default_factory=list)
    error: Optional[str] = None
    checked_at: str = field(default_factory=lambda: datetime.now().isoformat())


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
            return BreachResult(email=email, breached=bool(breaches), breaches=breaches)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return BreachResult(email=email, breached=False)
        if exc.code in (401, 403):
            return BreachResult(email=email, breached=False, error="Invalid API key")
        return BreachResult(email=email, breached=False, error=f"HTTP {exc.code}")
    except (urllib.error.URLError, OSError) as exc:
        return BreachResult(email=email, breached=False, error=str(exc))


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
