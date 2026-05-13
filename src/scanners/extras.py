"""
iOS Backup Finder
-----------------
Locates iTunes / Finder iPhone/iPad backups stored in:
  ~/Library/Application Support/MobileSync/Backup/

Each backup directory is named with a UUID and contains a Manifest.plist
that identifies the device name, iOS version, and backup date.

Language Pack Stripper
-----------------------
Many macOS apps ship with 30+ localisations bundled inside their .app
bundle as `*.lproj` directories. This scanner:
1. Walks installed applications in /Applications and ~/Applications.
2. For each app, identifies all bundled .lproj directories.
3. Computes the space used by localisations the user doesn't need.

NOTE: This module *reports only*. Actual stripping (via `ditto --arch`
and lproj removal) is handled by cleaner.py using the entries returned here.
"""

from __future__ import annotations

import locale
import logging
import plistlib
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from constants import HOME
from utils import bytes_human, iterdir_safe, size_of

logger = logging.getLogger(__name__)

# ── iOS Backup ─────────────────────────────────────────────────────────────────

BACKUP_ROOT = HOME / "Library" / "Application Support" / "MobileSync" / "Backup"


@dataclass
class IOSBackup:
    """One iPhone/iPad backup directory."""
    path: Path
    device_name: str
    product_type: str       # e.g. "iPhone14,3"
    ios_version: str
    last_backup_date: Optional[datetime]
    size: int = field(init=False)

    def __post_init__(self) -> None:
        self.size = size_of(self.path)

    @property
    def size_human(self) -> str:
        return bytes_human(self.size)

    @property
    def age_days(self) -> Optional[int]:
        if self.last_backup_date is None:
            return None
        delta = datetime.now() - self.last_backup_date
        return delta.days

    def to_dict(self) -> dict:
        return {
            "path": str(self.path),
            "device_name": self.device_name,
            "product_type": self.product_type,
            "ios_version": self.ios_version,
            "last_backup_date": (
                self.last_backup_date.isoformat()
                if self.last_backup_date else None
            ),
            "age_days": self.age_days,
            "size": self.size,
            "size_human": self.size_human,
        }

    def __repr__(self) -> str:
        return f"<IOSBackup {self.device_name!r} {self.size_human}>"


def _parse_backup(path: Path) -> Optional[IOSBackup]:
    """Read Manifest.plist and return an IOSBackup, or None on failure."""
    manifest = path / "Manifest.plist"
    info = path / "Info.plist"

    # Try Manifest first, then Info
    for plist_path in (manifest, info):
        if not plist_path.exists():
            continue
        try:
            with open(plist_path, "rb") as f:
                pl = plistlib.load(f)
            device_name = (
                pl.get("DeviceName")
                or pl.get("Product Name")
                or path.name[:8]
            )
            product_type = pl.get("Product Type", "Unknown")
            ios_version = (
                pl.get("ProductVersion")
                or pl.get("Installed Applications", {})
                and "Unknown"
                or "Unknown"
            )
            raw_date = pl.get("Date") or pl.get("Last Backup Date")
            last_backup = raw_date if isinstance(raw_date, datetime) else None
            return IOSBackup(
                path=path,
                device_name=str(device_name),
                product_type=str(product_type),
                ios_version=str(ios_version),
                last_backup_date=last_backup,
            )
        except (plistlib.InvalidFileException, OSError, KeyError, ValueError) as exc:
            logger.debug("Failed to read backup plist %s: %s", plist_path, exc)
            continue

    # No readable plist — still report the directory
    return IOSBackup(
        path=path,
        device_name=path.name[:8],
        product_type="Unknown",
        ios_version="Unknown",
        last_backup_date=None,
    )


def find_ios_backups() -> List[IOSBackup]:
    """
    Return all iOS backups found in the standard MobileSync location,
    sorted by size descending.
    """
    backups: List[IOSBackup] = []
    if not BACKUP_ROOT.exists():
        return backups

    for child in iterdir_safe(BACKUP_ROOT):
        if child.is_dir() and len(child.name) >= 8:
            b = _parse_backup(child)
            if b:
                backups.append(b)

    backups.sort(key=lambda b: b.size, reverse=True)
    return backups


# ── Language Pack ──────────────────────────────────────────────────────────────

# Locales that should ALWAYS be kept regardless of system language
_ALWAYS_KEEP_LOCALES: Set[str] = {"en", "en_US", "Base"}


def _system_preferred_locales() -> Set[str]:
    """
    Return the set of lproj names that should be kept.
    Includes the system locale, language code, and English.
    """
    keep: Set[str] = set(_ALWAYS_KEEP_LOCALES)

    # Ask macOS for preferred languages
    try:
        out = subprocess.run(
            ["defaults", "read", "-g", "AppleLanguages"],
            capture_output=True, text=True, timeout=5,
        ).stdout
        # Output is an array like: (\n    "en-US",\n    "fr-FR"\n)
        import re
        langs = re.findall(r'"?([a-zA-Z]{2,3}(?:[_-][a-zA-Z]{2,3})?)"?', out)
        for lang in langs:
            keep.add(lang)
            keep.add(lang.replace("-", "_"))
            keep.add(lang.split("-")[0])
            keep.add(lang.split("_")[0])
    except Exception as exc:
        logger.debug("Failed to read AppleLanguages: %s", exc)

    # Fallback: Python locale
    try:
        lc = locale.getdefaultlocale()[0]
        if lc:
            keep.add(lc)
            keep.add(lc.split("_")[0])
    except Exception as exc:
        logger.debug("Failed to read default locale: %s", exc)

    return keep


@dataclass
class LanguagePackEntry:
    """Strippable lproj directories inside a single application."""
    app_path: Path
    app_name: str
    removable_lprojs: List[Path]   # lproj dirs that are safe to delete
    kept_lprojs: List[Path]        # lproj dirs that will be kept
    removable_size: int = field(init=False)

    def __post_init__(self) -> None:
        self.removable_size = sum(size_of(p) for p in self.removable_lprojs)

    @property
    def removable_size_human(self) -> str:
        return bytes_human(self.removable_size)

    def to_dict(self) -> dict:
        return {
            "app": str(self.app_path),
            "app_name": self.app_name,
            "removable_count": len(self.removable_lprojs),
            "removable_size": self.removable_size,
            "removable_size_human": self.removable_size_human,
            "removable": [str(p) for p in self.removable_lprojs],
            "kept": [str(p) for p in self.kept_lprojs],
        }

    def __repr__(self) -> str:
        return (
            f"<LanguagePack {self.app_name!r} "
            f"removable={len(self.removable_lprojs)} "
            f"saves={self.removable_size_human}>"
        )


def _lprojs_in_bundle(app_path: Path) -> List[Path]:
    """Return all .lproj directories inside an .app bundle."""
    lprojs: List[Path] = []
    for candidate in [
        app_path / "Contents" / "Resources",
        app_path / "Resources",
    ]:
        if candidate.exists():
            try:
                for child in candidate.iterdir():
                    if child.suffix == ".lproj" and child.is_dir():
                        lprojs.append(child)
            except (PermissionError, OSError) as exc:
                logger.debug("Language pack scan failed for %s: %s", candidate, exc)
    return lprojs


def find_language_packs(
    app_dirs: Optional[List[Path]] = None,
) -> List[LanguagePackEntry]:
    """
    Scan installed apps and find removable language packs.

    Args:
        app_dirs: Directories to look for .app bundles.
                  Defaults to [/Applications, ~/Applications].

    Returns:
        List[LanguagePackEntry] with removable_size > 0, sorted by size desc.
    """
    if app_dirs is None:
        app_dirs = [
            Path("/Applications"),
            HOME / "Applications",
        ]

    keep = _system_preferred_locales()
    results: List[LanguagePackEntry] = []

    for app_dir in app_dirs:
        if not app_dir.exists():
            continue
        try:
            for item in app_dir.iterdir():
                if item.suffix != ".app" or not item.is_dir():
                    continue
                lprojs = _lprojs_in_bundle(item)
                if not lprojs:
                    continue

                removable: List[Path] = []
                kept: List[Path] = []

                for lproj in lprojs:
                    # lproj stem, e.g. "fr", "fr_FR", "Base", "en_GB"
                    stem = lproj.stem.replace("-", "_")
                    stem_short = stem.split("_")[0]
                    if stem in keep or stem_short in keep:
                        kept.append(lproj)
                    else:
                        removable.append(lproj)

                if removable:
                    results.append(LanguagePackEntry(
                        app_path=item,
                        app_name=item.stem,
                        removable_lprojs=removable,
                        kept_lprojs=kept,
                    ))
        except (PermissionError, OSError):
            continue

    results.sort(key=lambda e: e.removable_size, reverse=True)
    return results
