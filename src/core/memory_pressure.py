"""Memory pressure inspection and cache purge helpers."""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Tuple


@dataclass
class MemoryStats:
    """Snapshot of system memory statistics."""
    captured_at: str
    page_size: int
    pages_free: int
    pages_active: int
    pages_inactive: int
    pages_speculative: int
    pages_wired: int
    pages_compressed: int
    free_percent: Optional[float] = None
    pressure_level: Optional[str] = None

    @property
    def total_pages(self) -> int:
        return (
            self.pages_free
            + self.pages_active
            + self.pages_inactive
            + self.pages_speculative
            + self.pages_wired
            + self.pages_compressed
        )

    @property
    def free_pages(self) -> int:
        return self.pages_free + self.pages_speculative

    @property
    def total_bytes(self) -> int:
        return self.total_pages * self.page_size

    @property
    def free_bytes(self) -> int:
        return self.free_pages * self.page_size

    @property
    def used_bytes(self) -> int:
        used_pages = max(self.total_pages - self.free_pages, 0)
        return used_pages * self.page_size


@dataclass
class ReliefResult:
    """Summary of a cache purge attempt."""
    success: bool
    message: str
    stdout: str = ""
    stderr: str = ""


_VM_PAGE_RE = re.compile(r"page size of (\d+) bytes", re.IGNORECASE)
_VM_NUMBER_RE = re.compile(r"([0-9]+)\.")


def parse_vm_stat(output: str) -> Optional[MemoryStats]:
    """Parse vm_stat output into MemoryStats."""
    page_size = None
    pages = {
        "free": 0,
        "active": 0,
        "inactive": 0,
        "speculative": 0,
        "wired": 0,
        "compressed": 0,
    }

    for line in output.splitlines():
        if page_size is None:
            match = _VM_PAGE_RE.search(line)
            if match:
                page_size = int(match.group(1))
                continue
        lower = line.strip().lower()
        if not lower.startswith("pages "):
            continue
        number = _VM_NUMBER_RE.search(lower)
        if not number:
            continue
        value = int(number.group(1))
        if lower.startswith("pages free"):
            pages["free"] = value
        elif lower.startswith("pages active"):
            pages["active"] = value
        elif lower.startswith("pages inactive"):
            pages["inactive"] = value
        elif lower.startswith("pages speculative"):
            pages["speculative"] = value
        elif lower.startswith("pages wired"):
            pages["wired"] = value
        elif "pages occupied by compressor" in lower or lower.startswith("pages compressed"):
            pages["compressed"] = value

    if page_size is None:
        return None

    return MemoryStats(
        captured_at=datetime.now().isoformat(),
        page_size=page_size,
        pages_free=pages["free"],
        pages_active=pages["active"],
        pages_inactive=pages["inactive"],
        pages_speculative=pages["speculative"],
        pages_wired=pages["wired"],
        pages_compressed=pages["compressed"],
    )


def parse_memory_pressure(output: str) -> Tuple[Optional[float], Optional[str]]:
    """Parse memory_pressure output for free percentage and level."""
    free_percent = None
    level = None
    for line in output.splitlines():
        if "memory free percentage" in line.lower():
            parts = re.findall(r"(\d+(?:\.\d+)?)%", line)
            if parts:
                free_percent = float(parts[0])
        if "memory pressure" in line.lower():
            parts = line.split(":", 1)
            if len(parts) == 2:
                level = parts[1].strip().lower()
    return free_percent, level


def collect_memory_stats(
    runner=subprocess.run,
) -> Optional[MemoryStats]:
    """Collect memory stats using vm_stat and memory_pressure when available."""
    try:
        result = runner(
            ["vm_stat"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None

    if result.returncode != 0:
        return None

    stats = parse_vm_stat(result.stdout)
    if stats is None:
        return None

    mp_bin = shutil.which("memory_pressure")
    if mp_bin:
        try:
            mp = runner(
                [mp_bin, "-Q"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if mp.returncode == 0:
                free_percent, level = parse_memory_pressure(mp.stdout)
                stats.free_percent = free_percent
                stats.pressure_level = level
        except (OSError, subprocess.TimeoutExpired):
            pass

    return stats


def relieve_memory_pressure(runner=subprocess.run) -> ReliefResult:
    """Attempt to purge inactive memory caches using the system purge tool."""
    purge_bin = shutil.which("purge")
    if not purge_bin:
        return ReliefResult(False, "purge not available on this system")

    try:
        result = runner(
            [purge_bin],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        return ReliefResult(False, "purge timed out after 120 seconds")
    except OSError as exc:
        return ReliefResult(False, f"purge failed: {exc}")

    if result.returncode == 0:
        return ReliefResult(True, "purge completed", stdout=result.stdout)
    return ReliefResult(False, "purge failed", stdout=result.stdout, stderr=result.stderr)
