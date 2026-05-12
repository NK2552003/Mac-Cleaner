"""Spotlight indexing helpers."""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class SpotlightStatus:
    """Spotlight status for a volume."""
    volume: str
    enabled: Optional[bool]
    raw: str


def get_spotlight_status(volume: str = "/", runner=subprocess.run) -> SpotlightStatus:
    """Return Spotlight indexing status for a volume."""
    try:
        result = runner(
            ["mdutil", "-s", volume],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.debug("mdutil status failed: %s", exc)
        return SpotlightStatus(volume=volume, enabled=None, raw=str(exc))

    text = result.stdout.strip() or result.stderr.strip()
    enabled: Optional[bool]
    if "indexing enabled" in text.lower():
        enabled = True
    elif "indexing and searching disabled" in text.lower():
        enabled = False
    else:
        enabled = None

    return SpotlightStatus(volume=volume, enabled=enabled, raw=text)


def set_spotlight_indexing(
    volume: str,
    enabled: bool,
    runner=subprocess.run,
) -> bool:
    """Enable or disable Spotlight indexing."""
    flag = "on" if enabled else "off"
    try:
        result = runner(
            ["mdutil", "-i", flag, volume],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.debug("mdutil set failed: %s", exc)
        return False


def reindex_spotlight(volume: str = "/", runner=subprocess.run) -> bool:
    """Rebuild Spotlight index for the given volume."""
    if not set_spotlight_indexing(volume, True, runner=runner):
        return False
    try:
        result = runner(
            ["mdutil", "-E", volume],
            capture_output=True,
            text=True,
            timeout=120,
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.debug("mdutil reindex failed: %s", exc)
        return False
