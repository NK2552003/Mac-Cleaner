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


def test_browser_data_new_browsers(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from scanners import browser_data as bd

    monkeypatch.setattr(bd, "HOME", tmp_path)

    # Arc
    arc_data = tmp_path / "Library" / "Application Support" / "Arc" / "User Data" / "Default" / "Cache"
    arc_data.mkdir(parents=True)
    (arc_data / "f_0001").write_bytes(b"a" * 512)

    # Zen
    zen_profile = tmp_path / "Library" / "Application Support" / "zen" / "Profiles" / "default"
    zen_profile.mkdir(parents=True)
    (zen_profile / "cookies.sqlite").write_bytes(b"b" * 256)

    # Opera
    opera_data = tmp_path / "Library" / "Application Support" / "com.operasoftware.Opera" / "Default" / "Cache"
    opera_data.mkdir(parents=True)
    (opera_data / "data").write_bytes(b"c" * 128)

    # Vivaldi
    vivaldi_data = tmp_path / "Library" / "Application Support" / "Vivaldi" / "Default" / "History"
    vivaldi_data.parent.mkdir(parents=True)
    vivaldi_data.write_bytes(b"d" * 128)

    # Orion
    orion_data = tmp_path / "Library" / "Application Support" / "Orion" / "Defaults" / "history"
    orion_data.parent.mkdir(parents=True)
    orion_data.write_bytes(b"e" * 64)

    items = bd.collect_browser_data(browsers=["arc", "zen", "opera", "vivaldi", "orion"])
    browsers_found = {i.browser for i in items}
    assert "arc" in browsers_found
    assert "zen" in browsers_found
    assert "opera" in browsers_found
    assert "vivaldi" in browsers_found
    assert "orion" in browsers_found


def test_docker_cleaner_parse_size() -> None:
    from scanners.docker_cleaner import _parse_size

    assert _parse_size("1.5GB") == int(1.5 * 1024**3)
    assert _parse_size("1.5 GiB") == int(1.5 * 1024**3)
    assert _parse_size("1.5GiB") == int(1.5 * 1024**3)
    assert _parse_size("1.2 GB (50%)") == int(1.2 * 1024**3)
    assert _parse_size("500MB") == int(500 * 1024**2)
    assert _parse_size("500 MiB") == int(500 * 1024**2)
    assert _parse_size("250KB") == int(250 * 1024)
    assert _parse_size("250 KiB") == int(250 * 1024)
    assert _parse_size("100 B") == 100
    assert _parse_size("0B") == 0
    assert _parse_size("") == 0


def test_docker_cleaner_scan_and_clean(monkeypatch: pytest.MonkeyPatch) -> None:
    from scanners import docker_cleaner as dc
    import subprocess

    sample_df = (
        '{"Type":"Images","TotalCount":5,"Active":2,"Size":"1.5GB","Reclaimable":"1.2GB (80%)"}\n'
        '{"Type":"Containers","TotalCount":3,"Active":1,"Size":"200MB","Reclaimable":"150MB (75%)"}\n'
    )

    class FakeCompleted:
        def __init__(self, stdout: str, returncode: int = 0):
            self.stdout = stdout
            self.returncode = returncode

    def fake_run(cmd, **kwargs):
        if "df" in cmd:
            return FakeCompleted(sample_df)
        elif "prune" in cmd:
            return FakeCompleted("Total reclaimed space: 1.35GB\n")
        return FakeCompleted("", returncode=1)

    monkeypatch.setattr(dc, "_run_container_cmd", lambda cmd, **kw: fake_run(cmd))

    entries = dc.scan_docker_bloat()
    assert len(entries) == 2
    assert entries[0].category == "Container Images"
    assert entries[0].size == int(1.2 * 1024**3)
    assert entries[1].category == "Container Containers"
    assert entries[1].size == int(150 * 1024**2)

    freed = dc.clean_docker_bloat()
    assert freed == int(1.35 * 1024**3)


def test_installer_hunter(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from scanners import installer_hunter as ih

    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    apps_dir = tmp_path / "Applications"
    apps_dir.mkdir()

    # Install an app
    slack_app = apps_dir / "Slack.app"
    slack_app.mkdir()

    monkeypatch.setattr(ih, "HOME", tmp_path)
    monkeypatch.setattr(ih, "_DEFAULT_ROOTS", [downloads])

    # Fake _installed_app_names to check our tmp Applications dir
    monkeypatch.setattr(ih, "_installed_app_names", lambda: {"slack"})

    # Create installers in downloads
    slack_dmg = downloads / "Slack-4.36.140-arm64.dmg"
    slack_dmg.write_bytes(b"x" * (2 * 1024 * 1024))

    zoom_pkg = downloads / "Zoom_installer.pkg"
    zoom_pkg.write_bytes(b"y" * (3 * 1024 * 1024))

    items = ih.find_installers(roots=[downloads], min_size_mb=1)
    assert len(items) == 2

    slack_item = next(i for i in items if "slack" in i.path.name.lower())
    assert slack_item.is_installed is True
    assert slack_item.installed_app == "Slack"

    zoom_item = next(i for i in items if "zoom" in i.path.name.lower())
    assert zoom_item.is_installed is False

    # Test delete
    result = ih.delete_installers([zoom_item], allowed_roots=[downloads])
    assert result.deleted == 1
    assert not zoom_pkg.exists()
    assert slack_dmg.exists()


def test_xcode_cleaner(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from scanners import xcode_cleaner as xc

    xcode_root = tmp_path / "Developer" / "Xcode"
    derived_data = xcode_root / "DerivedData"
    derived_data.mkdir(parents=True)
    (derived_data / "ModuleCache").mkdir()
    (derived_data / "ModuleCache" / "cache.bin").write_bytes(b"x" * 2048)

    sim_caches = tmp_path / "Developer" / "CoreSimulator" / "Caches"
    sim_caches.mkdir(parents=True)
    (sim_caches / "data").write_bytes(b"y" * 1024)

    monkeypatch.setattr(xc, "_DEFAULT_PATHS", {
        "Derived Data": derived_data,
        "CoreSimulator Caches": sim_caches,
    })
    monkeypatch.setattr(xc, "_ALLOWED_ROOTS", [xcode_root, tmp_path / "Developer" / "CoreSimulator"])

    items = xc.collect_xcode_junk()
    assert len(items) == 2

    # Delete with category filter
    res = xc.delete_xcode_junk(items, categories=["Derived Data"])
    assert res.deleted == 1
    assert not derived_data.exists()
    assert sim_caches.exists()


def test_bytes_human_precision() -> None:
    from utils import bytes_human

    assert bytes_human(0) == "0 B"
    assert bytes_human(500) == "500 B"
    assert bytes_human(1536 * 1024) == "1.5 MB"
    assert bytes_human(int(2.5 * 1024 * 1024 * 1024)) == "2.5 GB"
    assert bytes_human(1500) == "1.5 KB"


def test_xcode_cleaner_category_normalization(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from scanners import xcode_cleaner as xc

    xcode_root = tmp_path / "Developer" / "Xcode"
    derived_data = xcode_root / "DerivedData"
    derived_data.mkdir(parents=True)
    (derived_data / "cache.bin").write_bytes(b"x" * 1024)

    monkeypatch.setattr(xc, "_DEFAULT_PATHS", {"Derived Data": derived_data})
    monkeypatch.setattr(xc, "_ALLOWED_ROOTS", [xcode_root])

    items = xc.collect_xcode_junk()
    assert len(items) == 1

    # Should match "Derived Data" even with hyphen or lowercase
    res = xc.delete_xcode_junk(items, categories=["derived-data"])
    assert res.deleted == 1
    assert not derived_data.exists()


def test_browser_data_caches_and_category_normalization(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from scanners import browser_data as bd

    monkeypatch.setattr(bd, "HOME", tmp_path)
    chrome_cache = tmp_path / "Library" / "Caches" / "Google" / "Chrome"
    chrome_cache.mkdir(parents=True)
    (chrome_cache / "data_0").write_bytes(b"c" * 2048)

    monkeypatch.setattr(bd, "_ALLOWED_ROOTS", [chrome_cache])

    items = bd.collect_browser_data(browsers=["chrome"])
    assert any(i.path == chrome_cache for i in items)

    # Test delete with underscore or dash category
    res = bd.delete_browser_data(items, categories=["cache"])
    assert res.deleted >= 1
    assert not chrome_cache.exists()
