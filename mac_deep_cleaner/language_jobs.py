"""Background language generation, independent of any cleanup workspace."""
import threading
from copy import deepcopy
from .errors import APIError


class LanguageJobs:
    def __init__(self, service):
        self.service = service
        self.lock = threading.RLock()
        self.job = {"done": True, "error": "", "message": "", "result": None}
        self.thread = None

    def report(self):
        with self.lock:
            return deepcopy(self.job)

    def start(self, work):
        service = self.service
        if not service.operation.acquire(blocking=False):
            raise APIError(409, "Another operation is running.")
        try:
            if not service._ready_to_change():
                raise APIError(409, "Wait for scans to finish.")
            with self.lock:
                self.job = {"done": False, "error": "", "message": "Working…", "result": None}

            def run():
                try:
                    result = work()
                    with self.lock:
                        self.job["result"] = result
                except Exception as exc:  # noqa: BLE001 - publish background failures and release lock
                    with self.lock:
                        self.job["error"] = str(exc)[:1000]
                finally:
                    with self.lock:
                        service.operation.release()
                        self.job["done"] = True

            self.thread = threading.Thread(target=run, name="translation-job", daemon=False)
            self.thread.start()
        except Exception:
            service.operation.release()
            raise
        return {"started": True}

    def progress(self, text):
        with self.lock:
            self.job["message"] = text

    def generate(self, body):
        from .localization import generate
        return self.start(lambda: generate(
            body.get("locale"), body.get("key", ""), self.progress, body.get("confirmed")))
