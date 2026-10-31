"""Application state and serialized, versioned operations."""
import os
import secrets
import shutil
import subprocess
import threading
from dataclasses import asdict, replace

from . import __version__
from .applications import AppAnalyzer, app_items
from .catalog import CAT_DESC, CAT_NAMES, TOOLCHAIN_NAMES, toolchain
from .cleanup import eligible, execute, guard_ok
from .common import HOME, IS_MAC
from .errors import APIError
from .icons import application_icon
from .scanner import Scanner
from .settings import reveal, save_settings
from .toolkit import Toolkit


def public_record(value):
    data = asdict(value)
    data.pop('fingerprint', None)
    data.pop('keeper_fingerprint', None)
    return data


class CleanerService:
    def __init__(self, args, settings, scanner_factory=Scanner, analyzer_factory=AppAnalyzer):
        self.args, self.settings = args, settings
        self.scanner_factory, self.analyzer_factory = scanner_factory, analyzer_factory
        self.lock = threading.RLock()
        self.operation = threading.Lock()
        self.scanner = None
        self.analyzer = None
        self.scan_id = ''
        self.apps_id = ''
        self.revision = 0
        self.icons = {}
        self.icon_slots = threading.BoundedSemaphore(4)
        self.scan_thread = None
        self.app_thread = None
        self.closed = False
        self.toolkit = Toolkit(self.operation, self._ready_to_change)

    def _ready_to_change(self):
        with self.lock:
            return (not self.closed and (not self.scanner or self.scanner.done)
                    and (not self.analyzer or self.analyzer.done))

    def start_scan(self):
        with self.lock:
            if self.closed:
                raise APIError(503, 'Application is shutting down.')
            if self.scanner and not self.scanner.done:
                raise APIError(409, 'A scan is already running.')
            if self.analyzer and not self.analyzer.done:
                raise APIError(409, 'Wait for application analysis to finish before rescanning.')
            if self.scanner:
                self.scanner.close()
            self.scanner = self.scanner_factory(self.args.large_mb, self.args.old_days, self.args.dup_min_mb,
                                                quiet=True, pinned=self.settings['pinned'])
            self.analyzer = None
            self.icons.clear()
            self.scan_id = secrets.token_hex(16)
            self.apps_id = ''
            self.revision += 1
            self.scan_thread = threading.Thread(target=self.scanner.run, name='storage-scan', daemon=True)
            self.scan_thread.start()

    def close(self):
        self.closed = True
        self.toolkit.closed = True
        if self.scanner:
            self.scanner.close()

    def _version(self, body):
        if body.get('scan_id') != self.scan_id or type(body.get('revision')) is not int or body['revision'] != self.revision:
            raise APIError(409, 'Results changed. Refresh and review the selection again.')
        if not self.scanner.done:
            raise APIError(409, 'Wait for the scan to finish before making changes.')
        if self.scanner.error:
            raise APIError(409, 'The scan did not finish successfully. Rescan before cleaning.')

    def state(self):
        with self.lock, self.scanner.lock:
            sc = self.scanner
            items = []
            for item in sc.items:
                data = public_record(item)
                data['group'] = toolchain(item) if item.category == 'Developer & Pro Tools' else item.category
                items.append(data)
            disk = shutil.disk_usage(HOME)
            return {'version': __version__, 'initial_view': getattr(self.args, 'view', 'clean'),
                    'scanning': not sc.done, 'progress': sc.progress, 'error': sc.error,
                    'items': items, 'cats': CAT_NAMES, 'tools': TOOLCHAIN_NAMES, 'desc': CAT_DESC,
                    'scan_id': self.scan_id, 'revision': self.revision, 'busy': self.operation.locked(),
                    'settings': {'mode': self.settings['mode'], 'min_mb': self.settings['min_mb']},
                    'disk': {'total': disk.total, 'used': disk.used, 'free': disk.free}}

    def apps(self):
        with self.lock:
            if self.analyzer is None:
                if self.operation.locked():
                    raise APIError(409, 'Wait for the current operation before starting application analysis.')
                sc = self.scanner
                self.analyzer = self.analyzer_factory(sc)
                self.apps_id = secrets.token_hex(16)
                an = self.analyzer
                def analyze():
                    sc.apps_ready.wait()
                    if not self.closed:
                        an.run()
                self.app_thread = threading.Thread(target=analyze, name='application-analysis', daemon=True)
                self.app_thread.start()
            an = self.analyzer
            return {'ready': an.done, 'started': True, 'progress': an.progress, 'total': an.total,
                    'scan_id': self.scan_id, 'apps_id': self.apps_id, 'error': an.error,
                    'apps': [self._app_json(a) for a in list(an.apps)]}

    @staticmethod
    def _app_json(app):
        data = public_record(app)
        data.update(cache_size=app.cache_size, data_size=app.data_size, total=app.total, idle_days=app.idle_days)
        data['parts'] = [public_record(p) for p in app.parts]
        return data

    def biggest(self):
        with self.lock, self.scanner.lock:
            if not self.scanner.done or self.operation.locked():
                return {'ids': []}
            return {'ids': [i.id for i in self.scanner.biggest(100)]}

    def _known_paths(self):
        paths = {i.path for i in self.scanner.items if i.path}
        if self.analyzer:
            for app in self.analyzer.apps:
                paths.add(app.path)
                paths.update(p.path for p in app.parts)
        return paths

    def icon(self, app_id):
        with self.lock:
            key = (self.apps_id, app_id)
            if key in self.icons:
                return self.icons[key]
            app = next((a for a in self.analyzer.apps if a.id == app_id), None) if self.analyzer else None
            if not app or not IS_MAC:
                return None
            path = app.path
            name = self.scanner.app_meta.get(path, {}).get('icon', '')
        with self.icon_slots:
            data = application_icon(path, name)
        with self.lock:
            self.icons[key] = data
        return data

    @staticmethod
    def _ids(value):
        if not isinstance(value, list) or not value or len(value) > 100000 or any(type(i) is not int or i < 0 for i in value):
            raise APIError(400, 'Select valid item IDs.')
        return set(value)

    @staticmethod
    def _booleans(body):
        for name in ('permanent', 'ack', 'permanent_ack'):
            if name in body and type(body[name]) is not bool:
                raise APIError(400, f'{name} must be true or false.')
        if body.get('permanent') and not body.get('permanent_ack'):
            raise APIError(400, 'Permanent deletion requires explicit confirmation.')

    def post(self, route, body):
        if route == '/api/brew/refresh':
            return self.toolkit.brew.report(refresh=True)
        if route == '/api/brew/plan':
            return self.toolkit.prepare('brew', body)
        if route == '/api/tools/plan':
            return self.toolkit.prepare('tool', body)
        if route == '/api/disks/plan':
            return self.toolkit.prepare('disk', body)
        if route == '/api/tools/run':
            return self.toolkit.start(body)
        if route == '/api/tools/open':
            return self.toolkit.open(body.get('action'))
        if route == '/api/reveal':
            with self.lock:
                path = body.get('path')
                known = isinstance(path, str) and path in self._known_paths()
            return {'ok': bool(known and reveal(path))}
        if route not in ('/api/rescan', '/api/pin', '/api/clean', '/api/app/clean', '/api/settings'):
            raise APIError(404, 'Unknown operation.')
        if not self.operation.acquire(blocking=False):
            raise APIError(409, 'Another operation is running. Wait for it to finish.')
        try:
            if route == '/api/rescan':
                self.start_scan()
                return {'scan_id': self.scan_id}
            if route == '/api/settings':
                if body.get('mode') not in ('normal', 'dev'):
                    raise APIError(400, 'Unknown workspace mode.')
                updated = {**self.settings, 'mode': body['mode']}
                if not save_settings(updated):
                    raise APIError(500, 'Could not save workspace settings.')
                self.settings = updated
                return {'ok': True}
            self._version(body)
            if route == '/api/pin':
                path = body.get('path')
                if not isinstance(path, str) or path not in self._known_paths() or not guard_ok(path):
                    raise APIError(400, 'Select an available location from the scan.')
                updated = {**self.settings, 'pinned': sorted(set(self.settings['pinned']) | {path})}
                if not save_settings(updated):
                    raise APIError(500, 'Could not save the exclusion. Nothing changed.')
                with self.lock, self.scanner.lock:
                    self.settings = updated
                    self.scanner.pinned.add(path)
                    self.scanner.items[:] = [i for i in self.scanner.items if not self._under(i.path, path)]
                    self.revision += 1
                return {'ok': True}
            self._booleans(body)
            if route == '/api/clean':
                ids = self._ids(body.get('ids'))
                with self.scanner.lock:
                    chosen = [replace(i, selected=True) for i in self.scanner.items if i.id in ids]
                if len(chosen) != len(ids) or any(not eligible(i) for i in chosen):
                    raise APIError(400, 'Some selected items are unavailable or protected.')
                if any(i.safety == 'risky' for i in chosen) and not body.get('ack'):
                    raise APIError(400, 'Risky items require acknowledgement.')
                # Keepers outside the selected duplicate set remain protected too.
                keepers = {i.keep for i in self.scanner.items if i.keep}
                if any(i.path and any(self._under(k, i.path) for k in keepers) for i in chosen):
                    raise APIError(409, 'The selection contains a retained duplicate. Rescan and review it.')
            else:
                chosen = self._app_selection(body)
            return self._execute(chosen, body.get('permanent', False))
        finally:
            self.operation.release()

    @staticmethod
    def _under(path, parent):
        return bool(path and parent and (path == parent or path.startswith(parent + os.sep)))

    def _app_selection(self, body):
        an = self.analyzer
        if not an or not an.done or an.error or body.get('apps_id') != self.apps_id:
            raise APIError(409, 'Application results changed. Reopen the app details.')
        if type(body.get('id')) is not int:
            raise APIError(400, 'Invalid application ID.')
        app = next((a for a in an.apps if a.id == body['id']), None)
        mode = body.get('mode')
        if app is None or mode not in ('caches', 'uninstall', 'pick'):
            raise APIError(400, 'Unknown application or operation.')
        picked = body.get('picked', [])
        allowed = {p.path for p in app.parts} | ({app.path} if app.removable else set())
        if not isinstance(picked, list) or any(not isinstance(p, str) or p not in allowed for p in picked):
            raise APIError(400, 'Choose only files belonging to this application.')
        if mode == 'uninstall' and not app.removable:
            raise APIError(400, 'This application is protected.')
        removes_bundle = mode == 'uninstall' or app.path in picked
        if removes_bundle and IS_MAC:
            try:
                processes = subprocess.run(['/bin/ps', '-axo', 'comm='], capture_output=True, text=True, check=True, timeout=5).stdout
            except (OSError, subprocess.SubprocessError):
                raise APIError(409, 'Could not check running apps. Try again.')
            if any(self._under(line.strip(), app.path) for line in processes.splitlines()):
                raise APIError(409, f'{app.name} is running. Quit it before uninstalling.')
        if mode in ('pick', 'uninstall') and not body.get('ack'):
            raise APIError(400, 'Removing app data requires acknowledgement.')
        chosen = app_items(app, mode, picked)
        if not chosen:
            raise APIError(400, 'No removable application files selected.')
        if any(any(self._under(i.path, pin) or self._under(pin, i.path) for pin in self.scanner.pinned) for i in chosen):
            raise APIError(409, 'The selection overlaps an excluded location.')
        return chosen

    def _execute(self, chosen, permanent):
        if any(i.path and any(self._under(i.path, pin) or self._under(pin, i.path) for pin in self.scanner.pinned) for i in chosen):
            raise APIError(409, 'The selection overlaps an excluded location.')
        done, logs = set(), []
        def tick(item, ok, _message):
            if ok:
                done.add(item.path or item.cmd)
        freed, roots, failures = execute(chosen, permanent=permanent, log=logs.append, tick=tick)
        with self.lock, self.scanner.lock:
            def removed(path):
                return any(self._under(path, p) for p in done if p.startswith('/'))
            self.scanner.items[:] = [i for i in self.scanner.items if not removed(i.path) and i.cmd not in done]
            self.scanner.walk_files[:] = [f for f in self.scanner.walk_files if not removed(f[0])]
            if self.analyzer:
                for app in self.analyzer.apps:
                    app.parts[:] = [p for p in app.parts if not removed(p.path)]
                self.analyzer.apps[:] = [a for a in self.analyzer.apps if not removed(a.path)]
            self.revision += 1
        return {'freed': freed, 'root': roots, 'fails': [(i.name, message) for i, message in failures], 'log': logs}
