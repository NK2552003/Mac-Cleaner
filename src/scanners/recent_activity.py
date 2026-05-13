"""Recent files and activity scanner."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional

from constants import HOME
from utils import size_of, safe_remove


RECENT_ITEMS_DIR = HOME / "Library" / "Recent Items"
FINDER_RECENT_ITEMS_DIR = (
    HOME / "Library" / "Containers" / "com.apple.Finder" / "Data" / "Library" / "Recent Items"
)
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


def _collect_dir_items_recursive(
    root: Path,
    category: str,
    safe_to_delete: bool,
    max_depth: int = 3,
) -> List[RecentActivityItem]:
    items: List[RecentActivityItem] = []
    if not root.exists():
        return items
    base_depth = len(root.parts)
    try:
        for dirpath, dirnames, filenames in os.walk(root):
            depth = len(Path(dirpath).parts) - base_depth
            if depth > max_depth:
                dirnames[:] = []
                continue
            if depth > 0:
                label = f"{category} / {Path(dirpath).name}"
            else:
                label = category
            for fname in filenames:
                fpath = Path(dirpath) / fname
                sz = size_of(fpath)
                if sz <= 0:
                    continue
                items.append(RecentActivityItem(
                    category=label,
                    path=fpath,
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

    recent_dirs: Iterable[Path] = [
        base / "Library" / "Recent Items",
        base / "Library" / "Containers" / "com.apple.Finder" / "Data" / "Library" / "Recent Items",
    ]
    for recent_dir in recent_dirs:
        items.extend(_collect_dir_items(recent_dir, "Recent Items", True))

    shared_dir = base / "Library" / "Application Support" / "com.apple.sharedfilelist"
    items.extend(_collect_dir_items_recursive(shared_dir, "Shared Lists", False))

    legacy_dir = base / "Library" / "Application Support" / "com.apple.LSSharedFileList"
    items.extend(_collect_dir_items_recursive(legacy_dir, "Shared Lists (Legacy)", False))

    seen = set()
    unique: List[RecentActivityItem] = []
    for item in items:
        if item.path in seen:
            continue
        seen.add(item.path)
        unique.append(item)

    return unique


def clear_recent_items(home: Optional[Path] = None) -> ClearResult:
    """Clear files under Recent Items folders (classic + Finder container)."""
    base = home or HOME
    result = ClearResult()

    targets = [
        base / "Library" / "Recent Items",
        base / "Library" / "Containers" / "com.apple.Finder" / "Data" / "Library" / "Recent Items",
    ]

    for target in targets:
        if not target.exists():
            continue
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
