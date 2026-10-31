"""One fixed loopback origin; neither environment proxies nor redirects are allowed."""
import json
import urllib.error
import urllib.request

BASE = 'http://127.0.0.1:11434'


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('Ollama redirects are refused. Only 127.0.0.1 is allowed.')


def open_local(path, body=None, method=None, timeout=8):
    if path not in ('/api/version', '/api/tags', '/api/chat', '/api/pull', '/api/delete', '/api/generate'):
        raise ValueError('Unsupported local Ollama endpoint.')
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    data = None if body is None else json.dumps(body).encode('utf-8')
    request = urllib.request.Request(BASE + path, data, {'Content-Type': 'application/json'}, method=method)
    return opener.open(request, timeout=timeout)


def local_json(path, body=None, method=None, timeout=8):
    with open_local(path, body, method, timeout) as response:
        raw = response.read(1_000_001)
    if len(raw) > 1_000_000:
        raise ValueError('Ollama returned too much data.')
    value = json.loads(raw)
    if not isinstance(value, dict) or value.get('error'):
        raise ValueError('Ollama did not return a valid response.')
    return value
