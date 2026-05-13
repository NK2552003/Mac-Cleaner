"""App update checker helpers."""

from __future__ import annotations

import logging
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import List

logger = logging.getLogger(__name__)


@dataclass
class UpdateReport:
    """Summary of available updates."""
    system_updates: List[str] = field(default_factory=list)
    brew_formulae: List[str] = field(default_factory=list)
    brew_casks: List[str] = field(default_factory=list)
    mas_updates: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


def _run(args: List[str], timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def check_system_updates() -> List[str]:
    """Return available macOS software updates."""
    try:
        result = _run(["softwareupdate", "-l"], timeout=120)
    except (OSError, subprocess.TimeoutExpired):
        return []

    if result.returncode != 0:
        return []

    updates: List[str] = []
    for line in result.stdout.splitlines():
        stripped = line.strip()
        if stripped.startswith("*"):
            updates.append(stripped.lstrip("* "))
        elif stripped.lower().startswith("label:"):
            updates.append(stripped.split(":", 1)[-1].strip())

    return updates


def check_brew_updates() -> tuple[list[str], list[str]]:
    """Return Homebrew outdated formulae and casks."""
    if not shutil.which("brew"):
        return [], []

    formulae: List[str] = []
    casks: List[str] = []

    try:
        out_formula = _run(["brew", "outdated", "--formula"], timeout=60)
        if out_formula.returncode == 0:
            formulae = [l.strip() for l in out_formula.stdout.splitlines() if l.strip()]
    except (OSError, subprocess.TimeoutExpired):
        pass

    try:
        out_cask = _run(["brew", "outdated", "--cask"], timeout=60)
        if out_cask.returncode == 0:
            casks = [l.strip() for l in out_cask.stdout.splitlines() if l.strip()]
    except (OSError, subprocess.TimeoutExpired):
        pass

    return formulae, casks


def check_mas_updates() -> List[str]:
    """Return Mac App Store updates via mas (if installed)."""
    if not shutil.which("mas"):
        return []

    try:
        result = _run(["mas", "outdated"], timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return []

    if result.returncode != 0:
        return []

    updates: List[str] = []
    for line in result.stdout.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        updates.append(stripped)
    return updates


def collect_update_report() -> UpdateReport:
    """Collect updates from system, Homebrew, and Mac App Store."""
    report = UpdateReport()

    try:
        report.system_updates = check_system_updates()
    except Exception as exc:
        logger.debug("system update check failed: %s", exc)
        report.errors.append("system update check failed")

    try:
        formulae, casks = check_brew_updates()
        report.brew_formulae = formulae
        report.brew_casks = casks
    except Exception as exc:
        logger.debug("brew update check failed: %s", exc)
        report.errors.append("brew update check failed")

    try:
        report.mas_updates = check_mas_updates()
    except Exception as exc:
        logger.debug("mas update check failed: %s", exc)
        report.errors.append("mas update check failed")

    return report
