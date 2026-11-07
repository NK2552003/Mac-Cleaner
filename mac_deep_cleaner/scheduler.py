"""Opt-in weekly launchd cleanup restricted to aged cache/log children."""

import fcntl
import os
import plistlib
import subprocess
import sys
import time
from pathlib import Path

from .cleanup import execute, guard_ok
from .common import dir_size, fingerprint
from .errors import APIError
from .history import History
from .models import Item
from .settings import load_settings

LABEL = "com.macdeepcleaner.weekly"
AGE_DAYS = 7
MAX_BYTES = 2_000_000_000


def agent_path():
    return Path.home() / "Library/LaunchAgents" / (LABEL + ".plist")


def command():
    if getattr(sys, "frozen", False):
        return [sys.executable, "care", "scheduled-run"]
    source_entry = Path(__file__).resolve().parent.parent / "mc.py"
    entry = [str(source_entry)] if source_entry.is_file() else ["-m", "mac_deep_cleaner"]
    return [sys.executable, *entry, "care", "scheduled-run"]


def definition(weekday=0, hour=10):
    if (
        type(weekday) is not int
        or not 0 <= weekday <= 6
        or type(hour) is not int
        or not 0 <= hour <= 23
    ):
        raise APIError(400, "Weekday must be 0–6 (Sunday–Saturday), and hour 0–23.")
    return {
        "Label": LABEL,
        "ProgramArguments": command(),
        "StartCalendarInterval": {"Weekday": weekday, "Hour": hour, "Minute": 0},
        "ProcessType": "Background",
        "LowPriorityIO": True,
        "Nice": 10,
        "WorkingDirectory": str(Path.home()),
        "EnvironmentVariables": {"PATH": "/usr/bin:/bin:/usr/sbin:/sbin"},
    }


def status():
    path = agent_path()
    try:
        value = plistlib.loads(path.read_bytes())
        if not isinstance(value, dict):
            raise TypeError('Invalid schedule definition')
        return {
            "enabled": value.get("Label") == LABEL,
            "calendar": value.get("StartCalendarInterval"),
            "path": str(path),
            "supported": sys.platform == "darwin",
        }
    except (OSError, ValueError, TypeError, plistlib.InvalidFileException):
        return {"enabled": False, "supported": sys.platform == "darwin", "path": str(path)}


def configure(enabled, weekday=0, hour=10):
    if type(enabled) is not bool:
        raise APIError(400, "enabled must be true or false.")
    if sys.platform != "darwin":
        raise APIError(400, "Scheduling requires macOS launchd.")
    path = agent_path()
    if path.resolve() != path:
        raise APIError(400, "LaunchAgents cannot contain symbolic links.")
    domain = "gui/" + str(os.getuid())
    if not enabled:
        result = subprocess.run(
            ["/bin/launchctl", "bootout", domain + "/" + LABEL],
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
        if result.returncode not in (0, 3, 113):
            raise APIError(400, result.stderr.strip() or "Could not unload the weekly agent.")
        path.unlink(missing_ok=True)
        return status()
    data = plistlib.dumps(definition(weekday, hour))
    if path.exists():
        raise APIError(409, "Disable the existing schedule before changing its time.")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with open(path, "xb") as handle:
        os.chmod(path, 0o600)
        handle.write(data)
    try:
        subprocess.run(
            ["/bin/launchctl", "bootstrap", domain, str(path)],
            capture_output=True,
            text=True,
            check=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        path.unlink(missing_ok=True)
        raise APIError(400, "launchd could not load the schedule: " + str(exc)) from exc
    return status()


def candidates(home=None):
    """Never empty Trash, execute commands, remove apps, or expand custom rules."""
    home = Path(home or Path.home())
    pins = load_settings()["pinned"]
    cutoff = time.time() - AGE_DAYS * 86400
    result, total = [], 0
    for relative in ("Library/Caches", "Library/Logs"):
        root = home / relative
        if root.resolve() != root:
            continue
        try:
            entries = sorted(root.iterdir())
        except OSError:
            continue
        for entry in entries:
            # Caches can contain live databases; only stale regular files are automatic.
            if not guard_ok(str(entry)) or entry.is_symlink() or not entry.is_file():
                continue
            if any(str(entry) == p or str(entry).startswith(p + os.sep) for p in pins):
                continue
            try:
                st = entry.stat()
            except OSError:
                continue  # Files may disappear while a scheduled scan is running.
            if max(st.st_mtime, st.st_atime, st.st_ctime) > cutoff or st.st_nlink != 1:
                continue
            size = dir_size(str(entry))
            if total + size > MAX_BYTES or len(result) >= 500:
                continue
            total += size
            result.append(
                Item(
                    path=str(entry),
                    name=entry.name,
                    size=size,
                    safety="safe",
                    fingerprint=fingerprint(str(entry)),
                    selected=True,
                )
            )
    return result


def run_scheduled(preview=False):
    history = History()
    if history.directory.resolve() != history.directory:
        raise OSError('Cleanup lock location cannot contain symbolic links.')
    history.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    flags = os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0)
    with os.fdopen(os.open(history.directory / 'scheduled.lock', flags, 0o600), 'a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {"skipped": "A scheduled cleanup is already running."}
        items = candidates()
        logs = []
        processed, _roots, failures = execute(items, dry_run=preview, log=logs.append)
        import shutil

        history.sample(shutil.disk_usage(Path.home()))
    if not preview and sys.platform == "darwin":
        message = f"Moved {len(items) - len(failures)} old cache/log files to Trash. Restore from Cleanup history."
        subprocess.run(
            [
                "/usr/bin/osascript",
                "-e",
                'on run argv\ndisplay notification (item 1 of argv) with title "Mac Deep Cleaner"\nend run',
                message,
            ],
            capture_output=True,
            check=False,
            timeout=15,
        )
    return {
        "preview": preview,
        "processed_bytes": processed,
        "files": len(items),
        "failures": len(failures),
        "log": logs,
    }
