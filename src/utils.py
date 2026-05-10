"""
Mac Deep Cleaner v1.0.0 — Utilities
================================
Shared helper functions for filesystem operations, formatting, etc.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import List, Tuple


def bytes_human(n: int) -> str:
    """Convert byte count to human-readable string."""
    if n < 0:
        return "0 B"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def actual_disk_usage(path: Path) -> int:
    """
    Return actual allocated disk usage in bytes using st_blocks.
    This gives the real on-disk size rather than apparent file size.
    """
    if path.is_symlink() or not path.exists():
        return 0
    if path.is_file():
        try:
            return path.stat().st_blocks * 512
        except (OSError, AttributeError):
            try:
                return path.stat().st_size
            except OSError:
                return 0
    total = 0
    try:
        for child in path.rglob("*"):
            if child.is_file() and not child.is_symlink():
                try:
                    total += child.stat().st_blocks * 512
                except (OSError, AttributeError):
                    try:
                        total += child.stat().st_size
                    except OSError:
                        pass
    except (PermissionError, OSError):
        pass
    return total


def size_of(path: Path) -> int:
    """Get size of a file or directory."""
    return actual_disk_usage(path)


def iterdir_safe(path: Path) -> List[Path]:
    """Safely iterate a directory, returning empty list on errors."""
    if not path.exists():
        return []
    try:
        return sorted(path.iterdir())
    except (PermissionError, OSError):
        return []


def rm_rf(path: Path) -> Tuple[bool, str]:
    """
    Remove path using subprocess rm -rf for reliable deletion of
    sandboxed containers that shutil.rmtree can't handle.
    Returns (success, error_message).
    """
    try:
        result = subprocess.run(
            ["rm", "-rf", str(path)],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode == 0:
            return True, ""
        return False, result.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "Deletion timed out after 60 seconds"
    except Exception as e:
        return False, str(e)


def safe_remove(path: Path) -> Tuple[bool, int]:
    """
    Remove a file/directory safely.
    Returns (success, freed_bytes).
    """
    sz = size_of(path)

    # Try standard Python deletion first
    try:
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink(missing_ok=True)
        return True, sz
    except PermissionError:
        # Fallback: subprocess rm -rf (for sandboxed containers)
        ok, _err = rm_rf(path)
        if ok:
            return True, sz
        return False, 0
    except OSError:
        ok, _err = rm_rf(path)
        if ok:
            return True, sz
        return False, 0


def stem_of(name: str) -> str:
    """Extract the lowercase stem of a filename."""
    return Path(name).stem.lower()


def derive_display_name(raw: str) -> str:
    """
    Derive a human-readable app name from a bundle-ID-style directory name.
    E.g., "com.example.myapp" → "Myapp"
    """
    stem = Path(raw).stem

    # Strip common domain prefixes
    for prefix in ("com.", "org.", "net.", "io.", "app.", "dev."):
        if stem.lower().startswith(prefix):
            stem = stem[len(prefix):]
            parts = stem.split(".")
            # Skip vendor prefix if short
            if len(parts) > 1 and len(parts[0]) <= 14 and " " not in parts[0]:
                stem = ".".join(parts[1:])
            break

    # Convert separators to spaces and title-case
    name = re.sub(r"[.\-_]+", " ", stem).strip().title()
    return name or raw


def count_files_recursive(path: Path) -> int:
    """Count files recursively inside a directory."""
    if not path.is_dir():
        return 1
    count = 0
    try:
        for child in path.rglob("*"):
            if child.is_file():
                count += 1
    except (PermissionError, OSError):
        pass
    return count
