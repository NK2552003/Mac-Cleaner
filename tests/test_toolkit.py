"""Safety and transport tests. All macOS commands are replaced by a fake runner."""
import http.client
import json
import subprocess
import sys
import threading
import time
import unittest
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

from mac_deep_cleaner.disks import DISKUTIL, disk_plan, inventory
from mac_deep_cleaner.errors import APIError
from mac_deep_cleaner.server import LocalServer
from mac_deep_cleaner.service import CleanerService
from mac_deep_cleaner.system_tools import CommandRunner, parse_processes, tool_plan
from mac_deep_cleaner.toolkit import Toolkit


class FakeRunner:
    def __init__(self):
        self.commands = []
        self.backups = {}
        self.fail_info = None
        self.fail_command = False
        self.hold = None
        self.infos = {}
        self.physical = []
        self.nodes = []
        self.containers = []
        for disk, container, internal, name in [('disk0', 'disk1', True, 'Macintosh HD'),
                                               ('disk8', 'disk9', False, 'Work SSD')]:
            part, vol = disk + 's2', container + 's1'
            mount = '/System/Volumes/Data' if internal else '/Volumes/' + name
            self.infos[disk] = {'DeviceIdentifier': disk, 'WholeDisk': True, 'Internal': internal,
                'TotalSize': 500_000_000_000, 'Writable': True, 'MediaName': name,
                'DeviceTreePath': '/devices/' + disk, 'BusProtocol': 'Apple Fabric' if internal else 'USB'}
            self.infos[part] = {**self.infos[disk], 'DeviceIdentifier': part, 'WholeDisk': False,
                'DiskUUID': 'partition-' + disk}
            self.infos[container] = {**self.infos[disk], 'DeviceIdentifier': container,
                'Content': 'Apple_APFS_Container'}
            self.infos[vol] = {**self.infos[part], 'DeviceIdentifier': vol, 'VolumeName': name,
                'VolumeUUID': 'volume-' + disk, 'FilesystemType': 'apfs',
                'FilesystemUserVisibleName': 'APFS', 'CapacityInUse': 180_000_000_000,
                'MountPoint': mount, 'Bootable': internal}
            self.physical.append({'DeviceIdentifier': disk})
            self.nodes.extend([{'DeviceIdentifier': disk, 'Partitions': [{'DeviceIdentifier': part}]},
                {'DeviceIdentifier': container, 'APFSVolumes': [{'DeviceIdentifier': vol}]}])
            self.containers.append({'ContainerReference': container, 'APFSContainerUUID': 'container-' + disk,
                'CapacityCeiling': 500_000_000_000, 'CapacityFree': 300_000_000_000,
                'PhysicalStores': [{'DeviceIdentifier': part}],
                'Volumes': [{'DeviceIdentifier': vol, 'Roles': ['Data'] if internal else []}]})
        self.infos['disk1s2s1'] = {**self.infos['disk1s1'], 'DeviceIdentifier': 'disk1s2s1',
            'VolumeName': 'Macintosh HD', 'VolumeUUID': 'snapshot-1', 'APFSSnapshot': True,
            'MountPoint': '/', 'Writable': False, 'CapacityInUse': 13_660_000_000}
        self.nodes[1]['APFSVolumes'].append({'DeviceIdentifier': 'disk1s2s1'})

    def plist(self, argv):
        if argv == [DISKUTIL, 'list', '-plist']:
            return {'AllDisksAndPartitions': deepcopy(self.nodes)}
        if argv == [DISKUTIL, 'list', '-plist', 'physical']:
            return {'AllDisksAndPartitions': deepcopy(self.physical)}
        if argv == [DISKUTIL, 'apfs', 'list', '-plist']:
            return {'Containers': deepcopy(self.containers)}
        if argv == ['/usr/bin/tmutil', 'destinationinfo', '-X']:
            if self.backups is None:
                raise APIError(400, 'denied')
            return deepcopy(self.backups)
        if argv[:3] == [DISKUTIL, 'info', '-plist']:
            key = {'/': 'disk1s2s1', '/dev/disk1s1': 'disk1s1'}.get(argv[3], argv[3])
            if key == self.fail_info:
                raise APIError(400, 'disk disappeared')
            return deepcopy(self.infos[key])
        raise AssertionError(f'Unexpected read: {argv}')

    def text(self, argv, timeout=20):
        if argv[:2] == ['/bin/df', '-P']:
            return 'Filesystem 1024-blocks Used Available Capacity Mounted on\n/dev/disk1s1 500 200 300 40% /System/Volumes/Data'
        self.commands.append(argv)
        if self.hold:
            self.hold.wait(2)
        if self.fail_command:
            raise APIError(400, 'Permission denied by macOS')
        return 'Completed fixture operation'

    def run(self, argv, timeout=20):
        return self.text(argv, timeout).encode()


def wait_job(toolkit):
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        job = toolkit.history()['jobs'][-1]
        if job['status'] != 'running':
            return job
        time.sleep(0.005)
    raise AssertionError('Job did not finish')


class DiskSafetyTest(unittest.TestCase):
    def setUp(self):
        self.mac = patch('mac_deep_cleaner.disks.IS_MAC', True)
        self.mac.start()
        self.addCleanup(self.mac.stop)
        self.runner = FakeRunner()

    def report(self):
        return inventory(self.runner)

    def plan(self, **fields):
        return disk_plan({'action': 'erase', 'target': 'disk8', 'format': 'APFS', 'name': 'New Drive', **fields}, self.report())

    def test_startup_internal_and_snapshot_are_protected(self):
        report = self.report()
        self.assertEqual(report['startup_id'], 'disk1s2s1')
        for d in report['devices']:
            if d['internal']:
                self.assertFalse(set(d['actions']) & {'erase', 'partition', 'mount', 'unmount', 'rename', 'add-volume'})
        with self.assertRaises(APIError):
            self.plan(target='disk0')

    def test_apfs_space_does_not_double_count_shared_capacity(self):
        d = next(d for d in self.report()['devices'] if d['id'] == 'disk1s2s1')
        self.assertEqual(d['used'], 13_660_000_000)
        self.assertEqual(d['used'] + d['other'] + d['free'], d['total'])

    def test_system_and_recovery_records_are_hidden_but_remain_protected(self):
        # This reaches the real inventory builder used by /api/disks.
        recovery = 'disk1s5'
        self.runner.infos[recovery] = {**self.runner.infos['disk1s1'], 'DeviceIdentifier':recovery,
                                      'VolumeName':'Recovery', 'MountPoint':'/Volumes/Recovery'}
        self.runner.nodes[1]['APFSVolumes'].append({'DeviceIdentifier':recovery})
        self.runner.containers[0]['Volumes'].append({'DeviceIdentifier':recovery,'Roles':['Recovery']})
        report=self.report(); by_id={d['id']:d for d in report['devices']}
        for identifier in (recovery,'disk0s2','disk1','disk1s1'):
            self.assertFalse(by_id[identifier]['visible'], identifier)
            self.assertTrue(by_id[identifier]['system_managed'], identifier)
            self.assertFalse(set(by_id[identifier]['actions']) & {'erase','partition','rename','unmount'})
        for identifier in ('disk0','disk1s2s1','disk8','disk9','disk9s1'):
            self.assertTrue(by_id[identifier]['visible'], identifier)

    def test_erase_plan_uses_exact_argv_and_never_runs(self):
        plan = self.plan(name='Photos & Projects')
        self.assertEqual(plan['commands'], [[DISKUTIL, 'eraseDisk', 'APFS', 'Photos & Projects', 'GPT', 'disk8']])
        self.assertEqual(plan['phrase'], 'ERASE disk8')
        self.assertEqual(self.runner.commands, [])

    def test_partition_plan_remainder_and_formats(self):
        parts = [{'name': 'Mac', 'format': 'APFS', 'size_gb': 100},
                 {'name': 'Shared', 'format': 'ExFAT'}]
        plan = self.plan(action='partition', partitions=parts)
        self.assertEqual(plan['commands'][0], [DISKUTIL, 'partitionDisk', 'disk8', '2', 'GPT', 'APFS', 'Mac', '100G', 'ExFAT', 'Shared', 'R'])
        for value in (0, -1, True, 499, 100001, 1.5, '20G', float('nan')):
            with self.subTest(value=value), self.assertRaises(APIError):
                self.plan(action='partition', partitions=[{**parts[0], 'size_gb': value}, parts[1]])

    def test_invalid_names_formats_targets_and_actions_rejected(self):
        for body in ({'name':'../disk0'}, {'name':'%noformat%'}, {'name':'-Danger'}, {'name':'x\nY'},
                     {'format':'Free Space'}, {'format':[]}, {'action':[]}, {'target':'disk8;echo x'},
                     {'target':'/dev/disk8'}, {'target':'disk999'}, {'name':'a'*65}):
            with self.subTest(body=body), self.assertRaises(APIError):
                self.plan(**body)

    def test_volume_and_container_commands(self):
        report = self.report()
        for action, target, expected in [
            ('add-volume', 'disk9', ['apfs','addVolume','disk9','APFS','Code']),
            ('rename', 'disk9s1', ['renameVolume','disk9s1','Code']),
            ('unmount', 'disk9s1', ['unmount','disk9s1']),
            ('eject', 'disk8', ['eject','disk8']),
            ('verify-disk', 'disk0', ['verifyDisk','disk0'])]:
            with self.subTest(action=action):
                plan = disk_plan({'action':action, 'target':target, 'format':'APFS','name':'Code'}, report)
                self.assertEqual(plan['commands'][0], [DISKUTIL,*expected])

    def test_time_machine_and_system_roles_protect_whole_disk(self):
        for setup in ('destination', 'backup-role', 'system-role', 'bootable'):
            with self.subTest(setup=setup):
                self.runner = FakeRunner()
                if setup == 'destination': self.runner.backups = {'Destinations':[{'MountPoint':'/Volumes/Work SSD'}]}
                elif setup == 'bootable': self.runner.infos['disk9s1']['Bootable'] = True
                else: self.runner.containers[1]['Volumes'][0]['Roles'] = ['Backup' if setup == 'backup-role' else 'System']
                with self.assertRaises(APIError): self.plan()

    def test_missing_safety_metadata_fails_closed(self):
        for setup in ('info', 'backup', 'internal', 'readonly', 'identity', 'multi-store'):
            with self.subTest(setup=setup):
                self.runner = FakeRunner()
                if setup == 'info': self.runner.fail_info = 'disk9s1'
                elif setup == 'backup': self.runner.backups = None
                elif setup == 'internal': del self.runner.infos['disk8']['Internal']
                elif setup == 'readonly': self.runner.infos['disk8']['Writable'] = False
                elif setup == 'multi-store': self.runner.containers[1]['PhysicalStores'].append({'DeviceIdentifier':'disk0s2'})
                else:
                    for key in ['disk8s2','disk9s1']:
                        self.runner.infos[key].pop('DiskUUID',None); self.runner.infos[key].pop('VolumeUUID',None)
                with self.assertRaises(APIError): self.plan()

    def test_external_home_volume_protects_its_physical_disk(self):
        original = self.runner.plist
        def moved_home(argv):
            if argv == [DISKUTIL, 'info', '-plist', '/dev/disk1s1']:
                return deepcopy(self.runner.infos['disk9s1'])
            return original(argv)
        self.runner.plist = moved_home
        with self.assertRaises(APIError): self.plan()

    def test_raid_and_missing_apfs_container_are_protected(self):
        self.runner.infos['disk8']['RAIDMaster'] = True
        with self.assertRaises(APIError): self.plan()
        self.runner = FakeRunner()
        self.runner.nodes[2]['Partitions'][0]['Content'] = 'Apple_APFS'
        self.runner.containers = self.runner.containers[:1]
        with self.assertRaises(APIError): self.plan()

    def test_unknown_apfs_topology_is_not_treated_as_external(self):
        self.runner.containers[1]['PhysicalStores'] = []
        with self.assertRaises(APIError): self.plan(target='disk9', action='add-volume')


class ToolkitJobsTest(unittest.TestCase):
    def setUp(self):
        self.mac = patch('mac_deep_cleaner.disks.IS_MAC', True)
        self.mac.start(); self.addCleanup(self.mac.stop)
        self.runner = FakeRunner()
        self.toolkit = Toolkit(threading.Lock(), runner=self.runner)

    def prepare(self):
        return self.toolkit.prepare('disk', {'action':'erase','target':'disk8','format':'APFS','name':'Work'})

    def confirm(self, plan, **overrides):
        return self.toolkit.start({'token':plan['token'],'confirmed':True,'phrase':plan['phrase'],'backup_ack':True,**overrides})

    def test_confirmation_phrase_backup_ack_expiration_and_replay(self):
        plan = self.prepare()
        for override in ({'confirmed':False},{'confirmed':1},{'phrase':'ERASE disk0'},{'backup_ack':False},{'token':[]}):
            with self.subTest(override=override), self.assertRaises(APIError): self.confirm(plan, **override)
        self.assertFalse(self.runner.commands)
        self.confirm(plan)
        self.assertEqual(wait_job(self.toolkit)['status'], 'succeeded')
        with self.assertRaises(APIError): self.confirm(plan)
        plan = self.prepare(); self.toolkit.plans[plan['token']]['expires_at'] = 0
        with self.assertRaises(APIError): self.confirm(plan)
        self.assertEqual(len(self.runner.commands), 1)

    def test_reconnected_or_changed_disk_never_executes(self):
        for change in ('uuid','internal','backup','layout'):
            with self.subTest(change=change):
                self.runner = FakeRunner(); self.toolkit = Toolkit(threading.Lock(), runner=self.runner)
                plan = self.prepare()
                if change == 'uuid': self.runner.infos['disk9s1']['VolumeUUID'] = 'different-drive'
                elif change == 'internal': self.runner.infos['disk8']['Internal'] = True
                elif change == 'backup': self.runner.backups = {'UUID':'volume-disk8'}
                else: self.runner.infos['disk9s1']['VolumeName'] = 'Changed'
                self.confirm(plan)
                self.assertEqual(wait_job(self.toolkit)['status'], 'failed')
                self.assertFalse(self.runner.commands)

    def test_volatile_free_space_does_not_invalidate_identity(self):
        plan = self.prepare(); self.runner.containers[1]['CapacityFree'] -= 1000
        self.confirm(plan)
        self.assertEqual(wait_job(self.toolkit)['status'], 'succeeded')

    def test_failure_unlocks_and_is_visible(self):
        plan = self.prepare(); self.runner.fail_command = True
        self.confirm(plan)
        job = wait_job(self.toolkit)
        self.assertEqual(job['status'], 'failed')
        self.assertIn('Permission denied', job['error'])
        self.assertFalse(self.toolkit.operation.locked())

    def test_cleanup_and_scans_cannot_overlap_a_disk_change(self):
        plan = self.prepare(); self.toolkit.ready_to_change = lambda: False
        with self.assertRaises(APIError): self.confirm(plan)
        self.toolkit.ready_to_change = lambda: True
        self.runner.hold = threading.Event()
        self.confirm(plan)
        self.assertTrue(self.toolkit.operation.locked())
        with self.assertRaises(APIError): self.prepare()
        self.runner.hold.set(); wait_job(self.toolkit)
        self.assertFalse(self.toolkit.operation.locked())

    def test_scan_readiness_is_checked_while_operation_is_locked(self):
        plan = self.prepare()
        checks = []
        def ready():
            checks.append(self.toolkit.operation.locked())
            return True
        self.toolkit.ready_to_change = ready
        self.confirm(plan); wait_job(self.toolkit)
        self.assertEqual(checks, [True])

    def test_new_application_analysis_cannot_start_during_job(self):
        service = CleanerService(SimpleNamespace(), {'pinned':[], 'mode':'normal','min_mb':10})
        service.operation.acquire()
        try:
            with self.assertRaises(APIError): service.apps()
            self.assertIsNone(service.analyzer)
        finally: service.operation.release()

    def test_shortcut_allowlist_and_plan_copies(self):
        with self.assertRaises(APIError): self.toolkit.open('https://example.com')
        self.toolkit.open('disk-utility')
        self.assertEqual(self.runner.commands[-1], ['/usr/bin/open','-a','Disk Utility'])
        plan = self.prepare(); plan['commands'][0][-1] = 'disk0'
        self.confirm(plan); wait_job(self.toolkit)
        self.assertEqual(self.runner.commands[-1][-1], 'disk8')


class DiagnosticsTest(unittest.TestCase):
    def test_process_names_exclude_command_arguments(self):
        result = parse_processes('12 22.0 1024 /Applications/Some App.app/Some App\n13 2.1 512 /bin/test\ninvalid')
        self.assertEqual(result[0], {'pid':12,'cpu':22.0,'memory':1048576,'name':'Some App'})

    def test_missing_dependencies_and_unknown_commands(self):
        with patch('mac_deep_cleaner.system_tools.executable', return_value=None), self.assertRaises(APIError):
            tool_plan('brew-cleanup')
        for action in (None, [], 'rm -rf /'):
            with self.assertRaises(APIError): tool_plan(action)

    def test_timeout_and_nonzero_exit_are_failures(self):
        with patch('mac_deep_cleaner.system_tools.IS_MAC', True):
            for result in (subprocess.CompletedProcess([], 1, b'', b'not allowed'), subprocess.TimeoutExpired('cmd', 1)):
                with self.subTest(result=result):
                    kwargs = {'side_effect': result} if isinstance(result, Exception) else {'return_value':result}
                    with patch('subprocess.run', **kwargs), self.assertRaises(APIError):
                        CommandRunner().run(['/usr/bin/test'])

    def test_cli_dry_run_and_version(self):
        result = subprocess.run([sys.executable,'-m','mac_deep_cleaner','--tool','dns-flush','--dry-run'], capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(result.stdout)['title'], 'Refresh DNS cache')
        result = subprocess.run([sys.executable,'-m','mac_deep_cleaner','--version'], capture_output=True, text=True, check=True)
        from mac_deep_cleaner import __version__
        self.assertIn(__version__,result.stdout)


class ToolkitHTTPTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.toolkit = Toolkit(threading.Lock(), runner=FakeRunner())
        service = SimpleNamespace(toolkit=cls.toolkit)
        routes = {'/api/disks/plan':lambda b: cls.toolkit.prepare('disk',b),
                  '/api/tools/plan':lambda b: cls.toolkit.prepare('tool',b),
                  '/api/tools/run':cls.toolkit.start}
        service.post = lambda route, body: routes[route](body)
        cls.server = LocalServer(service)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join()

    def request(self, path, body=None, authorized=True, origin=None):
        connection = http.client.HTTPConnection('127.0.0.1',self.server.server_port)
        headers = {'Content-Type':'application/json'}
        if authorized: headers['Cookie'] = f'{self.server.cookie_name}={self.server.token}'
        if origin: headers['Origin'] = origin
        connection.request('GET' if body is None else 'POST',path,body=None if body is None else json.dumps(body),headers=headers)
        response = connection.getresponse(); result = (response.status,response.read()); connection.close()
        return result

    def test_new_api_and_assets_require_session(self):
        for path in ('/api/disks','/api/health','/api/jobs','/assets/toolkit.js','/api/brew','/api/brew/explain','/api/brew/export','/assets/homebrew.js'):
            with self.subTest(path=path): self.assertEqual(self.request(path,authorized=False)[0],403)
        self.assertEqual(self.request('/api/tools/plan',{'action':'dns-flush'},origin='https://evil.test')[0],403)
        self.assertEqual(self.request('/api/tools/run',{'token':'missing'})[0],409)
        self.assertEqual(self.request('/assets/toolkit.js')[0],200)

    def test_review_plan_is_not_execution(self):
        status, data = self.request('/api/tools/plan',{'action':'dns-flush'})
        self.assertEqual(status,200)
        self.assertTrue(json.loads(data)['token'])
        self.assertEqual(self.toolkit.runner.commands,[])


if __name__ == '__main__':
    unittest.main()
