"""Bridge Ghost Files to the existing versioned scanner and cleanup service."""
from dataclasses import replace

from ..common import fingerprint
from ..errors import APIError
from ..feature_config import read_config, update_config
from .finder import Ghost, find_ghosts
from .haunt import fallback
from .jobs import Job
from .rules import RANK


class GhostController:
    def __init__(self, service):
        self.service = service
        self.entries = {}
        self.originals = {}
        self.hidden = set()
        self.unlocked = set()
        self.warnings = []
        self.scan_id = ''
        self.scan_job, self.haunt_job, self.setup_job = Job(), Job(), Job()
        self.manager = None
        self.status = None

    def ai_manager(self):
        if self.manager is None:
            from .ollama_manager import OllamaManager
            self.manager = OllamaManager()
        return self.manager

    def close(self):
        for job in (self.scan_job, self.haunt_job, self.setup_job):
            job.cancelled.set()
        if self.manager:
            self.manager.stop()

    def reset(self):
        sc = self.service.scanner
        if sc:
            with sc.lock:
                existing = {i.id for i in sc.items}
                sc.items[:] = [self.originals.get(i.id, i) for i in sc.items
                               if i.id not in self.entries or i.id in self.originals]
                sc.seen = {i.path for i in sc.items if i.path}
                # Never restore entries already removed by cleanup.
                assert all(i.id in existing for i in sc.items)
        self.entries.clear()
        self.originals.clear()
        self.unlocked.clear()
        if hasattr(self, '_icons'):
            self._icons.clear()
        self.hidden.clear()
        self.scan_id = ''

    def report(self):
        service = self.service
        with service.lock:
            live = {i.id for i in service.scanner.items}
            if self.scan_id != service.scan_id:
                entries = []
            else:
                entries = [{**g.to_dict(), 'id': identifier, **out,
                            'hidden': identifier in self.hidden, 'unlocked': identifier in self.unlocked}
                           for identifier, (g, out) in self.entries.items() if identifier in live]
            from .ofrenda import records
            return {'ghosts': entries, 'scan_id': service.scan_id, 'revision': service.revision,
                    'scanned': self.scan_id == service.scan_id, 'scan': self.scan_job.snapshot(),
                    'haunt': self.haunt_job.snapshot(), 'setup': self.setup_job.snapshot(),
                    'warnings': self.warnings, 'ai': self.status, 'ofrenda': records()}

    def run_job(self, job, work, require_ready=True):
        service = self.service
        if not service.operation.acquire(blocking=False):
            raise APIError(409, 'Another operation is running. Wait for it to finish.')
        try:
            if service.closed or (require_ready and not service._ready_to_change()):
                raise APIError(409, 'Wait for the storage scan and application analysis to finish.')
            return job.start(work, service.operation.release)
        except Exception:
            service.operation.release()
            raise

    def scan(self):
        service = self.service
        def work(job):
            warnings = []
            job.progress('scan', 'Comparing installed apps with Library leftovers…')
            ghosts = find_ghosts(warnings=warnings, cancelled=job.cancelled)
            job.check()
            with service.lock, service.scanner.lock:
                self.reset()
                self.warnings = list(dict.fromkeys(warnings)) + [
                    'Only standard application folders were checked. Apps on other drives or in custom folders may still own these files.']
                for ghost in ghosts:
                    if any(service._under(ghost.path, p) or service._under(p, ghost.path)
                           for p in service.scanner.pinned):
                        continue
                    if not ghost.identity or fingerprint(ghost.path) != ghost.identity:
                        continue
                    item = next((i for i in service.scanner.items if i.path == ghost.path), None)
                    if item and (item.protected or item.managed or item.action != 'trash' or item.keep):
                        continue
                    if item:
                        self.originals[item.id] = replace(item)
                    else:
                        item = service.scanner.add(path=ghost.path, name=ghost.name_guess,
                            size=ghost.size_bytes, fingerprint=ghost.identity, action='trash')
                    if item is None:
                        continue
                    self.entries[item.id] = (ghost, fallback(ghost))
                    self.apply(item, self.entries[item.id][1])
                self.scan_id = service.scan_id
                service.revision += 1
            job.progress('scan', f'{len(self.entries)} ghosts ready for review.', 100)
        return self.run_job(self.scan_job, work)

    @staticmethod
    def apply(item, output):
        verdict = output['final_verdict']
        item.category = 'Ghost Files'
        item.safety = {'keep': 'risky', 'review': 'caution', 'likely_safe': 'safe'}[verdict]
        item.manual = True  # Every ghost is individually reviewed, even from Cleanup.
        item.protected = verdict == 'keep'
        item.selected = False
        item.reason = output['reason']

    def check_selection(self, chosen, permanent, body):
        """Apply to EVERY cleanup entry point, including application and parent items."""
        overlaps = []
        for item in chosen:
            for identifier, (ghost, output) in self.entries.items():
                if self.service._under(item.path, ghost.path) or self.service._under(ghost.path, item.path):
                    if item.path != ghost.path:
                        raise APIError(409, 'This selection overlaps a ghost. Review the individual ghost in Ghost Files first.')
                    if output['final_verdict'] == 'keep' and identifier not in self.unlocked:
                        raise APIError(409, 'This ghost is locked. Review and unlock it in Ghost Files first.')
                    overlaps.append(identifier)
        if overlaps:
            if permanent:
                raise APIError(400, 'Ghost Files can only be moved to the Trash.')
            reviewed = body.get('ghost_reviewed_ids', [])
            if body.get('ghost_review_confirmed') is not True or not isinstance(reviewed, list) or any(
                    type(i) is not int for i in reviewed) or not set(overlaps).issubset(reviewed):
                raise APIError(400, 'Review these ghosts in Ghost Files before banishing them.')

    def removed(self, paths):
        from .ofrenda import remember
        ghosts = [g for g, _out in self.entries.values() if g.path in paths]
        warning = ''
        if ghosts:
            try:
                remember(ghosts)
            except OSError:
                warning = 'Files reached Trash, but the Ofrenda could not be saved.'
            removed = {i for i, (g, _) in self.entries.items() if g.path in paths}
            for identifier in removed:
                self.entries.pop(identifier, None)
                self.originals.pop(identifier, None)
                self.unlocked.discard(identifier)
        return warning

    def narrate(self, body):
        if read_config()['level'] != 2:
            raise APIError(409, 'Enable Ghosts + AI before requesting narration.')
        if self.scan_id != self.service.scan_id:
            raise APIError(409, 'Scan for ghosts first.')
        rest = body.get('rest', False)
        if type(rest) is not bool:
            raise APIError(400, 'rest must be true or false.')
        model = read_config()['model']
        live = {i.id for i in self.service.scanner.items}
        entries = [(i, g) for i, (g, out) in self.entries.items()
                   if i in live and i not in self.hidden and (out['source'] != 'ai' or out.get('model') != model)]
        batch = entries if rest else entries[:25]
        def work(job):
            from .haunt import narrate
            from .ollama_manager import setup_status
            config = read_config()
            self.status = setup_status(config['model'])
            if (self.status['state'] == 'INSTALLED_NOT_RUNNING' and config['auto_start_ollama']
                    and config['setup'].get('start_consent') is True):
                self.ai_manager().start_server(job)
                self.status = setup_status(config['model'])
            if self.status['state'] != 'READY':
                job.progress('haunt', 'Showing plain descriptions. Set up AI narration to continue.', 100)
                return
            def receive(ghost, output):
                with self.service.lock, self.service.scanner.lock:
                    identifier = next(i for i, g in batch if g.path == ghost.path)
                    # A subsequent model pass must not relax an earlier veto.
                    previous = self.entries[identifier][1]['final_verdict']
                    output['final_verdict'] = min((previous, output['final_verdict']), key=RANK.__getitem__)
                    output['model'] = config['model']
                    self.entries[identifier] = (ghost, output)
                    self.unlocked.discard(identifier)
                    item = next(i for i in self.service.scanner.items if i.id == identifier)
                    self.apply(item, output)
                    self.service.revision += 1
            narrate([g for _, g in batch], config['model'], job, receive)
        return self.run_job(self.haunt_job, work)

    def setup(self, body):
        from .ollama_manager import save_setup, setup_status
        if read_config()['level'] != 2:
            raise APIError(409, 'Choose Ghosts + AI first.')
        consent = body.get('consent')
        if not isinstance(consent, dict) or set(consent) - {'install', 'start', 'pull'} or any(type(v) is not bool for v in consent.values()):
            raise APIError(400, 'Explicit per-step consent is required.')
        model = body.get('model', read_config()['model'])
        from ..feature_config import MODEL_IDS
        if model not in MODEL_IDS:
            raise APIError(400, 'Choose a supported local model.')
        status = setup_status(model)
        if status.get('port_conflict'):
            raise APIError(409, 'Port 11434 is occupied by an unrecognized server. Resolve that before setting up AI.')
        needed = {'install': status['state'] == 'NOT_INSTALLED',
                  'start': status['state'] in ('NOT_INSTALLED', 'INSTALLED_NOT_RUNNING'),
                  'pull': model not in status['models']}
        if any(required and consent.get(step) is not True for step, required in needed.items()):
            raise APIError(400, 'Consent to each required install, start, and model download step before continuing.')
        if needed['install'] and body.get('install_method') != status['install_method']:
            raise APIError(409, 'The installation method changed. Review setup again.')
        required_gb = next(m['approx_gb'] for m in status['catalog'] if m['id'] == model) * 1.5 + 1
        if needed['pull'] and status['free_gb'] < required_gb:
            raise APIError(409, f'This model needs at least {required_gb:.1f} GB free. Stay with Ghosts without AI.')
        def work(job):
            from .llm import haunt_one, unload_model
            manager = self.ai_manager()
            update_config({'model': model})
            save_setup(model_selected=True)
            try:
                if needed['install']:
                    job.progress('install', 'Installing Ollama using ' + status['install_method'] + '…')
                    manager.install(job, status['install_method'])
                if consent.get('start') is True:
                    save_setup(start_consent=True)
                if needed['start']:
                    job.progress('start', 'Starting Ollama on 127.0.0.1…')
                    manager.start_server(job)
                if needed['pull']:
                    job.progress('pull', 'Downloading ' + model + '…')
                    manager.pull(model, job)
                job.check()
                job.progress('test', 'Testing narration with a fictional ghost…')
                try:
                    sample = haunt_one(Ghost('', 'Caches', 'org.example.lantern', 'Lantern', 1024, 31, 'high'), model)
                finally:
                    unload_model(model)
                job.check()
                with job.lock:
                    job.state['sample'] = sample['haunting']
                self.status = setup_status(model)
                job.progress('ready', 'AI narration is ready on this Mac.', 100)
            except Exception:
                update_config({'level': 1})
                manager.stop()
                raise
        return self.run_job(self.setup_job, work, require_ready=False)

    def get(self, route):
        if route == '/api/ghosts/state' or route == '/api/ghosts/haunt/status':
            return self.report()
        if route == '/api/ghosts/setup/progress':
            return self.setup_job.snapshot()
        if route == '/api/ghosts/setup/status':
            if read_config()['level'] != 2:
                raise APIError(409, 'AI detection runs only in Ghosts + AI mode.')
            from .ollama_manager import setup_status
            self.status = setup_status(read_config()['model'])
            return self.status
        if route == '/api/ghosts/ofrenda':
            from .ofrenda import markdown
            return {'markdown': markdown()}
        raise APIError(404, 'Unknown Ghost Files route.')

    def icon(self, ghost_id):
        if not hasattr(self, '_icons'):
            self._icons = {}
        if ghost_id in self._icons:
            return self._icons[ghost_id]
        entry = self.entries.get(ghost_id)
        if not entry:
            return None
        ghost = entry[0]
        from ..icons import ghost_icon
        data = ghost_icon(ghost.path, ghost.bundle_id, ghost.name_guess)
        self._icons[ghost_id] = data
        return data

    def post(self, route, body):
        if route == '/api/ghosts/scan':
            return self.scan()
        if route == '/api/ghosts/haunt':
            return self.narrate(body)
        if route == '/api/ghosts/setup/run':
            return self.setup(body)
        if route in ('/api/ghosts/setup/cancel', '/api/ghosts/haunt/cancel', '/api/ghosts/scan/cancel'):
            job = {'setup': self.setup_job, 'haunt': self.haunt_job, 'scan': self.scan_job}[route.split('/')[3]]
            job.cancelled.set()
            return job.snapshot()
        if route == '/api/ghosts/remove-ai':
            if body.get('confirmed') is not True:
                raise APIError(400, 'Confirm removal of the listed AI components.')
            if type(body.get('uninstall', False)) is not bool:
                raise APIError(400, 'uninstall must be true or false.')
            # Validate the entire request BEFORE removing anything.
            setup = read_config()['setup']
            models = body.get('models', [])
            if not isinstance(models, list) or any(not isinstance(m, str) or m not in setup.get('models_pulled_by_mdc', []) for m in models):
                raise APIError(400, 'Only models pulled by Mac Deep Cleaner may be removed.')
            if body.get('uninstall') and setup.get('installed_by_mdc') not in ('brew', 'app'):
                raise APIError(400, 'Mac Deep Cleaner did not install Ollama.')
            if not models and not body.get('uninstall'):
                raise APIError(400, 'Select a component to remove.')
            return self.run_job(self.setup_job, lambda job: self.ai_manager().remove(body, job))
        if route in ('/api/ghosts/unlock', '/api/ghosts/hide'):
            if not self.service.operation.acquire(blocking=False):
                raise APIError(409, 'Wait for the current operation to finish.')
            try:
                with self.service.lock, self.service.scanner.lock:
                    self.service._version(body)
                    identifier = body.get('id')
                    if type(identifier) is not int or identifier not in self.entries:
                        raise APIError(400, 'Choose a current ghost.')
                    if route.endswith('/unlock'):
                        if body.get('confirmed') is not True:
                            raise APIError(400, 'Confirm that you reviewed this locked ghost.')
                        self.unlocked.add(identifier)
                        item = next((i for i in self.service.scanner.items if i.id == identifier), None)
                        if item is None:
                            raise APIError(409, 'This ghost is no longer in the current scan.')
                        item.protected = False
                        self.service.revision += 1
                    else:
                        self.hidden.add(identifier)
                    return {'ok': True}
            finally:
                self.service.operation.release()
        if route == '/api/ghosts/show-hidden':
            self.hidden.clear()
            return {'ok': True}
        raise APIError(404, 'Unknown Ghost Files operation.')
