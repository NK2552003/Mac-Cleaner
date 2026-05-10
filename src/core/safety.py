"""
Mac Deep Cleaner v1.0.0 — Safety Module
=====================================
All safety checks, safelist lookups, and system-file protection logic.
Ensures that system-critical files are NEVER deleted.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Dict, Optional, Set, Tuple

from constants import (
    SYSTEM_CACHE_PREFIXES,
    SYSTEM_EXACT_SAFELIST,
    SYSTEM_GROUP_PREFIXES,
    SYSTEM_KEYWORD_SAFELIST,
    SYSTEM_PREF_PATTERNS,
    TEAM_ID_MAP,
)


def is_system_safe(name: str) -> bool:
    """
    Check if a directory/file name belongs to the operating system.
    Returns True if the item should NEVER be treated as an orphan.
    """
    n = name.lower().strip()
    stem = Path(name).stem.lower().strip()

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
    except Exception:
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
    except Exception:
        pass
    return result


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
    if path_str.rstrip("/") in ("/library", str(Path.home() / "Library").lower()):
        return False, "Library root directory"

    # Never delete Home directory
    if path == Path.home():
        return False, "Home directory"

    return True, ""
