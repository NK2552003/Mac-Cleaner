"""Application state and serialized, versioned operations."""
import os
import secrets
import shutil
import subprocess
import threading
import time
from dataclasses import asdict, replace

from . import __version__
from .applications import AppAnalyzer, app_items
from .catalog import CAT_DESC, CAT_NAMES, TOOLCHAIN_NAMES, toolchain
from .cleanup import eligible, execute, guard_ok
from .common import HOME, IS_MAC
from .errors import APIError
from .feature_config import read_config, update_config
from .icons import application_icon
from .scanner import Scanner
from .settings import reveal, save_settings, validated
from .toolkit import Toolkit


def public_record(value):
    data = asdict(value)
    data.pop('fingerprint', None)
    data.pop('keeper_fingerprint', None)
    return data


class CleanerService:
    def __init__(self, args, settings, scanner_factory=Scanner, analyzer_factory=AppAnalyzer):
        """Initialize validated settings, shared operation guards, and background services."""
        self.args, self.settings = args, validated(settings)
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
        self._ghosts = None
        self.events = []
        self.event_id = 0
        self.event_session = secrets.token_hex(16)
        from .automation import Automation
        from .updates import Updates
        self.automation = Automation(self)
        self.updates = Updates(self.notify)

    def notify(self, title, message):
        """Queue an opt-in event, retaining only the twenty most recent events."""
        with self.lock:
            if self.settings.get('notifications'):
                self.event_id += 1
                self.events.append({'id': self.event_id, 'title': title, 'message': message})
                self.events = self.events[-20:]

    def background_status(self):
        """Return job snapshots and events scoped to this service instance."""
        with self.lock:
            events = list(self.events)
        return {'automation': self.automation.report(), 'updates': self.updates.report(),
                'events': events, 'event_session': self.event_session}

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
            if self._ghosts:
                self._ghosts.reset()
            if self.scanner:
                self.scanner.close()
            self.scanner = self.scanner_factory(self.args.large_mb, self.args.old_days, self.args.dup_min_mb,
                                                quiet=True, pinned=self.settings['pinned'] + self.settings.get('ghost_allowlist', []))
            self.analyzer = None
            self.icons.clear()
            self.scan_id = secrets.token_hex(16)
            self.apps_id = ''
            self.revision += 1
            self.scan_thread = threading.Thread(target=self.scanner.run, name='storage-scan', daemon=True)
            self.scan_thread.start()

    def close(self):
        """Stop scheduling and close scanners and tools during application shutdown."""
        self.closed = True
        self.automation.stop.set()
        self.toolkit.closed = True
        if self._ghosts:
            self._ghosts.close()
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
        """Snapshot scan results, settings, disk usage, and operation state for the UI."""
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
                    'warnings': list(getattr(sc, 'warnings', [])),
                    'items': items, 'cats': CAT_NAMES, 'tools': TOOLCHAIN_NAMES, 'desc': CAT_DESC,
                    'scan_id': self.scan_id, 'revision': self.revision, 'busy': self.operation.locked(),
                    'settings': {key: value for key, value in self.settings.items() if key != 'pinned'},
                    'features': {'ghosts_level': read_config()['level']},
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
        paths.update(f[0] for f in getattr(self.scanner, 'walk_files', []))
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

    def ghosts(self):
        if read_config()['level'] == 0:
            raise APIError(409, 'Ghost Files is off. Enable it in Settings first.')
        with self.lock:
            if self._ghosts is None:
                from .ghosts.controller import GhostController
                self._ghosts = GhostController(self)
            return self._ghosts

    def ghost_config(self, body=None):
        if body is None:
            return read_config()
        if not self.operation.acquire(blocking=False):
            raise APIError(409, 'Cancel or finish the current operation before changing Ghost Files settings.')
        try:
            config = update_config(body)
            if self._ghosts:
                if config['level'] < 2 and self._ghosts.manager:
                    self._ghosts.manager.stop()
                if config['level'] == 0:
                    with self.lock:
                        self._ghosts.reset()
                        self.revision += 1
                    self._ghosts.close()
                    self._ghosts = None
            return config
        finally:
            self.operation.release()

    def post(self, route, body):
        """Dispatch authenticated mutations and serialize cleanup, settings, and quit approval."""
        if self.closed and route != '/api/prepare-quit':
            raise APIError(503, 'Application is shutting down.')
        if route == '/api/prepare-quit':
            if not self.operation.acquire(blocking=False):
                return {'can_quit': False}
            try:
                self.closed = True
                self.toolkit.closed = True
                self.automation.stop.set()
                return {'can_quit': True}
            finally:
                self.operation.release()
        if route == '/api/updates/check':
            return self.updates.start()
        if route == '/api/automation/clean':
            return self.automation.start()
        if route == '/api/ghosts/config':
            return self.ghost_config(body)
        if route.startswith('/api/ghosts/'):
            return self.ghosts().post(route, body)
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
        if route == '/api/open-url':
            target_url = body.get('url', '')
            if isinstance(target_url, str) and target_url.startswith(('https://', 'http://')):
                import subprocess
                subprocess.run(['/usr/bin/open', target_url], check=False)
                return {'ok': True}
            raise APIError(400, 'Invalid URL.')
        if route not in ('/api/rescan', '/api/pin', '/api/clean', '/api/app/clean', '/api/settings', '/api/history/restore', '/api/i18n/import', '/api/settings/ghost-allowlist/remove'):
            raise APIError(404, 'Unknown operation.')
        if not self.operation.acquire(blocking=False):
            raise APIError(409, 'Another operation is running. Wait for it to finish.')
        try:
            if self.closed:
                raise APIError(503, 'Application is shutting down.')
            if route in ('/api/history/restore', '/api/i18n/import', '/api/settings/ghost-allowlist/remove'):
                if not self._ready_to_change():
                    raise APIError(409, 'Wait for scans to finish.')
                if route == '/api/history/restore':
                    from .history import History
                    if not isinstance(body.get('id'), str):
                        raise APIError(400, 'Choose a history entry.')
                    result = History().restore(body['id'])
                    with self.lock:
                        self.revision += 1
                    return result
                if route == '/api/i18n/import':
                    from .localization import save_pack
                    return save_pack(body)
                path = body.get('path')
                with self.lock:
                    if not isinstance(path, str) or path not in self.settings.get('ghost_allowlist', []):
                        raise APIError(400, 'Choose a current ghost.')
                    updated = {**self.settings, 'ghost_allowlist': [p for p in self.settings['ghost_allowlist'] if p != path]}
                    if not save_settings(updated):
                        raise APIError(500, 'Could not save the allowlist.')
                    self.settings = updated
                    if self.scanner and path not in updated.get('pinned', []):
                        self.scanner.pinned.discard(path)
                return {'ok': True}
            if route == '/api/rescan':
                self.start_scan()
                return {'scan_id': self.scan_id}
            if route == '/api/settings':
                if set(body) <= {'automation_enabled', 'automation_hours', 'notifications', 'automatic_updates'} and body:
                    for key in ('automation_enabled', 'notifications', 'automatic_updates'):
                        if key in body and type(body[key]) is not bool:
                            raise APIError(400, 'Use true or false.')
                    if 'automation_hours' in body and (type(body['automation_hours']) is not int or not 1 <= body['automation_hours'] <= 720):
                        raise APIError(400, 'Choose an interval from 1 to 720 hours.')
                    updated = {**self.settings, **body}
                    if 'automation_enabled' in body or 'automation_hours' in body:
                        updated['automation_next_run'] = time.time() + updated['automation_hours'] * 3600 if updated['automation_enabled'] else 0
                elif 'language' in body:
                    from .localization import locale_code
                    updated = {**self.settings, 'language': locale_code(body['language'])}
                elif 'theme' in body:
                    if body['theme'] not in ('dark', 'light'):
                        raise APIError(400, 'Unknown theme.')
                    updated = {**self.settings, 'theme': body['theme']}
                elif body.get('mode') in ('normal', 'dev'):
                    updated = {**self.settings, 'mode': body['mode']}
                else:
                    raise APIError(400, 'Unknown workspace mode.')
                if not save_settings(updated):
                    raise APIError(500, 'Could not save workspace settings.')
                with self.lock:
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
                    self.scanner.items[:] = [i for i in self.scanner.items
                                            if not self._under(i.path, path) and not self._under(path, i.path)]
                    self.scanner.walk_files[:] = [f for f in self.scanner.walk_files if not self._under(f[0], path)]
                    self.revision += 1
                return {'ok': True}
            self._booleans(body)
            if route == '/api/clean':
                ids = self._ids(body.get('ids'))
                with self.scanner.lock:
                    chosen = [replace(i, selected=True) for i in self.scanner.items if i.id in ids]
                if len(chosen) != len(ids) or any(not eligible(i) for i in chosen):
                    raise APIError(400, 'Some selected items are unavailable or protected.')
                if any(i.action == 'empty' for i in chosen):
                    if len(chosen) != 1:
                        raise APIError(400, 'Empty Trash separately from other cleanup operations.')
                    if body.get('permanent_ack') is not True:
                        raise APIError(400, 'Permanent deletion requires explicit confirmation.')
                if any(i.safety == 'risky' for i in chosen) and not body.get('ack'):
                    raise APIError(400, 'Risky items require acknowledgement.')
                # Keepers outside the selected duplicate set remain protected too.
                keepers = {i.keep for i in self.scanner.items if i.keep}
                if any(i.path and any(self._under(k, i.path) for k in keepers) for i in chosen):
                    raise APIError(409, 'The selection contains a retained duplicate. Rescan and review it.')
            else:
                chosen = self._app_selection(body)
            return self._execute(chosen, body.get('permanent', False), body)
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

    def _execute(self, chosen, permanent, body=None, candidate_check=None):
        """Revalidate selected items, execute guarded cleanup, and publish results and history."""
        if self._ghosts:
            self._ghosts.check_selection(chosen, permanent, body or {})
        if any(i.path and any(self._under(i.path, pin) or self._under(pin, i.path) for pin in self.scanner.pinned) for i in chosen):
            raise APIError(409, 'The selection overlaps an excluded location.')
        done, logs, results = set(), [], []
        def tick(item, ok, _message):
            if ok:
                done.add(item.path or item.cmd)
            results.append({'id': item.id, 'name': item.name, 'path': item.path,
                            'action': item.action, 'ok': ok, 'message': _message,
                            'size': item.size})
        freed, roots, failures = execute(chosen, permanent=permanent, log=logs.append, tick=tick,
                                        candidate_check=candidate_check)
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
        warning = self._ghosts.removed(done) if self._ghosts else ''
        self.notify('Cleanup', 'Completed' if not failures else 'Cleanup completed with errors.')
        return {'freed': freed, 'processed_bytes': freed, 'results': results,
                'root': roots, 'warning': warning, 'fails': [(i.name, message) for i, message in failures], 'log': logs}
