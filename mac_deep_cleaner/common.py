"""Shared filesystem and formatting utilities."""

import os
import re
import subprocess
import sys
import time


HOME = os.path.expanduser("~")


IS_MAC = sys.platform == "darwin"


WORKERS = min(8, os.cpu_count() or 4)


NOW = time.time()


DAY = 86400


SAFE, CAUTION, RISKY = "safe", "caution", "risky"


MIN_SPEC = 256 * 1024          # ignore fixed-path targets smaller than this


USE_COLOR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def c(txt, code):
    return f"\033[{code}m{txt}\033[0m" if USE_COLOR else str(txt)


COL = {SAFE: "32", CAUTION: "33", RISKY: "31"}


def fmt(n):
    n = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1000 or unit == "TB":
            return f"{int(n)} B" if unit == "B" else (f"{n:.2f} {unit}" if unit in ("GB", "TB") else f"{n:.1f} {unit}")
        n /= 1000


def expand(p):
    return os.path.expanduser(p)


def run(cmd, timeout=30):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout
    except Exception:
        return ""


def dir_size(path):
    """Real disk usage (blocks) of a file or tree. Never follows symlinks, ignores errors."""
    try:
        st = os.lstat(path)
    except OSError:
        return 0
    if not os.path.isdir(path) or os.path.islink(path):
        return st.st_blocks * 512
    total, stack = 0, [path]
    while stack:
        d = stack.pop()
        try:
            with os.scandir(d) as it:
                for e in it:
                    try:
                        if e.is_dir(follow_symlinks=False):
                            stack.append(e.path)
                        else:
                            total += e.stat(follow_symlinks=False).st_blocks * 512
                    except OSError:
                        pass
        except OSError:
            pass
    return total


def newest_mtime(path):
    try:
        return os.lstat(path).st_mtime
    except OSError:
        return 0


def norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def is_readonly(path):
    return not os.access(path, os.W_OK) or (os.path.exists(path) and not os.access(os.path.dirname(path) or "/", os.W_OK))


def fingerprint(path):
    """Identity and change marker captured when a path is offered for review."""
    try:
        st = os.lstat(path)
        return (st.st_dev, st.st_ino, st.st_mode, st.st_size, st.st_mtime_ns)
    except OSError:
        return ()
