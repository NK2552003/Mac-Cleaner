"""Bounded, asynchronous checks against this project's stable GitHub releases."""
import json
import re
import threading
import time
import urllib.error
import urllib.request
from copy import deepcopy

from . import __version__

RELEASES = 'https://github.com/NK2552003/Mac-Cleaner/releases'
API = 'https://api.github.com/repos/NK2552003/Mac-Cleaner/releases/latest'


def version(value):
    match = re.fullmatch(r'v?(\d+)\.(\d+)\.(\d+)', value or '')
    return tuple(map(int, match.groups())) if match else None


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError('unexpected redirect')


class Updates:
    def __init__(self, notify=lambda *args: None):
        self.lock = threading.Lock()
        self.notify = notify
        self.result = {'checking': False, 'checked_at': 0, 'available': False,
                       'current': __version__, 'latest': '', 'url': RELEASES, 'error': ''}

    def report(self):
        with self.lock:
            return deepcopy(self.result)

    def start(self):
        with self.lock:
            if self.result['checking']:
                return deepcopy(self.result)
            self.result.update(checking=True, error='')
        threading.Thread(target=self.check, name='github-release-check', daemon=True).start()
        return self.report()

    def check(self):
        result = {'available': False, 'latest': '', 'url': RELEASES, 'error': ''}
        try:
            request = urllib.request.Request(API, headers={
                'Accept': 'application/vnd.github+json', 'User-Agent': 'Mac-Deep-Cleaner/' + __version__,
                'X-GitHub-Api-Version': '2022-11-28'})
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
            with opener.open(request, timeout=15) as response:
                raw = response.read(1_000_001)
            if len(raw) > 1_000_000:
                raise ValueError('oversized release')
            release = json.loads(raw)
            tag = release.get('tag_name')
            latest = version(tag)
            if not latest or release.get('draft') or release.get('prerelease'):
                raise ValueError('invalid stable release')
            result.update(latest=tag, available=latest > version(__version__),
                          url=RELEASES + '/tag/' + tag)
        except urllib.error.HTTPError as exc:
            result['error'] = 'No published releases yet.' if exc.code == 404 else 'Update check failed. Try again later.'
        except (OSError, ValueError, TypeError, AttributeError):
            result['error'] = 'Update check failed. Try again later.'
        with self.lock:
            previous = self.result.get('latest')
            self.result.update(result, checking=False, checked_at=time.time())
        if result['available'] and previous != result['latest']:
            self.notify('Update available', result['latest'])
