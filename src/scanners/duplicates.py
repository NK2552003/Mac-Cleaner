"""
Mac Deep Cleaner v1.5.0 — Duplicate File Finder
=============================================
Finds identical files by content hash across user-specified or default
directories. Groups duplicates, computes wasted space, and returns a
structured list so the caller can decide which copies to remove.

Strategy
--------
1. Walk directories, collecting files by size (cheap pre-filter).
2. For each size-group with ≥2 files, compute a fast 4 KB head-hash.
3. For head-hash collisions, compute the full SHA-256.
4. Return groups of confirmed duplicates.
"""

from __future__ import annotations

import hashlib
import logging
from collections import defaultdict
from pathlib import Path
from typing import Dict, Generator, List, Optional, Set, Tuple

from constants import HOME
from utils import bytes_human, size_of

logger = logging.getLogger(__name__)

# Default roots to scan when the user doesn't specify paths
DEFAULT_SCAN_ROOTS: List[Path] = [
    HOME / "Downloads",
    HOME / "Documents",
    HOME / "Desktop",
    HOME / "Pictures",
    HOME / "Movies",
    HOME / "Music",
]

# Never descend into these (system / hidden / venv junk)
SKIP_DIRS: Set[str] = {
    ".git", ".venv", "venv", "__pycache__", "node_modules",
    ".Trash", ".npm", ".cargo",
}

# Ignore files smaller than this (not worth de-duping)
MIN_FILE_BYTES = 4 * 1024  # 4 KB

# Head-hash sample size
HEAD_BYTES = 4 * 1024  # 4 KB


# ── Hashing helpers ────────────────────────────────────────────────────────────

def _head_hash(path: Path) -> Optional[str]:
    """SHA-256 of the first HEAD_BYTES of a file."""
    try:
        with open(path, "rb") as f:
            chunk = f.read(HEAD_BYTES)
        return hashlib.sha256(chunk).hexdigest()
    except OSError as exc:
        logger.debug("head hash failed for %s: %s", path, exc)
        return None


def _full_hash(path: Path) -> Optional[str]:
    """Full SHA-256 of a file."""
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError as exc:
        logger.debug("full hash failed for %s: %s", path, exc)
        return None


# ── Directory walker ───────────────────────────────────────────────────────────

def _walk(root: Path) -> Generator[Path, None, None]:
    """Yield every regular file under root, skipping SKIP_DIRS."""
    if not root.exists():
        return
    try:
        for item in root.iterdir():
            if item.name in SKIP_DIRS or item.name.startswith("."):
                continue
            if item.is_symlink():
                continue
            if item.is_dir():
                yield from _walk(item)
            elif item.is_file():
                yield item
    except (PermissionError, OSError) as exc:
        logger.debug("walk failed for %s: %s", root, exc)


# ── Public API ─────────────────────────────────────────────────────────────────

class DuplicateGroup:
    """One set of files that are byte-for-byte identical."""

    __slots__ = ("hash", "size", "paths")

    def __init__(self, file_hash: str, size: int, paths: List[Path]) -> None:
        self.hash = file_hash
        self.size = size          # per-file size
        self.paths = paths        # ≥2 confirmed duplicates

    @property
    def wasted_bytes(self) -> int:
        """Space wasted by keeping (n-1) extra copies."""
        return self.size * (len(self.paths) - 1)

    def to_dict(self) -> dict:
        return {
            "hash": self.hash,
            "size": self.size,
            "size_human": bytes_human(self.size),
            "copies": len(self.paths),
            "wasted_bytes": self.wasted_bytes,
            "wasted_human": bytes_human(self.wasted_bytes),
            "paths": [str(p) for p in self.paths],
        }

    def __repr__(self) -> str:
        return (
            f"<DuplicateGroup hash={self.hash[:8]}… "
            f"copies={len(self.paths)} wasted={bytes_human(self.wasted_bytes)}>"
        )


def find_duplicates(
    roots: Optional[List[Path]] = None,
    min_size: int = MIN_FILE_BYTES,
    progress_callback=None,   # callable(scanned_files: int) → None
) -> List[DuplicateGroup]:
    """
    Scan *roots* (default: DEFAULT_SCAN_ROOTS) and return a list of
    DuplicateGroup objects sorted by wasted space descending.

    Args:
        roots:             Directories to scan. Defaults to DEFAULT_SCAN_ROOTS.
        min_size:          Ignore files smaller than this many bytes.
        progress_callback: Optional hook called periodically with file count.

    Returns:
        List[DuplicateGroup], largest wasted space first.
    """
    if roots is None:
        roots = [r for r in DEFAULT_SCAN_ROOTS if r.exists()]

    # ── Phase 1: Collect files, group by size ─────────────────────────────
    by_size: Dict[int, List[Path]] = defaultdict(list)
    scanned = 0

    for root in roots:
        for fpath in _walk(root):
            try:
                sz = fpath.stat().st_size
            except OSError:
                continue
            if sz < min_size:
                continue
            by_size[sz].append(fpath)
            scanned += 1
            if progress_callback and scanned % 200 == 0:
                progress_callback(scanned)

    # ── Phase 2: Head-hash within size groups ─────────────────────────────
    by_head: Dict[Tuple[int, str], List[Path]] = defaultdict(list)
    for sz, paths in by_size.items():
        if len(paths) < 2:
            continue
        for p in paths:
            hh = _head_hash(p)
            if hh:
                by_head[(sz, hh)].append(p)

    # ── Phase 3: Full hash for confirmed head-hash collisions ─────────────
    by_full: Dict[str, List[Path]] = defaultdict(list)
    for (sz, _), paths in by_head.items():
        if len(paths) < 2:
            continue
        for p in paths:
            fh = _full_hash(p)
            if fh:
                # Include size in the key so same-content different-size
                # files (impossible, but defensive) don't merge
                by_full[f"{sz}:{fh}"].append(p)

    # ── Phase 4: Build DuplicateGroup list ────────────────────────────────
    groups: List[DuplicateGroup] = []
    seen_paths: Set[Path] = set()

    for key, paths in by_full.items():
        if len(paths) < 2:
            continue
        # Deduplicate paths (resolve symlinks)
        unique: List[Path] = []
        for p in paths:
            try:
                real = p.resolve()
            except OSError:
                real = p
            if real not in seen_paths:
                seen_paths.add(real)
                unique.append(p)
        if len(unique) < 2:
            continue

        sz_str, file_hash = key.split(":", 1)
        groups.append(DuplicateGroup(
            file_hash=file_hash,
            size=int(sz_str),
            paths=unique,
        ))

    groups.sort(key=lambda g: g.wasted_bytes, reverse=True)
    return groups


def total_wasted(groups: List[DuplicateGroup]) -> int:
    """Sum of wasted bytes across all duplicate groups."""
    return sum(g.wasted_bytes for g in groups)
