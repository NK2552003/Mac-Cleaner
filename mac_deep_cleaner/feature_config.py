"""Feature switches only: safe to read without importing any optional feature."""
import copy
import json
import os
import tempfile
import threading
from pathlib import Path

CONFIG = Path.home() / '.config/mac-deep-cleaner/config.json'
LOCK = threading.RLock()
DEFAULT = {'level': 0, 'model': 'llama3.2:3b', 'auto_start_ollama': True,
           'stop_ollama_on_exit': True, 'setup': {'installed_by_mdc': None,
           'started_by_mdc': False, 'start_consent': False, 'models_pulled_by_mdc': []}}
MODEL_IDS = ('llama3.2:1b', 'llama3.2:3b', 'gemma3:4b')


def read_document():
    try:
        value = json.loads(CONFIG.read_text(encoding='utf-8'))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def read_config():
    result = copy.deepcopy(DEFAULT)
    value = read_document().get('ghosts', {})
    if not isinstance(value, dict):
        return result
    if type(value.get('level')) is int and value['level'] in (0, 1, 2):
        result['level'] = value['level']
    if value.get('model') in MODEL_IDS:
        result['model'] = value['model']
    for key in ('auto_start_ollama', 'stop_ollama_on_exit'):
        if type(value.get(key)) is bool:
            result[key] = value[key]
    if isinstance(value.get('setup'), dict):
        setup = value['setup']
        for key in ('started_by_mdc', 'start_consent', 'model_selected'):
            if type(setup.get(key)) is bool:
                result['setup'][key] = setup[key]
        if setup.get('installed_by_mdc') in ('brew', 'app'):
            path, identity = setup.get('installed_path'), setup.get('installed_identity')
            if isinstance(path, str) and os.path.isabs(path) and isinstance(identity, list) and len(identity) == 5 and all(type(n) is int for n in identity):
                result['setup'].update(installed_by_mdc=setup['installed_by_mdc'], installed_path=path, installed_identity=identity)
        models = setup.get('models_pulled_by_mdc', [])
        if isinstance(models, list):
            result['setup']['models_pulled_by_mdc'] = list(dict.fromkeys(m for m in models if isinstance(m, str) and m in MODEL_IDS))
        digests = setup.get('model_digests', {})
        if isinstance(digests, dict):
            result['setup']['model_digests'] = {m: d for m, d in digests.items() if m in MODEL_IDS and isinstance(d, str)}
    return result


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            json.dump(value, handle, indent=2, ensure_ascii=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def update_config(changes, internal=False):
    from .errors import APIError
    allowed = {'level', 'model', 'auto_start_ollama', 'stop_ollama_on_exit'}
    if internal:
        allowed.add('setup')
    if not isinstance(changes, dict) or set(changes) - allowed:
        raise APIError(400, 'Unknown Ghost Files setting.')
    if 'level' in changes and (type(changes['level']) is not int or changes['level'] not in (0, 1, 2)):
        raise APIError(400, 'Ghost Files level must be 0, 1, or 2.')
    if 'model' in changes and changes['model'] not in MODEL_IDS:
        raise APIError(400, 'Choose a supported local model.')
    for key in ('auto_start_ollama', 'stop_ollama_on_exit'):
        if key in changes and type(changes[key]) is not bool:
            raise APIError(400, key + ' must be true or false.')
    with LOCK:
        config = read_config()
        config.update(changes)
        document = read_document()
        document['ghosts'] = config
        try:
            atomic_json(CONFIG, document)
        except OSError as exc:
            raise APIError(500, 'Could not save Ghost Files settings.') from exc
        return config
