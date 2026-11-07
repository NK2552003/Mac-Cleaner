"""Opt-in scheduling and conservative, recoverable unattended cleanup."""
import os
import re
import subprocess
import threading
import time
from copy import deepcopy
from dataclasses import replace

from .cleanup import eligible, guard_ok
from .common import HOME, norm
from .errors import APIError
from .settings import save_settings


def safe_candidate(item, now=None):
    """Only inactive cache/log contents; never user documents or tool commands."""
    if (not eligible(item) or item.readonly or item.manual or item.active_project or item.safety != 'safe'
            or item.action != 'trash' or item.keep or not guard_ok(item.path)):
        return False
    roots = [os.path.join(HOME, 'Library', name) for name in ('Caches', 'Logs')]
    if not any(item.path.startswith(root + os.sep) for root in roots):
        return False
    components = item.path.lower().split(os.sep)
    if any('webkit' in part or 'httpstorages' in part or part.startswith('com.apple.') for part in components):
        return False
    try:
        cutoff = (time.time() if now is None else now) - 7 * 86400
        pending, count, deadline = [item.path], 0, time.monotonic() + 5
        while pending:
            path = pending.pop()
            count += 1
            if count > 100000 or time.monotonic() > deadline or os.path.islink(path):
                return False
            if os.lstat(path).st_mtime > cutoff:
                return False
            if os.path.isdir(path):
                with os.scandir(path) as entries:
                    pending.extend(entry.path for entry in entries)
        return True
    except OSError:
        return False


class Automation:
    def __init__(self, service):
        self.service = service
        self.lock = threading.RLock()
        self.stop = threading.Event()
        self.thread = None
        self.worker = None
        self.job = {'running': False, 'last_run': 0, 'error': '', 'result': None}

    def report(self):
        with self.lock:
            return deepcopy(self.job)

    def start_scheduler(self):
        if self.thread is None:
            self.thread = threading.Thread(target=self._loop, name='cleanup-schedule', daemon=True)
            self.thread.start()

    def _loop(self):
        while not self.stop.wait(15):
            self.tick()

    def tick(self, now=None):
        now = time.time() if now is None else now
        service = self.service
        with service.lock:
            settings = dict(service.settings)
        if settings.get('automatic_updates'):
            updates = service.updates.report()
            if not updates['checking'] and now - updates['checked_at'] >= 86400:
                service.updates.start()
        if settings.get('automation_enabled') and now >= settings.get('automation_next_run', 0):
            try:
                self.start(scheduled=True, now=now)
            except APIError as exc:
                if exc.status != 409:
                    with self.lock:
                        self.job['error'] = str(exc)

    def start(self, scheduled=False, now=None):
        service = self.service
        if not service.operation.acquire(blocking=False):
            raise APIError(409, 'Another operation is running. Wait for it to finish.')
        try:
            if not service._ready_to_change():
                raise APIError(409, 'Wait for scans to finish.')
            if scheduled:
                with service.lock:
                    if not service.settings.get('automation_enabled'):
                        service.operation.release()
                        return {'started': False}
                    updated = {**service.settings, 'automation_next_run':
                               (time.time() if now is None else now) + service.settings['automation_hours'] * 3600}
                    if not save_settings(updated):
                        raise APIError(500, 'Could not save workspace settings.')
                    service.settings = updated
            with self.lock:
                self.job.update(running=True, error='', result=None)
            self.worker = threading.Thread(target=self._run, name='safe-cleanup', daemon=False)
            self.worker.start()
        except Exception:
            service.operation.release()
            raise
        return {'started': True}

    def _run(self):
        service = self.service
        fresh = None
        try:
            # A fresh restricted scan never walks documents or discovers app removal.
            fresh = service.scanner_factory(quiet=True, pinned=service.settings['pinned'] +
                                            service.settings.get('ghost_allowlist', []))
            fresh.load_apps()
            fresh.scan_specs()
            fresh.scan_app_caches()
            # Fail closed if the running-app inventory is unavailable. Include
            # bundle identifiers: app names alone do not match all cache names.
            processes = subprocess.run(['/bin/ps', '-axo', 'comm='], capture_output=True,
                                       text=True, check=True, timeout=5).stdout
            running = {norm(name) for name in re.findall(r'/([^/]+)\.app/', processes)}
            for name, identifier, _ in fresh.installed:
                if norm(name) in running and identifier:
                    running.add(norm(identifier))
            if fresh.error or service.closed:
                raise APIError(409, 'The scan did not finish successfully. Rescan before cleaning.')
            chosen = [replace(item, selected=True) for item in fresh.items if safe_candidate(item)
                      and not any(token and token in norm(os.path.relpath(item.path, HOME)) for token in running)]
            # The executor revalidates identities and exclusions and journals Trash moves.
            result = service._execute(chosen, False)
            with self.lock:
                self.job['result'] = result
        except Exception as exc:
            with self.lock:
                self.job['error'] = str(exc)[:1000]
            service.notify('Safe cleanup', 'Failed')
        finally:
            if fresh:
                fresh.close()
            with self.lock:
                self.job.update(running=False, last_run=time.time())
                service.operation.release()
