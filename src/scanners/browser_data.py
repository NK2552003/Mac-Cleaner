"""Browser data scanner and cleaner."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

from constants import HOME
from core.safety import validate_path_for_deletion
from utils import size_of

BROWSER_LABELS = {
    "safari": "Safari",
    "chrome": "Google Chrome",
    "firefox": "Firefox",
    "edge": "Microsoft Edge",
    "brave": "Brave Browser",
}

CATEGORY_LABELS = {
    "cache": "Cache",
    "cookies": "Cookies",
    "history": "History",
    "downloads": "Downloads",
    "site-data": "Site Data",
    "sessions": "Sessions",
}

_ALLOWED_ROOTS: List[Path] = [
    HOME / "Library" / "Safari",
    HOME / "Library" / "Caches" / "com.apple.Safari",
    HOME / "Library" / "Containers" / "com.apple.Safari",
    HOME / "Library" / "Cookies",
    HOME / "Library" / "Application Support" / "Google" / "Chrome",
    HOME / "Library" / "Application Support" / "Microsoft Edge",
    HOME / "Library" / "Application Support" / "BraveSoftware",
    HOME / "Library" / "Application Support" / "Firefox",
]


@dataclass
class BrowserDataItem:
    """One browser data path."""
    browser: str
    category: str
    path: Path
    size: int
    profile: Optional[str] = None


@dataclass
class DeleteResult:
    """Summary of a deletion run."""
    deleted: int = 0
    skipped: int = 0
    bytes_freed: int = 0
    errors: List[str] = field(default_factory=list)


def _add_item(
    items: List[BrowserDataItem],
    seen: Set[Path],
    browser: str,
    category: str,
    path: Path,
    profile: Optional[str] = None,
) -> None:
    if path in seen or not path.exists():
        return
    sz = size_of(path)
    if sz <= 0:
        return
    items.append(BrowserDataItem(browser=browser, category=category, path=path, size=sz, profile=profile))
    seen.add(path)


def _chromium_profiles(base: Path) -> List[Path]:
    if not base.exists():
        return []
    profiles: List[Path] = []
    for child in base.iterdir():
        if not child.is_dir():
            continue
        if child.name == "Default" or child.name.startswith("Profile ") or child.name == "Guest Profile":
            profiles.append(child)
    return profiles


def _collect_chromium(browser: str, base: Path) -> List[BrowserDataItem]:
    items: List[BrowserDataItem] = []
    seen: Set[Path] = set()

    for profile in _chromium_profiles(base):
        profile_name = profile.name
        cache_dirs = [
            profile / "Cache",
            profile / "Code Cache",
            profile / "GPUCache",
            profile / "Media Cache",
            profile / "Service Worker" / "CacheStorage",
            profile / "Service Worker" / "ScriptCache",
            profile / "ShaderCache",
        ]
        for p in cache_dirs:
            _add_item(items, seen, browser, "cache", p, profile=profile_name)

        _add_item(items, seen, browser, "cookies", profile / "Cookies", profile=profile_name)
        _add_item(items, seen, browser, "history", profile / "History", profile=profile_name)
        _add_item(items, seen, browser, "site-data", profile / "Local Storage", profile=profile_name)
        _add_item(items, seen, browser, "site-data", profile / "IndexedDB", profile=profile_name)
        _add_item(items, seen, browser, "site-data", profile / "WebStorage", profile=profile_name)
        _add_item(items, seen, browser, "sessions", profile / "Sessions", profile=profile_name)

    return items


def _collect_firefox() -> List[BrowserDataItem]:
    base = HOME / "Library" / "Application Support" / "Firefox" / "Profiles"
    items: List[BrowserDataItem] = []
    seen: Set[Path] = set()

    if not base.exists():
        return items

    for profile in base.iterdir():
        if not profile.is_dir():
            continue
        profile_name = profile.name
        _add_item(items, seen, "firefox", "cache", profile / "cache2", profile=profile_name)
        _add_item(items, seen, "firefox", "cookies", profile / "cookies.sqlite", profile=profile_name)
        _add_item(items, seen, "firefox", "history", profile / "places.sqlite", profile=profile_name)
        _add_item(items, seen, "firefox", "site-data", profile / "storage", profile=profile_name)
        _add_item(items, seen, "firefox", "sessions", profile / "sessionstore-backups", profile=profile_name)

    return items


def _collect_safari() -> List[BrowserDataItem]:
    items: List[BrowserDataItem] = []
    seen: Set[Path] = set()

    safari_root = HOME / "Library" / "Safari"
    safari_container = HOME / "Library" / "Containers" / "com.apple.Safari" / "Data" / "Library"

    _add_item(items, seen, "safari", "history", safari_root / "History.db")
    _add_item(items, seen, "safari", "downloads", safari_root / "Downloads.plist")
    _add_item(items, seen, "safari", "site-data", safari_root / "LocalStorage")
    _add_item(items, seen, "safari", "site-data", safari_root / "Databases")

    _add_item(items, seen, "safari", "history", safari_container / "Safari" / "History.db")
    _add_item(items, seen, "safari", "downloads", safari_container / "Safari" / "Downloads.plist")
    _add_item(items, seen, "safari", "cache", safari_container / "Caches")
    _add_item(items, seen, "safari", "site-data", safari_container / "WebKit" / "WebsiteData")

    _add_item(items, seen, "safari", "cookies", HOME / "Library" / "Cookies" / "Cookies.binarycookies")
    _add_item(items, seen, "safari", "cookies", safari_container / "Cookies")
    _add_item(items, seen, "safari", "cache", HOME / "Library" / "Caches" / "com.apple.Safari")

    return items


def collect_browser_data(browsers: Optional[List[str]] = None) -> List[BrowserDataItem]:
    """Collect browser data items for the selected browsers."""
    selected = {b.lower() for b in (browsers or BROWSER_LABELS.keys())}
    items: List[BrowserDataItem] = []

    if "safari" in selected:
        items.extend(_collect_safari())

    if "chrome" in selected:
        items.extend(
            _collect_chromium(
                "chrome",
                HOME / "Library" / "Application Support" / "Google" / "Chrome",
            )
        )

    if "edge" in selected:
        items.extend(
            _collect_chromium(
                "edge",
                HOME / "Library" / "Application Support" / "Microsoft Edge",
            )
        )

    if "brave" in selected:
        items.extend(
            _collect_chromium(
                "brave",
                HOME / "Library" / "Application Support" / "BraveSoftware" / "Brave-Browser",
            )
        )

    if "firefox" in selected:
        items.extend(_collect_firefox())

    return items


def summarize_browser_data(items: List[BrowserDataItem]) -> List[Tuple[str, str, int, int]]:
    """Return summary rows for tables."""
    summary: Dict[Tuple[str, str], List[BrowserDataItem]] = {}
    for item in items:
        key = (item.browser, item.category)
        summary.setdefault(key, []).append(item)

    rows: List[Tuple[str, str, int, int]] = []
    for (browser, category), group in sorted(summary.items()):
        total = sum(i.size for i in group)
        rows.append((
            BROWSER_LABELS.get(browser, browser.title()),
            CATEGORY_LABELS.get(category, category.title()),
            len(group),
            total,
        ))

    return rows


def delete_browser_data(
    items: List[BrowserDataItem],
    categories: Optional[List[str]] = None,
) -> "DeleteResult":
    """Delete selected browser data items."""
    from utils import safe_remove

    result = DeleteResult()
    targets: List[BrowserDataItem] = []
    category_set = {c.lower() for c in (categories or [])}

    for item in items:
        if category_set and item.category not in category_set:
            continue
        targets.append(item)

    seen: Set[Path] = set()
    for item in targets:
        if item.path in seen:
            continue
        seen.add(item.path)
        safe, reason = validate_path_for_deletion(item.path)
        if not safe and not _is_allowed_browser_path(item.path):
            result.skipped += 1
            result.errors.append(f"{item.path}: {reason}")
            continue
        ok, freed = safe_remove(item.path)
        if ok:
            result.deleted += 1
            result.bytes_freed += freed
        else:
            result.skipped += 1

    return result


def _is_allowed_browser_path(path: Path) -> bool:
    try:
        resolved = path.expanduser().resolve()
    except OSError:
        resolved = path.expanduser()
    for root in _ALLOWED_ROOTS:
        try:
            if resolved.is_relative_to(root.expanduser().resolve()):
                return True
        except OSError:
            continue
        except AttributeError:
            try:
                if str(resolved).startswith(str(root.expanduser().resolve())):
                    return True
            except OSError:
                continue
    return False
