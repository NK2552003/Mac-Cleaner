"""
Discovers all installed applications by scanning standard macOS
app directories and reading Info.plist files.
"""

from __future__ import annotations

import logging
import plistlib
from pathlib import Path
from typing import Dict

from constants import APP_SEARCH_DIRS
from config.models import AppInfo

logger = logging.getLogger(__name__)


def _ingest_app(app_path: Path, apps: Dict[str, AppInfo]) -> None:
    """Read an .app bundle's Info.plist and register it."""
    info_plist = app_path / "Contents" / "Info.plist"
    if not info_plist.exists():
        # Some apps (iOS-style) use a flat layout
        info_plist = app_path / "Info.plist"
        if not info_plist.exists():
            return

    try:
        with open(info_plist, "rb") as f:
            pl = plistlib.load(f)

        bid = pl.get("CFBundleIdentifier", "").strip()
        if not bid:
            return

        name = (
            pl.get("CFBundleDisplayName")
            or pl.get("CFBundleName")
            or app_path.stem
        )

        apps[bid.lower()] = AppInfo(
            name=name,
            bundle_id=bid,
            path=app_path,
        )
    except (plistlib.InvalidFileException, KeyError, OSError, ValueError) as exc:
        logger.debug("Failed to read Info.plist %s: %s", info_plist, exc)


def _scan_directory(root: Path, apps: Dict[str, AppInfo], depth: int = 0) -> None:
    """Recursively scan a directory for .app bundles."""
    if not root.exists() or depth > 3:
        return
    try:
        for item in sorted(root.iterdir()):
            if item.suffix == ".app":
                _ingest_app(item, apps)
            elif item.is_dir() and not item.is_symlink() and depth < 3:
                # Don't descend into .app bundles
                if item.suffix != ".app":
                    _scan_directory(item, apps, depth + 1)
    except PermissionError as exc:
        logger.debug("Permission denied scanning %s: %s", root, exc)


def discover_installed_apps() -> Dict[str, AppInfo]:
    """
    Scan all standard macOS application directories and return
    a dict mapping bundle_id (lowercase) → AppInfo.
    """
    apps: Dict[str, AppInfo] = {}

    for search_dir in APP_SEARCH_DIRS:
        _scan_directory(search_dir, apps)

    # Also scan Homebrew cask app links
    for cask_dir in [
        Path("/opt/homebrew/Caskroom"),
        Path("/usr/local/Caskroom"),
    ]:
        if cask_dir.exists():
            try:
                for cask in cask_dir.iterdir():
                    if cask.is_dir():
                        _scan_directory(cask, apps, depth=1)
            except PermissionError as exc:
                logger.debug("Permission denied scanning cask %s: %s", cask_dir, exc)

    return apps
