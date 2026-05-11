"""
Mac Deep Cleaner v1.2.0 — Self-Update
===================================
Checks PyPI for a newer version and upgrades the package in-place using pip.

Usage (CLI):
    mac-cleaner update            # check and prompt
    mac-cleaner update --yes      # upgrade without prompting
    mac-cleaner update --check    # check only, print result, exit 0/1

Design
------
- Does a lightweight HEAD request to the PyPI JSON API:
    https://pypi.org/pypi/mac-deep-cleaner/json
- Compares the 'info.version' field against the running __version__.
- Uses `packaging.version.Version` for correct PEP 440 comparison,
  with a plain tuple fallback if packaging is not installed.
- Upgrades via: sys.executable -m pip install --upgrade mac-deep-cleaner
"""

from __future__ import annotations

import logging
import subprocess
import sys
import urllib.error
import urllib.request
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

PYPI_URL = "https://pypi.org/pypi/mac-deep-cleaner/json"
PACKAGE_NAME = "mac-deep-cleaner"
REQUEST_TIMEOUT = 10  # seconds


# ── Version helpers ────────────────────────────────────────────────────────────

def _parse_version(v: str) -> Tuple[int, ...]:
    """Parse a version string into a comparable tuple."""
    try:
        from packaging.version import Version
        pv = Version(v)
        return (pv.major, pv.minor, pv.micro)
    except Exception:
        # Fallback: split on '.' and cast to int
        parts = []
        for segment in v.split(".")[:3]:
            try:
                parts.append(int("".join(c for c in segment if c.isdigit()) or "0"))
            except ValueError:
                parts.append(0)
        return tuple(parts)


def _is_newer(remote: str, local: str) -> bool:
    return _parse_version(remote) > _parse_version(local)


# ── PyPI query ─────────────────────────────────────────────────────────────────

def fetch_latest_version() -> Optional[str]:
    """
    Query PyPI and return the latest stable version string, or None on error.
    """
    import json

    try:
        req = urllib.request.Request(
            PYPI_URL,
            headers={"User-Agent": f"mac-deep-cleaner/5.0 (self-update)"},
        )
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            data = json.loads(resp.read().decode())
        return data["info"]["version"]
    except (urllib.error.URLError, KeyError, ValueError, OSError) as exc:
        logger.debug("PyPI request failed: %s", exc)
        return None


# ── Update check ───────────────────────────────────────────────────────────────

def check_for_update(current_version: str) -> Tuple[bool, Optional[str]]:
    """
    Check if a newer version is available on PyPI.

    Returns:
        (update_available, latest_version_string)
        latest_version_string is None if PyPI is unreachable.
    """
    latest = fetch_latest_version()
    if latest is None:
        return False, None
    return _is_newer(latest, current_version), latest


# ── Upgrade ────────────────────────────────────────────────────────────────────

def perform_upgrade(latest_version: Optional[str] = None) -> Tuple[bool, str]:
    """
    Upgrade mac-deep-cleaner via pip using the current Python interpreter.

    Args:
        latest_version: If provided, pin to this version (e.g. "5.1.0").
                        If None, installs the latest available.

    Returns:
        (success, message)
    """
    target = f"{PACKAGE_NAME}=={latest_version}" if latest_version else PACKAGE_NAME
    cmd = [sys.executable, "-m", "pip", "install", "--upgrade", target]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            return True, result.stdout.strip() or f"Successfully upgraded to {latest_version}"
        return False, result.stderr.strip() or "pip upgrade failed"
    except subprocess.TimeoutExpired:
        logger.debug("pip upgrade timed out")
        return False, "Upgrade timed out after 120 seconds"
    except OSError as e:
        logger.debug("pip upgrade failed: %s", e)
        return False, str(e)
