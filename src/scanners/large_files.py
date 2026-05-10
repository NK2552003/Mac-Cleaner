"""
Mac Deep Cleaner v1.0.0 — Large File Scanner
==========================================
Finds files above a configurable size threshold anywhere on disk
(or within user-specified roots). Results are sorted by size and
returned as LargeFileEntry objects.

Design notes
------------
- Uses os.scandir via a recursive walker for speed (avoids Path.rglob
  overhead on large directory trees).
- Respects a hard-coded blocklist of paths that should never be walked
  (system volumes, Time Machine sparsebundles, etc.).
- Symlinks are never followed to avoid double-counting.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Generator, List, Optional, Set

from constants import HOME
from utils import bytes_human

# Default threshold
DEFAULT_MIN_BYTES: int = 100 * 1024 * 1024  # 100 MB

# Default roots (user-visible filesystems only)
DEFAULT_ROOTS: List[Path] = [HOME]

# Absolute path prefixes to skip entirely
_SKIP_PREFIXES: tuple = (
    "/System",
    "/private/var",
    "/Volumes/.com.apple.TimeMachine",
    "/dev",
    "/proc",
)

# Directory names (basenames) to skip
_SKIP_DIRS: Set[str] = {
    ".git",
    ".Spotlight-V100",
    ".fseventsd",
    ".DocumentRevisions-V100",
    ".TemporaryItems",
    "__pycache__",
    "node_modules",
}


@dataclass(order=False)
class LargeFileEntry:
    """A single large file found on disk."""
    path: Path
    size: int           # actual file size in bytes (st_size)
    category: str = ""  # inferred from extension / location

    def __post_init__(self) -> None:
        if not self.category:
            self.category = _categorise(self.path)

    @property
    def size_human(self) -> str:
        return bytes_human(self.size)

    def to_dict(self) -> dict:
        return {
            "path": str(self.path),
            "size": self.size,
            "size_human": self.size_human,
            "category": self.category,
        }

    def __repr__(self) -> str:
        return f"<LargeFile {self.size_human} {self.path.name}>"


# ── Category inference ─────────────────────────────────────────────────────────

_EXT_CATEGORIES = {
    # Video
    ".mp4": "Video", ".mov": "Video", ".mkv": "Video", ".avi": "Video",
    ".m4v": "Video", ".wmv": "Video", ".flv": "Video", ".webm": "Video",
    # Audio
    ".mp3": "Audio", ".flac": "Audio", ".wav": "Audio", ".aac": "Audio",
    ".m4a": "Audio", ".ogg": "Audio", ".aiff": "Audio",
    # Images / RAW
    ".psd": "Image", ".tiff": "Image", ".raw": "Image", ".cr2": "Image",
    ".nef": "Image", ".arw": "Image", ".dng": "Image",
    # Archives
    ".zip": "Archive", ".tar": "Archive", ".gz": "Archive",
    ".bz2": "Archive", ".xz": "Archive", ".7z": "Archive",
    ".rar": "Archive", ".dmg": "Disk Image", ".iso": "Disk Image",
    ".pkg": "Installer", ".mpkg": "Installer",
    # Documents
    ".pdf": "PDF", ".docx": "Document", ".xlsx": "Spreadsheet",
    ".pptx": "Presentation",
    # Developer
    ".ipa": "iOS App", ".app": "App Bundle", ".xcarchive": "Xcode Archive",
    ".dSYM": "Debug Symbols",
    # Backups / Disk images
    ".sparseimage": "Disk Image", ".sparsebundle": "Disk Image",
    ".vmdk": "VM Disk", ".vdi": "VM Disk", ".vhd": "VM Disk",
}


def _categorise(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in _EXT_CATEGORIES:
        return _EXT_CATEGORIES[ext]
    # Location-based fallbacks
    s = str(path)
    if "DerivedData" in s or "Xcode" in s:
        return "Xcode"
    if "Simulator" in s:
        return "iOS Simulator"
    if "Library/Caches" in s:
        return "Cache"
    if ".Trash" in s:
        return "Trash"
    return "Other"


# ── Walker ─────────────────────────────────────────────────────────────────────

def _walk(root: Path) -> Generator[os.DirEntry, None, None]:  # type: ignore[type-arg]
    """Yield DirEntry objects for regular files, skipping blocked paths."""
    root_str = str(root)
    for prefix in _SKIP_PREFIXES:
        if root_str.startswith(prefix):
            return

    try:
        with os.scandir(root) as it:
            for entry in it:
                if entry.is_symlink():
                    continue
                if entry.is_dir(follow_symlinks=False):
                    if entry.name in _SKIP_DIRS or entry.name.startswith("."):
                        continue
                    # Check if subtree is blocked
                    skip = False
                    for prefix in _SKIP_PREFIXES:
                        if entry.path.startswith(prefix):
                            skip = True
                            break
                    if not skip:
                        yield from _walk(Path(entry.path))
                elif entry.is_file(follow_symlinks=False):
                    yield entry
    except (PermissionError, OSError):
        pass


# ── Public API ─────────────────────────────────────────────────────────────────

def find_large_files(
    roots: Optional[List[Path]] = None,
    min_bytes: int = DEFAULT_MIN_BYTES,
    limit: int = 500,
    progress_callback: Optional[Callable[[int], None]] = None,
) -> List[LargeFileEntry]:
    """
    Scan *roots* for files larger than *min_bytes*.

    Args:
        roots:             Directories to walk. Defaults to [HOME].
        min_bytes:         Size threshold in bytes (default 100 MB).
        limit:             Maximum number of results to return.
        progress_callback: Called every 500 files with the current count.

    Returns:
        List[LargeFileEntry] sorted by size descending, capped at *limit*.
    """
    if roots is None:
        roots = DEFAULT_ROOTS

    results: List[LargeFileEntry] = []
    scanned = 0

    for root in roots:
        for entry in _walk(root):
            scanned += 1
            if progress_callback and scanned % 500 == 0:
                progress_callback(scanned)
            try:
                st = entry.stat(follow_symlinks=False)
            except OSError:
                continue
            if st.st_size >= min_bytes:
                results.append(LargeFileEntry(
                    path=Path(entry.path),
                    size=st.st_size,
                ))

    results.sort(key=lambda e: e.size, reverse=True)
    return results[:limit]


def group_by_category(entries: List[LargeFileEntry]) -> dict:
    """Return entries grouped by category name."""
    from collections import defaultdict
    groups: dict = defaultdict(list)
    for e in entries:
        groups[e.category].append(e)
    return dict(groups)
