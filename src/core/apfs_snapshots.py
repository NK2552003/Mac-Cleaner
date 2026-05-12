"""APFS snapshot listing and pruning helpers."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional


_TMUTIL_RE = re.compile(
    r"com\.apple\.TimeMachine\.(\d{4}-\d{2}-\d{2}-\d{6})\.local"
)


@dataclass
class Snapshot:
    """One APFS local snapshot entry."""
    name: str
    token: str
    created_at: Optional[datetime]


def parse_tmutil_output(output: str) -> List[Snapshot]:
    """Parse tmutil listlocalsnapshots output."""
    snapshots: List[Snapshot] = []
    for line in output.splitlines():
        match = _TMUTIL_RE.search(line)
        if match:
            token = match.group(1)
            created_at = None
            try:
                created_at = datetime.strptime(token, "%Y-%m-%d-%H%M%S")
            except ValueError:
                created_at = None
            name = f"com.apple.TimeMachine.{token}.local"
            snapshots.append(Snapshot(name=name, token=token, created_at=created_at))
    return snapshots


def list_snapshots(
    volume: str = "/",
    runner=subprocess.run,
) -> List[Snapshot]:
    """List local APFS snapshots for a volume using tmutil."""
    try:
        result = runner(
            ["tmutil", "listlocalsnapshots", volume],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []

    if result.returncode != 0:
        return []

    return parse_tmutil_output(result.stdout)


def select_snapshots_to_delete(
    snapshots: List[Snapshot],
    keep: Optional[int] = None,
    older_than_days: Optional[int] = None,
) -> List[Snapshot]:
    """Select snapshots to delete based on age or keep count."""
    ordered = sorted(
        [s for s in snapshots if s.created_at is not None],
        key=lambda s: s.created_at,
    )
    if not ordered:
        return []

    to_delete: List[Snapshot] = []

    if older_than_days is not None and older_than_days > 0:
        cutoff = datetime.now() - timedelta(days=older_than_days)
        for snap in ordered:
            if snap.created_at and snap.created_at < cutoff:
                to_delete.append(snap)

    if keep is not None and keep >= 0:
        excess = len(ordered) - keep
        if excess > 0:
            to_delete.extend(ordered[:excess])

    unique = {s.name: s for s in to_delete}
    return list(unique.values())


def delete_snapshot(
    snapshot: Snapshot,
    runner=subprocess.run,
) -> bool:
    """Delete a snapshot by token using tmutil."""
    try:
        result = runner(
            ["tmutil", "deletelocalsnapshots", snapshot.token],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False

    return result.returncode == 0
