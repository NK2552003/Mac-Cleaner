"""Installer and package file hunter."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional, Set, Tuple

from constants import HOME
from utils import size_of, safe_remove


@dataclass
class InstallerItem:
    """One installer file entry."""
    path: Path
    size: int
    kind: str
    modified_at: str
    age_days: int

    @property
    def size_human(self) -> str:
        from utils import bytes_human
        return bytes_human(self.size)


@dataclass
class DeleteResult:
    """Summary of delete operation."""
    deleted: int = 0
    skipped: int = 0
    bytes_freed: int = 0
    errors: List[str] = field(default_factory=list)


_DEFAULT_ROOTS: List[Path] = [
    HOME / "Downloads",
    HOME / "Desktop",
    HOME / "Documents",
]

_SKIP_DIRS: Set[str] = {
    ".git",
    ".Trash",
    ".Spotlight-V100",
    "node_modules",
    "Library",
    "Applications",
    "System",
}

_INSTALLER_EXTS = {
    ".dmg": "Disk Image",
    ".pkg": "PKG",
    ".mpkg": "PKG",
    ".iso": "Disk Image",
}

_ARCHIVE_EXTS = {
    ".zip": "Archive",
    ".rar": "Archive",
    ".7z": "Archive",
    ".tar": "Archive",
    ".tgz": "Archive",
    ".gz": "Archive",
    ".bz2": "Archive",
    ".xz": "Archive",
}


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


def _walk(root: Path, max_depth: int = 6) -> Iterable[Path]:
    if not root.exists():
        return []
    base_depth = len(root.parts)
    try:
        for entry in os.scandir(root):
            try:
                if entry.is_symlink():
                    continue
                if entry.is_dir(follow_symlinks=False):
                    if entry.name.startswith(".") or entry.name in _SKIP_DIRS:
                        continue
                    depth = len(Path(entry.path).parts) - base_depth
                    if depth >= max_depth:
                        continue
                    yield from _walk(Path(entry.path), max_depth=max_depth)
                elif entry.is_file(follow_symlinks=False):
                    yield Path(entry.path)
            except OSError:
                continue
    except OSError:
        return []


def _classify(path: Path, include_archives: bool) -> Optional[str]:
    ext = path.suffix.lower()
    if ext in _INSTALLER_EXTS:
        return _INSTALLER_EXTS[ext]
    if include_archives and ext in _ARCHIVE_EXTS:
        return _ARCHIVE_EXTS[ext]
    return None


def find_installers(
    roots: Optional[Iterable[Path]] = None,
    min_age_days: Optional[int] = None,
    min_size_mb: int = 0,
    include_archives: bool = False,
    max_depth: int = 6,
    limit: int = 500,
) -> List[InstallerItem]:
    """Find installer files in the given roots."""
    targets = list(roots) if roots else _DEFAULT_ROOTS
    items: List[InstallerItem] = []

    min_size_bytes = max(min_size_mb, 0) * 1024 * 1024
    now = datetime.now()

    for root in targets:
        for path in _walk(root, max_depth=max_depth):
            kind = _classify(path, include_archives=include_archives)
            if not kind:
                continue
            sz = size_of(path)
            if sz <= 0 or sz < min_size_bytes:
                continue
            try:
                mtime = datetime.fromtimestamp(path.stat().st_mtime)
            except OSError:
                continue
            age = (now - mtime).days
            if min_age_days is not None and age < min_age_days:
                continue
            items.append(InstallerItem(
                path=path,
                size=sz,
                kind=kind,
                modified_at=mtime.isoformat(timespec="seconds"),
                age_days=age,
            ))
            if len(items) >= limit:
                return sorted(items, key=lambda i: i.size, reverse=True)

    return sorted(items, key=lambda i: i.size, reverse=True)


def delete_installers(
    items: List[InstallerItem],
    allowed_roots: Optional[Iterable[Path]] = None,
) -> DeleteResult:
    """Delete installer files under allowed roots."""
    result = DeleteResult()
    roots = list(allowed_roots) if allowed_roots else _DEFAULT_ROOTS

    for item in items:
        allowed = any(_is_within(item.path, root) for root in roots)
        if not allowed:
            result.skipped += 1
            result.errors.append(f"Blocked outside roots: {item.path}")
            continue
        ok, freed = safe_remove(item.path)
        if ok:
            result.deleted += 1
            result.bytes_freed += freed
        else:
            result.skipped += 1
            result.errors.append(str(item.path))

    return result
