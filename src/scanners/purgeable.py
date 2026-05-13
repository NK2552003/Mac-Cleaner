"""Purgeable space scanner and reclaim helpers."""

from __future__ import annotations

import logging
import plistlib
import subprocess
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Tuple

from core.apfs_snapshots import delete_snapshot, list_snapshots, select_snapshots_to_delete
from utils import bytes_human

logger = logging.getLogger(__name__)


@dataclass
class PurgeableSource:
    """One purgeable space source."""
    name: str
    detail: str
    bytes: int = 0
    actionable: bool = False

    @property
    def size_human(self) -> str:
        return bytes_human(self.bytes)


@dataclass
class ThinResult:
    """Result of tmutil thinlocalsnapshots."""
    success: bool
    message: str
    stdout: str = ""
    stderr: str = ""


def _run_diskutil_info(volume: str, runner=subprocess.run) -> Optional[dict]:
    try:
        result = runner(
            ["diskutil", "info", "-plist", volume],
            capture_output=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.debug("diskutil info failed: %s", exc)
        return None
    if result.returncode != 0:
        return None
    try:
        return plistlib.loads(result.stdout)
    except (ValueError, plistlib.InvalidFileException) as exc:
        logger.debug("plist parse failed: %s", exc)
        return None


def _find_purgeable_bytes(info: dict) -> Optional[int]:
    for key in ("PurgeableSpace", "PurgeableSpaceTotal", "PurgeableSpaceFree"):
        value = info.get(key)
        if isinstance(value, (int, float)):
            return int(value)
    for key, value in info.items():
        if "Purgeable" in str(key) and isinstance(value, (int, float)):
            return int(value)
    return None


def collect_purgeable_sources(volume: str = "/") -> List[PurgeableSource]:
    """Collect purgeable space sources for a volume."""
    sources: List[PurgeableSource] = []

    info = _run_diskutil_info(volume)
    if info:
        purgeable = _find_purgeable_bytes(info)
        if purgeable is not None:
            sources.append(PurgeableSource(
                name="APFS purgeable",
                detail=f"diskutil info {volume}",
                bytes=purgeable,
                actionable=False,
            ))

    snapshots = list_snapshots(volume)
    if snapshots:
        ordered = [s for s in snapshots if s.created_at is not None]
        oldest = min((s.created_at for s in ordered if s.created_at), default=None)
        oldest_str = oldest.strftime("%Y-%m-%d") if oldest else "unknown"
        sources.append(PurgeableSource(
            name="Local Time Machine snapshots",
            detail=f"{len(snapshots)} snapshot(s), oldest {oldest_str}",
            bytes=0,
            actionable=True,
        ))
    else:
        sources.append(PurgeableSource(
            name="Local Time Machine snapshots",
            detail="none found",
            bytes=0,
            actionable=False,
        ))

    return sources


def thin_local_snapshots(
    volume: str,
    target_bytes: int,
    urgency: int = 4,
    runner=subprocess.run,
) -> ThinResult:
    """Ask tmutil to reclaim purgeable space by thinning snapshots."""
    if target_bytes <= 0:
        return ThinResult(False, "target bytes must be > 0")

    try:
        result = runner(
            ["tmutil", "thinlocalsnapshots", volume, str(target_bytes), str(urgency)],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return ThinResult(False, f"tmutil thinlocalsnapshots failed: {exc}")

    if result.returncode == 0:
        return ThinResult(True, "thinning completed", result.stdout, result.stderr)
    return ThinResult(False, "thinning failed", result.stdout, result.stderr)


def delete_snapshots_by_policy(
    volume: str,
    keep: Optional[int] = None,
    older_than_days: Optional[int] = None,
) -> Tuple[int, int]:
    """Delete snapshots according to keep or age policy.

    Returns:
        (deleted_count, total_candidates)
    """
    snapshots = list_snapshots(volume)
    targets = select_snapshots_to_delete(
        snapshots,
        keep=keep,
        older_than_days=older_than_days,
    )
    deleted = 0
    for snap in targets:
        if delete_snapshot(snap):
            deleted += 1
    return deleted, len(targets)


def summarize_sources(sources: List[PurgeableSource]) -> dict:
    """Return a JSON-friendly summary."""
    total = sum(s.bytes for s in sources if s.bytes > 0)
    return {
        "generated_at": datetime.now().isoformat(),
        "total_purgeable_bytes": total,
        "total_purgeable_human": bytes_human(total),
        "sources": [
            {
                "name": s.name,
                "detail": s.detail,
                "bytes": s.bytes,
                "size_human": s.size_human,
                "actionable": s.actionable,
            }
            for s in sources
        ],
    }
