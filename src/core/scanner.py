"""
Mac Deep Cleaner v1.0.0 — Scanner Module
======================================
Core scanning logic for orphan detection and general junk discovery.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

from constants import (
    ORPHAN_ALWAYS_SKIP_NAMES,
    ORPHAN_ALWAYS_SKIP_PREFIXES,
    SEARCH_ROOTS,
    VENDOR_COMPONENT_OWNERS,
)
from scanners.matching import match_to_app
from config.models import AppInfo, JunkEntry, OrphanEntry
from core.safety import (
    is_apple_user_library_path,
    is_system_cache,
    is_system_safe,
    resolve_group_container,
    validate_path_for_deletion,
)
from utils import derive_display_name, iterdir_safe


def _is_app_owned_junk(item: Path, apps: Dict[str, AppInfo]) -> bool:
    """Check whether a file/directory belongs to an installed app.

    Returns True if the item's name matches a known installed app,
    meaning it should not be reported as general junk.
    """
    display = derive_display_name(str(item))
    matched = match_to_app(display, apps)
    if matched:
        return True
    # Also try matching on the raw filename (stem) for plist files
    raw_stem = item.stem.lower()
    matched = match_to_app(raw_stem, apps)
    if matched:
        return True
    return False


def _normalized_name_parts(name: str) -> Tuple[str, str]:
    n = name.lower().strip()
    stem = Path(name).stem.lower().strip()
    if n.startswith("."):
        n = n[1:]
    if stem.startswith("."):
        stem = stem[1:]
    return n, stem


def _matches_prefix(name: str, stem: str, prefixes: Set[str]) -> bool:
    for prefix in prefixes:
        if name.startswith(prefix) or stem.startswith(prefix):
            return True
    return False


def _is_always_skip_component(name: str) -> bool:
    n, stem = _normalized_name_parts(name)
    if n in ORPHAN_ALWAYS_SKIP_NAMES or stem in ORPHAN_ALWAYS_SKIP_NAMES:
        return True
    return _matches_prefix(n, stem, ORPHAN_ALWAYS_SKIP_PREFIXES)


def _is_vendor_component_for_installed_apps(
    name: str,
    installed_bids: Set[str],
) -> bool:
    if not installed_bids:
        return False
    n, stem = _normalized_name_parts(name)
    for comp_prefix, owner_prefixes in VENDOR_COMPONENT_OWNERS.items():
        if n.startswith(comp_prefix) or stem.startswith(comp_prefix):
            for bid in installed_bids:
                for owner_prefix in owner_prefixes:
                    if bid.startswith(owner_prefix):
                        return True
    return False


def _scan_roots(extra_roots: Optional[Iterable[Path]] = None) -> List[Path]:
    """Return built-in scan roots plus configured custom roots, deduplicated."""
    roots: List[Path] = []
    seen: Set[Path] = set()
    for root in list(SEARCH_ROOTS) + list(extra_roots or []):
        try:
            resolved = root.expanduser().resolve()
        except OSError:
            resolved = root.expanduser()
        if resolved not in seen:
            seen.add(resolved)
            roots.append(resolved)
    return roots


def classify_root(root: Path) -> str:
    """Classify a search root into a human-readable category."""
    s = str(root).lower()
    if "application support" in s:
        return "App Support"
    if "caches" in s:
        return "Caches"
    if "preferences" in s:
        return "Preferences"
    if "containers" in s or "groups" in s:
        return "Containers"
    if "logs" in s:
        return "Logs"
    if "Trash" in s or ".Trash" in s:
        return "Trash"
    return "Other"


def scan_orphans(
    apps: Dict[str, AppInfo],
    whitelist_set: Set[Path],
    running_bids: Set[str],
    roots: Optional[Iterable[Path]] = None,
    enabled: bool = True,
) -> Dict[str, List[OrphanEntry]]:
    """Scan for orphaned app leftovers."""
    if not enabled:
        return {}

    matched_paths: Dict[Path, AppInfo] = {}
    installed_bids: Set[str] = {a.bundle_id for a in apps.values()}
    scan_roots = _scan_roots(roots)

    # Match search roots to known apps
    for root in scan_roots:
        if not root.is_dir():
            continue
        for item in iterdir_safe(root):
            if not item.name.endswith((".plist", ".lproj", ".savedState")):
                continue
            display = derive_display_name(str(item))
            matched = match_to_app(display, apps)
            if matched:
                matched_paths[item] = matched

    # Scan orphan leftovers (items not matched to any installed app)
    orphans: Dict[str, List[OrphanEntry]] = defaultdict(list)
    seen: Set[Path] = set()

    for root in scan_roots:
        if not root.is_dir():
            continue
        category = classify_root(root)
        for item in iterdir_safe(root):
            if item in seen:
                continue
            seen.add(item)

            # Skip whitelisted paths
            if item in whitelist_set or any(wl in item.parents for wl in whitelist_set):
                continue

            # Skip shared components and vendor services tied to installed apps
            if _is_always_skip_component(item.name):
                continue
            if _is_vendor_component_for_installed_apps(item.name, installed_bids):
                continue

            display = derive_display_name(str(item))
            matched = match_to_app(display, apps)

            # Skip items matched to running bundle IDs
            if matched and matched.bundle_id in running_bids:
                continue

            if not matched:
                # Safety check: skip Apple-owned system files
                # (e.g. com.apple.SetupAssistant.plist, ByHost prefs, etc.)
                if is_system_safe(item.name):
                    continue
                protected, _ = is_apple_user_library_path(item)
                if protected:
                    continue
                # Also reject items that fail the final deletion validation
                safe, _ = validate_path_for_deletion(item)
                if not safe:
                    continue

                # Confirm it's an orphan
                try:
                    fsize = item.stat().st_size
                except OSError:
                    continue
                if fsize == 0:
                    continue
                leaf = OrphanEntry(
                    path=item,
                    size=fsize,
                    reason=category,
                    category=category,
                    app_name=display or item.stem,
                    bundle_id="",
                    vendor="Unknown",
                )
                orphans[leaf.app_name].append(leaf)

    return dict(orphans)


def scan_junk(
    whitelist_set: Set[Path],
    apps: Optional[Dict[str, AppInfo]] = None,
    roots: Optional[Iterable[Path]] = None,
    skip_categories: Optional[Set[str]] = None,
    enabled: bool = True,
) -> List[JunkEntry]:
    """Scan for user junk: caches, logs, .Trash items, etc.

    Files that belong to installed applications (matched via `apps`) are
    skipped so they don't appear as general junk.
    """
    if not enabled:
        return []

    junk: List[JunkEntry] = []
    seen: Set[Path] = set()
    skip_categories = skip_categories or set()
    installed_bids: Set[str] = {a.bundle_id for a in apps.values()} if apps else set()

    for root in _scan_roots(roots):
        if not root.is_dir():
            continue
        category = classify_root(root)
        if category in skip_categories:
            continue
        for item in iterdir_safe(root):
            if item in seen:
                continue
            seen.add(item)

            # Skip whitelisted
            if item in whitelist_set or any(wl in item.parents for wl in whitelist_set):
                continue

            # Skip shared components and vendor services tied to installed apps
            if _is_always_skip_component(item.name):
                continue
            if _is_vendor_component_for_installed_apps(item.name, installed_bids):
                continue

            try:
                is_candidate = item.is_file() or item.is_symlink()
            except OSError:
                continue
            if not is_candidate:
                continue
            try:
                fsize = item.stat().st_size
            except OSError:
                continue
            if fsize == 0:
                continue

            # Skip files that belong to installed apps (e.g. iTerm2 plist)
            if apps and _is_app_owned_junk(item, apps):
                continue

            # Determine if system-owned
            is_system = str(item).startswith("/System")

            # Also mark Apple-owned files in user Library as system junk
            if not is_system:
                apple_protected, _ = is_apple_user_library_path(item)
                if apple_protected:
                    is_system = True

            # Mark any other system-safe files as system junk
            if not is_system:
                if is_system_safe(item.name):
                    is_system = True

            junk.append(JunkEntry(
                path=item,
                size=fsize,
                category=category,
                is_system=is_system,
                bundle_id="",
            ))

    return junk
