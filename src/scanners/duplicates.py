"""
Finds identical files by content hash across user-specified or default
directories. Groups duplicates, computes wasted space, and returns a
structured list so the caller can decide which copies to remove.

Strategy
--------
1. Walk directories, collecting files by size (cheap pre-filter).
2. For each size-group with ≥2 files, compute a fast 4 KB head-hash.
3. For head-hash collisions, compute the full SHA-256.
4. Return groups of confirmed duplicates.
5. (macOS, optional) Estimate APFS shared extents to avoid overstating wasted space.
"""

from __future__ import annotations

import hashlib
import logging
import struct
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, Generator, List, Optional, Set, Tuple

try:
    import fcntl  # type: ignore
except ImportError:  # pragma: no cover - non-Unix platforms
    fcntl = None

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

# APFS shared-extents (clone) detection via F_LOG2PHYS_EXT (macOS only)
_HAS_LOG2PHYS = sys.platform == "darwin" and fcntl is not None
_F_LOG2PHYS_EXT = 65
_L2P_QUERY_BYTES = 4096
_L2P_STRUCT = struct.Struct("=Iqq")
_CLONE_SAMPLE_MODES = {"fast", "balanced", "thorough"}


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


def _sample_offsets(size: int, mode: str) -> List[int]:
    if size <= 0:
        return [0]
    mode = mode if mode in _CLONE_SAMPLE_MODES else "balanced"
    offsets = [0]
    if size > HEAD_BYTES:
        offsets.append(size - HEAD_BYTES)
    if mode in {"balanced", "thorough"} and size > 2 * HEAD_BYTES:
        offsets.append(size // 2)
    if mode == "thorough" and size > 4 * HEAD_BYTES:
        offsets.extend([size // 4, (size * 3) // 4])
    aligned = {max(0, (o // _L2P_QUERY_BYTES) * _L2P_QUERY_BYTES) for o in offsets}
    return sorted({min(o, size - 1) for o in aligned})


def _log2phys_offset(fd: int, offset: int) -> Optional[int]:
    if not _HAS_LOG2PHYS:
        return None
    try:
        buf = _L2P_STRUCT.pack(0, _L2P_QUERY_BYTES, offset)
        out = fcntl.fcntl(fd, _F_LOG2PHYS_EXT, buf)
        _, _, devoffset = _L2P_STRUCT.unpack(out)
        if devoffset < 0:
            return None
        return int(devoffset)
    except OSError as exc:
        logger.debug("log2phys failed for fd %s offset %s: %s", fd, offset, exc)
        return None


def _physical_signature(
    path: Path,
    size: int,
    sample_mode: str,
) -> Optional[Tuple[int, Tuple[int, ...]]]:
    if not _HAS_LOG2PHYS:
        return None
    try:
        st = path.stat()
    except OSError as exc:
        logger.debug("stat failed for %s: %s", path, exc)
        return None
    offsets = _sample_offsets(size, sample_mode)
    try:
        with open(path, "rb") as f:
            fd = f.fileno()
            dev_offsets: List[int] = []
            for offset in offsets:
                dev_offset = _log2phys_offset(fd, offset)
                if dev_offset is None:
                    return None
                dev_offsets.append(dev_offset)
    except OSError as exc:
        logger.debug("log2phys open failed for %s: %s", path, exc)
        return None
    return (st.st_dev, tuple(dev_offsets))


def _group_by_physical_extents(
    paths: List[Path],
    size: int,
    clone_detect: bool,
    clone_sampling: str,
) -> Tuple[Optional[List[List[Path]]], int]:
    if not clone_detect or not _HAS_LOG2PHYS:
        return None, 0
    groups: Dict[Tuple[int, Tuple[int, ...]], List[Path]] = defaultdict(list)
    unknown = 0
    for p in paths:
        sig = _physical_signature(p, size, clone_sampling)
        if sig is None:
            unknown += 1
        else:
            groups[sig].append(p)
    if not groups and unknown == len(paths):
        return None, 0
    return list(groups.values()), unknown


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

    __slots__ = ("hash", "size", "paths", "physical_groups", "physical_unknown")

    def __init__(
        self,
        file_hash: str,
        size: int,
        paths: List[Path],
        physical_groups: Optional[List[List[Path]]] = None,
        physical_unknown: int = 0,
    ) -> None:
        self.hash = file_hash
        self.size = size          # per-file size
        self.paths = paths        # ≥2 confirmed duplicates
        self.physical_groups = physical_groups
        self.physical_unknown = physical_unknown

    @property
    def logical_wasted_bytes(self) -> int:
        """Space wasted by keeping (n-1) extra copies."""
        return self.size * (len(self.paths) - 1)

    @property
    def physical_group_count(self) -> Optional[int]:
        if self.physical_groups is None:
            return None
        return len(self.physical_groups) + self.physical_unknown

    @property
    def physical_wasted_bytes(self) -> Optional[int]:
        group_count = self.physical_group_count
        if group_count is None:
            return None
        return self.size * max(0, group_count - 1)

    @property
    def has_shared_extents(self) -> bool:
        if not self.physical_groups:
            return False
        return any(len(g) > 1 for g in self.physical_groups)

    @property
    def wasted_bytes(self) -> int:
        """Best-effort wasted bytes (APFS shared extents when available)."""
        physical = self.physical_wasted_bytes
        return physical if physical is not None else self.logical_wasted_bytes

    def to_dict(self) -> dict:
        physical_wasted = self.physical_wasted_bytes
        return {
            "hash": self.hash,
            "size": self.size,
            "size_human": bytes_human(self.size),
            "copies": len(self.paths),
            "wasted_bytes": self.wasted_bytes,
            "wasted_human": bytes_human(self.wasted_bytes),
            "logical_wasted_bytes": self.logical_wasted_bytes,
            "logical_wasted_human": bytes_human(self.logical_wasted_bytes),
            "physical_wasted_bytes": physical_wasted,
            "physical_wasted_human": (
                bytes_human(physical_wasted) if physical_wasted is not None else None
            ),
            "physical_group_count": self.physical_group_count,
            "has_shared_extents": self.has_shared_extents,
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
    clone_detect: bool = False,
    clone_sampling: str = "balanced",
) -> List[DuplicateGroup]:
    """
    Scan *roots* (default: DEFAULT_SCAN_ROOTS) and return a list of
    DuplicateGroup objects sorted by wasted space descending.

    Args:
        roots:             Directories to scan. Defaults to DEFAULT_SCAN_ROOTS.
        min_size:          Ignore files smaller than this many bytes.
        progress_callback: Optional hook called periodically with file count.
        clone_detect:       Enable APFS clone-aware wasted space estimates (macOS only).
        clone_sampling:     Sampling profile: fast, balanced, thorough.

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
        physical_groups, physical_unknown = _group_by_physical_extents(
            unique,
            int(sz_str),
            clone_detect,
            clone_sampling,
        )
        groups.append(DuplicateGroup(
            file_hash=file_hash,
            size=int(sz_str),
            paths=unique,
            physical_groups=physical_groups,
            physical_unknown=physical_unknown,
        ))

    groups.sort(key=lambda g: g.wasted_bytes, reverse=True)
    return groups


def total_wasted(groups: List[DuplicateGroup]) -> int:
    """Sum of wasted bytes across all duplicate groups."""
    return sum(g.wasted_bytes for g in groups)
