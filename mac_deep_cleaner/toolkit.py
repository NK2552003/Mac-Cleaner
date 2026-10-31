"""Session-bound review plans and serialized background maintenance jobs."""
import secrets
import threading
import time
from copy import deepcopy

from .disks import disk_plan, inventory
from .errors import APIError
from .homebrew import HomebrewManager
from .system_tools import SHORTCUTS, CommandRunner, health_report, tool_plan


class Toolkit:
    def __init__(self, operation, ready_to_change=lambda: True, runner=None):
        self.runner = runner or CommandRunner()
        self.operation = operation
        self.ready_to_change = ready_to_change
        self.lock = threading.RLock()
        self.plans = {}
        self.jobs = []
        self.closed = False
        self.brew = HomebrewManager(self.runner)

    def health(self):
        return health_report(self.runner)

    def disks(self):
        return inventory(self.runner)

    def history(self):
        with self.lock:
            return {'jobs': deepcopy(self.jobs)}

    def prepare(self, kind, body):
        if self.closed:
            raise APIError(503, 'Application is shutting down.')
        if self.operation.locked():
            raise APIError(409, 'Another operation is running. Wait for it to finish.')
        legacy_brew = {'brew-doctor': 'doctor', 'brew-preview': 'cleanup', 'brew-cleanup': 'cleanup'}
        if kind == 'tool' and isinstance(body.get('action'), str) and body['action'] in legacy_brew:
            preview_only = body['action'] == 'brew-preview'
            body = {**body, 'action': legacy_brew[body['action']], 'preview_only': preview_only}
            kind = 'brew'
        if kind == 'disk':
            plan = disk_plan(body, self.disks())
        elif kind == 'brew':
            plan = self.brew.plan(body)
            if body.get('preview_only') is True:
                plan.update(commands=[], changes=False, danger=False, phrase='')
        else:
            plan = tool_plan(body.get('action'))
        token = secrets.token_urlsafe(32)
        with self.lock:
            self.plans = {k: p for k, p in self.plans.items() if p['expires_at'] > time.time()}
            if len(self.plans) >= 32:
                self.plans.pop(next(iter(self.plans)))
            plan.update(token=token, kind=kind, request=deepcopy(body), expires_at=time.time() + 300)
            self.plans[token] = plan
        return {k: deepcopy(v) for k, v in plan.items() if k not in ('request', 'fingerprint')}

    def start(self, body):
        with self.lock:
            token = body.get('token')
            plan = self.plans.get(token) if isinstance(token, str) else None
            if not plan or plan['expires_at'] <= time.time():
                raise APIError(409, 'This review expired or was already used. Prepare a new review.')
            if body.get('confirmed') is not True or body.get('phrase', '') != plan['phrase']:
                raise APIError(400, 'Confirm this exact operation and type the requested phrase.')
            if plan['danger'] and plan['kind'] == 'disk' and body.get('backup_ack') is not True:
                raise APIError(400, 'Confirm that you have backed up everything you need from this disk.')
            if self.closed:
                raise APIError(503, 'Application is shutting down.')
            if not self.operation.acquire(blocking=False):
                raise APIError(409, 'Another operation is running. Wait for it to finish.')
            try:
                if plan['changes'] and not self.ready_to_change():
                    raise APIError(409, 'Wait for storage and application scans to finish before making changes.')
            except Exception:
                self.operation.release()
                raise
            del self.plans[token]  # One use, including failed revalidation or command execution.
            job = {'id': secrets.token_hex(12), 'title': plan['title'], 'kind': plan['kind'],
                   'status': 'running', 'started_at': time.time(), 'finished_at': None,
                   'output': '', 'error': ''}
            self.jobs = [*self.jobs[-19:], job]
            thread = threading.Thread(target=self._run, args=(plan, job),
                                      name='maintenance-job', daemon=False)
            try:
                thread.start()
            except Exception:
                self.jobs.remove(job)
                self.operation.release()
                raise
            return deepcopy(job)

    def _run(self, plan, job):
        output = []
        try:
            if plan['kind'] == 'brew':
                current = self.brew.plan(plan['request'])
                expected_commands = [] if plan['request'].get('preview_only') is True else current['commands']
                if (current['fingerprint'] != plan['fingerprint'] or expected_commands != plan['commands']
                        or current['preview'] != plan['preview']):
                    raise APIError(409, 'Homebrew packages, dependencies, or the command preview changed. Nothing was run. Refresh and review again.')
                if plan['preview']:
                    output.append(plan['preview'])
            if plan['kind'] == 'disk':
                current = disk_plan(plan['request'], self.disks())
                if current['fingerprint'] != plan['fingerprint'] or current['commands'] != plan['commands']:
                    raise APIError(409, 'The disk identity or layout changed after review. Nothing was run. Refresh and review again.')
            for command in plan['commands']:
                runner = self.brew.runner if plan['kind'] == 'brew' else self.runner
                output.append(runner.text(command, timeout=1800 if plan['kind'] in ('disk', 'brew') else 600))
                with self.lock:
                    job['output'] = '\n\n'.join(output)[-24000:]
            with self.lock:
                job['status'] = 'succeeded'
                job['output'] = '\n\n'.join(output)[-24000:] or 'Operation completed successfully.'
        except Exception as exc:  # noqa: BLE001 - keep the job visible and always release its lock
            with self.lock:
                job['status'] = 'failed'
                job['error'] = str(exc) if isinstance(exc, APIError) else 'The operation failed unexpectedly. Check the current state before retrying.'
        finally:
            if plan['kind'] == 'brew':
                self.brew.invalidate()
            with self.lock:
                job['finished_at'] = time.time()
            self.operation.release()

    def open(self, action):
        if not isinstance(action, str) or action not in SHORTCUTS:
            raise APIError(400, 'Choose an available system settings shortcut.')
        title, args = SHORTCUTS[action]
        self.runner.run(['/usr/bin/open', *args])
        return {'ok': True, 'title': title}
