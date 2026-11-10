"""v3.5 safety tests use only temporary files and mocked external services."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from mac_deep_cleaner import cleanup, common, localization, settings
from mac_deep_cleaner.errors import APIError
from mac_deep_cleaner.history import History, mutation_lock


@pytest.fixture
def home(tmp_path, monkeypatch):
    root = tmp_path.resolve()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: root))
    monkeypatch.setattr(cleanup, "HOME", str(root))
    monkeypatch.setattr(common, "HOME", str(root))
    monkeypatch.setattr(settings, "SETTINGS_DIR", str(root / "settings"))
    monkeypatch.setattr(settings, "SETTINGS_FILE", str(root / "settings/settings.json"))
    monkeypatch.setattr(settings, "LEGACY_SETTINGS_FILE", str(root / "legacy.json"))
    return root


def test_trash_and_restore_with_duplicate_names_and_conflict(home):
    a, b = home / "one/data.txt", home / "two/data.txt"
    for path in (a, b):
        path.parent.mkdir()
        path.write_text(path.parent.name)
        assert cleanup.to_trash(str(path))[0]
    ledger = History(home)
    records = ledger.records()
    assert len(records) == 2 and len({r["trash"] for r in records}) == 2
    record = next(r for r in records if r["original"] == str(a))
    a.write_text("replacement")
    with pytest.raises(APIError, match="occupied"):
        ledger.restore(record["id"])
    assert a.read_text() == "replacement"
    a.unlink()
    ledger.restore(record["id"])
    assert a.read_text() == "one"
    with pytest.raises(APIError):
        ledger.restore(record["id"])


def test_changed_trash_and_substituted_parent_cannot_restore(home):
    path = home / "data/file"
    path.parent.mkdir()
    path.write_text("original")
    ledger = History(home)
    identifier = ledger.move(str(path))
    record = ledger.records()[0]
    Path(record["trash"]).write_text("changed content")
    with pytest.raises(APIError, match="changed"):
        ledger.restore(identifier)
    path.parent.rmdir()
    other = home / "other"
    other.mkdir()
    path.parent.symlink_to(other)
    with pytest.raises(APIError, match="safe"):
        ledger.restore(identifier)
    assert not (other / "file").exists()


def test_intent_survives_crash_before_final_journal_write(home):
    path = home / "file"
    path.write_text("keep")
    history = History(home)
    identifier = history.move(str(path))
    with history.connect() as db:
        db.execute("UPDATE moves SET status='prepared' WHERE id=?", (identifier,))
    assert history.records()[0]["available"]
    history.restore(identifier)
    assert path.read_text() == "keep"


def test_restore_failure_remains_retryable(home, monkeypatch):
    path = home / "file"
    path.write_text("keep")
    history = History(home)
    identifier = history.move(str(path))
    from mac_deep_cleaner import history as module

    real = module.exclusive_rename
    monkeypatch.setattr(module, "exclusive_rename", Mock(side_effect=OSError("busy")))
    with pytest.raises(OSError):
        history.restore(identifier)
    assert history.records()[0]["available"]
    monkeypatch.setattr(module, "exclusive_rename", real)
    history.restore(identifier)
    assert path.exists()


def test_cleanup_lock_blocks_other_operations(home):
    with mutation_lock(home), pytest.raises(APIError, match="different process"):
        cleanup.execute([])


def test_history_storage_and_trash_symlinks_are_rejected(home):
    outside = home / "outside"
    outside.mkdir()
    (home / ".Trash").symlink_to(outside)
    path = home / "file"
    path.write_text("keep")
    assert not cleanup.to_trash(str(path))[0]
    assert path.exists() and not list(outside.iterdir())


def test_all_language_packs_valid_and_registry_broad(home):
    assert len(localization.LANGUAGES) >= 190
    for path in (localization.WEB / "locales").glob("*.json"):
        localization.validate_pack(json.loads(path.read_text()))
    assert localization.load_pack("ar")["direction"] == "rtl"
    assert localization.load_pack("zh-TW")["direction"] == "ltr"
    assert localization.load_pack("ja")["messages"]["Settings"] == "設定"
    assert localization.load_pack("aa")["messages"] == {}


def test_language_pack_changing_and_coverage(home):
    from mac_deep_cleaner import settings

    # Test coverage across core languages
    for code, expected_settings, expected_dir in [
        ("es", "Ajustes", "ltr"),
        ("hi", "सेटिंग्स", "ltr"),
        ("fr", "Paramètres", "ltr"),
        ("de", "Einstellungen", "ltr"),
        ("ja", "設定", "ltr"),
        ("ar", "الإعدادات", "rtl"),
        ("zh-CN", "设置", "ltr"),
        ("it", "Impostazioni", "ltr"),
        ("pt", "Ajustes", "ltr"),
        ("ru", "Настройки", "ltr"),
    ]:
        pack = localization.load_pack(code)
        assert pack["locale"] == code
        assert pack["direction"] == expected_dir
        assert pack["messages"]["Settings"] == expected_settings
        assert "Appearance" in pack["messages"]
        assert "Theme" in pack["messages"]
        assert "Storage cleanup" in pack["messages"]
        assert "Safe" in pack["messages"]
        assert "Caution" in pack["messages"]
        assert "Risky" in pack["messages"]
        assert "Ghost Files" in pack["messages"]
        assert "Disk Used" in pack["messages"]
        assert "Name" in pack["messages"]
        assert "Size" in pack["messages"]
        assert "macOS Native" in pack["messages"]
        assert "Off" in pack["messages"]
        assert "On" in pack["messages"]

    # Test settings update & persistence
    settings.save_settings({"language": "es"})
    assert localization.metadata()["language"] == "es"
    settings.save_settings({"language": "ar"})
    assert localization.metadata()["language"] == "ar"
    settings.save_settings({"language": "en"})
    assert localization.metadata()["language"] == "en"


def test_language_pack_rejects_code_traversal_and_unknown_private_data(home):
    for document in [
        {"locale": "../evil", "messages": {}},
        {"locale": "fr", "messages": {"private.txt": "secret"}},
        {"locale": "fr", "messages": {"Settings": "<script>alert(1)</script>"}},
        {"locale": "fr", "messages": {"Settings": "\u202eevil"}},
    ]:
        with pytest.raises(APIError):
            localization.save_pack(document)
    localization.save_pack({"locale": "fr", "messages": {"Settings": "Options"}})
    assert localization.load_pack("fr")["messages"]["Settings"] == "Options"


def test_localization_is_offline(home, monkeypatch):
    """Ensure locale metadata advertises offline packs without cloud credentials."""
    import urllib.request
    monkeypatch.setattr(urllib.request, 'urlopen', Mock(side_effect=AssertionError('Unexpected network')))
    assert localization.metadata()['provider'] == 'offline'
    assert not hasattr(localization, 'generate')
    assert localization.load_pack('fr')['messages']['Settings']


def test_dismissed_ghost_stays_excluded_after_rescan(home, monkeypatch):
    from mac_deep_cleaner.ghosts import controller
    from mac_deep_cleaner.ghosts.finder import Ghost
    from mac_deep_cleaner.scanner import Scanner
    from mac_deep_cleaner.service import CleanerService

    path = home / "Library/Caches/org.example.vanished"
    path.parent.mkdir(parents=True)
    path.write_text("cache")
    ghost = Ghost(
        str(path),
        "Caches",
        "org.example.vanished",
        "Vanished",
        5,
        90,
        "high",
        common.fingerprint(str(path)),
    )
    monkeypatch.setattr(controller, "find_ghosts", lambda **kwargs: [ghost])
    service = CleanerService(SimpleNamespace(), {"mode": "normal", "min_mb": 0, "pinned": []})
    service.scanner = Scanner(quiet=True)
    service.scanner.done = True
    service.scan_id = "fixture"
    ghosts = controller.GhostController(service)
    try:
        ghosts.scan()
        ghosts.scan_job.thread.join(3)
        identifier = next(iter(ghosts.entries))
        ghosts.post(
            "/api/ghosts/hide",
            {"id": identifier, "scan_id": service.scan_id, "revision": service.revision},
        )
        assert str(path) in settings.load_settings()["ghost_allowlist"]
        assert str(path) in service.scanner.pinned
        ghosts.scan()
        ghosts.scan_job.thread.join(3)
        assert not ghosts.entries
    finally:
        service.close()
