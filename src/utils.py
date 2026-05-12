
"""Utility helpers for logging and filesystem operations.

Functions:
    configure_logging: Configure app-wide logging handlers.
    bytes_human: Format bytes in a human-friendly way.
    actual_disk_usage: Calculate real on-disk size using filesystem blocks.
    safe_remove: Delete files/directories with fallbacks for sandboxed paths.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
import re
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple

from constants import CONFIG_DIR

logger = logging.getLogger(__name__)

_LOGGER_CONFIGURED = False
_LOG_PATH: Optional[Path] = None
_DEFAULT_LOG_FILE = CONFIG_DIR / "mac-cleaner.log"


def configure_logging(
    verbose: bool = False,
    log_file: Optional[Path] = None,
) -> Optional[Path]:
    """Configure app-wide logging.

    Args:
        verbose: Enable debug logging if True.
        log_file: Optional log file path override.

    Returns:
        The resolved log file path if file logging is enabled; otherwise None.
    """
    global _LOGGER_CONFIGURED
    global _LOG_PATH
    if _LOGGER_CONFIGURED:
        return _LOG_PATH

    level = logging.DEBUG if verbose else logging.INFO
    target = log_file or _DEFAULT_LOG_FILE
    handler: logging.Handler
    resolved: Optional[Path]

    try:
        resolved = Path(target).expanduser().resolve()
        resolved.parent.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            str(resolved),
            maxBytes=1_000_000,
            backupCount=3,
            encoding="utf-8",
        )
    except OSError:
        resolved = None
        handler = logging.StreamHandler()

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(level)
    if isinstance(handler, RotatingFileHandler):
        exists = any(
            isinstance(h, RotatingFileHandler)
            and getattr(h, "baseFilename", "") == handler.baseFilename
            for h in root.handlers
        )
        if not exists:
            root.addHandler(handler)
    else:
        root.addHandler(handler)

    _LOG_PATH = resolved
    _LOGGER_CONFIGURED = True
    return _LOG_PATH


def bytes_human(n: int) -> str:
    """Convert a byte count to a human-readable string.

    Args:
        n: Byte count.

    Returns:
        Human-friendly size string (e.g., "1.2 GB").
    """
    if n < 0:
        return "0 B"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n = int(n/1024)
    return f"{n:.1f} PB"


def actual_disk_usage(path: Path) -> int:
    """Return actual allocated disk usage in bytes.

    Uses `st_blocks` when available to report real on-disk size, falling back
    to apparent size when needed.

    Args:
        path: File or directory to inspect.

    Returns:
        Allocated size in bytes.
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
    except (PermissionError, OSError) as exc:
        logger.debug("actual_disk_usage failed for %s: %s", path, exc)
    return total


def size_of(path: Path) -> int:
    """Get the allocated size of a file or directory.

    Args:
        path: File or directory path.

    Returns:
        Size in bytes.
    """
    return actual_disk_usage(path)


def iterdir_safe(path: Path) -> List[Path]:
    """Safely iterate a directory.

    Args:
        path: Directory to list.

    Returns:
        Sorted list of children, or an empty list on error.
    """
    if not path.exists():
        return []
    try:
        return sorted(path.iterdir())
    except (PermissionError, OSError) as exc:
        logger.debug("iterdir_safe failed for %s: %s", path, exc)
        return []


def rm_rf(path: Path) -> Tuple[bool, str]:
    """Remove a path using the system `rm -rf` command.

    This is a fallback for sandboxed containers that `shutil.rmtree` can't
    delete reliably.

    Args:
        path: File or directory to delete.

    Returns:
        Tuple of (success, error_message).
    """
    try:
        result = subprocess.run(
            ["rm", "-rf", "--", str(path)],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode == 0:
            return True, ""
        logger.debug("rm_rf failed for %s: %s", path, result.stderr.strip())
        return False, result.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "Deletion timed out after 60 seconds"
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        logger.debug("rm_rf exception for %s: %s", path, exc)
        return False, str(exc)


def safe_remove(path: Path) -> Tuple[bool, int]:
    """Remove a file or directory safely.

    Args:
        path: File or directory to remove.

    Returns:
        Tuple of (success, freed_bytes).
    """
    sz = size_of(path)

    # Try standard Python deletion first
    try:
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink(missing_ok=True)
        return True, sz
    except PermissionError as exc:
        logger.debug("safe_remove permission error for %s: %s", path, exc)
        # Fallback: subprocess rm -rf (for sandboxed containers)
        ok, _err = rm_rf(path)
        if ok:
            return True, sz
        return False, 0
    except OSError as exc:
        logger.debug("safe_remove os error for %s: %s", path, exc)
        ok, _err = rm_rf(path)
        if ok:
            return True, sz
        return False, 0


def stem_of(name: str) -> str:
    """Extract the lowercase stem of a filename.

    Args:
        name: Filename or path-like string.

    Returns:
        Lowercased stem.
    """
    return Path(name).stem.lower()


def derive_display_name(raw: str) -> str:
    """Derive a human-readable app name from a bundle-style identifier.

    Args:
        raw: Bundle-ID-like directory name (e.g., "com.example.myapp").

    Returns:
        Display-friendly name.
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
    """Count files recursively inside a directory.

    Args:
        path: Directory to count.

    Returns:
        Number of files found.
    """
    if not path.is_dir():
        return 1
    count = 0
    try:
        for child in path.rglob("*"):
            if child.is_file():
                count += 1
    except (PermissionError, OSError) as exc:
        logger.debug("count_files_recursive failed for %s: %s", path, exc)
    return count
