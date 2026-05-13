"""Font cache rebuild helpers."""

from __future__ import annotations

import logging
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from constants import HOME
from utils import safe_remove

logger = logging.getLogger(__name__)


@dataclass
class FontCacheStep:
    """One font cache action."""
    command: List[str]
    success: bool
    stdout: str = ""
    stderr: str = ""


@dataclass
class FontCacheResult:
    """Summary of font cache rebuild."""
    success: bool
    steps: List[FontCacheStep] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


_USER_CACHE_DIRS = [
    HOME / "Library" / "FontCaches",
    HOME / "Library" / "Caches" / "com.apple.ATS",
]


def _run_cmd(args: List[str], runner=subprocess.run) -> FontCacheStep:
    try:
        result = runner(
            args,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.debug("Font cache command failed: %s", exc)
        return FontCacheStep(command=args, success=False, stderr=str(exc))

    ok = result.returncode == 0
    return FontCacheStep(
        command=args,
        success=ok,
        stdout=result.stdout.strip(),
        stderr=result.stderr.strip(),
    )


def rebuild_font_cache(
    clear_user: bool = False,
    runner=subprocess.run,
) -> FontCacheResult:
    """Rebuild system font caches using atsutil."""
    steps: List[FontCacheStep] = []
    errors: List[str] = []

    if clear_user:
        for cache_dir in _USER_CACHE_DIRS:
            if cache_dir.exists():
                ok, _freed = safe_remove(cache_dir)
                if not ok:
                    errors.append(f"Failed to remove {cache_dir}")

    atsutil = shutil.which("atsutil")
    if not atsutil:
        return FontCacheResult(
            success=False,
            steps=steps,
            errors=["atsutil not found"],
        )

    for cmd in [
        [atsutil, "server", "-shutdown"],
        [atsutil, "databases", "-remove"],
        [atsutil, "server", "-ping"],
    ]:
        step = _run_cmd(cmd, runner=runner)
        steps.append(step)
        if not step.success:
            errors.append(" ".join(cmd))

    return FontCacheResult(
        success=all(s.success for s in steps) and not errors,
        steps=steps,
        errors=errors,
    )
