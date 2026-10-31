"""Private, validated settings with atomic writes."""
import json
import math
import os
import subprocess
import tempfile
from .common import HOME, IS_MAC, expand, run

SETTINGS_DIR = os.path.join(HOME, "Library", "Application Support", "Mac Deep Cleaner")
SETTINGS_FILE = os.path.join(SETTINGS_DIR, "settings.json")
LEGACY_SETTINGS_FILE = os.path.join(HOME, "Library", "Application Support", "Mac Cleaner", "settings.json")
DEFAULT_SETTINGS = {"mode": "normal", "delete": "trash", "min_mb": 10, "pinned": [], "theme": "dark"}


def validated(value):
    result = {**DEFAULT_SETTINGS, "pinned": []}
    if not isinstance(value, dict):
        return result
    if value.get("mode") in ("normal", "dev"):
        result["mode"] = value["mode"]
    if value.get("delete") in ("trash", "rm"):
        result["delete"] = value["delete"]
    if value.get("theme") in ("dark", "light"):
        result["theme"] = value["theme"]
    size = value.get("min_mb")
    if type(size) in (int, float) and math.isfinite(size) and 0 <= size <= 1_000_000:
        result["min_mb"] = size
    pins = value.get("pinned")
    if isinstance(pins, list):
        result["pinned"] = sorted({os.path.abspath(p) for p in pins if isinstance(p, str) and os.path.isabs(p) and "\x00" not in p})[:10000]
    return result


def load_settings():
    try:
        source = SETTINGS_FILE if os.path.exists(SETTINGS_FILE) else LEGACY_SETTINGS_FILE
        with open(source, encoding="utf-8") as handle:
            return validated(json.load(handle))
    except (OSError, ValueError):
        return validated({})


def save_settings(value):
    temporary = None
    try:
        os.makedirs(SETTINGS_DIR, mode=0o700, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=".settings-", dir=SETTINGS_DIR)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(validated(value), handle, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, SETTINGS_FILE)
        return True
    except OSError:
        return False
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def full_disk_access():
    """True/False when we can tell, None when unknown. Protected files only open with Full Disk Access."""
    if not IS_MAC:
        return None
    for p in ("~/Library/Safari", "~/Library/Application Support/com.apple.TCC/TCC.db"):
        p = expand(p)
        if os.path.exists(p):
            try:
                if os.path.isdir(p):
                    os.listdir(p)
                else:
                    open(p, "rb").close()
                return True
            except PermissionError:
                return False
            except OSError:
                continue
    return None


def open_fda_settings():
    run(["open", "x-apple.systempreferences:com.apple.preference.security?Privacy_AllFiles"], 5)


def reveal(path):
    if IS_MAC and path and os.path.lexists(path):
        subprocess.Popen(["open", "-R", path])
        return True
    return False
