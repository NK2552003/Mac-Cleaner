"""Cloud storage cache and log scanner."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set

from constants import HOME
from utils import size_of, safe_remove


@dataclass
class CloudJunkItem:
    """One cloud cache or log directory."""
    provider: str
    category: str
    path: Path
    size: int
    safe_to_delete: bool = True


@dataclass
class CloudDeleteResult:
    """Summary of cloud junk deletions."""
    deleted: int = 0
    skipped: int = 0
    bytes_freed: int = 0
    errors: List[str] = field(default_factory=list)


_PROVIDER_ALIASES: Dict[str, str] = {
    "dropbox": "Dropbox",
    "google-drive": "Google Drive",
    "googledrive": "Google Drive",
    "drive": "Google Drive",
    "onedrive": "OneDrive",
    "box": "Box",
}

_ALLOWED_ROOTS: List[Path] = [
    HOME / "Dropbox" / ".dropbox.cache",
    HOME / "Library" / "Caches" / "com.dropbox.Dropbox",
    HOME / "Library" / "Logs" / "Dropbox",
    HOME / "Library" / "Caches" / "com.google.drivefs",
    HOME / "Library" / "Caches" / "com.microsoft.OneDrive",
    HOME / "Library" / "Logs" / "OneDrive",
    HOME / "Library" / "Application Support" / "OneDrive" / "Logs",
    HOME / "Library" / "Application Support" / "OneDrive" / "Cache",
    HOME / "Library" / "Application Support" / "OneDrive" / "Caches",
    HOME / "Library" / "Caches" / "com.box.desktop",
    HOME / "Library" / "Logs" / "Box",
]


def _is_allowed_cloud_path(path: Path) -> bool:
    try:
        resolved = path.expanduser().resolve()
    except OSError:
        resolved = path.expanduser()

    if "DriveFS" in resolved.parts and resolved.name in {"content_cache", "Logs"}:
        return True

    for root in _ALLOWED_ROOTS:
        try:
            if resolved.is_relative_to(root.expanduser().resolve()):
                return True
        except AttributeError:
            try:
                if str(resolved).startswith(str(root.expanduser().resolve())):
                    return True
            except OSError:
                continue
        except OSError:
            continue
    return False


def _add_item(items: List[CloudJunkItem], provider: str, category: str, path: Path) -> None:
    if not path.exists():
        return
    sz = size_of(path)
    if sz <= 0:
        return
    items.append(CloudJunkItem(provider=provider, category=category, path=path, size=sz))


def _collect_dropbox(home: Path) -> List[CloudJunkItem]:
    items: List[CloudJunkItem] = []
    _add_item(items, "Dropbox", "Cache", home / "Dropbox" / ".dropbox.cache")
    _add_item(items, "Dropbox", "Cache", home / "Library" / "Caches" / "com.dropbox.Dropbox")
    _add_item(items, "Dropbox", "Logs", home / "Library" / "Logs" / "Dropbox")
    return items


def _collect_google_drive(home: Path) -> List[CloudJunkItem]:
    items: List[CloudJunkItem] = []
    drive_root = home / "Library" / "Application Support" / "Google" / "DriveFS"
    if drive_root.exists():
        for child in drive_root.iterdir():
            if not child.is_dir():
                continue
            _add_item(items, "Google Drive", "Cache", child / "content_cache")
            _add_item(items, "Google Drive", "Logs", child / "Logs")
    _add_item(items, "Google Drive", "Cache", home / "Library" / "Caches" / "com.google.drivefs")
    return items


def _collect_onedrive(home: Path) -> List[CloudJunkItem]:
    items: List[CloudJunkItem] = []
    base = home / "Library" / "Application Support" / "OneDrive"
    _add_item(items, "OneDrive", "Cache", home / "Library" / "Caches" / "com.microsoft.OneDrive")
    _add_item(items, "OneDrive", "Logs", home / "Library" / "Logs" / "OneDrive")
    if base.exists():
        for name in ["Logs", "Cache", "Caches"]:
            _add_item(items, "OneDrive", "Cache", base / name)
    return items


def _collect_box(home: Path) -> List[CloudJunkItem]:
    items: List[CloudJunkItem] = []
    _add_item(items, "Box", "Cache", home / "Library" / "Caches" / "com.box.desktop")
    _add_item(items, "Box", "Logs", home / "Library" / "Logs" / "Box")
    return items


def collect_cloud_junk(
    providers: Optional[Iterable[str]] = None,
    home: Optional[Path] = None,
) -> List[CloudJunkItem]:
    """Collect cloud storage cache/log entries."""
    base = home or HOME
    selected: Set[str] = set()

    if providers:
        for p in providers:
            key = p.lower().strip()
            selected.add(_PROVIDER_ALIASES.get(key, p))

    items: List[CloudJunkItem] = []
    if not providers or "Dropbox" in selected:
        items.extend(_collect_dropbox(base))
    if not providers or "Google Drive" in selected:
        items.extend(_collect_google_drive(base))
    if not providers or "OneDrive" in selected:
        items.extend(_collect_onedrive(base))
    if not providers or "Box" in selected:
        items.extend(_collect_box(base))

    return items


def delete_cloud_junk(items: List[CloudJunkItem]) -> CloudDeleteResult:
    """Delete cloud junk items marked safe."""
    result = CloudDeleteResult()
    for item in items:
        if not item.safe_to_delete:
            result.skipped += 1
            continue
        if not _is_allowed_cloud_path(item.path):
            result.skipped += 1
            result.errors.append(f"Blocked outside allowlist: {item.path}")
            continue
        ok, freed = safe_remove(item.path)
        if ok:
            result.deleted += 1
            result.bytes_freed += freed
        else:
            result.skipped += 1
            result.errors.append(str(item.path))
    return result
