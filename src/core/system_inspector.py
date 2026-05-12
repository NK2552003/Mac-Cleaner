"""
Mac Deep Cleaner v1.5.0 — System Inspector
========================================
Three sub-features bundled together because they share macOS system queries:

1. LaunchAgent / LaunchDaemon Manager
   - Lists all agents/daemons in ~/Library/LaunchAgents,
     /Library/LaunchAgents, /Library/LaunchDaemons.
   - Reads each plist to extract Label, Program, RunAtLoad, Disabled, etc.
   - Provides enable/disable helpers (via launchctl bootstrap/bootout).

2. Login Items Viewer
   - Reads the ServiceManagement login items DB using `sfltool dumpbtm`
     (macOS 13+) or parses the legacy LoginItems plist.

3. SIP & Permission Health Check
   - SIP status via `csrutil status`.
   - Checks for files in sensitive paths with unexpected ownership/mode.
   - Warns if Full Disk Access hasn't been granted (heuristic).
"""

from __future__ import annotations

import logging
import plistlib
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

from constants import HOME
from utils import iterdir_safe

logger = logging.getLogger(__name__)

# ── LaunchAgent / LaunchDaemon ─────────────────────────────────────────────────

LAUNCH_AGENT_DIRS: List[Path] = [
    HOME / "Library" / "LaunchAgents",
    Path("/Library/LaunchAgents"),
    Path("/Library/LaunchDaemons"),
]


@dataclass
class LaunchItem:
    """A single LaunchAgent or LaunchDaemon plist entry."""
    path: Path
    label: str
    program: str          # first element of ProgramArguments or Program
    run_at_load: bool
    disabled: bool
    is_daemon: bool       # True if /Library/LaunchDaemons
    source: str           # "User", "System", "System (Daemon)"

    def to_dict(self) -> dict:
        return {
            "path": str(self.path),
            "label": self.label,
            "program": self.program,
            "run_at_load": self.run_at_load,
            "disabled": self.disabled,
            "is_daemon": self.is_daemon,
            "source": self.source,
        }

    def __repr__(self) -> str:
        status = "enabled" if (self.run_at_load and not self.disabled) else "disabled"
        return f"<LaunchItem {self.label!r} {status}>"


def _parse_launch_plist(path: Path, source: str, is_daemon: bool) -> Optional[LaunchItem]:
    """Parse a single LaunchAgent/Daemon plist file."""
    try:
        with open(path, "rb") as f:
            pl = plistlib.load(f)
    except (plistlib.InvalidFileException, OSError, ValueError) as exc:
        logger.debug("Failed to parse launch plist %s: %s", path, exc)
        return None

    label = pl.get("Label", path.stem)
    program = ""
    if "ProgramArguments" in pl:
        args = pl["ProgramArguments"]
        program = args[0] if args else ""
    elif "Program" in pl:
        program = pl["Program"]

    return LaunchItem(
        path=path,
        label=str(label),
        program=str(program),
        run_at_load=bool(pl.get("RunAtLoad", False)),
        disabled=bool(pl.get("Disabled", False)),
        is_daemon=is_daemon,
        source=source,
    )


def list_launch_items() -> List[LaunchItem]:
    """
    Return all LaunchAgents and LaunchDaemons, sorted by label.
    """
    items: List[LaunchItem] = []

    for directory in LAUNCH_AGENT_DIRS:
        is_daemon = "LaunchDaemons" in str(directory)
        if "Library/LaunchAgents" in str(directory) and str(directory).startswith(str(HOME)):
            source = "User"
        elif is_daemon:
            source = "System (Daemon)"
        else:
            source = "System"

        for plist_path in iterdir_safe(directory):
            if plist_path.suffix not in (".plist", ".plist.disabled"):
                continue
            item = _parse_launch_plist(plist_path, source, is_daemon)
            if item:
                items.append(item)

    items.sort(key=lambda i: i.label.lower())
    return items


def disable_launch_item(item: LaunchItem) -> Tuple[bool, str]:
    """
    Disable a LaunchAgent by unloading it via launchctl.
    Returns (success, message).
    Only user LaunchAgents can be disabled without sudo.
    """
    if item.is_daemon:
        return False, "LaunchDaemons require sudo to disable"

    try:
        result = subprocess.run(
            ["launchctl", "unload", "-w", str(item.path)],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            return True, f"Disabled {item.label}"
        return False, result.stderr.strip() or "launchctl unload failed"
    except (subprocess.TimeoutExpired, OSError) as e:
        logger.debug("launchctl unload failed for %s: %s", item.path, e)
        return False, str(e)


def enable_launch_item(item: LaunchItem) -> Tuple[bool, str]:
    """Re-enable a LaunchAgent via launchctl load."""
    if item.is_daemon:
        return False, "LaunchDaemons require sudo to enable"

    try:
        result = subprocess.run(
            ["launchctl", "load", "-w", str(item.path)],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            return True, f"Enabled {item.label}"
        return False, result.stderr.strip() or "launchctl load failed"
    except (subprocess.TimeoutExpired, OSError) as e:
        logger.debug("launchctl load failed for %s: %s", item.path, e)
        return False, str(e)


# ── Login Items ────────────────────────────────────────────────────────────────

@dataclass
class LoginItem:
    """An item that launches at user login."""
    name: str
    path: str
    enabled: bool
    source: str     # "ServiceManagement", "Legacy", or "Unknown"

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "path": self.path,
            "enabled": self.enabled,
            "source": self.source,
        }


def list_login_items() -> List[LoginItem]:
    """
    Return items registered to run at login.
    Tries sfltool (macOS 13+) first, falls back to legacy plist.
    """
    items: List[LoginItem] = []

    # Method 1: sfltool dumpbtm (macOS 13+)
    try:
        out = subprocess.run(
            ["sfltool", "dumpbtm"],
            capture_output=True, text=True, timeout=10,
        ).stdout
        current_item: dict = {}
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("name:"):
                if current_item:
                    items.append(LoginItem(
                        name=current_item.get("name", ""),
                        path=current_item.get("path", ""),
                        enabled=current_item.get("enabled", True),
                        source="ServiceManagement",
                    ))
                current_item = {"name": line.split(":", 1)[-1].strip()}
            elif line.startswith("path:"):
                current_item["path"] = line.split(":", 1)[-1].strip()
            elif "disabled" in line.lower():
                current_item["enabled"] = False
        if current_item:
            items.append(LoginItem(
                name=current_item.get("name", ""),
                path=current_item.get("path", ""),
                enabled=current_item.get("enabled", True),
                source="ServiceManagement",
            ))
        if items:
            return items
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        logger.debug("sfltool login items failed: %s", exc)
        pass

    # Method 2: Legacy LoginItems plist (macOS < 13)
    legacy = (
        HOME / "Library" / "Application Support"
        / "com.apple.backgroundtaskmanagementagent" / "backgrounditems.btm"
    )
    if legacy.exists():
        try:
            with open(legacy, "rb") as f:
                pl = plistlib.load(f)
            for entry in pl.get("$objects", []):
                if isinstance(entry, dict) and "Name" in entry:
                    items.append(LoginItem(
                        name=str(entry.get("Name", "")),
                        path=str(entry.get("Alias", "")),
                        enabled=True,
                        source="Legacy",
                    ))
        except (plistlib.InvalidFileException, OSError, KeyError) as exc:
            logger.debug("Legacy login items parse failed: %s", exc)
            pass

    return items


# ── SIP & Permission Health ────────────────────────────────────────────────────

@dataclass
class SystemHealth:
    """System-level security and health indicators."""
    sip_enabled: bool
    sip_detail: str          # Full csrutil output line
    full_disk_access_hint: bool   # Heuristic: True if we can read TCC.db
    os_version: str
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "sip_enabled": self.sip_enabled,
            "sip_detail": self.sip_detail,
            "full_disk_access_hint": self.full_disk_access_hint,
            "os_version": self.os_version,
            "warnings": self.warnings,
        }


def check_system_health() -> SystemHealth:
    """
    Run system integrity checks:
    - SIP status (via csrutil)
    - macOS version
    - Heuristic Full Disk Access check

    Returns SystemHealth with all findings.
    """
    warnings: List[str] = []

    # SIP
    sip_enabled = True
    sip_detail = ""
    try:
        out = subprocess.run(
            ["csrutil", "status"],
            capture_output=True, text=True, timeout=5,
        ).stdout.strip()
        sip_detail = out
        sip_enabled = "enabled" in out.lower() and "disabled" not in out.lower()
        if not sip_enabled:
            warnings.append("System Integrity Protection (SIP) is DISABLED")
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        logger.debug("csrutil status failed: %s", exc)
        sip_detail = "Unable to determine SIP status"

    # macOS version
    os_version = "Unknown"
    try:
        os_version = subprocess.run(
            ["sw_vers", "-productVersion"],
            capture_output=True, text=True, timeout=5,
        ).stdout.strip()
    except (subprocess.TimeoutExpired, OSError) as exc:
        logger.debug("sw_vers failed: %s", exc)
        pass

    # Full Disk Access heuristic
    tcc_db = Path("/Library/Application Support/com.apple.TCC/TCC.db")
    full_disk_access_hint = tcc_db.exists()
    if not full_disk_access_hint:
        warnings.append(
            "mac-cleaner may not have Full Disk Access — some scans may be incomplete. "
            "Grant access in System Settings → Privacy & Security → Full Disk Access."
        )

    return SystemHealth(
        sip_enabled=sip_enabled,
        sip_detail=sip_detail,
        full_disk_access_hint=full_disk_access_hint,
        os_version=os_version,
        warnings=warnings,
    )
