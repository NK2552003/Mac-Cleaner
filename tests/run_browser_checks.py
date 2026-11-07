"""Run browser flows against fresh fixtures. Requires Playwright on NODE_PATH."""
import contextlib
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@contextlib.contextmanager
def fixture(name, marker, *args):
    marker = Path(marker)
    previous = marker.read_text() if marker.exists() else ''
    with open(f'/tmp/mdc-{name}-fixture.log', 'w') as log:
        process = subprocess.Popen([sys.executable, str(ROOT / 'tests' / f'{name}_fixture.py'), *args],
                                   cwd=ROOT, stdout=log, stderr=log)
        try:
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError(f'{name} fixture exited; inspect {log.name}')
                if marker.exists() and marker.read_text() != previous:
                    break
                time.sleep(.1)
            else:
                raise RuntimeError(f'{name} fixture did not start; inspect {log.name}')
            yield marker.read_text()
        finally:
            # Let fixture context managers remove their temporary data.
            process.send_signal(signal.SIGINT)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def main():
    checks = sys.argv[1:] or ['workspace', 'deletion', 'toolkit', 'homebrew', 'care', 'ghosts', 'localization', 'accessibility', 'progress']
    allowed = {'workspace', 'deletion', 'toolkit', 'homebrew', 'care', 'ghosts', 'localization', 'accessibility', 'progress'}
    for check in checks:
        if check not in allowed:
            raise SystemExit(f'Unknown check: {check}')
        with contextlib.ExitStack() as stack:
            if check != 'ghosts':
                args = ['--deletion'] if check == 'deletion' else []
                url = stack.enter_context(fixture('workspace', '/tmp/mdc-care-check/launch-url', *args))
                if check == 'care':
                    Path('/tmp/mdc-care-check/launch-url').write_text(url + '#care')
                if check in {'toolkit', 'homebrew'}:
                    marker = Path('/tmp/mdc-ui-check/launch-url')
                    marker.parent.mkdir(exist_ok=True)
                    marker.write_text(url + '#optimize')
            if check in {'ghosts', 'localization', 'progress'}:
                stack.enter_context(fixture('ghosts', '/tmp/mdc-ghost-check/launch-url'))
            print(f'Checking {check} with fresh fixtures', flush=True)
            subprocess.run(['node', str(ROOT / 'tests' / f'verify_{check}.cjs')], cwd=ROOT,
                           env=os.environ.copy(), check=True, timeout=240)


if __name__ == '__main__':
    main()
