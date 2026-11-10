"""Opt-in scheduling and conservative, recoverable unattended cleanup."""
import os
import plistlib
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


def excluded_storage(name):
    """Identify storage that unattended cleanup must never move."""
    name = name.lower()
    return 'webkit' in name or 'httpstorages' in name or name.startswith('com.apple.')


def safe_candidate(item, now=None):
    """Only inactive cache/log contents; never user documents or tool commands."""
    if (not eligible(item) or item.readonly or item.manual or item.active_project or item.safety != 'safe'
            or item.action != 'trash' or item.keep or not guard_ok(item.path)):
        return False
    roots = [os.path.join(HOME, 'Library', name) for name in ('Caches', 'Logs')]
    if not any(item.path.startswith(root + os.sep) for root in roots):
        return False
    components = item.path.lower().split(os.sep)
    if any(excluded_storage(part) for part in components):
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
                    for entry in entries:
                        if (count + len(pending) >= 100000 or time.monotonic() > deadline
                                or excluded_storage(entry.name)):
                            return False
                        pending.append(entry.path)
        return True
    except OSError:
        return False


class Automation:
    def __init__(self, service):
        """Create scheduler and worker state for a single cleanup service."""
        self.service = service
        self.lock = threading.RLock()
        self.stop = threading.Event()
        self.thread = None
        self.worker = None
        self.job = {'running': False, 'last_run': 0, 'error': '', 'result': None}

    def report(self):
        """Return an isolated snapshot of the latest background cleanup job."""
        with self.lock:
            return deepcopy(self.job)

    def start_scheduler(self):
        """Start one daemon scheduler; cleanup workers remain non-daemon."""
        if self.thread is None:
            self.thread = threading.Thread(target=self._loop, name='cleanup-schedule', daemon=True)
            self.thread.start()

    def _loop(self):
        """Check due work until shutdown is requested."""
        while not self.stop.wait(15):
            self.tick()

    def tick(self, now=None):
        """Request due cleanup and daily update checks, deferring busy operations."""
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
        """Acquire the operation lock and revalidate the schedule before launching cleanup."""
        service = self.service
        if not service.operation.acquire(blocking=False):
            raise APIError(409, 'Another operation is running. Wait for it to finish.')
        try:
            if not service._ready_to_change():
                raise APIError(409, 'Wait for scans to finish.')
            if scheduled:
                with service.lock:
                    current_time = time.time() if now is None else now
                    if (not service.settings.get('automation_enabled')
                            or current_time < service.settings.get('automation_next_run', 0)):
                        service.operation.release()
                        return {'started': False}
                    updated = {**service.settings, 'automation_next_run':
                               current_time + service.settings['automation_hours'] * 3600}
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
        """Discover inactive caches, exclude running apps, and journal guarded Trash moves."""
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
            installed_ids = {path: identifier for _, identifier, path in fresh.installed}
            resolved_bundles = set()
            for process in processes.splitlines():
                # Include bundles launched from Downloads, disk images, or nested helpers.
                executable = process.strip()
                for match in re.finditer(r'\.app/', executable):
                    bundle = executable[:match.end() - 1]
                    # Sealed system daemons can use .app paths without bundle metadata;
                    # their com.apple storage and process names are already excluded.
                    if bundle.startswith('/System/') or bundle in resolved_bundles:
                        continue
                    resolved_bundles.add(bundle)
                    identifier = installed_ids.get(bundle)
                    if not identifier:
                        with open(os.path.join(bundle, 'Contents', 'Info.plist'), 'rb') as metadata:
                            identifier = plistlib.load(metadata).get('CFBundleIdentifier')
                    if not isinstance(identifier, str) or not identifier:
                        raise ValueError('Could not identify a running application. Try again.')
                    running.add(norm(identifier))
            if fresh.error or service.closed:
                raise APIError(409, 'The scan did not finish successfully. Rescan before cleaning.')
            chosen = [replace(item, selected=True) for item in fresh.items if safe_candidate(item)
                      and not any(token and token in norm(os.path.relpath(item.path, HOME)) for token in running)]
            # The executor revalidates identities and exclusions and journals Trash moves.
            result = service._execute(chosen, False, candidate_check=safe_candidate)
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
