"""Homebrew status and maintenance helpers."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from utils import size_of


@dataclass
class BrewStatus:
    """Summary of Homebrew installation and caches."""
    installed: bool
    version: Optional[str] = None
    prefix: Optional[Path] = None
    cache: Optional[Path] = None
    cellar: Optional[Path] = None
    cache_size: int = 0
    cellar_size: int = 0
    formulae: int = 0
    casks: int = 0
    outdated_formulae: List[str] = field(default_factory=list)
    outdated_casks: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


@dataclass
class BrewActionResult:
    """Summary of a Homebrew command execution."""
    success: bool
    message: str
    stdout: str = ""
    stderr: str = ""


def _run_brew(args: List[str], runner=subprocess.run, timeout: int = 30) -> subprocess.CompletedProcess:
    return runner(
        ["brew"] + args,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _split_lines(text: str) -> List[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def brew_installed() -> bool:
    return shutil.which("brew") is not None


def collect_brew_status(
    include_outdated: bool = False,
    runner=subprocess.run,
) -> BrewStatus:
    """Collect Homebrew status and cache sizes."""
    if not brew_installed():
        return BrewStatus(installed=False)

    status = BrewStatus(installed=True)

    try:
        version = _run_brew(["--version"], runner=runner)
        if version.returncode == 0:
            status.version = version.stdout.splitlines()[0].strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        status.errors.append(f"brew --version failed: {exc}")

    for label, args, attr in [
        ("prefix", ["--prefix"], "prefix"),
        ("cache", ["--cache"], "cache"),
        ("cellar", ["--cellar"], "cellar"),
    ]:
        try:
            result = _run_brew(args, runner=runner)
            if result.returncode == 0:
                path = Path(result.stdout.strip())
                setattr(status, attr, path)
        except (OSError, subprocess.TimeoutExpired) as exc:
            status.errors.append(f"brew {label} lookup failed: {exc}")

    if status.cache and status.cache.exists():
        status.cache_size = size_of(status.cache)
    if status.cellar and status.cellar.exists():
        status.cellar_size = size_of(status.cellar)

    try:
        formulas = _run_brew(["list", "--formula"], runner=runner)
        if formulas.returncode == 0:
            status.formulae = len(_split_lines(formulas.stdout))
    except (OSError, subprocess.TimeoutExpired) as exc:
        status.errors.append(f"brew list --formula failed: {exc}")

    try:
        casks = _run_brew(["list", "--cask"], runner=runner)
        if casks.returncode == 0:
            status.casks = len(_split_lines(casks.stdout))
    except (OSError, subprocess.TimeoutExpired) as exc:
        status.errors.append(f"brew list --cask failed: {exc}")

    if include_outdated:
        try:
            outdated_formula = _run_brew(["outdated", "--formula"], runner=runner)
            if outdated_formula.returncode == 0:
                status.outdated_formulae = _split_lines(outdated_formula.stdout)
        except (OSError, subprocess.TimeoutExpired) as exc:
            status.errors.append(f"brew outdated --formula failed: {exc}")

        try:
            outdated_casks = _run_brew(["outdated", "--cask"], runner=runner)
            if outdated_casks.returncode == 0:
                status.outdated_casks = _split_lines(outdated_casks.stdout)
        except (OSError, subprocess.TimeoutExpired) as exc:
            status.errors.append(f"brew outdated --cask failed: {exc}")

    return status


def brew_cleanup(prune_all: bool = False, runner=subprocess.run) -> BrewActionResult:
    """Run brew cleanup (optionally with --prune=all)."""
    args = ["cleanup"]
    if prune_all:
        args.append("--prune=all")
    try:
        result = _run_brew(args, runner=runner, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return BrewActionResult(False, f"brew cleanup failed: {exc}")

    if result.returncode == 0:
        return BrewActionResult(True, "brew cleanup completed", result.stdout, result.stderr)
    return BrewActionResult(False, "brew cleanup failed", result.stdout, result.stderr)


def brew_autoremove(runner=subprocess.run) -> BrewActionResult:
    """Run brew autoremove to remove unused dependencies."""
    try:
        result = _run_brew(["autoremove"], runner=runner, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return BrewActionResult(False, f"brew autoremove failed: {exc}")

    if result.returncode == 0:
        return BrewActionResult(True, "brew autoremove completed", result.stdout, result.stderr)
    return BrewActionResult(False, "brew autoremove failed", result.stdout, result.stderr)


def brew_update(runner=subprocess.run) -> BrewActionResult:
    """Run brew update."""
    try:
        result = _run_brew(["update"], runner=runner, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return BrewActionResult(False, f"brew update failed: {exc}")

    if result.returncode == 0:
        return BrewActionResult(True, "brew update completed", result.stdout, result.stderr)
    return BrewActionResult(False, "brew update failed", result.stdout, result.stderr)


def brew_doctor(runner=subprocess.run) -> BrewActionResult:
    """Run brew doctor."""
    try:
        result = _run_brew(["doctor"], runner=runner, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return BrewActionResult(False, f"brew doctor failed: {exc}")

    if result.returncode == 0:
        return BrewActionResult(True, "brew doctor completed", result.stdout, result.stderr)
    return BrewActionResult(False, "brew doctor failed", result.stdout, result.stderr)
