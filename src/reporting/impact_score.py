"""Cleaning impact score calculation."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from utils import bytes_human


@dataclass
class ImpactScore:
    """Impact score summary."""
    score: int
    label: str
    total_bytes: int
    total_human: str
    total_items: int

    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "label": self.label,
            "total_bytes": self.total_bytes,
            "total_human": self.total_human,
            "total_items": self.total_items,
        }


def _scale(value: int, max_value: int, weight: int) -> int:
    if value <= 0:
        return 0
    return int(min(weight, weight * math.log1p(value) / math.log1p(max_value)))


def impact_label(score: int) -> str:
    if score >= 85:
        return "critical"
    if score >= 70:
        return "very high"
    if score >= 50:
        return "high"
    if score >= 30:
        return "moderate"
    return "low"


def compute_impact_score(
    total_bytes: int,
    total_items: int,
) -> ImpactScore:
    """Compute an impact score from totals."""
    bytes_score = _scale(total_bytes, max_value=50 * 1024 ** 3, weight=60)
    item_score = _scale(total_items, max_value=5000, weight=35)
    bonus = 5 if total_bytes > 5 * 1024 ** 3 else 0

    raw = min(100, bytes_score + item_score + bonus)
    label = impact_label(raw)

    return ImpactScore(
        score=raw,
        label=label,
        total_bytes=total_bytes,
        total_human=bytes_human(total_bytes),
        total_items=total_items,
    )


def compute_impact_from_summary(
    orphan_bytes: int,
    junk_bytes: int,
    dev_bytes: int,
    orphan_count: int,
    junk_count: int,
    dev_count: int,
) -> ImpactScore:
    total_bytes = orphan_bytes + junk_bytes + dev_bytes
    total_items = orphan_count + junk_count + dev_count
    return compute_impact_score(total_bytes, total_items)
