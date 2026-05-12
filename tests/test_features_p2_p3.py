"""Tests for P2/P3 feature modules."""

from __future__ import annotations

import pathlib
import sqlite3
import sys
from collections import namedtuple

REPO_ROOT = pathlib.Path(__file__).parent.parent
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def test_storage_trend_record_and_summary(tmp_path: pathlib.Path) -> None:
    from reporting.storage_trend import append_snapshot, load_snapshots, record_snapshot, summarize_trend

    Usage = namedtuple("Usage", ["total", "used", "free"])

    def fake_usage(_path: str) -> Usage:
        return Usage(1000, 600, 400)

    trend_file = tmp_path / "trend.json"
    snap1 = record_snapshot(volume=tmp_path, disk_usage=fake_usage)
    append_snapshot(snap1, trend_path=trend_file)

    def fake_usage2(_path: str) -> Usage:
        return Usage(1000, 700, 300)

    snap2 = record_snapshot(volume=tmp_path, disk_usage=fake_usage2)
    append_snapshot(snap2, trend_path=trend_file)

    snapshots = load_snapshots(trend_path=trend_file)
    assert len(snapshots) == 2

    summary = summarize_trend(snapshots)
    assert summary is not None
    assert summary.delta_used == 100


def test_recent_activity_collect_and_clear(tmp_path: pathlib.Path) -> None:
    from scanners.recent_activity import clear_recent_items, collect_recent_activity

    recent_dir = tmp_path / "Library" / "Recent Items"
    recent_dir.mkdir(parents=True)
    target = recent_dir / "recent.alias"
    target.write_bytes(b"x" * 64)

    items = collect_recent_activity(home=tmp_path)
    assert any(i.path == target for i in items)

    result = clear_recent_items(home=tmp_path)
    assert result.deleted == 1
    assert not target.exists()


def test_cloud_junk_collect(tmp_path: pathlib.Path) -> None:
    from scanners.cloud_junk import collect_cloud_junk

    cache_dir = tmp_path / "Library" / "Caches" / "com.dropbox.Dropbox"
    cache_dir.mkdir(parents=True)
    (cache_dir / "cache.bin").write_bytes(b"z" * 128)

    items = collect_cloud_junk(home=tmp_path)
    assert any(i.provider == "Dropbox" for i in items)


def test_permissions_auditor_reads_db(tmp_path: pathlib.Path) -> None:
    from core.permissions_auditor import audit_permissions

    db_path = tmp_path / "TCC.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE access (service TEXT, client TEXT, client_type INTEGER, "
        "auth_value INTEGER, auth_reason INTEGER, auth_version INTEGER, last_modified INTEGER)"
    )
    conn.execute(
        "INSERT INTO access VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("kTCCServiceSystemPolicyAllFiles", "com.example.app", 0, 1, 0, 1, 0),
    )
    conn.commit()
    conn.close()

    report = audit_permissions(db_paths=[db_path])
    assert len(report.entries) == 1
    assert report.entries[0].allowed is True


def test_apfs_snapshot_parse() -> None:
    from core.apfs_snapshots import parse_tmutil_output

    sample = """Snapshots for disk /:
com.apple.TimeMachine.2024-05-10-120102.local
com.apple.TimeMachine.2024-05-11-083012.local
"""
    snaps = parse_tmutil_output(sample)
    assert len(snaps) == 2
    assert snaps[0].token == "2024-05-10-120102"


def test_memory_pressure_parse() -> None:
    from core.memory_pressure import parse_vm_stat

    sample = """Mach Virtual Memory Statistics: (page size of 4096 bytes)
Pages free:                               1000.
Pages active:                             2000.
Pages inactive:                           3000.
Pages speculative:                        400.
Pages wired down:                         500.
Pages occupied by compressor:             600.
"""
    stats = parse_vm_stat(sample)
    assert stats is not None
    assert stats.page_size == 4096
    assert stats.pages_wired == 500


def test_breach_monitor_parse() -> None:
    from core.breach_monitor import parse_breach_response

    payload = "[{\"Name\": \"Example\", \"Title\": \"Example\"}]"
    data = parse_breach_response(payload)
    assert data and data[0]["Name"] == "Example"


def test_menubar_format_swiftbar() -> None:
    from core.menubar import MenubarStatus, format_swiftbar

    status = MenubarStatus(
        label="Cleaner: 1.0 GB",
        subtitle="Last scan: 2026-05-12 10:00",
        orphan_bytes=1024,
        junk_bytes=2048,
        dev_junk_bytes=0,
        scanned_at="2026-05-12T10:00:00",
    )
    output = format_swiftbar(status)
    assert "---" in output
    assert "mac-cleaner" in output
