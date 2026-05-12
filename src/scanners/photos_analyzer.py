"""Photos library analyzer."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from constants import HOME
from utils import bytes_human, count_files_recursive, size_of


@dataclass
class PhotoLibraryReport:
    """Summary of a Photos library."""
    path: Path
    size: int
    originals_size: int
    previews_size: int
    database_size: int
    originals_count: int
    extension_counts: Dict[str, int] = field(default_factory=dict)
    extension_sizes: Dict[str, int] = field(default_factory=dict)

    @property
    def name(self) -> str:
        return self.path.stem

    def top_extensions(self, limit: int = 8) -> List[Tuple[str, int, int]]:
        entries = []
        for ext, count in self.extension_counts.items():
            size = self.extension_sizes.get(ext, 0)
            entries.append((ext, count, size))
        entries.sort(key=lambda e: e[2], reverse=True)
        return entries[:limit]

    def to_dict(self) -> dict:
        return {
            "path": str(self.path),
            "size": self.size,
            "size_human": bytes_human(self.size),
            "originals_size": self.originals_size,
            "originals_size_human": bytes_human(self.originals_size),
            "previews_size": self.previews_size,
            "previews_size_human": bytes_human(self.previews_size),
            "database_size": self.database_size,
            "database_size_human": bytes_human(self.database_size),
            "originals_count": self.originals_count,
            "extensions": self.extension_counts,
            "extension_sizes": self.extension_sizes,
        }


def find_photo_libraries(search_roots: Optional[Iterable[Path]] = None) -> List[Path]:
    """Return Photos libraries found under search roots."""
    roots = list(search_roots) if search_roots else [HOME / "Pictures"]
    libraries: List[Path] = []

    for root in roots:
        if not root.exists():
            continue
        if root.suffix in {".photoslibrary", ".photolibrary"}:
            libraries.append(root)
            continue
        try:
            for child in root.iterdir():
                if child.is_dir() and child.suffix in {".photoslibrary", ".photolibrary"}:
                    libraries.append(child)
        except (PermissionError, OSError):
            continue

    return sorted(libraries)


def _extension_stats(root: Path) -> Tuple[Dict[str, int], Dict[str, int]]:
    counts: Dict[str, int] = {}
    sizes: Dict[str, int] = {}
    if not root.exists():
        return counts, sizes

    for dirpath, _dirs, files in os.walk(root):
        for fname in files:
            fpath = Path(dirpath) / fname
            try:
                sz = fpath.stat().st_size
            except OSError:
                continue
            ext = fpath.suffix.lower() or "<none>"
            counts[ext] = counts.get(ext, 0) + 1
            sizes[ext] = sizes.get(ext, 0) + sz

    return counts, sizes


def analyze_photo_library(path: Path) -> PhotoLibraryReport:
    """Analyze a Photos library bundle."""
    size = size_of(path)

    originals_dir = path / "originals"
    if not originals_dir.exists():
        originals_dir = path / "Masters"

    previews_dir = path / "resources"
    if not previews_dir.exists():
        previews_dir = path / "Resources"

    database_dir = path / "database"
    if not database_dir.exists():
        database_dir = path / "Database"

    originals_size = size_of(originals_dir) if originals_dir.exists() else 0
    previews_size = size_of(previews_dir) if previews_dir.exists() else 0
    database_size = size_of(database_dir) if database_dir.exists() else 0
    originals_count = count_files_recursive(originals_dir) if originals_dir.exists() else 0
    ext_counts, ext_sizes = _extension_stats(originals_dir)

    return PhotoLibraryReport(
        path=path,
        size=size,
        originals_size=originals_size,
        previews_size=previews_size,
        database_size=database_size,
        originals_count=originals_count,
        extension_counts=ext_counts,
        extension_sizes=ext_sizes,
    )
