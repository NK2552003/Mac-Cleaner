"""Recent files and activity scanner."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from constants import HOME
from utils import size_of, safe_remove


RECENT_ITEMS_DIR = HOME / "Library" / "Recent Items"
SHARED_LIST_DIR = HOME / "Library" / "Application Support" / "com.apple.sharedfilelist"
LEGACY_SHARED_LIST_DIR = HOME / "Library" / "Application Support" / "com.apple.LSSharedFileList"


@dataclass
class RecentActivityItem:
    """One recent activity file entry."""
    category: str
    path: Path
    size: int
    safe_to_delete: bool


@dataclass
class ClearResult:
    """Summary of a clear operation."""
    deleted: int = 0
    skipped: int = 0
    bytes_freed: int = 0
    errors: List[str] = field(default_factory=list)


def _collect_dir_items(
    root: Path,
    category: str,
    safe_to_delete: bool,
) -> List[RecentActivityItem]:
    items: List[RecentActivityItem] = []
    if not root.exists():
        return items
    try:
        for child in root.iterdir():
            if child.is_dir():
                continue
            sz = size_of(child)
            if sz <= 0:
                continue
            items.append(RecentActivityItem(
                category=category,
                path=child,
                size=sz,
                safe_to_delete=safe_to_delete,
            ))
    except OSError:
        return items
    return items


def collect_recent_activity(home: Optional[Path] = None) -> List[RecentActivityItem]:
    """Collect recent activity files in known locations."""
    base = home or HOME
    items: List[RecentActivityItem] = []

    recent_dir = base / "Library" / "Recent Items"
    items.extend(_collect_dir_items(recent_dir, "Recent Items", True))

    shared_dir = base / "Library" / "Application Support" / "com.apple.sharedfilelist"
    items.extend(_collect_dir_items(shared_dir, "Shared Lists", False))

    legacy_dir = base / "Library" / "Application Support" / "com.apple.LSSharedFileList"
    items.extend(_collect_dir_items(legacy_dir, "Shared Lists (Legacy)", False))

    return items


def clear_recent_items(home: Optional[Path] = None) -> ClearResult:
    """Clear files under ~/Library/Recent Items only."""
    base = home or HOME
    target = base / "Library" / "Recent Items"
    result = ClearResult()

    if not target.exists():
        return result

    try:
        for child in target.iterdir():
            if child.is_dir():
                continue
            ok, freed = safe_remove(child)
            if ok:
                result.deleted += 1
                result.bytes_freed += freed
            else:
                result.skipped += 1
                result.errors.append(str(child))
    except OSError:
        result.errors.append(str(target))

    return result
