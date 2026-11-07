"""Review revalidation and copy-only transformations with isolated filesystem data."""
import plistlib
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from mac_deep_cleaner import review_tools, scheduler
from mac_deep_cleaner.common import fingerprint
from mac_deep_cleaner.errors import APIError


def test_startup_change_revalidates_identity_before_launchctl(tmp_path, monkeypatch):
    root = tmp_path.resolve()
    monkeypatch.setattr(Path, 'home', classmethod(lambda cls: root))
    monkeypatch.setattr(review_tools.sys, 'platform', 'darwin')
    path = root / 'Library/LaunchAgents/test.plist'; path.parent.mkdir(parents=True)
    path.write_bytes(plistlib.dumps({'Label':'org.example.startup','Program':'/example/tool'}))
    item = next(i for i in review_tools.startup_items(root) if i['path']==str(path))
    calls = []
    monkeypatch.setattr(review_tools.subprocess, 'run', lambda args, **kw:calls.append(args))
    path.write_bytes(plistlib.dumps({'Label':'org.example.changed','Program':'/different/tool'}))
    with pytest.raises(APIError, match='changed'):
        review_tools.startup_change(item, False)
    assert not calls
    current = next(i for i in review_tools.startup_items(root) if i['path']==str(path))
    review_tools.startup_change(current, False)
    assert calls[0][:2] == ['/bin/launchctl', 'disable']
    assert calls[0][2].endswith('/org.example.changed')


def test_slimming_only_changes_copy_and_keeps_requested_language_variants(tmp_path, monkeypatch):
    root = tmp_path.resolve()
    monkeypatch.setattr(Path, 'home', classmethod(lambda cls: root))
    monkeypatch.setattr(review_tools.sys, 'platform', 'darwin')
    source = root / 'Example.app'; resources = source / 'Contents/Resources'
    for lang in ('Base','English','en_GB','fr','French','fr_CA','zh_Hans','zh_TW','de'):
        folder=resources/(lang+'.lproj');folder.mkdir(parents=True)
        (folder/'text').write_text(lang)
    (root/'Downloads').mkdir()
    commands=[]
    def run(args, **kwargs):
        commands.append(args)
        if args[0]=='/usr/bin/ditto': shutil.copytree(args[1],args[2],symlinks=True)
        return SimpleNamespace(returncode=0,stdout='',stderr='')
    monkeypatch.setattr(review_tools.subprocess,'run',run)
    original={str(p.relative_to(source)):p.read_bytes() for p in source.rglob('*') if p.is_file()}
    result=review_tools.slim_copy({'path':str(source),'identity':fingerprint(str(source)),'size':4096},['fr-CA','zh-CN'])
    copy=Path(result['path'])/'Contents/Resources'
    assert not (copy/'de.lproj').exists()
    assert all((copy/(lang+'.lproj/text')).exists() for lang in ('Base','English','en_GB','fr','French','fr_CA','zh_Hans','zh_TW'))
    assert original == {str(p.relative_to(source)):p.read_bytes() for p in source.rglob('*') if p.is_file()}
    assert commands[-1][:4]==['/usr/bin/codesign','--force','--deep','--sign']
    assert commands[-1][-1]==result['path']


def test_corrupt_schedule_does_not_break_care_status(tmp_path, monkeypatch):
    path=tmp_path/'weekly.plist';path.write_bytes(plistlib.dumps(['invalid']))
    monkeypatch.setattr(scheduler,'agent_path',lambda:path)
    assert scheduler.status()['enabled'] is False


def test_failed_schedule_install_removes_only_its_own_definition(tmp_path, monkeypatch):
    root=tmp_path.resolve()
    monkeypatch.setattr(Path,'home',classmethod(lambda cls:root))
    monkeypatch.setattr(scheduler.sys,'platform','darwin')
    path=scheduler.agent_path();path.parent.mkdir(parents=True)
    unrelated=path.parent/'other.plist';unrelated.write_bytes(b'keep')
    def fail(*args,**kwargs): raise OSError('fixture bootstrap failure')
    monkeypatch.setattr(scheduler.subprocess,'run',fail)
    with pytest.raises(APIError,match='could not load'):
        scheduler.configure(True,2,14)
    assert not path.exists() and unrelated.read_bytes()==b'keep'


def test_schedule_lock_refuses_symlink(tmp_path, monkeypatch):
    root=tmp_path.resolve()
    monkeypatch.setattr(Path,'home',classmethod(lambda cls:root))
    directory=root/'Library/Application Support/Mac Deep Cleaner';directory.mkdir(parents=True)
    target=root/'outside';target.write_text('keep')
    (directory/'scheduled.lock').symlink_to(target)
    with pytest.raises(OSError):scheduler.run_scheduled(preview=True)
    assert target.read_text()=='keep'
