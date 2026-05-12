"""
Mac Deep Cleaner v1.5.0 — Broken Symlink Detector
===============================================
Finds dangling symbolic links in developer-relevant directories
(e.g. /usr/local, ~/bin, ~/.local/bin, Homebrew prefixes).

A symlink is "broken" when its target does not exist (ENOENT) or
is itself a chain of symlinks with a missing terminal target.

Safety
------
- Never deletes anything itself; only reports.
- Skips /System, /private/var, and other protected trees.
- Limits recursion depth to avoid pathological directory structures.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Generator, List, Optional, Set

from constants import HOME
from utils import bytes_human

logger = logging.getLogger(__name__)

# Default roots for broken-symlink scanning
DEFAULT_ROOTS: List[Path] = [
    Path("/usr/local"),
    Path("/opt/homebrew"),
    HOME / "bin",
    HOME / ".local" / "bin",
    HOME / ".config",
    HOME / "Library" / "LaunchAgents",
]

# Never recurse into these dir names
_SKIP_NAMES: Set[str] = {
    ".git", "__pycache__", "node_modules",
    ".DocumentRevisions-V100", ".fseventsd",
}

_MAX_DEPTH = 8


@dataclass
class BrokenSymlink:
    """A single dangling symlink."""
    path: Path
    target: str   # raw link target (may be relative or absolute)
    location: str  # human-readable root category

    def to_dict(self) -> dict:
        return {
            "path": str(self.path),
            "target": self.target,
            "location": self.location,
        }

    def __repr__(self) -> str:
        return f"<BrokenSymlink {self.path} → {self.target}>"


# ── Walker ─────────────────────────────────────────────────────────────────────

def _label(root: Path, path: Path) -> str:
    """Return a short human-readable label for the root."""
    root_str = str(root)
    labels = {
        "/usr/local": "Homebrew (/usr/local)",
        "/opt/homebrew": "Homebrew (/opt/homebrew)",
        str(HOME / "bin"): "~/bin",
        str(HOME / ".local/bin"): "~/.local/bin",
        str(HOME / ".config"): "~/.config",
        str(HOME / "Library/LaunchAgents"): "LaunchAgents",
    }
    return labels.get(root_str, root_str)


def _walk_symlinks(
    root: Path,
    depth: int = 0,
) -> Generator[Path, None, None]:
    """Yield all symlinks (broken or not) under root."""
    if depth > _MAX_DEPTH or not root.exists():
        return
    try:
        with os.scandir(root) as it:
            for entry in it:
                if entry.name in _SKIP_NAMES:
                    continue
                if entry.is_symlink():
                    yield Path(entry.path)
                elif entry.is_dir(follow_symlinks=False):
                    yield from _walk_symlinks(Path(entry.path), depth + 1)
    except (PermissionError, OSError) as exc:
        logger.debug("walk symlinks failed for %s: %s", root, exc)


def _is_broken(path: Path) -> bool:
    """Return True if path is a symlink whose target does not exist."""
    if not path.is_symlink():
        return False
    try:
        # resolve() raises if any component is missing
        resolved = path.resolve(strict=True)
        return not resolved.exists()
    except (OSError, ValueError):
        return True


# ── Public API ─────────────────────────────────────────────────────────────────

def find_broken_symlinks(
    roots: Optional[List[Path]] = None,
    progress_callback: Optional[Callable[[int], None]] = None,
) -> List[BrokenSymlink]:
    """
    Scan *roots* (default: DEFAULT_ROOTS) and return a list of
    BrokenSymlink objects for every dangling link found.

    Args:
        roots:             Directories to search.
        progress_callback: Called every 100 symlinks with current count.

    Returns:
        List[BrokenSymlink] sorted by path.
    """
    if roots is None:
        roots = [r for r in DEFAULT_ROOTS if r.exists()]

    results: List[BrokenSymlink] = []
    seen: Set[Path] = set()
    checked = 0

    for root in roots:
        label = _label(root, root)
        for link_path in _walk_symlinks(root):
            checked += 1
            if progress_callback and checked % 100 == 0:
                progress_callback(checked)

            try:
                real = link_path.resolve()
            except (OSError, ValueError) as exc:
                logger.debug("resolve failed for %s: %s", link_path, exc)
                real = link_path

            if real in seen:
                continue
            seen.add(real)

            if _is_broken(link_path):
                try:
                    target = os.readlink(link_path)
                except OSError:
                    target = "<unreadable>"
                results.append(BrokenSymlink(
                    path=link_path,
                    target=target,
                    location=label,
                ))

    results.sort(key=lambda s: str(s.path))
    return results
