"""Tests for P0/P1 features."""

from __future__ import annotations

import pathlib
import plistlib
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).parent.parent
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def test_photo_library_analyzer(tmp_path: pathlib.Path) -> None:
    from scanners.photos_analyzer import analyze_photo_library, find_photo_libraries

    pictures = tmp_path / "Pictures"
    pictures.mkdir()
    lib = pictures / "Test.photoslibrary"
    originals = lib / "originals"
    database = lib / "database"
    originals.mkdir(parents=True)
    database.mkdir(parents=True)

    (originals / "img1.jpg").write_bytes(b"x" * 1024)
    (database / "Photos.sqlite").write_bytes(b"y" * 256)

    libs = find_photo_libraries([pictures])
    assert lib in libs

    report = analyze_photo_library(lib)
    assert report.originals_count == 1
    assert report.originals_size > 0


def test_browser_data_collect_chrome(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from scanners import browser_data as bd

    monkeypatch.setattr(bd, "HOME", tmp_path)

    base = tmp_path / "Library" / "Application Support" / "Google" / "Chrome" / "Default"
    cache_dir = base / "Cache"
    cache_dir.mkdir(parents=True)
    (cache_dir / "data").write_bytes(b"z" * 1024)

    items = bd.collect_browser_data(browsers=["chrome"])
    categories = {i.category for i in items}
    assert "cache" in categories


def test_simulator_device_parsing(tmp_path: pathlib.Path) -> None:
    from scanners.simulators import find_simulator_devices, purge_simulator_devices

    devices_root = tmp_path / "Devices"
    device_dir = devices_root / "ABC-123"
    device_dir.mkdir(parents=True)

    info = {
        "name": "iPhone 15",
        "runtime": "com.apple.CoreSimulator.SimRuntime.iOS-17-0",
        "state": "Shutdown",
        "isAvailable": False,
    }
    with open(device_dir / "device.plist", "wb") as f:
        plistlib.dump(info, f)

    devices = find_simulator_devices(devices_root)
    assert len(devices) == 1
    assert devices[0].name == "iPhone 15"
    assert devices[0].is_available is False

    result = purge_simulator_devices(devices)
    assert result.deleted == 1
    assert not device_dir.exists()
