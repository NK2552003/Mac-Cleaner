"""
Mac Deep Cleaner v1.5.0 — Scan History & Diff
==========================================
Stores past scan results in ~/.config/mac-cleaner/history/ as JSON files.
Allows comparing two scans to show what's new or resolved since the last run.

Storage format
--------------
Each scan is stored as <timestamp>_<uuid8>.json with this schema:

{
  "schema_version": 2,
  "scan_id":        "abc12345",
  "scanned_at":     "2024-01-15T10:30:00",
  "profile":        "developer",          // optional
  "orphans": {
    "Slack": {
      "total_size": 123456,
      "items": [{"path": "...", "reason": "...", "size": 123}]
    }
  },
  "junk": [
    {"path": "...", "category": "User Cache", "size": 123}
  ],
    "dev_junk": [
        {"path": "...", "category": "Node Modules", "size": 123}
    ],
  "summary": {
    "orphan_count": 3,
    "orphan_bytes": 456789,
        "junk_count": 12,
        "junk_bytes": 987654,
        "dev_junk_count": 5,
        "dev_junk_bytes": 55555
  }
}
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from utils import bytes_human

# ── Paths ──────────────────────────────────────────────────────────────────────

HISTORY_DIR = Path.home() / ".config" / "mac-cleaner" / "history"
SCHEMA_VERSION = 3
MAX_HISTORY_ENTRIES = 100   # prune oldest beyond this


def _ensure_history_dir() -> None:
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)


# ── Data models ────────────────────────────────────────────────────────────────

@dataclass
class ScanRecord:
    """A single historical scan result."""
    scan_id: str
    scanned_at: datetime
    profile: Optional[str]
    orphans: Dict[str, Any]   # name → {total_size, items:[]}
    junk: List[Dict[str, Any]]
    dev_junk: List[Dict[str, Any]]
    summary: Dict[str, Any]

    @property
    def file_path(self) -> Path:
        ts = self.scanned_at.strftime("%Y%m%d_%H%M%S")
        return HISTORY_DIR / f"{ts}_{self.scan_id[:8]}.json"

    @property
    def orphan_bytes(self) -> int:
        return int(self.summary.get("orphan_bytes", 0))

    @property
    def junk_bytes(self) -> int:
        return int(self.summary.get("junk_bytes", 0))

    @property
    def dev_junk_bytes(self) -> int:
        return int(self.summary.get("dev_junk_bytes", 0))

    @property
    def total_bytes(self) -> int:
        return self.orphan_bytes + self.junk_bytes + self.dev_junk_bytes

    def to_dict(self) -> dict:
        return {
            "schema_version": SCHEMA_VERSION,
            "scan_id": self.scan_id,
            "scanned_at": self.scanned_at.isoformat(),
            "profile": self.profile,
            "orphans": self.orphans,
            "junk": self.junk,
            "dev_junk": self.dev_junk,
            "summary": self.summary,
        }

    def save(self) -> None:
        _ensure_history_dir()
        with open(self.file_path, "w") as f:
            json.dump(self.to_dict(), f, indent=2, default=str)
        _prune_old_entries()

    @classmethod
    def from_dict(cls, d: dict) -> "ScanRecord":
        return cls(
            scan_id=d["scan_id"],
            scanned_at=datetime.fromisoformat(d["scanned_at"]),
            profile=d.get("profile"),
            orphans=d.get("orphans", {}),
            junk=d.get("junk", []),
            dev_junk=d.get("dev_junk", []),
            summary=d.get("summary", {}),
        )

    @classmethod
    def load(cls, path: Path) -> Optional["ScanRecord"]:
        try:
            with open(path) as f:
                data = json.load(f)
            return cls.from_dict(data)
        except (json.JSONDecodeError, KeyError, OSError, ValueError):
            return None

    def __repr__(self) -> str:
        return (
            f"<ScanRecord {self.scan_id[:8]} "
            f"at={self.scanned_at:%Y-%m-%d %H:%M} "
            f"total={bytes_human(self.total_bytes)}>"
        )


# ── Builder ────────────────────────────────────────────────────────────────────

def build_scan_record(
    orphans: Dict,
    junk: List,
    dev_junk: Optional[List] = None,
    profile: Optional[str] = None,
) -> ScanRecord:
    """
    Create a ScanRecord from live scan results.

    Args:
        orphans: Dict[str, List[OrphanEntry]] from scanner.scan_orphans()
        junk:    List[JunkEntry] from scanner.scan_junk()
        profile: Active profile name (optional).
    """
    orphan_data: Dict[str, Any] = {}
    orphan_bytes = 0

    for name, entries in orphans.items():
        total = sum(e.size for e in entries)
        orphan_bytes += total
        orphan_data[name] = {
            "total_size": total,
            "total_size_human": bytes_human(total),
            "items": [e.to_dict() for e in entries],
        }

    user_junk = [j for j in junk if not j.is_system]
    junk_bytes = sum(j.size for j in user_junk)

    dev_junk = dev_junk or []
    dev_junk_bytes = sum(j.size for j in dev_junk)

    summary = {
        "orphan_count": len(orphans),
        "orphan_bytes": orphan_bytes,
        "orphan_size_human": bytes_human(orphan_bytes),
        "junk_count": len(user_junk),
        "junk_bytes": junk_bytes,
        "junk_size_human": bytes_human(junk_bytes),
        "dev_junk_count": len(dev_junk),
        "dev_junk_bytes": dev_junk_bytes,
        "dev_junk_size_human": bytes_human(dev_junk_bytes),
    }

    return ScanRecord(
        scan_id=str(uuid.uuid4()),
        scanned_at=datetime.now(),
        profile=profile,
        orphans=orphan_data,
        junk=[j.to_dict() for j in user_junk],
        dev_junk=[j.to_dict() for j in dev_junk],
        summary=summary,
    )


# ── History listing ────────────────────────────────────────────────────────────

def list_history(limit: int = 20) -> List[ScanRecord]:
    """Return past scan records, newest first."""
    _ensure_history_dir()
    records: List[ScanRecord] = []
    for p in sorted(HISTORY_DIR.glob("*.json"), reverse=True):
        r = ScanRecord.load(p)
        if r:
            records.append(r)
        if len(records) >= limit:
            break
    return records


def latest_scan() -> Optional[ScanRecord]:
    """Return the most recent scan record, or None."""
    records = list_history(limit=1)
    return records[0] if records else None


def _prune_old_entries() -> None:
    """Delete oldest history files beyond MAX_HISTORY_ENTRIES."""
    files = sorted(HISTORY_DIR.glob("*.json"))
    excess = len(files) - MAX_HISTORY_ENTRIES
    for f in files[:excess]:
        try:
            f.unlink()
        except OSError:
            pass


# ── Diff ───────────────────────────────────────────────────────────────────────

@dataclass
class ScanDiff:
    """Comparison between two scan records."""
    older: ScanRecord
    newer: ScanRecord

    # Orphans
    new_orphans: List[str] = field(default_factory=list)    # appeared in newer
    resolved_orphans: List[str] = field(default_factory=list)  # gone in newer
    persistent_orphans: List[str] = field(default_factory=list)  # still there

    # Junk bytes
    junk_delta_bytes: int = 0     # positive = more junk, negative = less
    dev_junk_delta_bytes: int = 0

    def __post_init__(self) -> None:
        older_names: Set[str] = set(self.older.orphans.keys())
        newer_names: Set[str] = set(self.newer.orphans.keys())

        self.new_orphans = sorted(newer_names - older_names)
        self.resolved_orphans = sorted(older_names - newer_names)
        self.persistent_orphans = sorted(older_names & newer_names)
        self.junk_delta_bytes = self.newer.junk_bytes - self.older.junk_bytes
        self.dev_junk_delta_bytes = self.newer.dev_junk_bytes - self.older.dev_junk_bytes

    @property
    def size_delta_bytes(self) -> int:
        return self.newer.total_bytes - self.older.total_bytes

    @property
    def summary(self) -> Dict[str, Any]:
        return {
            "older_scan": self.older.scan_id[:8],
            "older_date": self.older.scanned_at.isoformat(),
            "newer_scan": self.newer.scan_id[:8],
            "newer_date": self.newer.scanned_at.isoformat(),
            "new_orphans": self.new_orphans,
            "resolved_orphans": self.resolved_orphans,
            "persistent_orphans": self.persistent_orphans,
            "size_delta_bytes": self.size_delta_bytes,
            "size_delta_human": bytes_human(abs(self.size_delta_bytes)),
            "junk_delta_bytes": self.junk_delta_bytes,
            "dev_junk_delta_bytes": self.dev_junk_delta_bytes,
        }


def diff_scans(older: ScanRecord, newer: ScanRecord) -> ScanDiff:
    """Compare two ScanRecords and return a ScanDiff."""
    return ScanDiff(older=older, newer=newer)


def diff_with_latest(current_orphans: Dict, current_junk: List) -> Optional[ScanDiff]:
    """
    Compare the current (live) scan results with the most recent stored scan.
    Returns None if there is no history yet.
    """
    last = latest_scan()
    if last is None:
        return None

    current = build_scan_record(current_orphans, current_junk)
    return diff_scans(older=last, newer=current)
