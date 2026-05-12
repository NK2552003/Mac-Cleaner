"""
Mac Deep Cleaner v1.5.0 — Universal Binary Thinner
================================================
Detects fat (universal) Mach-O binaries that contain both arm64 and x86_64
slices, and optionally thins them to keep only the slice matching the current
CPU. This can reclaim several hundred MB on machines with many Homebrew or
cross-compiled tools.

Detection
---------
Uses the `file` command (built into macOS) to detect Mach-O universal
binaries quickly without parsing binary headers in Python.

Thinning
--------
Uses `ditto --arch <arch> <src> <dst>` — the Apple-recommended approach.
`ditto` preserves extended attributes, resource forks, and ACLs, making it
safer than `lipo -remove`.

Safety
------
- Never thins system binaries in /System or /usr (not /usr/local).
- Requires explicit opt-in; this module never deletes automatically.
- Validates that the thinned binary is larger than 0 bytes before replacing.
- Creates a backup copy next to the original (*.fat_backup) unless the user
  passes keep_backup=False.
"""

from __future__ import annotations

import logging
import platform
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional, Set, Tuple

from utils import bytes_human, size_of

logger = logging.getLogger(__name__)

# ── Architecture detection ─────────────────────────────────────────────────────

def _current_arch() -> str:
    """Return 'arm64' or 'x86_64' for the running CPU."""
    machine = platform.machine()
    if machine == "arm64":
        return "arm64"
    return "x86_64"


def _other_arch(arch: str) -> str:
    return "x86_64" if arch == "arm64" else "arm64"


# ── Protected paths ────────────────────────────────────────────────────────────

_PROTECTED_PREFIXES: Tuple[str, ...] = (
    "/System",
    "/usr/bin",
    "/usr/sbin",
    "/usr/lib",
    "/private",
    "/bin",
    "/sbin",
)


def _is_protected(path: Path) -> bool:
    s = str(path)
    return any(s.startswith(p) for p in _PROTECTED_PREFIXES)


# ── Data model ─────────────────────────────────────────────────────────────────

@dataclass
class FatBinary:
    """A universal (fat) binary with both arm64 and x86_64 slices."""
    path: Path
    size: int = field(init=False)

    def __post_init__(self) -> None:
        self.size = size_of(self.path)

    @property
    def size_human(self) -> str:
        return bytes_human(self.size)

    def estimated_saving(self) -> int:
        """Rough estimate: ~40–50% of binary size for a single-arch slice."""
        return int(self.size * 0.45)

    def to_dict(self) -> dict:
        return {
            "path": str(self.path),
            "size": self.size,
            "size_human": self.size_human,
            "estimated_saving": self.estimated_saving(),
            "estimated_saving_human": bytes_human(self.estimated_saving()),
        }

    def __repr__(self) -> str:
        return f"<FatBinary {self.path.name} {self.size_human}>"


@dataclass
class ThinResult:
    """Result of a thinning operation."""
    path: Path
    success: bool
    bytes_freed: int = 0
    error: str = ""


# ── Scanner ────────────────────────────────────────────────────────────────────

def _is_universal(path: Path) -> bool:
    """Use `file` to check if a path is a Mach-O universal binary."""
    try:
        result = subprocess.run(
            ["file", str(path)],
            capture_output=True, text=True, timeout=5,
        )
        out = result.stdout.lower()
        return "universal binary" in out and (
            "arm64" in out and "x86_64" in out
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        logger.debug("file command failed for %s: %s", path, exc)
        return False


def _walk_executables(root: Path) -> List[Path]:
    """Walk root and yield executable files (by permission bit)."""
    results: List[Path] = []
    try:
        for item in root.rglob("*"):
            if item.is_symlink() or not item.is_file():
                continue
            if _is_protected(item):
                continue
            # Check execute bit
            try:
                if item.stat().st_mode & 0o111:
                    results.append(item)
            except OSError:
                pass
    except (PermissionError, OSError) as exc:
        logger.debug("walk executables failed for %s: %s", root, exc)
    return results


def find_fat_binaries(
    roots: Optional[List[Path]] = None,
    progress_callback: Optional[Callable[[int], None]] = None,
) -> List[FatBinary]:
    """
    Find universal (fat) binaries in *roots*.

    Default roots:
      /usr/local/bin, /usr/local/lib,
      /opt/homebrew/bin, /opt/homebrew/lib,
      ~/Applications

    Returns:
        List[FatBinary] sorted by size descending.
    """
    from constants import HOME

    if roots is None:
        roots = [
            p for p in [
                Path("/usr/local/bin"),
                Path("/usr/local/lib"),
                Path("/opt/homebrew/bin"),
                Path("/opt/homebrew/lib"),
                HOME / "Applications",
            ] if p.exists()
        ]

    candidates: List[Path] = []
    for root in roots:
        candidates.extend(_walk_executables(root))

    results: List[FatBinary] = []
    for i, path in enumerate(candidates):
        if progress_callback and i % 50 == 0:
            progress_callback(i)
        if _is_universal(path):
            results.append(FatBinary(path=path))

    results.sort(key=lambda b: b.size, reverse=True)
    return results


# ── Thinner ────────────────────────────────────────────────────────────────────

def thin_binary(
    fat: FatBinary,
    arch: Optional[str] = None,
    keep_backup: bool = True,
) -> ThinResult:
    """
    Thin a fat binary to the specified architecture using `ditto --arch`.

    Args:
        fat:         FatBinary to thin.
        arch:        Target architecture ('arm64' or 'x86_64').
                     Defaults to the current CPU architecture.
        keep_backup: If True, copy original to <path>.fat_backup first.

    Returns:
        ThinResult with success status and bytes freed.
    """
    if arch is None:
        arch = _current_arch()

    path = fat.path

    if _is_protected(path):
        return ThinResult(path=path, success=False, error="Protected path")

    if not path.exists():
        return ThinResult(path=path, success=False, error="File not found")

    original_size = size_of(path)

    # Backup
    if keep_backup:
        backup_path = path.with_suffix(path.suffix + ".fat_backup")
        try:
            shutil.copy2(path, backup_path)
        except OSError as e:
            return ThinResult(path=path, success=False, error=f"Backup failed: {e}")

    # Thin to temp file first, then replace
    try:
        with tempfile.NamedTemporaryFile(
            dir=path.parent, prefix=".thin_", delete=False
        ) as tmp:
            tmp_path = Path(tmp.name)

        result = subprocess.run(
            ["ditto", "--arch", arch, str(path), str(tmp_path)],
            capture_output=True, text=True, timeout=120,
        )

        if result.returncode != 0:
            tmp_path.unlink(missing_ok=True)
            return ThinResult(
                path=path, success=False,
                error=result.stderr.strip() or "ditto failed",
            )

        new_size = size_of(tmp_path)
        if new_size == 0:
            tmp_path.unlink(missing_ok=True)
            return ThinResult(path=path, success=False, error="Thinned file is empty")

        # Replace original with thinned version
        shutil.move(str(tmp_path), str(path))
        freed = max(0, original_size - new_size)
        return ThinResult(path=path, success=True, bytes_freed=freed)

    except subprocess.TimeoutExpired:
        return ThinResult(path=path, success=False, error="ditto timed out")
    except OSError as e:
        return ThinResult(path=path, success=False, error=str(e))


def current_architecture() -> str:
    """Return the current machine architecture for display."""
    return _current_arch()
