"""Exercise Ghost routes through authenticated HTTP, with no host changes."""
import http.client
import json
import threading
from types import SimpleNamespace

import pytest

from mac_deep_cleaner import feature_config
from mac_deep_cleaner.ghosts import ollama_manager, ofrenda
from mac_deep_cleaner.scanner import Scanner
from mac_deep_cleaner.server import LocalServer
from mac_deep_cleaner.service import CleanerService


@pytest.fixture
def server(tmp_path, monkeypatch):
    monkeypatch.setattr(feature_config, 'CONFIG', tmp_path/'config.json')
    monkeypatch.setattr(ofrenda, 'LEDGER', tmp_path/'ofrenda.json')
    service = CleanerService(SimpleNamespace(), {'mode':'normal', 'min_mb':0, 'pinned':[]})
    service.scanner = Scanner(quiet=True)
    service.scanner.done = True
    local = LocalServer(service)
    worker = threading.Thread(target=local.serve_forever, daemon=True)
    worker.start()
    yield local
    local.shutdown()
    local.server_close()
    service.close()
    worker.join()


def request(server, path, body=None, **overrides):
    conn = http.client.HTTPConnection('127.0.0.1', server.server_port)
    headers = {'Content-Type':'application/json', 'Cookie':f'{server.cookie_name}={server.token}',
               'X-MDC-Token':server.token, 'Origin':server.origin}
    headers.update(overrides)
    headers = {k:v for k,v in headers.items() if v is not None}
    try:
        conn.request('GET' if body is None else 'POST', path,
                     body=None if body is None else json.dumps(body), headers=headers)
        response = conn.getresponse()
        data = response.read()
        return response.status, data, response.getheaders()
    finally:
        conn.close()


@pytest.mark.parametrize('bad', [{'X-MDC-Token':None}, {'X-MDC-Token':'bad'},
    {'Host':'evil.example'}, {'Origin':None}, {'Origin':'https://evil.example'}, {'Cookie':None}])
@pytest.mark.parametrize('route', ['/api/ghosts/config', '/api/ghosts/setup/run', '/api/ghosts/remove-ai', '/api/clean'])
def test_every_mutation_needs_host_origin_cookie_and_token(server, route, bad):
    assert request(server, route, {}, **bad)[0] == 403


def test_token_bootstrap_no_cors_and_lazy_routes(server):
    status, body, headers = request(server, '/')
    assert status == 200 and server.token.encode() in body
    assert b'__MDC_SESSION__' not in body
    assert b'src="/assets/ghosts.js"' not in body
    assert not any(k.lower() == 'access-control-allow-origin' for k,v in headers)
    assert request(server, '/api/ghosts/setup/status')[0] == 409
    assert request(server, '/api/ghosts/config', {'level':1})[0] == 200
    assert request(server, '/api/ghosts/state')[0] == 200
    assert request(server, '/api/ghosts/setup/status')[0] == 409


def test_setup_needs_per_step_consent_over_http(server, monkeypatch):
    monkeypatch.setattr(ollama_manager, 'setup_status', lambda m: {'state':'NOT_INSTALLED',
        'models':[], 'free_gb':40, 'catalog':ollama_manager.MODELS, 'install_method':'app'})
    assert request(server, '/api/ghosts/config', {'level':2})[0] == 200
    status, body, _ = request(server, '/api/ghosts/setup/run', {'consent':{}, 'install_method':'app'})
    assert status == 400
    assert 'Consent to each' in json.loads(body)['error']
    assert server.service._ghosts.manager is None
