"""Authenticated loopback-only HTTP transport; no external services or uploads."""
import hmac
import http.cookies
import json
import logging
import os
from pathlib import Path
import secrets
import signal
import socket
import threading
import time
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from .service import APIError, CleanerService

WEB = Path(__file__).with_name('web')
ASSETS = {'/': ('index.html', 'text/html; charset=utf-8'),
          '/assets/overlays.js': ('overlays.js', 'text/javascript; charset=utf-8'),
          '/assets/app.js': ('app.js', 'text/javascript; charset=utf-8'),
          '/assets/controls.js': ('controls.js', 'text/javascript; charset=utf-8'),
          '/assets/totoro.svg': ('totoro.svg', 'image/svg+xml'),
          '/assets/mascot.png': ('mascot.png', 'image/png'),
          '/assets/icons.js': ('icons.js', 'text/javascript; charset=utf-8'),
          '/assets/styles.css': ('styles.css', 'text/css; charset=utf-8')}
MAX_BODY = 2_000_000
LOG = logging.getLogger(__name__)


class LocalServer(ThreadingHTTPServer):
    daemon_threads = True
    block_on_close = False
    request_queue_size = 16

    def __init__(self, service, port=0, idle_timeout=0):
        self.service = service
        self.token = secrets.token_urlsafe(32)
        self.last_activity = time.monotonic()
        self.idle_timeout = idle_timeout
        self._slots = threading.BoundedSemaphore(24)
        super().__init__(('127.0.0.1', port), Handler)
        self.origin = f'http://127.0.0.1:{self.server_port}'
        self.url = self.origin + '/?t=' + self.token
        # Cookie name includes the port so separate launches do not log each other out.
        self.cookie_name = f'mdc_{self.server_port}'

    def process_request(self, request, address):
        if not self._slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, address)
        except Exception:
            self._slots.release()
            raise

    def process_request_thread(self, request, address):
        try:
            super().process_request_thread(request, address)
        finally:
            self._slots.release()

    def get_request(self):
        connection, address = super().get_request()
        connection.settimeout(15)
        return connection, address


class Handler(BaseHTTPRequestHandler):
    server_version = 'MacDeepCleaner'
    sys_version = ''

    def log_message(self, *_args):
        pass  # URLs can contain launch credentials or personal filenames.

    def _send(self, status, body, content_type='application/json; charset=utf-8', headers=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=True).encode()
        elif isinstance(body, str):
            body = body.encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Content-Security-Policy', "default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, socket.timeout):
            pass

    def _cookie_ok(self):
        try:
            jar = http.cookies.SimpleCookie(self.headers.get('Cookie', ''))
            key = self.server.cookie_name
            return key in jar and hmac.compare_digest(jar[key].value, self.server.token)
        except (http.cookies.CookieError, TypeError):
            return False

    def _host_ok(self):
        hosts = self.headers.get_all('Host', [])
        return len(hosts) == 1 and hosts[0] == f'127.0.0.1:{self.server.server_port}'

    def _authorized(self):
        if not self._host_ok() or not self._cookie_ok():
            raise APIError(403, 'Session expired. Open Mac Deep Cleaner again or use its launch link.')
        origin = self.headers.get('Origin')
        if origin and origin != self.server.origin:
            raise APIError(403, 'This request must come from the local application.')
        if self.headers.get('Sec-Fetch-Site') == 'cross-site':
            raise APIError(403, 'Cross-site requests are blocked.')
        self.server.last_activity = time.monotonic()

    def do_GET(self):
        try:
            if not self._host_ok():
                raise APIError(403, 'Invalid local host.')
            url = urllib.parse.urlsplit(self.path)
            query = urllib.parse.parse_qs(url.query)
            if url.path == '/' and hmac.compare_digest(query.get('t', [''])[0], self.server.token):
                return self._send(303, '', 'text/plain', {'Location': '/', 'Set-Cookie': f'{self.server.cookie_name}={self.server.token}; HttpOnly; SameSite=Strict; Path=/'})
            self._authorized()
            if url.path == '/favicon.ico':
                return self._send(204, b'')
            if url.path in ASSETS:
                filename, kind = ASSETS[url.path]
                return self._send(200, (WEB / filename).read_bytes(), kind)
            service = self.server.service
            if url.path == '/api/state':
                return self._send(200, service.state())
            if url.path == '/api/apps':
                return self._send(200, service.apps())
            if url.path == '/api/biggest':
                return self._send(200, service.biggest())
            if url.path == '/api/icon':
                try:
                    app_id = int(query.get('id', ['-1'])[0])
                except ValueError:
                    raise APIError(400, 'Invalid application ID.')
                data = service.icon(app_id)
                if data:
                    return self._send(200, data, 'image/png')
            raise APIError(404, 'Not found.')
        except APIError as exc:
            self._send(exc.status, {'error': str(exc)})
        except Exception:
            LOG.exception('GET request failed')
            self._send(500, {'error': 'The local service could not complete this request. Retry or restart the application.'})

    def do_POST(self):
        try:
            self._authorized()
            if self.headers.get('Transfer-Encoding'):
                raise APIError(400, 'Chunked request bodies are not supported.')
            lengths = self.headers.get_all('Content-Length', [])
            if len(lengths) != 1 or not lengths[0].isdigit():
                raise APIError(400, 'A valid request length is required.')
            length = int(lengths[0])
            if length > MAX_BODY:
                raise APIError(413, 'Request is too large.')
            if self.headers.get_content_type() != 'application/json':
                raise APIError(415, 'Use application/json.')
            try:
                raw = self.rfile.read(length)
                if len(raw) != length:
                    raise ValueError('incomplete body')
                body = json.loads(raw)
            except (ValueError, UnicodeDecodeError, socket.timeout):
                raise APIError(400, 'Invalid JSON request.')
            if not isinstance(body, dict):
                raise APIError(400, 'The request must be a JSON object.')
            route = urllib.parse.urlsplit(self.path).path
            self._send(200, self.server.service.post(route, body))
        except APIError as exc:
            self._send(exc.status, {'error': str(exc)})
        except Exception:
            LOG.exception('POST request failed')
            self._send(500, {'error': 'The operation could not complete. Refresh the scan before trying again.'})


def create_server(args, settings, service=None):
    service = service or CleanerService(args, settings)
    server = LocalServer(service, args.port, getattr(args, 'idle_timeout', 0))
    try:
        if service.scanner is None:
            service.start_scan()
    except Exception:
        server.server_close()
        raise
    return server


def serve(args, settings, on_ready=None):
    server = create_server(args, settings)
    stopped = threading.Event()
    def shutdown(*_args):
        if not stopped.is_set():
            stopped.set()
            threading.Thread(target=server.shutdown, daemon=True).start()
    previous = {}
    if threading.current_thread() is threading.main_thread():
        for sig in (signal.SIGINT, signal.SIGTERM):
            previous[sig] = signal.signal(sig, shutdown)
    if server.idle_timeout:
        def idle_watch():
            while not stopped.wait(10):
                if time.monotonic() - server.last_activity > server.idle_timeout and not server.service.operation.locked():
                    shutdown()
        threading.Thread(target=idle_watch, daemon=True).start()
    if on_ready:
        on_ready(server)
    elif getattr(args, 'no_open', False):
        print(f'Mac Deep Cleaner: {server.url}', flush=True)
    if not getattr(args, 'no_open', False):
        webbrowser.open(server.url)
    try:
        server.serve_forever(poll_interval=0.3)
    finally:
        stopped.set()
        server.service.close()
        server.server_close()
        for sig, handler in previous.items():
            signal.signal(sig, handler)
