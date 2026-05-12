"""Storage trend tracker for disk usage snapshots."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, List, Optional

from constants import CONFIG_DIR
from utils import bytes_human

TREND_FILE = CONFIG_DIR / "storage_trend.json"
MAX_ENTRIES = 180


@dataclass
class StorageSnapshot:
    """One storage usage snapshot for a volume."""
    timestamp: str
    volume: str
    total_bytes: int
    used_bytes: int
    free_bytes: int

    @property
    def total_human(self) -> str:
        return bytes_human(self.total_bytes)

    @property
    def used_human(self) -> str:
        return bytes_human(self.used_bytes)

    @property
    def free_human(self) -> str:
        return bytes_human(self.free_bytes)

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "volume": self.volume,
            "total_bytes": self.total_bytes,
            "used_bytes": self.used_bytes,
            "free_bytes": self.free_bytes,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "StorageSnapshot":
        return cls(
            timestamp=data["timestamp"],
            volume=data.get("volume", "/"),
            total_bytes=int(data["total_bytes"]),
            used_bytes=int(data["used_bytes"]),
            free_bytes=int(data["free_bytes"]),
        )


@dataclass
class TrendSummary:
    """Summary statistics for a collection of snapshots."""
    start: StorageSnapshot
    end: StorageSnapshot
    delta_used: int
    delta_free: int
    days: int

    @property
    def delta_used_human(self) -> str:
        return bytes_human(abs(self.delta_used))

    @property
    def delta_free_human(self) -> str:
        return bytes_human(abs(self.delta_free))


def record_snapshot(
    volume: Path = Path("/"),
    disk_usage=shutil.disk_usage,
) -> StorageSnapshot:
    """Capture a snapshot for the given volume."""
    usage = disk_usage(str(volume))
    return StorageSnapshot(
        timestamp=datetime.now().isoformat(),
        volume=str(volume),
        total_bytes=int(usage.total),
        used_bytes=int(usage.used),
        free_bytes=int(usage.free),
    )


def load_snapshots(
    trend_path: Path = TREND_FILE,
    volume: Optional[str] = None,
) -> List[StorageSnapshot]:
    if not trend_path.exists():
        return []
    try:
        data = json.loads(trend_path.read_text())
    except (json.JSONDecodeError, OSError):
        return []
    snapshots = [StorageSnapshot.from_dict(d) for d in data.get("snapshots", [])]
    if volume:
        snapshots = [s for s in snapshots if s.volume == volume]
    return sorted(snapshots, key=lambda s: s.timestamp)


def append_snapshot(
    snapshot: StorageSnapshot,
    trend_path: Path = TREND_FILE,
    max_entries: int = MAX_ENTRIES,
) -> List[StorageSnapshot]:
    """Append a snapshot and persist to disk. Returns full list."""
    existing = load_snapshots(trend_path)
    existing.append(snapshot)
    existing = sorted(existing, key=lambda s: s.timestamp)

    grouped: dict[str, List[StorageSnapshot]] = {}
    for snap in existing:
        grouped.setdefault(snap.volume, []).append(snap)

    trimmed: List[StorageSnapshot] = []
    for volume, snaps in grouped.items():
        snaps = sorted(snaps, key=lambda s: s.timestamp)
        if len(snaps) > max_entries:
            snaps = snaps[-max_entries:]
        trimmed.extend(snaps)

    existing = sorted(trimmed, key=lambda s: s.timestamp)

    payload = {
        "generated_at": datetime.now().isoformat(),
        "snapshots": [s.to_dict() for s in existing],
    }
    trend_path.parent.mkdir(parents=True, exist_ok=True)
    trend_path.write_text(json.dumps(payload, indent=2))
    return existing


def summarize_trend(
    snapshots: Iterable[StorageSnapshot],
    days: Optional[int] = None,
) -> Optional[TrendSummary]:
    """Return a summary across a time range."""
    items = list(sorted(snapshots, key=lambda s: s.timestamp))
    if not items:
        return None

    if days is not None and days > 0:
        cutoff = datetime.now() - timedelta(days=days)
        items = [s for s in items if datetime.fromisoformat(s.timestamp) >= cutoff]
        if not items:
            return None

    start = items[0]
    end = items[-1]
    delta_used = end.used_bytes - start.used_bytes
    delta_free = end.free_bytes - start.free_bytes

    span_days = (
        datetime.fromisoformat(end.timestamp)
        - datetime.fromisoformat(start.timestamp)
    ).days

    return TrendSummary(
        start=start,
        end=end,
        delta_used=delta_used,
        delta_free=delta_free,
        days=max(span_days, 0),
    )
