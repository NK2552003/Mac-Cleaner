"""Actual deletion/restore tests, confined to disposable temporary directories."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from mac_deep_cleaner import applications, cleanup, common, scanner, settings
from mac_deep_cleaner.applications import AppAnalyzer, app_items
from mac_deep_cleaner.errors import APIError
from mac_deep_cleaner.history import History
from mac_deep_cleaner.models import Item
from mac_deep_cleaner.service import CleanerService


@pytest.fixture
def home(tmp_path, monkeypatch):
    root = tmp_path.resolve()
    monkeypatch.setattr(Path, 'home', classmethod(lambda cls: root))
    for module in (cleanup, common, scanner, applications):
        monkeypatch.setattr(module, 'HOME', str(root))
    monkeypatch.setattr(applications, 'expand', lambda path: path.replace('~', str(root), 1))
    monkeypatch.setattr(cleanup, 'FORBIDDEN', cleanup.FORBIDDEN | {str(root)} |
                        {str(root / name) for name in ('Documents', 'Library', 'Downloads')})
    monkeypatch.setattr(settings, 'SETTINGS_DIR', str(root / 'settings'))
    monkeypatch.setattr(settings, 'SETTINGS_FILE', str(root / 'settings/settings.json'))
    return root


def item(path, **kwargs):
    return Item(name=path.name, path=str(path), size=common.dir_size(str(path)),
                selected=True, fingerprint=common.fingerprint(str(path)), **kwargs)


@pytest.fixture
def service(home):
    service = CleanerService(SimpleNamespace(), {'mode':'normal','min_mb':0,'pinned':[]})
    service.scanner = scanner.Scanner(quiet=True)
    service.scanner.done = True
    service.scan_id = 'disposable-cleanup'
    yield service
    service.close()


def request(service, ids, **kwargs):
    return service.post('/api/clean', {'scan_id':service.scan_id, 'revision':service.revision,
                                     'ids':ids, **kwargs})


@pytest.mark.parametrize('directory', [False, True])
def test_trash_restore_preserves_exact_bytes_and_siblings(home, directory):
    source = home / 'Résumé 🗂.data'
    payload = bytes(range(256)) * 41
    if directory:
        source.mkdir()
        (source / 'nested').mkdir()
        (source / 'nested/contents').write_bytes(payload)
    else:
        source.write_bytes(payload)
    sibling = home / 'untouched'; sibling.write_bytes(payload[::-1])
    expected = item(source)
    processed, _, failures = cleanup.execute([expected], log=lambda _:None)
    assert processed == expected.size and not failures and not source.exists()
    entry = History(home).records()[0]
    assert entry['available'] and Path(entry['trash']).exists()
    History(home).restore(entry['id'])
    assert (source / 'nested/contents' if directory else source).read_bytes() == payload
    assert sibling.read_bytes() == payload[::-1]


def test_permanent_directory_removal_does_not_follow_child_symlinks(home):
    source = home / 'cache'; source.mkdir()
    outside = home / 'keep'; outside.write_text('precious')
    (source / 'link').symlink_to(outside)
    (source / 'temporary').write_text('discard')
    _, _, failures = cleanup.execute([item(source)], permanent=True, log=lambda _:None)
    assert not failures and not source.exists() and outside.read_text() == 'precious'
    assert not History(home).records()


@pytest.mark.parametrize('target', ['.', 'Documents', 'Library', 'Downloads'])
def test_protected_roots_cannot_be_deleted(home, target):
    source = home / target; source.mkdir(exist_ok=True)
    assert not cleanup.hard_delete(str(source))[0]
    assert source.is_dir()


def test_dry_run_has_no_deletions_selection_changes_or_double_counting(home):
    parent = home / 'cache'; parent.mkdir()
    child = parent / 'file'; child.write_bytes(b'x' * 8192)
    selection = [item(parent), item(child)]
    processed, _, failures = cleanup.execute(selection, dry_run=True, log=lambda _:None)
    assert not failures and processed == selection[0].size
    assert child.exists() and all(i.selected for i in selection)
    assert not History(home).records()


def test_parent_child_removal_counts_once_and_has_one_restore(home):
    parent = home / 'cache'; parent.mkdir()
    child = parent / 'file'; child.write_bytes(b'x' * 8192)
    selection = [item(parent), item(child)]
    processed, _, failures = cleanup.execute(selection, log=lambda _:None)
    assert not failures and processed == selection[0].size
    entries = History(home).records()
    assert len(entries) == 1
    History(home).restore(entries[0]['id'])
    assert child.read_bytes() == b'x' * 8192


def test_changed_file_fails_but_other_selection_completes(home, service):
    good, changed = home / 'good', home / 'changed'
    good.write_text('good'); changed.write_text('before')
    service.scanner.items = [item(good,id=1), item(changed,id=2)]
    changed.write_text('after scan: preserve this')
    result = request(service, [1,2])
    assert result['fails'] and not good.exists() and changed.exists()
    assert [i.id for i in service.scanner.items] == [2]
    assert len(History(home).records()) == 1
    assert not service.operation.locked()


def test_permanent_deletion_requires_explicit_boolean_ack(home, service):
    path = home / 'file'; path.write_text('keep')
    service.scanner.items = [item(path,id=1)]
    for values in ({'permanent':True}, {'permanent':True,'permanent_ack':'true'}):
        with pytest.raises(APIError):
            request(service,[1],**values)
        assert path.exists()
    assert not request(service,[1],permanent=True,permanent_ack=True)['fails']
    assert not path.exists()


def test_safe_selection_never_includes_irreversible_or_cloud_operations():
    normal = Item(action='trash')
    special = [Item(action=action) for action in ('empty','cmd','root','evict')]
    cleanup.select_level([normal,*special], 'safe')
    assert normal.selected and not any(i.selected for i in special)


def test_empty_trash_requires_confirmation_and_cannot_mix_with_trash_moves(home, service):
    trash = home / '.Trash'; trash.mkdir()
    (trash / 'discard').write_text('discard')
    other = home / 'other'; other.write_text('keep')
    service.scanner.items = [item(trash,id=1,action='empty'), item(other,id=2)]
    with pytest.raises(APIError): request(service,[1])
    with pytest.raises(APIError): request(service,[1,2],permanent_ack=True)
    assert (trash / 'discard').exists() and other.exists()
    assert not request(service,[1],permanent_ack=True)['fails']
    assert trash.exists() and not list(trash.iterdir()) and other.exists()


def test_duplicate_requires_unchanged_matching_keeper_and_never_removes_original(home):
    original, copy = home / 'original', home / 'copy'
    original.write_bytes(b'same'); copy.write_bytes(b'same')
    candidate = item(copy,keep=str(original),keeper_fingerprint=common.fingerprint(str(original)))
    original.write_bytes(b'changed')
    assert cleanup.execute([candidate], log=lambda _:None)[2]
    assert original.exists() and copy.exists()
    original.write_bytes(b'same')
    candidate.keeper_fingerprint = common.fingerprint(str(original))
    assert not cleanup.execute([candidate], log=lambda _:None)[2]
    assert original.read_bytes() == b'same' and not copy.exists()


def test_excluded_child_prevents_parent_selection_in_all_scan_consumers(home):
    parent = home / 'cache'; parent.mkdir()
    pinned = parent / 'keep'; pinned.write_text('keep')
    sc = scanner.Scanner(quiet=True,pinned=[str(pinned)])
    try:
        assert sc.add(path=str(parent),name='Cache') is None
        assert sc.add(path=str(pinned),name='Keep') is None
    finally: sc.close()


def test_interrupted_restore_before_rename_remains_retryable(home):
    path = home / 'file'; path.write_text('recover')
    history = History(home); identifier = history.move(str(path))
    with history.connect() as db:
        db.execute("UPDATE moves SET status='restoring' WHERE id=?", (identifier,))
    assert history.records()[0]['available']
    history.restore(identifier)
    assert path.read_text() == 'recover'


def test_post_move_journal_failure_does_not_report_a_successful_move_as_failure(home, monkeypatch):
    path = home / 'file'; path.write_text('recover')
    from contextlib import contextmanager
    real = History.connect
    calls = 0
    @contextmanager
    def broken_final_write(self):
        nonlocal calls
        calls += 1
        if calls == 2: raise OSError('temporary journal outage')
        with real(self) as db: yield db
    with monkeypatch.context() as patcher:
        patcher.setattr(History,'connect',broken_final_write)
        assert cleanup.to_trash(str(path))[0]
    entry = History(home).records()[0]
    assert entry['available'] and not path.exists()
    History(home).restore(entry['id'])
    assert path.read_text() == 'recover'


def test_clear_app_caches_preserves_webkit_and_http_storage(home, service):
    lib = home / 'Library'; bid = 'org.example.editor'
    for folder in ('Caches','WebKit','HTTPStorages'):
        path = lib / folder / bid; path.mkdir(parents=True)
        (path / 'data').write_text(folder)
    app = home / 'Applications/Editor.app'; app.mkdir(parents=True)
    (app / 'binary').write_text('app')
    sc = SimpleNamespace(app_meta={},running=set(),last_used=lambda _:0)
    analyzer = AppAnalyzer(sc)
    record = analyzer.analyze_one(('Editor',bid,str(app)),analyzer._index(),{bid})
    result = cleanup.execute(app_items(record, 'caches'),log=lambda _:None)
    assert not result[2] and not (lib / 'Caches' / bid).exists()
    assert (lib / 'WebKit' / bid / 'data').read_text() == 'WebKit'
    assert (lib / 'HTTPStorages' / bid / 'data').read_text() == 'HTTPStorages'
    assert app.exists()


def test_zero_byte_removal_has_successful_result_even_without_reclaimed_bytes(home, service):
    path=home/'empty';path.touch()
    service.scanner.items=[item(path,id=1)]
    result=request(service,[1])
    assert result['processed_bytes']==0 and result['results'][0]['ok']
    assert not path.exists() and not result['fails']


def test_permission_gaps_are_reported_without_hiding_other_results(home, monkeypatch):
    denied=home/'Documents';denied.mkdir()
    accessible=home/'file';accessible.write_bytes(b'x'*8192)
    real=scanner.os.scandir
    def scandir(path):
        if str(path)==str(denied): raise PermissionError('fixture denial')
        return real(path)
    monkeypatch.setattr(scanner.os,'scandir',scandir)
    sc=scanner.Scanner(quiet=True,large_mb=0,dup_min_mb=0)
    try:
        result=sc.walk_home()
        assert sc.warnings==[str(denied)]
        assert str(accessible) in [f[0] for f in result['files']]
    finally:sc.close()


@pytest.mark.parametrize('override', [
    {'scan_id':'stale'}, {'revision':-1}, {'revision':True}, {'ids':[999]}, {'ids':[True]},
])
def test_invalid_or_stale_request_never_changes_files(home, service, override):
    path=home/'keep';path.write_text('unchanged')
    service.scanner.items=[item(path,id=1)]
    body={'scan_id':service.scan_id,'revision':service.revision,'ids':[1],**override}
    with pytest.raises(APIError):service.post('/api/clean',body)
    assert path.read_text()=='unchanged' and not service.operation.locked()


def test_active_operation_blocks_cleanup(home, service):
    path=home/'keep';path.write_text('unchanged')
    service.scanner.items=[item(path,id=1)]
    with service.operation, pytest.raises(APIError,match='Another operation'):
        request(service,[1])
    assert path.exists()


def test_unsupported_command_cannot_execute(home, monkeypatch):
    def unexpected(*args,**kwargs):raise AssertionError('Unexpected external command')
    monkeypatch.setattr(cleanup.subprocess,'run',unexpected)
    _,roots,failures=cleanup.execute([Item(action='cmd',cmd='rm -rf /',selected=True)],log=lambda _:None)
    assert failures and not roots


def test_empty_trash_unlinks_internal_links_without_touching_destinations(home):
    trash=home/'.Trash';trash.mkdir()
    outside=home/'keep';outside.write_text('precious')
    (trash/'link').symlink_to(outside)
    assert cleanup.empty_dir(str(trash))[0]
    assert outside.read_text()=='precious' and not list(trash.iterdir())
