"""Exercise asset delivery through the real authenticated HTTP transport."""
import http.client
import threading
import unittest

from mac_deep_cleaner.server import LocalServer


class WebAssetsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # These tests serve static assets only; never start a scanner or cleanup.
        cls.server = LocalServer(service=None)
        cls.worker = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.worker.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.worker.join()

    def get(self, path, authenticated=True):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port)
        headers = {}
        if authenticated:
            headers['Cookie'] = f'{self.server.cookie_name}={self.server.token}'
        try:
            connection.request('GET', path, headers=headers)
            response = connection.getresponse()
            return response.status, response.getheader('Content-Type'), response.read()
        finally:
            connection.close()

    def test_shared_icon_and_favicon_deliver_same_png(self):
        status, kind, icon = self.get('/assets/app_icon.png')
        self.assertEqual(status, 200)
        self.assertEqual(kind, 'image/png')
        self.assertTrue(icon.startswith(b'\x89PNG\r\n\x1a\n'))
        self.assertEqual(self.get('/favicon.ico'), (status, kind, icon))

    def test_dashboard_references_the_shared_icon(self):
        status, _, html = self.get('/')
        self.assertEqual(status, 200)
        self.assertIn(b'href="/assets/app_icon.png"', html)
        status, _, script = self.get('/assets/app.js')
        self.assertEqual(status, 200)
        self.assertIn(b'src="/assets/app_icon.png"', script)

    def test_assets_require_the_local_session(self):
        for path in ('/', '/assets/app_icon.png', '/favicon.ico', '/assets/styles.css'):
            with self.subTest(path=path):
                self.assertEqual(self.get(path, authenticated=False)[0], 403)

    def test_asset_directory_is_not_exposed(self):
        for path in ('/assets/', '/assets/../pyproject.toml', '/assets/__init__.py'):
            with self.subTest(path=path):
                self.assertEqual(self.get(path)[0], 404)


if __name__ == '__main__':
    unittest.main()
