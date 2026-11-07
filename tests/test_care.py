"""v3.5 safety tests use only temporary files and mocked external services."""

import json
import os
import shutil
import threading
import time
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from mac_deep_cleaner import cleanup, common, localization, profiles, scheduler, settings
from mac_deep_cleaner.care import Care, export_html
from mac_deep_cleaner.errors import APIError
from mac_deep_cleaner.history import History, mutation_lock
from mac_deep_cleaner.media import difference_hash, distance, scan
from mac_deep_cleaner.models import Item


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


def test_hourly_samples_do_not_duplicate(home):
    history = History(home)
    disk = shutil.disk_usage(home)
    history.sample(disk)
    values = history.sample(disk)
    assert len(values) == 1 and values[0]["free"] == disk.free


def test_profiles_exclude_dangerous_or_manual_operations():
    safe = Item(id=1, category="App Caches", safety="safe")
    excluded = [
        replace(safe, id=i + 2, **kw)
        for i, kw in enumerate(
            [
                {"action": "empty"},
                {"action": "cmd"},
                {"manual": True},
                {"protected": True},
                {"managed": True},
                {"readonly": True},
                {"keep": "/keeper"},
                {"safety": "risky"},
            ]
        )
    ]
    assert profiles.profile_items([safe, *excluded], "minimal") == [safe]
    with pytest.raises(APIError):
        profiles.profile_items([safe], "unknown")


@pytest.mark.parametrize(
    "path",
    [
        "~/Documents/*",
        "~/Library/Caches/*",
        "~/Library/Caches/*/data",
        "~/Library/Caches/app/../../Documents/*",
        "~/Library/Caches/app/**",
    ],
)
def test_rules_reject_broad_or_traversal_globs(path):
    with pytest.raises(APIError):
        profiles.validate_rules({"rules": [{"name": "test", "path": path, "reason": "test"}]})


def test_rules_cannot_execute_commands():
    rule = {
        "name": "test",
        "path": "~/Library/Caches/example/tmp/*",
        "reason": "temporary previews",
    }
    assert profiles.validate_rules({"rules": [rule]})["rules"] == [rule]
    with pytest.raises(APIError):
        profiles.validate_rules({"rules": [{**rule, "command": "rm -rf /"}]})


def test_scheduler_only_aged_regular_children(home, monkeypatch):
    root = home / "Library/Caches"
    root.mkdir(parents=True)
    old = root / "old"
    old.write_text("old")
    (root / "directory").mkdir()
    (root / "directory/file").write_text("nested")
    (root / "link").symlink_to(old)
    os.link(old, root / "hardlink")
    monkeypatch.setattr(scheduler.time, "time", lambda: time.time_ns() / 1e9 + 9 * 86400)
    assert scheduler.candidates(home) == []  # hard-linked files excluded
    (root / "hardlink").unlink()
    assert [i.path for i in scheduler.candidates(home)] == [str(old)]
    settings.save_settings({"pinned": [str(old)]})
    assert scheduler.candidates(home) == []


def test_launchd_definition_has_no_shell_or_permanent_cleanup():
    value = scheduler.definition(2, 9)
    assert value["StartCalendarInterval"] == {"Weekday": 2, "Hour": 9, "Minute": 0}
    assert value["ProgramArguments"][-2:] == ["care", "scheduled-run"]
    assert not value.get("RunAtLoad") and "/bin/sh" not in value["ProgramArguments"]
    with pytest.raises(APIError):
        scheduler.definition(9, 25)


def test_perceptual_similarity_and_video_dependency_notice(home):
    Image = pytest.importorskip("PIL.Image")
    first = Image.new("RGB", (32, 32))
    first.putdata([(x * 7, y * 7, 40) for y in range(32) for x in range(32)])
    second = first.resize((96, 96))
    assert distance(difference_hash(first), difference_hash(second)) <= 6
    a, b = home / "one.png", home / "two.png"
    first.save(a)
    second.save(b)
    report = scan([(str(a),), (str(b),)])
    assert report["checked"] == 2 and report["pairs"][0]["review_only"]
    assert report["pairs"][0]["score"] >= 90


def test_report_escapes_names_and_omits_paths(home):
    item = Item(
        name="<img onerror=alert(1)>",
        path="/Users/private/secret",
        category="Duplicate Files",
        reason="A & B",
    )
    report = export_html([item], shutil.disk_usage(home))
    assert "<img" not in report and "&lt;img" in report and "/Users/private/secret" not in report
    assert item.path in export_html([item], shutil.disk_usage(home), True)


def service_stub():
    return SimpleNamespace(
        operation=threading.Lock(),
        lock=threading.RLock(),
        closed=False,
        _ready_to_change=lambda: True,
        settings={},
        scanner=SimpleNamespace(installed=[], walk_files=[]),
    )


def test_review_tokens_are_one_use_and_job_failures_release_lock(home, monkeypatch):
    service = service_stub()
    care = Care(service)
    monkeypatch.setattr(scheduler, "configure", Mock(side_effect=OSError("fixture failure")))
    plan = care.prepare({"action": "schedule", "enabled": True})
    with pytest.raises(APIError):
        care.post("/api/care/run", {"token": plan["token"], "confirmed": False})
    care.post("/api/care/run", {"token": plan["token"], "confirmed": True})
    care.thread.join(3)
    assert care.job["error"] == "fixture failure" and not service.operation.locked()
    with pytest.raises(APIError):
        care.post("/api/care/run", {"token": plan["token"], "confirmed": True})


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
        assert "Care center" in pack["messages"]
        assert "Disk Used" in pack["messages"]
        assert "Name" in pack["messages"]
        assert "Size" in pack["messages"]
        assert "Date modified" in pack["messages"]
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


def test_translation_needs_consent_and_sends_only_catalog(home, monkeypatch):
    monkeypatch.setattr(localization, "catalog", lambda: ["Settings", "Restore"])
    with pytest.raises(APIError, match="Confirm"):
        localization.generate("af", "fixture-key")
    with pytest.raises(APIError, match="API key"):
        localization.generate("af", confirmed=True)
    request_seen = []

    class Reply:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self, n):
            return b'{"data":{"translations":[{"translatedText":"Instellings"},{"translatedText":"Herstel"}]}}'

    def open_request(request, timeout):
        request_seen.append(request)
        return Reply()

    monkeypatch.setattr(
        localization.urllib.request,
        "build_opener",
        lambda *args: SimpleNamespace(open=open_request),
    )
    result = localization.generate("af", "fixture-key", confirmed=True)
    assert result["translated"] == 2
    assert request_seen[0].full_url == "https://translation.googleapis.com/language/translate/v2"
    assert "fixture-key" not in (localization.pack_directory() / "af.json").read_text()
    assert localization.load_pack("af")["messages"]["Restore"] == "Herstel"


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


def test_video_hash_compares_three_frames_and_duration(home, monkeypatch):
    from mac_deep_cleaner import media

    pytest.importorskip("PIL.Image")
    paths = [home / "first.mov", home / "second.mov", home / "different.mov"]
    for p in paths:
        p.write_bytes(b"fixture video")
    monkeypatch.setattr(media.shutil, "which", lambda tool: "/fixture/" + tool)
    monkeypatch.setattr(
        media, "video_hash", lambda path: (15 if path.endswith("different.mov") else 60, [1, 2, 3])
    )
    result = media.scan([(str(p),) for p in paths])
    assert len(result["pairs"]) == 1
    assert result["pairs"][0]["kind"] == "video"
    assert result["pairs"][0]["score"] == 100


def test_slimming_only_modifies_the_copy(home, monkeypatch):
    from mac_deep_cleaner import review_tools

    source = home / "Applications/Example.app"
    for language in ["Base", "en", "fr", "hi"]:
        folder = source / "Contents/Resources" / (language + ".lproj")
        folder.mkdir(parents=True)
        (folder / "text").write_text(language)
    (home / "Downloads").mkdir()
    record = {
        "path": str(source),
        "identity": common.fingerprint(str(source)),
        "size": common.dir_size(str(source)),
    }
    commands = []

    def run(argv, **kwargs):
        commands.append(argv)
        if argv[0] == "/usr/bin/ditto":
            shutil.copytree(argv[1], argv[2])
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(review_tools.sys, "platform", "darwin")
    monkeypatch.setattr(review_tools.subprocess, "run", run)
    result = review_tools.slim_copy(record, ["hi"])
    copy = Path(result["path"])
    assert (source / "Contents/Resources/fr.lproj/text").read_text() == "fr"
    assert not (copy / "Contents/Resources/fr.lproj").exists()
    for language in ["Base", "en", "hi"]:
        assert (copy / "Contents/Resources" / (language + ".lproj") / "text").exists()
    assert commands[-1][0] == "/usr/bin/codesign" and commands[-1][-1] == str(copy)


def test_startup_change_revalidates_identity_before_command(monkeypatch):
    from mac_deep_cleaner import review_tools

    item = {
        "path": "/fixture/agent.plist",
        "identity": (1, 2),
        "editable": True,
        "label": "org.example.sync",
    }
    monkeypatch.setattr(review_tools.sys, "platform", "darwin")
    monkeypatch.setattr(review_tools, "startup_items", lambda: [{**item, "identity": (3, 4)}])
    command = Mock()
    monkeypatch.setattr(review_tools.subprocess, "run", command)
    with pytest.raises(APIError, match="changed"):
        review_tools.startup_change(item, False)
    command.assert_not_called()
