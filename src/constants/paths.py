"""Paths and roots configuration."""

from pathlib import Path
from typing import List

HOME = Path.home()
LOG_FILE = HOME / ".mac_cleaner_deleted.log"
CONFIG_DIR = HOME / ".config" / "mac-cleaner"

# ── Scan roots ────────────────────────────────────────────────────────────────

SEARCH_ROOTS: List[Path] = [
    HOME / "Library" / "Application Support",
    HOME / "Library" / "Preferences",
    HOME / "Library" / "Caches",
    HOME / "Library" / "Logs",
    HOME / "Library" / "LaunchAgents",
    HOME / "Library" / "Containers",
    HOME / "Library" / "Group Containers",
    HOME / "Library" / "Saved Application State",
    HOME / "Library" / "WebKit",
    HOME / "Library" / "HTTPStorages",
    HOME / "Library" / "Cookies",
    HOME / "Library" / "SyncedPreferences",
    Path("/Library/Application Support"),
    Path("/Library/Preferences"),
    Path("/Library/Caches"),
    Path("/Library/LaunchAgents"),
    Path("/Library/LaunchDaemons"),
    Path("/Library/Logs"),
    Path("/Library/PrivilegedHelperTools"),
]

# ── App Discovery Directories ─────────────────────────────────────────────────

APP_SEARCH_DIRS: List[Path] = [
    Path("/Applications"),
    HOME / "Applications",
    Path("/System/Applications"),
    Path("/System/Library/CoreServices"),
    Path("/Applications/Utilities"),
    Path("/System/Applications/Utilities"),
    Path("/System/Library/PreferencePanes"),
    HOME / "Library" / "PreferencePanes",
]

# ── Production scanner defaults ──────────────────────────────────────────────

DEFAULT_DUPLICATE_ROOTS: List[Path] = [
    HOME / "Downloads",
    HOME / "Documents",
    HOME / "Desktop",
    HOME / "Pictures",
    HOME / "Movies",
    HOME / "Music",
]

DEFAULT_LARGE_FILE_ROOTS: List[Path] = [HOME]

DEFAULT_SYMLINK_ROOTS: List[Path] = [
    Path("/usr/local"),
    Path("/opt/homebrew"),
    HOME / "bin",
    HOME / ".local" / "bin",
    HOME / ".config",
    HOME / "Library" / "LaunchAgents",
]

# ── Developer junk scan defaults ─────────────────────────────────────────────

DEFAULT_DEV_JUNK_ROOTS: List[Path] = [
    HOME / "Projects",
    HOME / "Development",
    HOME / "Code",
    HOME / "Workspace",
    HOME / "Documents",
]

DEV_JUNK_SKIP_DIRS = {
    ".git", ".hg", ".svn", ".idea", ".vscode", ".cache", ".DS_Store",
    "Library", "System", ".Trash",
}

DEV_JUNK_MARKER_DEPTH = 3
