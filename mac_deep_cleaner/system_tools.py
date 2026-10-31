"""Bounded macOS diagnostics and an explicit maintenance command catalogue."""
import os
import platform
import plistlib
import re
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .common import IS_MAC
from .errors import APIError


class CommandRunner:
    def run(self, argv, timeout=20):
        if not IS_MAC:
            raise APIError(400, 'These tools require macOS.')
        try:
            result = subprocess.run(argv, capture_output=True, stdin=subprocess.DEVNULL, check=False,
                                    timeout=timeout, env={**os.environ, 'LC_ALL': 'C',
                                    'HOMEBREW_NO_AUTO_UPDATE': '1',
                                    'HOMEBREW_NO_AUTOREMOVE': '1',
                                    'HOMEBREW_NO_INSTALL_CLEANUP': '1',
                                    'HOMEBREW_NO_INSTALLED_DEPENDENTS_CHECK': '1',
                                    'HOMEBREW_NO_ANALYTICS': '1'})
        except subprocess.TimeoutExpired:
            raise APIError(408, 'The command timed out. Check the current state before retrying; '
                           'some changes may already have completed.') from None
        except OSError as exc:
            raise APIError(400, f'Cannot start {Path(argv[0]).name}: {exc.strerror}') from None
        output = (result.stdout + result.stderr).decode('utf-8', errors='replace').strip()
        if result.returncode:
            if result.stdout.startswith(b'<?xml'):
                try:
                    output = plistlib.loads(result.stdout).get('ErrorMessage', output)
                except (ValueError, plistlib.InvalidFileException, AttributeError):
                    pass
            raise APIError(400, output[-8000:] or f'{Path(argv[0]).name} failed ({result.returncode}).')
        return result.stdout

    def text(self, argv, timeout=20):
        return self.run(argv, timeout).decode('utf-8', errors='replace').strip()

    def plist(self, argv):
        try:
            result = plistlib.loads(self.run(argv))
            if not isinstance(result, dict):
                raise TypeError('expected a dictionary')
            if result.get('Error'):
                raise APIError(400, result.get('ErrorMessage', 'macOS could not inspect this disk.'))
            return result
        except (TypeError, ValueError, plistlib.InvalidFileException):
            raise APIError(502, 'macOS returned unreadable disk information. Refresh and try again.') from None


# Labels describe exactly what will happen. No arbitrary command, path, or URL is accepted.
SHORTCUTS = {
    'activity-monitor': ('Activity Monitor', ['-a', 'Activity Monitor']),
    'disk-utility': ('Disk Utility', ['-a', 'Disk Utility']),
    'login-items': ('Login items', ['x-apple.systempreferences:com.apple.LoginItems-Settings.extension']),
    'storage-settings': ('Storage settings', ['x-apple.systempreferences:com.apple.settings.Storage']),
    'software-update': ('Software Update', ['x-apple.systempreferences:com.apple.Software-Update-Settings.extension']),
    'battery-settings': ('Battery settings', ['x-apple.systempreferences:com.apple.preference.battery']),
    'time-machine': ('Time Machine', ['x-apple.systempreferences:com.apple.Time-Machine-Settings.extension']),
    'network-settings': ('Network settings', ['x-apple.systempreferences:com.apple.Network-Settings.extension']),
}

TOOLS = {
    'quicklook-reset': {
        'title': 'Rebuild Quick Look thumbnails', 'group': 'Everyday maintenance',
        'description': 'Clear generated previews when Finder thumbnails are missing or incorrect. They rebuild when needed.',
        'commands': [['/usr/bin/qlmanage', '-r', 'cache']], 'changes': True,
    },
    'dns-flush': {
        'title': 'Refresh DNS cache', 'group': 'Everyday maintenance',
        'description': 'Clear cached network lookups to troubleshoot sites that will not load. macOS asks for administrator permission.',
        'commands': [['/usr/bin/osascript', '-e', 'do shell script "/usr/bin/dscacheutil -flushcache && /usr/bin/killall -HUP mDNSResponder" with administrator privileges']],
        'changes': True,
    },
    'spotlight-rebuild': {
        'title': 'Rebuild Spotlight index', 'group': 'Everyday maintenance',
        'description': 'Restart indexing of the startup disk when search results are incomplete. Indexing can take hours and temporarily use more energy. Administrator permission is required.',
        'commands': [['/usr/bin/osascript', '-e', 'do shell script "/usr/bin/mdutil -E /" with administrator privileges']],
        'changes': True,
    },
    'snapshots': {
        'title': 'Inspect local snapshots', 'group': 'Everyday maintenance',
        'description': 'List Time Machine snapshots on the startup volume. macOS manages their space automatically.',
        'commands': [['/usr/bin/tmutil', 'listlocalsnapshots', '/']], 'changes': False,
    },
    'brew-doctor': {
        'title': 'Homebrew health check', 'group': 'Developer tools',
        'description': 'Check your Homebrew installation and show actionable diagnostics.',
        'tool': 'brew', 'args': ['doctor'], 'changes': False,
    },
    'brew-preview': {
        'title': 'Preview Homebrew cleanup', 'group': 'Developer tools',
        'description': 'List old package versions and downloads that Homebrew would remove. No packages are removed.',
        'tool': 'brew', 'args': ['cleanup', '--dry-run'], 'changes': False,
    },
    'brew-cleanup': {
        'title': 'Clean old Homebrew downloads', 'group': 'Developer tools',
        'description': 'Permanently remove outdated downloads and old installed package versions using brew cleanup. This can remove versions you might otherwise roll back to.',
        'tool': 'brew', 'args': ['cleanup'], 'changes': True,
    },
    'simulator-cleanup': {
        'title': 'Remove unavailable simulators', 'group': 'Developer tools',
        'description': 'Permanently delete simulator devices and their data only for runtimes no longer installed. Requires Xcode.',
        'commands': [['/usr/bin/xcrun', 'simctl', 'delete', 'unavailable']],
        'changes': True, 'requires_xcode': True,
    },
    'npm-verify': {
        'title': 'Verify npm cache', 'group': 'Developer tools',
        'description': 'Check cached package integrity and let npm garbage-collect unneeded cache entries. Project dependencies stay installed.',
        'tool': 'npm', 'args': ['cache', 'verify'], 'changes': True,
    },
}


def executable(name):
    # Native app launches often have a minimal PATH.
    return shutil.which(name) or next((str(p) for p in
        (Path('/opt/homebrew/bin') / name, Path('/usr/local/bin') / name)
        if p.is_file() and os.access(p, os.X_OK)), None)


def tool_plan(action):
    if not isinstance(action, str) or action not in TOOLS:
        raise APIError(400, 'Choose an available maintenance tool.')
    tool = TOOLS[action]
    commands = tool.get('commands')
    if tool.get('tool'):
        path = executable(tool['tool'])
        if not path:
            raise APIError(400, f'Install {tool["tool"]} before using this tool.')
        commands = [[path, *tool['args']]]
    return {**{k: tool[k] for k in ('title', 'description', 'changes')},
            'commands': commands, 'layout': [], 'danger': action in ('brew-cleanup', 'simulator-cleanup'),
            'phrase': 'REMOVE' if action in ('brew-cleanup', 'simulator-cleanup') else ''}


def catalogue():
    return [{**{k: v[k] for k in ('title', 'description', 'group', 'changes')},
             'id': key, 'available': IS_MAC and (not v.get('tool') or bool(executable(v['tool']))),
             'requirement': v.get('tool', 'Xcode' if v.get('requires_xcode') else 'macOS')}
            for key, v in TOOLS.items() if not key.startswith('brew-')]


def parse_processes(output):
    rows = []
    for line in output.splitlines():
        parts = line.strip().split(None, 3)
        if len(parts) != 4:
            continue
        try:
            rows.append({'pid': int(parts[0]), 'cpu': float(parts[1]),
                         'memory': int(parts[2]) * 1024, 'name': Path(parts[3]).name})
        except ValueError:
            continue
    return sorted(rows, key=lambda p: p['cpu'], reverse=True)[:10]


def health_report(runner):
    checks = {
        'memory_total': ['/usr/sbin/sysctl', '-n', 'hw.memsize'],
        'pressure': ['/usr/sbin/sysctl', '-n', 'kern.memorystatus_vm_pressure_level'],
        'swap': ['/usr/sbin/sysctl', '-n', 'vm.swapusage'],
        'battery': ['/usr/bin/pmset', '-g', 'batt'],
        'uptime': ['/usr/bin/uptime'],
        'spotlight': ['/usr/bin/mdutil', '-s', '/'],
        'processes': ['/bin/ps', '-axo', 'pid=,pcpu=,rss=,comm='],
    }
    warnings = []

    def read(item):
        key, cmd = item
        try:
            return key, runner.text(cmd, timeout=6)
        except APIError as exc:
            return key, {'error': str(exc)}

    with ThreadPoolExecutor(max_workers=4) as pool:
        raw = dict(pool.map(read, checks.items()))
    for key, value in list(raw.items()):
        if isinstance(value, dict):
            warnings.append(f'{key}: {value["error"]}')
            raw[key] = ''
    disk = shutil.disk_usage(Path.home())
    agents = []
    for folder in (Path.home() / 'Library/LaunchAgents', Path('/Library/LaunchAgents'),
                   Path('/Library/LaunchDaemons')):
        try:
            agents.extend({'name': p.stem, 'location': str(folder)}
                          for p in sorted(folder.glob('*.plist')))
        except OSError:
            warnings.append(f'Cannot read {folder}')
    pressure = {'1': 'Normal', '2': 'Elevated', '4': 'High'}.get(raw['pressure'], 'Unavailable')
    swap = re.search(r'used\s*=\s*([\d.]+[MG])', raw['swap'])
    return {'supported': IS_MAC, 'checked_at': time.time(), 'os': platform.mac_ver()[0],
            'memory_total': int(raw['memory_total']) if raw['memory_total'].isdigit() else None,
            'pressure': pressure, 'swap': swap.group(1) if swap else 'Unavailable',
            'battery': raw['battery'] or 'Battery information unavailable',
            'uptime': raw['uptime'], 'spotlight': raw['spotlight'],
            'disk': {'total': disk.total, 'free': disk.free, 'used': disk.used},
            'processes': parse_processes(raw['processes']), 'launch_agents': agents,
            'warnings': warnings, 'tools': catalogue(),
            'shortcuts': [{'id': k, 'title': v[0]} for k, v in SHORTCUTS.items()]}
