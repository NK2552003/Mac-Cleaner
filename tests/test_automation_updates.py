"""Unattended cleanup tests use disposable files; release checks use fake HTTP."""
import io
import json
import os
import time
import urllib.error
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from mac_deep_cleaner import automation, cleanup, common, scanner, settings, updates
from mac_deep_cleaner.errors import APIError
from mac_deep_cleaner.history import History
from mac_deep_cleaner.service import CleanerService


@pytest.fixture
def service(tmp_path, monkeypatch):
    home = tmp_path.resolve()
    monkeypatch.setattr(Path, 'home', classmethod(lambda cls: home))
    for module in (automation, cleanup, common, scanner):
        monkeypatch.setattr(module, 'HOME', str(home))
    monkeypatch.setattr(settings, 'SETTINGS_DIR', str(home / 'settings'))
    monkeypatch.setattr(settings, 'SETTINGS_FILE', str(home / 'settings/settings.json'))
    monkeypatch.setattr(automation.subprocess, 'run', lambda *a, **k: SimpleNamespace(stdout=''))
    service = CleanerService(SimpleNamespace(), {})
    service.scanner = scanner.Scanner(quiet=True)
    service.scanner.done = True
    service.scan_id = 'fixture'
    seeds = []
    def factory(**kwargs):
        result = scanner.Scanner(**kwargs)
        result.items = list(seeds)
        result.load_apps = lambda: None
        result.scan_specs = lambda: None
        result.scan_app_caches = lambda: None
        return result
    service.scanner_factory = factory
    service.seeds = seeds
    yield service
    service.close()


def candidate(service, relative='Library/Caches/org.example.idle', **values):
    path = Path(automation.HOME) / relative
    path.mkdir(parents=True, exist_ok=True)
    (path / 'data').write_text('recover this cache')
    old = time.time() - 8 * 86400
    for child in (path / 'data', path):
        os.utime(child, (old, old))
    item = service.scanner.add(path=str(path), name=path.name, size=4096, **values)
    service.seeds.append(item)
    return path, item


def run(service):
    service.post('/api/automation/clean', {})
    service.automation.worker.join(5)
    assert not service.automation.worker.is_alive()
    assert not service.operation.locked()
    return service.automation.report()


def test_one_click_trashes_only_safe_inactive_cache_and_restores(service):
    path, _ = candidate(service)
    personal, _ = candidate(service, 'Documents/valuable')
    recent, _ = candidate(service, 'Library/Caches/recent')
    (recent / 'data').write_text('changed child with old parent')
    risky, _ = candidate(service, 'Library/Caches/risky', safety='caution')
    webkit, _ = candidate(service, 'Library/Caches/WebKit')
    protected, _ = candidate(service, 'Library/Caches/com.apple.example')
    result = run(service)
    assert not result['error'] and not result['result']['fails']
    assert not path.exists()
    assert all(p.exists() for p in (personal, recent, risky, webkit, protected))
    history = History(Path(automation.HOME))
    entries = history.records()
    assert len(entries) == 1
    history.restore(entries[0]['id'])
    assert (path / 'data').read_text() == 'recover this cache'


def test_exclusions_fingerprints_and_running_apps_are_rechecked(service, monkeypatch):
    path, item = candidate(service)
    service.scanner.pinned.add(str(path))
    assert run(service)['error']
    assert path.exists()
    service.scanner.pinned.clear()
    os.utime(path, (1, 1))
    assert run(service)['result']['fails']
    item.fingerprint = common.fingerprint(str(path))
    service.scanner_factory = lambda **kw: SimpleNamespace(
        items=[item], installed=[('Example', 'org.example.idle', '/Applications/Example.app')],
        load_apps=lambda:None, scan_specs=lambda:None, scan_app_caches=lambda:None, close=lambda:None, error='')
    monkeypatch.setattr(automation.subprocess, 'run', lambda *a, **k: SimpleNamespace(stdout='/Applications/Example.app/Contents/MacOS/Example'))
    assert not run(service)['result']['results']
    assert path.exists()


def test_automation_defaults_validation_schedule_busy_deferral_and_disable(service):
    assert not service.settings['automation_enabled']
    for invalid in (0, 721, 1.5, True, '24'):
        with pytest.raises(APIError):
            service.post('/api/settings', {'automation_hours': invalid})
    for key in ('automation_enabled','automatic_updates','notifications'):
        with pytest.raises(APIError):
            service.post('/api/settings', {key:'true'})
    service.post('/api/settings', {'automation_enabled':True,'automation_hours':24})
    due = service.settings['automation_next_run']
    assert 23 * 3600 < due - time.time() <= 24 * 3600
    assert settings.load_settings()['automation_next_run'] == due
    service.automation.tick(due - 1)
    assert service.automation.worker is None
    service.operation.acquire()
    service.automation.tick(due + 1)
    assert service.settings['automation_next_run'] == due
    service.operation.release()
    service.automation.tick(due + 1)
    service.automation.worker.join(5)
    assert service.settings['automation_next_run'] == due + 1 + 86400
    service.post('/api/settings', {'automation_enabled':False})
    service.automation.start = Mock(side_effect=AssertionError('Disabled schedule ran'))
    service.automation.tick(due + 200000)


def test_failed_process_inventory_never_deletes_and_releases_lock(service, monkeypatch):
    path, _ = candidate(service)
    monkeypatch.setattr(automation.subprocess, 'run', Mock(side_effect=OSError('unavailable')))
    assert run(service)['error'] == 'unavailable'
    assert path.exists()


def test_quit_defers_during_cleanup_and_prevents_future_scheduled_runs(service):
    service.operation.acquire()
    assert service.post('/api/prepare-quit', {}) == {'can_quit':False}
    service.operation.release()
    assert service.post('/api/prepare-quit', {}) == {'can_quit':True}
    with pytest.raises(APIError):
        service.post('/api/automation/clean', {})
    assert service.closed and service.automation.stop.is_set()


def test_notifications_are_opt_in_and_bounded(service):
    service.notify('Cleanup', 'Completed')
    assert not service.background_status()['events']
    service.post('/api/settings', {'notifications':True})
    for _ in range(25):
        service.notify('Cleanup', 'Completed')
    events = service.background_status()['events']
    assert len(events) == 20 and events[-1]['id'] == 25


@pytest.mark.parametrize('tag,available', [('v3.6.1',True),('v3.10.0',True),('3.6.0',False),('v3.5.0',False)])
def test_github_version_comparison_and_canonical_release_link(monkeypatch, tag, available):
    monkeypatch.setattr(updates, '__version__', '3.6.0')
    payload = {'tag_name':tag,'html_url':'https://attacker.invalid', 'draft':False, 'prerelease':False}
    opener = Mock()
    opener.open.return_value = io.BytesIO(json.dumps(payload).encode())
    monkeypatch.setattr(updates.urllib.request, 'build_opener', lambda *a:opener)
    checker = updates.Updates()
    checker.check()
    result = checker.report()
    assert result['available'] is available
    assert result['url'] == updates.RELEASES + '/tag/' + tag
    assert opener.open.call_args[0][0].full_url == updates.API


@pytest.mark.parametrize('response', [b'{}', b'{', b'x' * 1000001, b'{"tag_name":"v4.0.0-rc1"}', b'{"tag_name":"v4.0.0","prerelease":true}'])
def test_release_errors_do_not_claim_up_to_date(monkeypatch, response):
    opener = Mock()
    opener.open.return_value = io.BytesIO(response)
    monkeypatch.setattr(updates.urllib.request, 'build_opener', lambda *a:opener)
    checker = updates.Updates()
    checker.check()
    assert checker.report()['error'] and not checker.report()['available']


def test_rate_limit_and_no_release_are_actionable(monkeypatch):
    for status in (403, 404, 429):
        opener = Mock()
        opener.open.side_effect = urllib.error.HTTPError(updates.API, status, '', {}, io.BytesIO())
        monkeypatch.setattr(updates.urllib.request, 'build_opener', lambda *a:opener)
        checker = updates.Updates()
        checker.check()
        assert checker.report()['error']
        assert not checker.report()['checking']
