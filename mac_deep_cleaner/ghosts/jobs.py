"""Bounded background work with progress, cancellation, and process ownership."""
import os
import signal
import subprocess
import tempfile
import threading
import time


class Cancelled(Exception):
    pass


class Job:
    def __init__(self):
        self.cancelled = threading.Event()
        self.lock = threading.RLock()
        self.state = {'step': '', 'msg': '', 'pct': None, 'done': True, 'error': '', 'cancelled': False}
        self.thread = None

    def snapshot(self):
        with self.lock:
            return dict(self.state)

    def check(self):
        if self.cancelled.is_set():
            raise Cancelled('Cancelled. Completed steps are retained; downloads can be resumed.')

    def progress(self, step, msg, pct=None):
        with self.lock:
            self.state.update(step=step, msg=msg, pct=None if pct is None else max(0, min(100, round(pct))))

    def start(self, work, finished=lambda: None):
        self.cancelled.clear()
        self.state = {'step': 'starting', 'msg': 'Starting…', 'pct': None, 'done': False, 'error': '', 'cancelled': False}
        def run():
            try:
                work(self)
            except Cancelled as exc:
                with self.lock:
                    self.state.update(cancelled=True, msg=str(exc))
            except Exception as exc:  # noqa: BLE001 - background boundary must publish failure and release the operation lock
                with self.lock:
                    self.state['error'] = str(exc)[:400]
            finally:
                try:
                    finished()
                finally:
                    with self.lock:
                        self.state['done'] = True
        self.thread = threading.Thread(target=run, name='ghost-files-job', daemon=True)
        self.thread.start()
        return self.snapshot()

    def command(self, argv, env=None, timeout=120):
        self.check()
        with tempfile.TemporaryFile() as output:
            proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=output, stderr=output,
                                    env=env, start_new_session=True)
            deadline = time.monotonic() + timeout
            try:
                while proc.poll() is None:
                    self.check()
                    if time.monotonic() >= deadline:
                        raise TimeoutError('The setup command timed out.')
                    self.cancelled.wait(0.15)
                output.seek(0)
                text = output.read(20000).decode('utf-8', 'replace')
                if proc.returncode:
                    raise RuntimeError(f'{os.path.basename(argv[0])} failed: {text[-1200:]}')
                return text
            finally:
                if proc.poll() is None:
                    os.killpg(proc.pid, signal.SIGTERM)
                    try:
                        proc.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        os.killpg(proc.pid, signal.SIGKILL)
                        proc.wait(timeout=3)
