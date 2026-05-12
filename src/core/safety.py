"""
All safety checks, safelist lookups, and system-file protection logic.
Ensures that system-critical files are NEVER deleted.
"""

from __future__ import annotations

import logging
import re
import subprocess
from pathlib import Path
from typing import Dict, Optional, Set, Tuple

from constants import (
    PROTECTED_APPLE_PREF_STEMS,
    SYSTEM_CACHE_PREFIXES,
    SYSTEM_EXACT_SAFELIST,
    SYSTEM_GROUP_PREFIXES,
    SYSTEM_KEYWORD_SAFELIST,
    SYSTEM_PREF_PATTERNS,
    TEAM_ID_MAP,
)

HOME = Path.home()
logger = logging.getLogger(__name__)


def is_system_safe(name: str) -> bool:
    """
    Check if a directory/file name belongs to the operating system.
    Returns True if the item should NEVER be treated as an orphan.
    """
    n = name.lower().strip()
    stem = Path(name).stem.lower().strip()
    if n.startswith("."):
        n = n[1:]
    if stem.startswith("."):
        stem = stem[1:]

    # 1. Exact match on stem
    if stem in SYSTEM_EXACT_SAFELIST or n in SYSTEM_EXACT_SAFELIST:
        return True

    # 2. Remove trailing 'd' daemon suffix and check
    if stem.endswith("d") and len(stem) > 3:
        daemon_base = stem[:-1]
        if daemon_base in SYSTEM_EXACT_SAFELIST:
            return True

    # 3. Keyword prefix matching
    for kw in SYSTEM_KEYWORD_SAFELIST:
        if n.startswith(kw) or stem.startswith(kw):
            return True

    # 4. System preference patterns
    for pattern in SYSTEM_PREF_PATTERNS:
        if n.startswith(pattern) or stem.startswith(pattern):
            return True

    # 5. Anything with "com.apple" anywhere
    if "com.apple" in n:
        return True

    # 6. savedapplicationstate suffix pattern
    if stem.endswith(".savedstate"):
        return True

    return False


def is_system_cache(name: str) -> bool:
    """Returns True if an entry in ~/Library/Caches is system-owned."""
    n = name.lower().strip()
    for prefix in SYSTEM_CACHE_PREFIXES:
        if n.startswith(prefix) or n == prefix.rstrip("."):
            return True
    return False


def is_system_preference(name: str) -> bool:
    """Returns True if a preference file is system-owned."""
    n = name.lower().strip()
    for pattern in SYSTEM_PREF_PATTERNS:
        if n.startswith(pattern):
            return True
    return False


def is_hidden_system_dir(name: str) -> bool:
    """Returns True for dotfiles/dirs that are system or developer managed."""
    if name.startswith("."):
        return True
    return False


def resolve_group_container(name: str) -> Tuple[bool, Optional[str]]:
    """
    Determine if a Group Container belongs to the system or a known vendor.

    Returns:
        (is_safe, owner_name) — is_safe=True means DON'T treat as orphan
    """
    lower = name.lower()

    # System-owned prefixes
    for prefix in SYSTEM_GROUP_PREFIXES:
        if lower.startswith(prefix):
            return True, "System (Apple)"

    # Split on '.' to find team ID
    parts = lower.split(".")
    if not parts:
        return False, None

    first_component = parts[0]

    # Check known team IDs
    if first_component in TEAM_ID_MAP:
        return True, TEAM_ID_MAP[first_component]

    # Valid Apple team IDs are exactly 10 alphanumeric characters.
    # If we see one we don't recognise, assume it's a legitimate vendor
    # container and DON'T treat it as an orphan (conservative approach).
    is_team_id = len(first_component) == 10 and first_component.isalnum()
    if is_team_id:
        return True, f"Unknown vendor (Team ID: {first_component.upper()})"

    # Short fragments that look like partial IDs — be conservative
    if len(first_component) < 6 and first_component.isalnum():
        return True, "Unknown (short ID)"

    return False, None


def is_process_running(name_fragment: str) -> bool:
    """Check if a process whose name contains name_fragment is running."""
    try:
        result = subprocess.run(
            ["pgrep", "-if", name_fragment],
            capture_output=True, timeout=5,
        )
        return result.returncode == 0
    except Exception as exc:
        logger.debug("pgrep failed for %s: %s", name_fragment, exc)
        return False


def running_bundle_ids() -> Set[str]:
    """Return a set of bundle IDs of currently-running GUI apps."""
    result: Set[str] = set()
    try:
        out = subprocess.run(
            ["lsappinfo", "list", "-only", "bundleid"],
            capture_output=True, text=True, timeout=10,
        ).stdout
        for line in out.splitlines():
            m = re.search(r'"bundleID"\s*=\s*"([^"]+)"', line)
            if m:
                result.add(m.group(1).lower())
    except Exception as exc:
        logger.debug("lsappinfo failed: %s", exc)
        pass
    return result


def is_apple_owned_pref(name: str) -> bool:
    """
    Returns True if a preference filename stem is an Apple system preference
    that must never be treated as orphan junk.

    This covers com.apple.* pref files whose corresponding .app is NOT
    discoverable via the standard APP_SEARCH_DIRS (e.g. SetupAssistant,
    loginwindow, etc.).
    """
    n = name.lower().strip()
    stem = Path(name).stem.lower().strip()

    # Fast check: if "com.apple." is not present, it's likely not Apple-owned
    if "com.apple." not in n:
        return False

    # Check against the protected pref stems table
    for protected_stem in PROTECTED_APPLE_PREF_STEMS:
        # Exact match
        if stem == protected_stem:
            return True
        # Stem starts with protected prefix (e.g. "com.apple.siri" matches "com.apple.siri.suggestions")
        if stem.startswith(protected_stem + "."):
            return True
        # Stem starts with protected stem (e.g. protected "com.apple.security" matches "com.apple.security.csp")
        if protected_stem.startswith(stem + "."):
            return True

    return False


def _library_relative(path: Path) -> Optional[str]:
    """
    Extract the relative path within a Library directory.
    Supports both ~/Library/ and /Library/.
    Returns None if the path is not inside any Library directory.
    """
    path_str = str(path).lower()
    home_str = str(HOME).lower()

    # Check user's Library (~/Library/)
    user_prefix = home_str + "/library/"
    if path_str.startswith(user_prefix):
        return path_str[len(user_prefix):]

    # Check system Library (/Library/)
    if path_str.startswith("/library/"):
        relative = path_str[len("/library/"):]
        return relative

    return None


def is_apple_user_library_path(path: Path) -> Tuple[bool, str]:
    """
    Check if a path under a Library directory is an Apple-owned system file
    that must NOT be deleted.

    Supports both ~/Library/ and /Library/ paths.

    Returns:
        (is_protected, reason) — is_protected=True means the path must NOT be deleted.
    """
    relative = _library_relative(path)
    if relative is None:
        return False, ""

    # ── ByHost directory — contains per-host preferences ──────────────────
    # e.g. Library/Preferences/ByHost/com.apple.loginwindow.*
    if "byhost" in relative:
        if path.name.lower() == "byhost":
            return True, "ByHost preferences directory"
        name_part = path.name.lower()
        if "com.apple" in name_part:
            return True, "Apple per-host preference (ByHost)"
        if path.suffix == ".plist":
            return True, "ByHost preference"

    # ── Preferences/ directory ────────────────────────────────────────────
    relative_lower = relative.lower()
    if relative_lower.startswith("preferences/"):
        pref_name = path.name.lower()
        if is_apple_owned_pref(pref_name):
            return True, f"Protected Apple preference: {path.name}"
        if is_system_preference(pref_name):
            return True, f"Apple system preference: {path.name}"
        if pref_name.endswith(".plist"):
            # Any .plist pref containing "com.apple." anywhere is Apple-owned
            if "com.apple." in pref_name:
                return True, f"Apple system preference: {path.name}"
            # systemgroup.com.apple. patterns
            if pref_name.startswith("systemgroup.com.apple."):
                return True, f"Apple system group preference: {path.name}"

    # ── Caches/ directory — Apple-owned cache entries ─────────────────────
    if relative_lower.startswith("caches/"):
        cache_name = path.name.lower()
        if is_system_cache(cache_name):
            return True, f"Apple system cache: {cache_name}"
        if cache_name.startswith("com.apple.") and path.is_dir():
            return True, f"Apple cache directory: {cache_name}"

    # ── Application Support/ — Apple-owned support dirs ───────────────────
    if relative_lower.startswith("application support/"):
        support_name = path.name.lower()
        if support_name.startswith("com.apple."):
            return True, f"Apple application support: {support_name}"

    # ── Saved Application State/ — Apple saved states ─────────────────────
    if relative_lower.startswith("saved application state/"):
        state_name = path.name.lower()
        if state_name.startswith("com.apple."):
            return True, f"Apple saved state: {state_name}"

    # ── Containers/ — Apple-owned containers ──────────────────────────────
    if relative_lower.startswith("containers/"):
        container_name = path.name.lower()
        if container_name.startswith("com.apple."):
            return True, f"Apple container: {container_name}"

    # ── Group Containers/ — Apple-owned group containers ──────────────────
    if relative_lower.startswith("group containers/"):
        safe, owner = resolve_group_container(path.name)
        if safe:
            return True, f"System group container: {owner}"

    # ── SyncedPreferences/ — Apple iCloud sync prefs ──────────────────────
    if relative_lower.startswith("syncedpreferences/"):
        sync_name = path.name.lower()
        if sync_name.startswith("com.apple."):
            return True, f"Apple synced preference: {sync_name}"

    # ── HTTPStorages/ — Apple HTTP storage ────────────────────────────────
    if relative_lower.startswith("httpstorages/"):
        storage_name = path.name.lower()
        if storage_name.startswith("com.apple."):
            return True, f"Apple HTTP storage: {storage_name}"

    # ── Cookies/ — Apple cookies ──────────────────────────────────────────
    if relative_lower.startswith("cookies/"):
        cookie_name = path.name.lower()
        if cookie_name.startswith("com.apple."):
            return True, f"Apple cookie: {cookie_name}"

    # ── LaunchAgents/ and LaunchDaemons/ — Apple plists ───────────────────
    if relative_lower.startswith("launchagents/") or relative_lower.startswith("launchdaemons/"):
        launch_name = path.name.lower()
        if "com.apple." in launch_name:
            return True, f"Apple launch plist: {path.name}"

    # ── PrivilegedHelperTools/ — Apple helpers ────────────────────────────
    if relative_lower.startswith("privilegedhelpertools/"):
        helper_name = path.name.lower()
        if "com.apple." in helper_name:
            return True, f"Apple privileged helper: {path.name}"

    # ── Logs/ — Apple logs ────────────────────────────────────────────────
    if relative_lower.startswith("logs/"):
        log_name = path.name.lower()
        if log_name.startswith("com.apple."):
            return True, f"Apple log: {log_name}"

    # ── WebKit/ — Apple webkit data ───────────────────────────────────────
    if relative_lower.startswith("webkit/"):
        return True, "WebKit system data"

    return False, ""


def validate_path_for_deletion(path: Path) -> Tuple[bool, str]:
    """
    Final safety gate before any deletion.
    Returns (is_safe_to_delete, reason_if_not).
    """
    path_str = str(path).lower()

    # Never delete anything in /System
    if path_str.startswith("/system"):
        return False, "System directory"

    # Never delete anything in /usr (except /usr/local)
    if path_str.startswith("/usr") and not path_str.startswith("/usr/local"):
        return False, "Protected /usr directory"

    # Never delete anything in /bin, /sbin, /etc
    for protected in ("/bin", "/sbin", "/etc", "/var"):
        if path_str.startswith(protected):
            return False, f"Protected {protected} directory"

    # Never delete the Library directory itself
    if path_str.rstrip("/") in ("/library", str(HOME / "Library").lower()):
        return False, "Library root directory"

    # Never delete Home directory
    if path == HOME:
        return False, "Home directory"

    # Check for Apple-owned files in user's Library
    apple_protected, reason = is_apple_user_library_path(path)
    if apple_protected:
        return False, reason

    return True, ""