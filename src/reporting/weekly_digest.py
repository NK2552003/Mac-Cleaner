"""Weekly digest report builder."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from config.history import ScanRecord
from utils import bytes_human


@dataclass
class WeeklyDigest:
    """Summary of recent scans."""
    start: str
    end: str
    scan_count: int
    total_reclaimable_bytes: int
    total_reclaimable_human: str
    avg_reclaimable_bytes: int
    avg_reclaimable_human: str
    top_orphan_apps: List[Tuple[str, int]] = field(default_factory=list)
    top_junk_categories: List[Tuple[str, int]] = field(default_factory=list)
    top_dev_categories: List[Tuple[str, int]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "start": self.start,
            "end": self.end,
            "scan_count": self.scan_count,
            "total_reclaimable_bytes": self.total_reclaimable_bytes,
            "total_reclaimable_human": self.total_reclaimable_human,
            "avg_reclaimable_bytes": self.avg_reclaimable_bytes,
            "avg_reclaimable_human": self.avg_reclaimable_human,
            "top_orphan_apps": [(n, s) for n, s in self.top_orphan_apps],
            "top_junk_categories": [(n, s) for n, s in self.top_junk_categories],
            "top_dev_categories": [(n, s) for n, s in self.top_dev_categories],
        }


def _sum_orphans(records: List[ScanRecord]) -> Dict[str, int]:
    totals: Dict[str, int] = {}
    for r in records:
        for name, data in r.orphans.items():
            size = int(data.get("total_size", 0))
            totals[name] = totals.get(name, 0) + size
    return totals


def _sum_junk(records: List[ScanRecord]) -> Dict[str, int]:
    totals: Dict[str, int] = {}
    for r in records:
        for item in r.junk:
            category = item.get("category", "Other")
            size = int(item.get("size", 0))
            totals[category] = totals.get(category, 0) + size
    return totals


def _sum_dev(records: List[ScanRecord]) -> Dict[str, int]:
    totals: Dict[str, int] = {}
    for r in records:
        for item in r.dev_junk:
            category = item.get("category", "Other")
            size = int(item.get("size", 0))
            totals[category] = totals.get(category, 0) + size
    return totals


def generate_weekly_digest(
    records: List[ScanRecord],
    days: int = 7,
) -> Optional[WeeklyDigest]:
    """Generate a digest from recent scan records."""
    if not records:
        return None

    cutoff = datetime.now() - timedelta(days=days)
    recent = [r for r in records if r.scanned_at >= cutoff]
    if not recent:
        return None

    total = sum(r.total_bytes for r in recent)
    avg = int(total / len(recent)) if recent else 0

    orphan_totals = _sum_orphans(recent)
    junk_totals = _sum_junk(recent)
    dev_totals = _sum_dev(recent)

    top_orphans = sorted(orphan_totals.items(), key=lambda kv: kv[1], reverse=True)[:8]
    top_junk = sorted(junk_totals.items(), key=lambda kv: kv[1], reverse=True)[:8]
    top_dev = sorted(dev_totals.items(), key=lambda kv: kv[1], reverse=True)[:8]

    return WeeklyDigest(
        start=cutoff.date().isoformat(),
        end=datetime.now().date().isoformat(),
        scan_count=len(recent),
        total_reclaimable_bytes=total,
        total_reclaimable_human=bytes_human(total),
        avg_reclaimable_bytes=avg,
        avg_reclaimable_human=bytes_human(avg),
        top_orphan_apps=top_orphans,
        top_junk_categories=top_junk,
        top_dev_categories=top_dev,
    )
