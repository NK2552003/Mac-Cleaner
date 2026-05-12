"""Full app uninstaller helpers."""

from __future__ import annotations

import plistlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

from config.models import AppInfo
from constants import SEARCH_ROOTS
from core.safety import validate_path_for_deletion
from core.scanner import classify_root
from scanners.matching import match_to_app
from utils import iterdir_safe, size_of


@dataclass
class UninstallItem:
    """One deletable (or protected) app artifact."""
    path: Path
    category: str
    size: int
    protected: bool = False
    reason: str = ""


@dataclass
class UninstallPlan:
    """Resolved uninstall plan for a single app."""
    app: AppInfo
    items: List[UninstallItem] = field(default_factory=list)
    protected_items: List[UninstallItem] = field(default_factory=list)

    @property
    def deletable_items(self) -> List[UninstallItem]:
        return [i for i in self.items if not i.protected]

    @property
    def total_size(self) -> int:
        return sum(i.size for i in self.deletable_items)


@dataclass
class UninstallResult:
    """Summary of an uninstall operation."""
    deleted: int = 0
    staged: int = 0
    skipped: int = 0
    bytes_freed: int = 0
    errors: List[str] = field(default_factory=list)


def _read_app_info(app_path: Path) -> AppInfo:
    info_plist = app_path / "Contents" / "Info.plist"
    if not info_plist.exists():
        info_plist = app_path / "Info.plist"

    name = app_path.stem
    bundle_id = app_path.stem

    if info_plist.exists():
        try:
            with open(info_plist, "rb") as f:
                pl = plistlib.load(f)
            bundle_id = pl.get("CFBundleIdentifier", bundle_id)
            name = pl.get("CFBundleDisplayName") or pl.get("CFBundleName") or name
        except (OSError, plistlib.InvalidFileException, ValueError):
            pass

    return AppInfo(name=str(name), bundle_id=str(bundle_id), path=app_path)


def find_app_candidates(query: str, apps: Dict[str, AppInfo]) -> List[AppInfo]:
    """Return matching installed apps for a query string or .app path."""
    q = query.strip()
    candidates: List[AppInfo] = []

    path = Path(q).expanduser()
    if path.exists() and path.suffix == ".app":
        app_info = _read_app_info(path)
        if app_info.bundle_id in apps:
            return [apps[app_info.bundle_id]]
        return [app_info]

    q_lower = q.lower()

    for app in apps.values():
        if q_lower in (app.bundle_id, app.name_lower):
            candidates.append(app)
            continue
        if q_lower in app.bundle_id or q_lower in app.name_lower:
            candidates.append(app)

    if not candidates:
        matched = match_to_app(q_lower, apps)
        if matched:
            candidates.append(matched)

    seen: Set[str] = set()
    unique: List[AppInfo] = []
    for app in candidates:
        if app.bundle_id in seen:
            continue
        seen.add(app.bundle_id)
        unique.append(app)

    return sorted(unique, key=lambda a: a.name_lower)


def _identifier_set(app: AppInfo) -> Tuple[str, str, Set[str], str]:
    bundle_id = app.bundle_id.lower().strip()
    parts = [p for p in bundle_id.split(".") if p]
    vendor = parts[1] if len(parts) >= 2 else ""
    product = parts[-1] if parts else bundle_id

    tokens: Set[str] = set()
    if len(product) >= 4:
        tokens.add(product)
    for word in re.split(r"[\s\-_]+", app.name_lower):
        if len(word) >= 4:
            tokens.add(word)

    return bundle_id, vendor, tokens, app.name_lower


def _matches_bundle_prefix(name: str, bundle_id: str) -> bool:
    if not bundle_id:
        return False
    return name == bundle_id or name.startswith(bundle_id + ".") or name.startswith(bundle_id + "-")


def _matches_bundle_suffix(name: str, bundle_id: str) -> bool:
    if not bundle_id:
        return False
    return name == bundle_id or name.endswith("." + bundle_id) or name.endswith(bundle_id)


def _matches_direct_name(name: str, bundle_id: str, tokens: Set[str], app_name: str) -> bool:
    if _matches_bundle_prefix(name, bundle_id):
        return True
    if app_name and name == app_name:
        return True
    if name in tokens:
        return True
    return False


def _matches_vendor_child(name: str, bundle_id: str, tokens: Set[str]) -> bool:
    if _matches_bundle_prefix(name, bundle_id):
        return True
    for token in tokens:
        if name == token or name.startswith(token):
            return True
    return False


def _root_kind(root: Path) -> str:
    s = str(root).lower().rstrip("/")
    if "group containers" in s:
        return "Group Containers"
    if s.endswith("/containers"):
        return "Containers"
    if s.endswith("/saved application state"):
        return "Saved State"
    if s.endswith("/preferences"):
        return "Preferences"
    if s.endswith("/launchagents"):
        return "Launch Agent"
    if s.endswith("/launchdaemons"):
        return "Launch Daemon"
    if s.endswith("/privilegedhelpertools"):
        return "Helper Tool"
    if s.endswith("/httpstorages"):
        return "HTTP Storage"
    if s.endswith("/cookies"):
        return "Cookies"
    if s.endswith("/syncedpreferences"):
        return "Synced Prefs"
    if s.endswith("/webkit"):
        return "WebKit Data"
    return classify_root(root)


def _matching_paths(
    root: Path,
    bundle_id: str,
    vendor: str,
    tokens: Set[str],
    app_name: str,
) -> List[Path]:
    matches: List[Path] = []
    kind = _root_kind(root)

    for item in iterdir_safe(root):
        name = item.name.lower()

        if kind == "Preferences":
            if name.startswith(bundle_id) and item.suffix in {".plist", ".lockfile", ".plist.lockfile", ".plist.disabled"}:
                matches.append(item)
            continue

        if kind == "Saved State":
            if name.startswith(bundle_id) and name.endswith(".savedstate"):
                matches.append(item)
            continue

        if kind == "Containers":
            if name == bundle_id:
                matches.append(item)
            continue

        if kind == "Group Containers":
            if _matches_bundle_suffix(name, bundle_id) or f".{bundle_id}" in name:
                matches.append(item)
            continue

        if kind in {"Launch Agent", "Launch Daemon", "Helper Tool"}:
            if _matches_bundle_prefix(name, bundle_id) or f".{bundle_id}" in name:
                matches.append(item)
            continue

        if kind in {"HTTP Storage", "Cookies", "Synced Prefs", "WebKit Data"}:
            if _matches_bundle_prefix(name, bundle_id) or _matches_bundle_suffix(name, bundle_id):
                matches.append(item)
            continue

        if vendor and name == vendor and item.is_dir():
            for child in iterdir_safe(item):
                if _matches_vendor_child(child.name.lower(), bundle_id, tokens):
                    matches.append(child)
            continue

        if _matches_direct_name(name, bundle_id, tokens, app_name):
            matches.append(item)

    return matches


def _label_root(root: Path, default: str) -> str:
    root_str = str(root).lower()
    if "saved application state" in root_str:
        return "Saved State"
    return default


def build_uninstall_plan(
    app: AppInfo,
    whitelist_set: Optional[Set[Path]] = None,
    roots: Optional[Iterable[Path]] = None,
    keep_preferences: bool = False,
) -> UninstallPlan:
    """Build an uninstall plan for the given app."""
    whitelist = whitelist_set or set()
    plan = UninstallPlan(app=app)
    seen: Set[Path] = set()

    def _add_item(path: Path, category: str) -> None:
        if path in seen:
            return
        seen.add(path)
        if not path.exists():
            return
        if path in whitelist or any(wl in path.parents for wl in whitelist):
            return
        size = size_of(path)
        if size <= 0:
            return
        safe, reason = validate_path_for_deletion(path)
        item = UninstallItem(
            path=path,
            category=category,
            size=size,
            protected=not safe,
            reason=reason,
        )
        if item.protected:
            plan.protected_items.append(item)
        else:
            plan.items.append(item)

    _add_item(app.path, "App Bundle")

    bundle_id, vendor, tokens, app_name = _identifier_set(app)
    for root in roots or SEARCH_ROOTS:
        if not root.exists():
            continue
        category = _label_root(root, _root_kind(root))
        if keep_preferences and category in {"Preferences", "Saved State"}:
            continue
        for match in _matching_paths(root, bundle_id, vendor, tokens, app_name):
            _add_item(match, category)

    plan.items.sort(key=lambda i: i.size, reverse=True)
    plan.protected_items.sort(key=lambda i: i.size, reverse=True)
    return plan


def execute_uninstall(plan: UninstallPlan, session=None) -> UninstallResult:
    """Execute an uninstall plan (delete or stage)."""
    from core.cleaner import write_deletion_log
    from utils import safe_remove

    result = UninstallResult()
    deleted_entries: List[tuple[str, int]] = []

    if session is not None:
        from core.undo import stage_file

    for item in plan.deletable_items:
        safe, reason = validate_path_for_deletion(item.path)
        if not safe:
            result.skipped += 1
            result.errors.append(f"{item.path}: {reason}")
            continue

        if session is not None:
            ok, sz = stage_file(item.path, session, category=item.category)
            if ok:
                result.staged += 1
                result.bytes_freed += sz
                deleted_entries.append((str(item.path), sz))
            else:
                result.skipped += 1
            continue

        ok, sz = safe_remove(item.path)
        if ok:
            result.deleted += 1
            result.bytes_freed += sz
            deleted_entries.append((str(item.path), sz))
        else:
            result.skipped += 1

    if deleted_entries:
        write_deletion_log(deleted_entries)

    return result
