"""Local UI fixture: no scanner, real files, or macOS maintenance commands are run."""
import sys
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_homebrew import FakeBrewRunner, manager
from test_toolkit import FakeRunner

from mac_deep_cleaner.server import LocalServer
from mac_deep_cleaner.service import CleanerService
from mac_deep_cleaner.system_tools import SHORTCUTS, catalogue
from mac_deep_cleaner.toolkit import Toolkit

service = CleanerService(SimpleNamespace(view='optimize'), {'mode':'normal','min_mb':10,'pinned':[]})
service.scanner = SimpleNamespace(lock=threading.RLock(), items=[], done=True, error='', progress='Complete')
service.toolkit = Toolkit(service.operation, runner=FakeRunner())
service.toolkit.brew = manager(FakeBrewRunner())
service.toolkit.health = lambda: {
    'supported':True, 'checked_at':1793412000, 'os':'27.0.1', 'memory_total':16_000_000_000,
    'pressure':'Normal','swap':'256.0M','battery':'Now drawing from AC Power\nBattery: 82%; charging',
    'uptime':'Up 2 days, 3:14 · load averages: 1.4 1.2 1.1','spotlight':'Indexing enabled.',
    'disk':{'total':500_000_000_000,'free':300_000_000_000,'used':200_000_000_000},
    'processes':[{'pid':200,'cpu':14.2,'memory':450_000_000,'name':'Xcode'},
                 {'pid':300,'cpu':3.4,'memory':125_000_000,'name':'Safari'}],
    'launch_agents':[{'name':'com.example.background','location':'~/Library/LaunchAgents'}],
    'tools':[{**t,'available':True} for t in catalogue()], 'warnings':[],
    'shortcuts':[{'id':k,'title':v[0]} for k,v in SHORTCUTS.items()]}
with patch('mac_deep_cleaner.disks.IS_MAC', True):
    server = LocalServer(service)
    Path('/tmp/mdc-ui-check').mkdir(parents=True, exist_ok=True)
    Path('/tmp/mdc-ui-check/launch-url').write_text(server.url)
    print('Fixture server ready', flush=True)
    try: server.serve_forever()
    finally: server.server_close()
