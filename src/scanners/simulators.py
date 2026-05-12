"""iOS Simulator data scanner and cleaner."""

from __future__ import annotations

import plistlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from constants import HOME
from utils import size_of

SIM_ROOT = HOME / "Library" / "Developer" / "CoreSimulator"
DEVICES_DIR = SIM_ROOT / "Devices"
CACHES_DIR = SIM_ROOT / "Caches"
LOGS_DIR = SIM_ROOT / "Logs"


@dataclass
class SimulatorDevice:
    """One simulator device bundle."""
    udid: str
    name: str
    runtime: str
    state: str
    is_available: bool
    path: Path
    size: int


@dataclass
class SimulatorCache:
    """One simulator cache directory."""
    category: str
    path: Path
    size: int


@dataclass
class PurgeResult:
    """Summary of a purge operation."""
    deleted: int = 0
    bytes_freed: int = 0
    errors: List[str] = field(default_factory=list)


def _read_device_plist(path: Path) -> dict:
    try:
        with open(path, "rb") as f:
            return plistlib.load(f)
    except (OSError, plistlib.InvalidFileException, ValueError):
        return {}


def find_simulator_devices(devices_root: Optional[Path] = None) -> List[SimulatorDevice]:
    """Return simulator devices sorted by size descending."""
    root = devices_root or DEVICES_DIR
    devices: List[SimulatorDevice] = []

    if not root.exists():
        return devices

    for child in root.iterdir():
        if not child.is_dir():
            continue
        info = _read_device_plist(child / "device.plist")
        name = str(info.get("name", child.name[:8]))
        runtime = str(info.get("runtime", "Unknown"))
        state = str(info.get("state", "unknown"))
        is_available = bool(info.get("isAvailable", True))
        devices.append(SimulatorDevice(
            udid=child.name,
            name=name,
            runtime=runtime,
            state=state,
            is_available=is_available,
            path=child,
            size=size_of(child),
        ))

    devices.sort(key=lambda d: d.size, reverse=True)
    return devices


def find_simulator_caches(sim_root: Optional[Path] = None) -> List[SimulatorCache]:
    """Return CoreSimulator cache directories."""
    root = sim_root or SIM_ROOT
    caches: List[SimulatorCache] = []

    for category, path in [
        ("Caches", root / "Caches"),
        ("Logs", root / "Logs"),
    ]:
        if path.exists():
            caches.append(SimulatorCache(category=category, path=path, size=size_of(path)))

    return caches


def purge_simulator_devices(devices: List[SimulatorDevice]) -> PurgeResult:
    """Delete simulator device directories."""
    from utils import safe_remove

    result = PurgeResult()
    for device in devices:
        ok, freed = safe_remove(device.path)
        if ok:
            result.deleted += 1
            result.bytes_freed += freed
        else:
            result.errors.append(str(device.path))
    return result


def purge_simulator_caches(caches: List[SimulatorCache]) -> PurgeResult:
    """Delete simulator cache directories."""
    from utils import safe_remove

    result = PurgeResult()
    for cache in caches:
        ok, freed = safe_remove(cache.path)
        if ok:
            result.deleted += 1
            result.bytes_freed += freed
        else:
            result.errors.append(str(cache.path))
    return result
