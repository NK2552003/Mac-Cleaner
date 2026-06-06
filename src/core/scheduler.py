"""
Notifications
-------------
Posts a native macOS notification after a scan completes using
`osascript` (no third-party dependencies). Falls back to printing
to terminal if osascript is unavailable.

Scheduler
----------
Installs a LaunchAgent plist into ~/Library/LaunchAgents/ to run
weekly scans automatically. The scheduled scan writes JSON results
to ~/.config/mac-cleaner/history/ and optionally sends a notification.

Also supports:
- `mac-cleaner schedule install`  — install the LaunchAgent
- `mac-cleaner schedule remove`   — unload and delete the LaunchAgent
- `mac-cleaner schedule status`   — show whether the agent is loaded
"""

from __future__ import annotations

import logging
import plistlib
import subprocess
from pathlib import Path
from typing import Optional, Tuple

from constants import HOME

logger = logging.getLogger(__name__)

# ── Notification ───────────────────────────────────────────────────────────────

NOTIFICATION_TITLE = "Mac Deep Cleaner"


def post_notification(
    message: str,
    subtitle: Optional[str] = None,
    sound: bool = False,
) -> bool:
    """
    Post a native macOS notification via osascript.

    Args:
        message:  Main notification body text.
        subtitle: Optional subtitle line.
        sound:    If True, play the default notification sound.

    Returns:
        True if the notification was posted successfully.
    """
    parts = [f'display notification "{message}"']
    parts.append(f'with title "{NOTIFICATION_TITLE}"')
    if subtitle:
        parts.append(f'subtitle "{subtitle}"')
    if sound:
        parts.append('sound name "Purr"')

    script = " ".join(parts)
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, timeout=10,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        logger.debug("osascript notification failed: %s", exc)
        return False


def notify_scan_complete(
    orphan_size_human: str,
    junk_size_human: str,
    grand_total_human: str,
) -> bool:
    """
    Post a scan-complete notification with space summary.
    """
    msg = f"Found {grand_total_human} to clean · Orphans: {orphan_size_human} · Junk: {junk_size_human}"
    return post_notification(msg, subtitle="Scan complete")


# ── Scheduler ──────────────────────────────────────────────────────────────────

_AGENT_LABEL = "com.mac-cleaner.weekly-scan"
_AGENT_PLIST = HOME / "Library" / "LaunchAgents" / f"{_AGENT_LABEL}.plist"

# Interval: every 7 days in seconds
_WEEKLY_SECONDS = 7 * 24 * 60 * 60


def _find_mac_cleaner_binary() -> str:
    """Locate the mac-cleaner executable."""
    try:
        result = subprocess.run(
            ["which", "mac-cleaner"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, OSError) as exc:
        logger.debug("which mac-cleaner failed: %s", exc)
        pass
    # Common fallback locations
    for candidate in [
        HOME / ".local" / "bin" / "mac-cleaner",
        Path("/usr/local/bin/mac-cleaner"),
        Path("/opt/homebrew/bin/mac-cleaner"),
    ]:
        if candidate.exists():
            return str(candidate)
    return "mac-cleaner"   # Hope it's in PATH at runtime


def _build_plist(binary: str, notify: bool, clean: bool) -> dict:
    """Construct the LaunchAgent plist dictionary."""
    log_path = str(HOME / ".config" / "mac-cleaner" / "scheduler.log")
    if clean:
        args = [binary, "clean", "--auto"]
    else:
        args = [binary, "scan", "--export",
                str(HOME / ".config" / "mac-cleaner" / "history" / "scheduled_scan.json")]
    
    if notify:
        args.append("--notify")

    return {
        "Label": _AGENT_LABEL,
        "ProgramArguments": args,
        "StartInterval": _WEEKLY_SECONDS,
        "RunAtLoad": False,
        "StandardOutPath": log_path,
        "StandardErrorPath": log_path,
    }


def install_schedule(notify: bool = True, clean: bool = False) -> Tuple[bool, str]:
    """
    Install a weekly LaunchAgent for automatic scanning.

    Args:
        notify: If True, schedule will post a notification after each scan.
        clean: If True, schedule will run 'clean --auto' instead of 'scan'.

    Returns:
        (success, message)
    """
    binary = _find_mac_cleaner_binary()
    plist_data = _build_plist(binary, notify, clean)

    # Ensure LaunchAgents directory exists
    _AGENT_PLIST.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(_AGENT_PLIST, "wb") as f:
            plistlib.dump(plist_data, f)
    except OSError as e:
        return False, f"Failed to write plist: {e}"

    # Load the agent
    try:
        result = subprocess.run(
            ["launchctl", "load", "-w", str(_AGENT_PLIST)],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            err = result.stderr.strip() or "launchctl load failed"
            return False, f"Plist written but could not load agent: {err}"
    except (subprocess.TimeoutExpired, OSError) as e:
        logger.debug("launchctl load failed: %s", e)
        return False, f"Plist written but launchctl failed: {e}"

    return True, (
        f"Weekly scan scheduled ✓\n"
        f"  Agent: {_AGENT_PLIST}\n"
        f"  Binary: {binary}\n"
        f"  Notifications: {'on' if notify else 'off'}"
    )


def remove_schedule() -> Tuple[bool, str]:
    """Unload and delete the weekly scan LaunchAgent."""
    if not _AGENT_PLIST.exists():
        return False, "No scheduled scan found"

    # Unload
    try:
        subprocess.run(
            ["launchctl", "unload", "-w", str(_AGENT_PLIST)],
            capture_output=True, timeout=10,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        logger.debug("launchctl unload failed: %s", exc)
        pass  # Already unloaded — still delete the plist

    try:
        _AGENT_PLIST.unlink()
    except OSError as e:
        return False, f"Could not remove plist: {e}"

    return True, "Weekly scan schedule removed ✓"


def schedule_status() -> Tuple[bool, Optional[str]]:
    """
    Check whether the weekly scan agent is loaded.

    Returns:
        (is_loaded, detail_string)
    """
    if not _AGENT_PLIST.exists():
        return False, None

    try:
        result = subprocess.run(
            ["launchctl", "list", _AGENT_LABEL],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return True, result.stdout.strip()
    except (subprocess.TimeoutExpired, OSError) as exc:
        logger.debug("launchctl list failed: %s", exc)
        pass

    return False, "Plist exists but agent is not loaded"
