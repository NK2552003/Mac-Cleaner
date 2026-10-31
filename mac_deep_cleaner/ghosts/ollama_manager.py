"""Consent-driven Ollama lifecycle. Own only the process and artifacts we create."""
import os
import re
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

from ..common import fingerprint
from ..errors import APIError
from ..feature_config import MODEL_IDS, read_config, update_config
from .local_http import local_json, open_local

HOST = '127.0.0.1:11434'
DOWNLOAD_URL = 'https://ollama.com/download/Ollama-darwin.zip'
# Ollama Inc.; also published by Installomator's ollama label. Fail closed on rotation.
TEAM_ID = '3MU9H2V9Y9'
MODELS = [{'id': i, 'label': label, 'approx_gb': size, 'min_ram_gb': ram}
          for i, label, size, ram in zip(MODEL_IDS, ('Light', 'Balanced', 'Richer'),
                                         (1.3, 2.0, 3.4), (4, 8, 8))]
APP_TARGET = Path.home() / 'Applications/Ollama.app'
CANDIDATE_BINS = ['/opt/homebrew/bin/ollama', '/usr/local/bin/ollama',
                  '/Applications/Ollama.app/Contents/Resources/ollama',
                  str(APP_TARGET / 'Contents/Resources/ollama')]


def find_binary():
    return next((p for p in [shutil.which('ollama')] + CANDIDATE_BINS
                 if p and os.path.isfile(p) and os.access(p, os.X_OK)), None)


def system_info():
    try:
        ram = int(subprocess.check_output(['/usr/sbin/sysctl', '-n', 'hw.memsize'],
                  stderr=subprocess.DEVNULL, timeout=3)) / 2**30
    except (OSError, ValueError, subprocess.SubprocessError):
        ram = 0
    free = shutil.disk_usage(Path.home()).free / 1e9
    return {'ram_gb': round(ram, 1), 'free_gb': round(free, 1),
            'recommended_model': 'llama3.2:1b' if ram < 8 else 'llama3.2:3b'}


def model_records():
    value = local_json('/api/tags', timeout=1.5).get('models')
    if not isinstance(value, list) or any(not isinstance(m, dict) or
            not isinstance(m.get('name'), str) or not isinstance(m.get('digest'), str) for m in value):
        raise ValueError('Port 11434 did not return an Ollama model list.')
    return {m['name']: m['digest'] for m in value}


def setup_status(model):
    binary, version, models, error = find_binary(), None, {}, ''
    conflict = False
    try:
        version = local_json('/api/version', timeout=0.7).get('version')
        if not isinstance(version, str) or not re.fullmatch(r'\d+\.\d+\.\d+[\w.+-]*', version):
            raise ValueError('Port 11434 is not a recognized Ollama server.')
        models = model_records()
    except (OSError, ValueError) as exc:
        version = None
        conflict = isinstance(exc, (ValueError, urllib.error.HTTPError))
        error = str(exc) if isinstance(exc, ValueError) else 'Ollama is not responding on 127.0.0.1:11434.'
    state = ('READY' if model in models else 'RUNNING_NO_MODEL') if version else (
        'INSTALLED_NOT_RUNNING' if binary else 'NOT_INSTALLED')
    remote = os.environ.get('OLLAMA_HOST', '')
    warning = ('OLLAMA_HOST is ignored. Ghost Files always uses 127.0.0.1:11434.' if remote else '')
    return {'state': state, 'binary': binary, 'version': version, 'models': list(models),
            'catalog': MODELS, 'install_method': 'brew' if shutil.which('brew') else 'app',
            'warning': warning, 'error': error, 'port_conflict': conflict, **system_info()}


def save_setup(**changes):
    setup = read_config()['setup']
    setup.update(changes)
    update_config({'setup': setup}, internal=True)


class OllamaManager:
    def __init__(self):
        self.process = None  # A Popen owned by this instance, never a persisted/reused PID.

    def start_server(self, job):
        status = setup_status(read_config()['model'])
        if status['version']:
            return
        if status.get('port_conflict'):
            raise APIError(409, 'Port 11434 is occupied by an unrecognized server. No process was stopped.')
        if self.process is not None and self.process.poll() is None:
            raise APIError(409, 'The Ollama process started by Mac Deep Cleaner is not responding yet.')
        binary = find_binary()
        if not binary:
            raise APIError(409, 'Install Ollama before starting it.')
        job.check()
        # Never launch the GUI app: its process/server ownership is ambiguous.
        env = {**os.environ, 'OLLAMA_HOST': HOST, 'OLLAMA_NO_CLOUD': '1',
               'OLLAMA_ORIGINS': 'http://127.0.0.1'}
        self.process = proc = subprocess.Popen([binary, 'serve'], env=env, start_new_session=True,
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        save_setup(started_by_mdc=True)
        for _ in range(50):
            job.check()
            if proc.poll() is not None:
                self.process = None
                save_setup(started_by_mdc=False)
                raise APIError(409, 'Ollama could not start. Port 11434 may be occupied; no existing process was stopped.')
            if setup_status(read_config()['model'])['version']:
                return
            job.cancelled.wait(0.3)
        self.stop(force=True)
        raise APIError(409, 'Ollama did not become ready. Try starting it manually.')

    def stop(self, force=False):
        if not force and not read_config()['stop_ollama_on_exit']:
            return
        if self.process is not None:
            if self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    # It is still our child; never signal a PID loaded from disk.
                    self.process.kill()
                    self.process.wait(timeout=5)
            self.process = None
            save_setup(started_by_mdc=False)

    def install(self, job, method):
        if find_binary():
            return  # Reuse without claiming ownership.
        if method == 'brew':
            brew = shutil.which('brew')
            if not brew:
                raise APIError(409, 'Homebrew changed. Review setup again.')
            job.command([brew, 'install', 'ollama'], env={**os.environ, 'HOMEBREW_NO_AUTO_UPDATE': '1',
                        'NONINTERACTIVE': '1'}, timeout=1800)
            binary = find_binary()
            if not binary:
                raise APIError(500, 'Homebrew completed but the Ollama binary was not found.')
            save_setup(installed_by_mdc='brew', installed_path=os.path.realpath(binary),
                       installed_identity=list(fingerprint(os.path.realpath(binary))))
            return
        if method != 'app':
            raise APIError(400, 'Choose the displayed install method.')
        if APP_TARGET.exists() or APP_TARGET.is_symlink():
            raise APIError(409, '~/Applications/Ollama.app already exists. It will not be overwritten.')
        APP_TARGET.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='mdc-ollama-') as temporary:
            archive = Path(temporary) / 'Ollama.zip'
            # This is the only non-loopback request, reachable only after install consent.
            with urllib.request.urlopen(DOWNLOAD_URL, timeout=20) as response, archive.open('wb') as output:
                if not response.geturl().startswith('https://'):
                    raise APIError(400, 'The Ollama download must use HTTPS.')
                total, done = int(response.headers.get('Content-Length') or 0), 0
                while True:
                    job.check()
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    done += len(chunk)
                    if done > 4_000_000_000:
                        raise APIError(400, 'Ollama download exceeded the installation limit.')
                    output.write(chunk)
                    job.progress('install', 'Downloading the official Ollama app…', done * 100 / total if total else None)
            # Reject path traversal and escaping symlinks before ditto extracts anything.
            with zipfile.ZipFile(archive) as zipped:
                if sum(x.file_size for x in zipped.infolist()) > 10_000_000_000:
                    raise APIError(400, 'Ollama archive expands beyond the installation limit.')
                for member in zipped.infolist():
                    path = Path(member.filename)
                    if path.is_absolute() or '..' in path.parts or '\\' in member.filename:
                        raise APIError(400, 'Unsafe path in Ollama archive.')
                    if (member.external_attr >> 16) & 0o170000 == 0o120000:
                        target = zipped.read(member).decode('utf-8')
                        resolved = os.path.normpath(str(path.parent / target))
                        if target.startswith('/') or resolved.startswith('../'):
                            raise APIError(400, 'Unsafe link in Ollama archive.')
            extracted = Path(temporary) / 'extracted'
            job.command(['/usr/bin/ditto', '-x', '-k', str(archive), str(extracted)])
            app = extracted / 'Ollama.app'
            job.command(['/usr/bin/codesign', '--verify', '--deep', '--strict', str(app)])
            signature = job.command(['/usr/bin/codesign', '-dv', '--verbose=4', str(app)])
            if f'TeamIdentifier={TEAM_ID}' not in signature.splitlines():
                raise APIError(400, 'Ollama signing identity did not match Ollama Inc. Installation stopped.')
            job.command(['/usr/sbin/spctl', '--assess', '--type', 'execute', str(app)])
            job.check()
            if APP_TARGET.exists() or APP_TARGET.is_symlink():
                raise APIError(409, 'Ollama appeared during setup; refusing to overwrite it.')
            shutil.move(str(app), str(APP_TARGET))
        save_setup(installed_by_mdc='app', installed_path=str(APP_TARGET),
                   installed_identity=list(fingerprint(str(APP_TARGET))))

    def pull(self, model, job):
        if model not in MODEL_IDS:
            raise APIError(400, 'Choose a supported local model.')
        existing = model_records()
        if model in existing:
            return
        size = next(m['approx_gb'] for m in MODELS if m['id'] == model)
        if system_info()['free_gb'] < size * 1.5 + 1:
            raise APIError(409, f'Downloading this model needs at least {size * 1.5 + 1:.1f} GB free. Use Ghosts without AI for now.')
        import json
        success = False
        with open_local('/api/pull', {'model': model, 'stream': True}, timeout=15) as response:
            while True:
                job.check()
                raw = response.readline(65537)
                if not raw:
                    break
                if len(raw) > 65536:
                    raise ValueError('Ollama returned an oversized progress event.')
                event = json.loads(raw)
                if event.get('error'):
                    raise APIError(400, str(event['error'])[:200])
                total, done = event.get('total'), event.get('completed')
                job.progress('pull', str(event.get('status', 'Downloading model'))[:160],
                             done * 100 / total if total and isinstance(done, (int, float)) else None)
                success = event.get('status') == 'success'
        records = model_records()
        if not success or model not in records:
            raise APIError(409, 'The model download did not finish. Retry to resume it.')
        setup = read_config()['setup']
        pulled = list(setup.get('models_pulled_by_mdc', []))
        if model not in pulled:
            pulled.append(model)
        digests = {**setup.get('model_digests', {}), model: records[model]}
        save_setup(models_pulled_by_mdc=pulled, model_digests=digests)

    def remove(self, body, job):
        setup = read_config()['setup']
        models = body.get('models', [])
        if not isinstance(models, list) or any(m not in setup.get('models_pulled_by_mdc', []) for m in models):
            raise APIError(400, 'Only models downloaded by Mac Deep Cleaner can be removed here.')
        for model in models:
            job.check()
            records = model_records()
            if model in records:
                if records[model] != setup.get('model_digests', {}).get(model):
                    raise APIError(409, 'This model changed outside Mac Deep Cleaner. Remove it in Ollama instead.')
                job.progress('remove', 'Removing ' + model, None)
                with open_local('/api/delete', {'model': model}, method='DELETE', timeout=15) as response:
                    response.read(65536)
            setup['models_pulled_by_mdc'] = [m for m in setup['models_pulled_by_mdc'] if m != model]
            setup.get('model_digests', {}).pop(model, None)
            save_setup(**setup)
        if body.get('uninstall') is True:
            method = setup.get('installed_by_mdc')
            if method not in ('brew', 'app'):
                raise APIError(400, 'This Ollama installation belongs to you and cannot be removed here.')
            path = setup.get('installed_path', '')
            if not path or list(fingerprint(path)) != setup.get('installed_identity'):
                raise APIError(409, 'Ollama changed since installation. Remove it yourself to avoid deleting another installation.')
            self.stop(force=True)
            if method == 'brew':
                brew = shutil.which('brew')
                if not brew or os.path.realpath(find_binary() or '') != path:
                    raise APIError(409, 'The Homebrew installation changed. Nothing was uninstalled.')
                job.command([brew, 'uninstall', 'ollama'], timeout=180)
            else:
                if path != str(APP_TARGET):
                    raise APIError(400, 'Unrecognized installation location.')
                from ..cleanup import execute
                from ..models import Item
                item = Item(path=path, name='Ollama', fingerprint=tuple(setup['installed_identity']), selected=True)
                _, _, failures = execute([item], log=lambda _line: None)
                if failures:
                    raise APIError(409, failures[0][1])
            save_setup(installed_by_mdc=None, installed_path=None, installed_identity=None)
        update_config({'level': 1})
