"""Time Machine backup guard helpers."""

from __future__ import annotations

import logging
import plistlib
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from core.apfs_snapshots import list_snapshots

logger = logging.getLogger(__name__)

_BACKUP_RE = re.compile(r"(\d{4}-\d{2}-\d{2}-\d{6})")


@dataclass
class TimeMachineStatus:
    """Summary of Time Machine status."""
    destinations: List[str] = field(default_factory=list)
    last_backup: Optional[str] = None
    last_backup_age_days: Optional[int] = None
    is_running: Optional[bool] = None
    local_snapshot_count: int = 0
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "destinations": self.destinations,
            "last_backup": self.last_backup,
            "last_backup_age_days": self.last_backup_age_days,
            "is_running": self.is_running,
            "local_snapshot_count": self.local_snapshot_count,
            "errors": self.errors,
        }


def _run(args: List[str], timeout: int = 20) -> subprocess.CompletedProcess:
    return subprocess.run(
        args,
        capture_output=True,
        text=False,
        timeout=timeout,
    )


def _parse_latest_backup(path: str) -> Optional[int]:
    match = _BACKUP_RE.search(path)
    if not match:
        return None
    token = match.group(1)
    try:
        stamp = datetime.strptime(token, "%Y-%m-%d-%H%M%S")
    except ValueError:
        return None
    return (datetime.now() - stamp).days


def get_time_machine_status() -> TimeMachineStatus:
    status = TimeMachineStatus()

    # Destinations
    try:
        result = _run(["tmutil", "destinationinfo", "-plist"], timeout=20)
        if result.returncode == 0:
            pl = plistlib.loads(result.stdout)
            dests = pl.get("Destinations", [])
            for d in dests:
                name = d.get("DestinationName") or d.get("MountPoint") or d.get("ID")
                if name:
                    status.destinations.append(str(name))
        else:
            status.errors.append("tmutil destinationinfo failed")
    except Exception as exc:
        logger.debug("destinationinfo failed: %s", exc)
        status.errors.append("tmutil destinationinfo failed")

    # Running status
    try:
        result = _run(["tmutil", "status", "-plist"], timeout=10)
        if result.returncode == 0:
            pl = plistlib.loads(result.stdout)
            status.is_running = bool(pl.get("Running", False))
    except Exception as exc:
        logger.debug("tmutil status failed: %s", exc)

    # Latest backup
    try:
        latest = subprocess.run(
            ["tmutil", "latestbackup"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if latest.returncode == 0:
            path = latest.stdout.strip()
            status.last_backup = path
            status.last_backup_age_days = _parse_latest_backup(path)
    except (OSError, subprocess.TimeoutExpired):
        pass

    # Local snapshots
    status.local_snapshot_count = len(list_snapshots("/"))

    return status


def enable_time_machine() -> tuple[bool, str]:
    try:
        result = subprocess.run(
            ["tmutil", "enable"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return True, "Time Machine enabled"
        return False, result.stderr.strip() or "tmutil enable failed"
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)


def disable_time_machine() -> tuple[bool, str]:
    try:
        result = subprocess.run(
            ["tmutil", "disable"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return True, "Time Machine disabled"
        return False, result.stderr.strip() or "tmutil disable failed"
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)
