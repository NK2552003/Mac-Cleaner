"""Xcode derived data and cache cleaner."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional, Set

from constants import HOME
from utils import size_of, safe_remove


@dataclass
class XcodeJunkItem:
    """One Xcode-related junk folder."""
    category: str
    path: Path
    size: int
    safe_to_delete: bool = True


@dataclass
class DeleteResult:
    """Summary of delete operation."""
    deleted: int = 0
    skipped: int = 0
    bytes_freed: int = 0
    errors: List[str] = field(default_factory=list)


_XCODE_ROOT = HOME / "Library" / "Developer" / "Xcode"

_DEFAULT_PATHS = {
    "Derived Data": _XCODE_ROOT / "DerivedData",
    "Archives": _XCODE_ROOT / "Archives",
    "iOS Device Support": _XCODE_ROOT / "iOS DeviceSupport",
    "Build Cache": _XCODE_ROOT / "BuildCache",
    "Xcode Cache": _XCODE_ROOT / "Cache",
    "Xcode Logs": _XCODE_ROOT / "Logs",
    "Xcode Caches (System)": HOME / "Library" / "Caches" / "com.apple.dt.Xcode",
}

_ALLOWED_ROOTS: List[Path] = [
    _XCODE_ROOT,
    HOME / "Library" / "Caches" / "com.apple.dt.Xcode",
]


def _is_within(path: Path, root: Path) -> bool:
    try:
        return path.resolve().is_relative_to(root.resolve())
    except AttributeError:
        try:
            return str(path.resolve()).startswith(str(root.resolve()))
        except OSError:
            return False
    except OSError:
        return False


def collect_xcode_junk(extra_paths: Optional[Iterable[Path]] = None) -> List[XcodeJunkItem]:
    """Collect Xcode-derived data, caches, and archives."""
    items: List[XcodeJunkItem] = []
    seen: Set[Path] = set()

    for category, path in _DEFAULT_PATHS.items():
        if not path.exists() or path in seen:
            continue
        sz = size_of(path)
        if sz <= 0:
            continue
        items.append(XcodeJunkItem(category=category, path=path, size=sz))
        seen.add(path)

    for extra in extra_paths or []:
        if extra in seen or not extra.exists():
            continue
        sz = size_of(extra)
        if sz <= 0:
            continue
        items.append(XcodeJunkItem(category="Custom", path=extra, size=sz))
        seen.add(extra)

    return sorted(items, key=lambda i: i.size, reverse=True)


def delete_xcode_junk(
    items: List[XcodeJunkItem],
    categories: Optional[Iterable[str]] = None,
) -> DeleteResult:
    """Delete selected Xcode junk items."""
    result = DeleteResult()
    category_set = {c.lower() for c in (categories or [])}

    for item in items:
        if category_set and item.category.lower() not in category_set:
            continue
        allowed = any(_is_within(item.path, root) for root in _ALLOWED_ROOTS)
        if not allowed:
            result.skipped += 1
            result.errors.append(f"Blocked outside allowlist: {item.path}")
            continue
        ok, freed = safe_remove(item.path)
        if ok:
            result.deleted += 1
            result.bytes_freed += freed
        else:
            result.skipped += 1
            result.errors.append(str(item.path))

    return result
