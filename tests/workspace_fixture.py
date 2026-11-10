"""Integrated fixture: every operation stays in temporary data or fake runners."""
import copy
import os
import runpy
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_homebrew import FakeBrewRunner, manager
from test_toolkit import FakeRunner

from mac_deep_cleaner.common import fingerprint
from mac_deep_cleaner.models import AppInfo, AppPart
from mac_deep_cleaner.scanner import Scanner
from mac_deep_cleaner.system_tools import SHORTCUTS, catalogue
from mac_deep_cleaner.toolkit import Toolkit


def configure(service, root, stack):
    """Populate a temporary dashboard with fake tools, apps, disks, and cleanup data."""
    stack.enter_context(patch('mac_deep_cleaner.automation.HOME', str(root)))
    service.args = SimpleNamespace(view='clean', large_mb=100, old_days=90, dup_min_mb=1)
    service.toolkit = Toolkit(service.operation, runner=FakeRunner())
    service.toolkit.brew = manager(FakeBrewRunner())
    stack.enter_context(patch('mac_deep_cleaner.disks.IS_MAC', True))
    stack.enter_context(patch('mac_deep_cleaner.service.reveal', return_value=True))
    service.toolkit.health = lambda: {
        'supported':True, 'checked_at':time.time(), 'os':'27.0.1', 'memory_total':16_000_000_000,
        'pressure':'Normal', 'swap':'256 MB', 'battery':'Battery: 82%; charging',
        'uptime':'2 days', 'spotlight':'Indexing enabled.',
        'disk':{'total':500_000_000_000,'free':300_000_000_000,'used':200_000_000_000},
        'processes':[{'pid':200,'cpu':14.2,'memory':450_000_000,'name':'Example Editor'}],
        'launch_agents':[], 'tools':[{**t,'available':True} for t in catalogue()], 'warnings':[],
        'shortcuts':[{'id':k,'title':v[0]} for k,v in SHORTCUTS.items()]}
    original = root / 'Original.txt'
    duplicate = root / 'Copy.txt'
    original.write_text('sample content')
    duplicate.write_text('sample content')
    service.scanner.add(name='Copy.txt', path=str(duplicate), size=20_000_000,
                        category='Duplicate Files', safety='safe', keep=str(original), set_id='fixture-duplicates')
    app = root / 'Example Editor.app'
    app.mkdir()
    (app / 'Contents').mkdir()
    (app / 'Contents/executable').write_bytes(b'disposable application fixture')
    cache = root / 'Library/Caches/org.example.editor'
    cache.mkdir(parents=True)
    (cache / 'preview').write_text('fixture')
    record = AppInfo(id=0, name='Example Editor', path=str(app), size=900_000_000,
                     version='1.2', bundle_id='org.example.editor', last_used=time.time(),
                     fingerprint=fingerprint(str(app)),
                     parts=[AppPart('Cache','cache',str(cache),50_000_000,fingerprint(str(cache)))])
    if '--deletion' in sys.argv:
        trash = root / '.Trash'
        service.scanner.add(name='Trash', path=str(trash), size=4096,
                            category='Trash', safety='caution', action='empty', manual=True)
    service.analyzer = SimpleNamespace(done=True, progress='Complete', total=1, error='', apps=[record])
    service.apps_id = 'fixture-apps'
    service.analyzer_factory = lambda scanner: SimpleNamespace(done=True, progress='Complete', total=1,
                                                                error='', apps=[record], run=lambda:None)
    service.scanner.apps_ready.set()
    idle = root / 'Library/Caches/org.example.idle'
    idle.mkdir(parents=True)
    (idle / 'data').write_text('disposable automation fixture')
    for path in (idle / 'data', idle):
        os.utime(path, (time.time() - 8 * 86400,) * 2)
    service.scanner.add(name='Idle cache', path=str(idle), size=4096, category='App Caches', safety='safe')
    seed_items, seed_files = copy.deepcopy(service.scanner.items), list(service.scanner.walk_files)

    def scanner_factory(*args, **kwargs):
        """Create repeatable scans from disposable fixture items without host discovery."""
        scanner = Scanner(quiet=True)
        scanner.items = copy.deepcopy(seed_items)
        scanner.walk_files = list(seed_files)
        def run():
            scanner.done = True
            scanner.progress = 'Complete'
            scanner.apps_ready.set()
        scanner.run = run
        scanner.load_apps = lambda:None
        scanner.scan_specs = lambda:None
        scanner.scan_app_caches = lambda:None
        return scanner
    service.scanner_factory = scanner_factory


if __name__ == '__main__':
    sys.argv.append('--workspace')
    runpy.run_path(str(Path(__file__).with_name('storage_fixture.py')), run_name='__main__')
