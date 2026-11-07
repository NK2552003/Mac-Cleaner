"""Version 3.5 workspace: reviewed tools, local history, and storage insights."""

import html
import secrets
import shutil
import threading
import time
from copy import deepcopy
from pathlib import Path

from . import __version__, review_tools, scheduler
from .errors import APIError
from .feature_config import atomic_json
from .history import History
from .profiles import PROFILES, load_rules, profile_items, rules_file, validate_rules


class Care:
    def __init__(self, service):
        self.service = service
        self.history = History()
        self.lock = threading.RLock()
        self.plans = {}
        self.job = {"done": True, "error": "", "message": "", "result": None}
        self.inventory = None
        self.media = None
        self.thread = None
        self.cancelled = threading.Event()

    def report(self):
        with self.lock:
            return {
                "profiles": PROFILES,
                "history": self.history.records(),
                "samples": self.history.sample(shutil.disk_usage(Path.home())),
                "schedule": scheduler.status(),
                "rules": load_rules(),
                "job": deepcopy(self.job),
                "inventory": deepcopy(self.inventory),
                "media": deepcopy(self.media),
                "map": [
                    {"path": f[0], "name": Path(f[0]).name, "size": f[1], "mtime": f[3]}
                    for f in sorted(
                        getattr(self.service.scanner, "walk_files", []), key=lambda f: -f[1]
                    )[:120]
                ],
                "allowlist": self.service.settings.get("ghost_allowlist", []),
            }

    def start(self, work):
        service = self.service
        if not service.operation.acquire(blocking=False):
            raise APIError(409, "Another operation is running.")
        try:
            if not service._ready_to_change():
                raise APIError(409, "Wait for scans to finish.")
            self.cancelled.clear()
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

            self.thread = threading.Thread(target=run, name="care-job", daemon=False)
            self.thread.start()
        except Exception:
            service.operation.release()
            raise
        return {"started": True}

    def progress(self, text):
        with self.lock:
            self.job["message"] = text

    def prepare(self, body):
        action = body.get("action")
        params = {}
        if action == "startup":
            if type(body.get("enabled")) is not bool:
                raise APIError(400, "Choose enable or disable.")
            item = next(
                (
                    i
                    for i in review_tools.startup_items()
                    if i["path"] == body.get("path") and i["editable"]
                ),
                None,
            )
            if not item:
                raise APIError(400, "Choose a user startup item from the inventory.")
            params = {"item": item, "enabled": body["enabled"]}
            summary = (
                ("Enable " if body["enabled"] else "Disable ")
                + item["label"]
                + " for future launches. Currently running processes continue until logout."
            )
        elif action == "slim":
            item = next(
                (
                    i
                    for i in (self.inventory or {}).get("apps", [])
                    if i["path"] == body.get("path")
                ),
                None,
            )
            if not item:
                raise APIError(400, "Inspect applications first, then choose an app.")
            keep = body.get("keep", [])
            if not isinstance(keep, list) or any(
                not isinstance(k, str) or len(k) > 40 for k in keep
            ):
                raise APIError(400, "Choose languages to retain.")
            params = {"item": item, "keep": keep}
            summary = (
                "Create a separate copy of "
                + item["name"]
                + " in Downloads. Keep English, Base, and "
                + ", ".join(keep)
                + "; remove other languages and non-native CPU slices. The copy is ad-hoc signed: notarization, updates, and entitlements may stop working. Test the copy; the installed app stays unchanged. A failed operation may leave a partial copy in Downloads."
            )
        elif action == "schedule":
            if type(body.get("enabled")) is not bool:
                raise APIError(400, "Choose enable or disable.")
            params = {k: body[k] for k in ("enabled", "weekday", "hour") if k in body}
            scheduler.definition(params.get("weekday", 0), params.get("hour", 10))
            summary = (
                "Enable weekly cleanup: only regular files directly inside ~/Library/Caches and ~/Library/Logs untouched for 7 days; at most 500 files / 2 GB per run, moved to Trash with history and a notification. No Trash emptying. Runs at the chosen local time, or after wake if the scheduled time was missed."
                if params["enabled"]
                else "Disable and remove the Mac Deep Cleaner weekly launch agent."
            )
        else:
            raise APIError(400, "Unknown review action.")
        token = secrets.token_urlsafe(32)
        with self.lock:
            self.plans = {k: v for k, v in self.plans.items() if v["expires"] > time.time()}
            if len(self.plans) >= 20:
                self.plans.pop(next(iter(self.plans)))
            self.plans[token] = {
                "action": action,
                "params": deepcopy(params),
                "expires": time.time() + 300,
            }
        return {"token": token, "summary": summary, "action": action}

    def post(self, route, body):
        if route == "/api/care/language/import":
            from .localization import save_pack

            return self.start(lambda: save_pack(body))
        if route == "/api/care/language/generate":
            from .localization import generate

            return self.start(
                lambda: generate(
                    body.get("locale"), body.get("key", ""), self.progress, body.get("confirmed")
                )
            )
        if route == "/api/care/plan":
            return self.prepare(body)
        if route == "/api/care/run":
            if body.get("confirmed") is not True or not isinstance(body.get("token"), str):
                raise APIError(400, "Confirm the reviewed operation.")
            with self.lock:
                plan = self.plans.pop(body["token"], None)
            if not plan or plan["expires"] < time.time():
                raise APIError(409, "Review expired. Prepare it again.")
            handlers = {
                "startup": review_tools.startup_change,
                "slim": review_tools.slim_copy,
                "schedule": scheduler.configure,
            }
            return self.start(lambda: handlers[plan["action"]](**plan["params"]))
        if route == "/api/care/profile":
            with self.service.lock, self.service.scanner.lock:
                self.service._version(body)
                return {
                    "ids": [
                        i.id for i in profile_items(self.service.scanner.items, body.get("profile"))
                    ]
                }
        if route == "/api/care/restore":
            if not isinstance(body.get("id"), str):
                raise APIError(400, "Choose a history entry.")

            def restore():
                result = self.history.restore(body["id"])
                with self.service.lock:
                    self.service.revision += 1
                return result

            return self.start(restore)
        if route == "/api/care/inventory":
            installed = list(getattr(self.service.scanner, "installed", []))

            def inspect():
                value = {
                    "startup": review_tools.startup_items(),
                    "browsers": review_tools.browser_extensions(),
                    "apps": review_tools.slimming_inventory(installed),
                }
                with self.lock:
                    self.inventory = value
                return {
                    "message": "Inventory refreshed. Modern login items are managed in System Settings → General → Login Items."
                }

            return self.start(inspect)
        if route == "/api/care/media":
            with self.service.scanner.lock:
                files = list(self.service.scanner.walk_files)

            def compare():
                from .media import scan

                result = scan(files, self.cancelled, self.progress)
                with self.lock:
                    self.media = result
                return {
                    "message": "Similarity analysis finished; review candidate pairs individually."
                }

            return self.start(compare)
        if route == "/api/care/browser":
            return review_tools.open_extensions(body.get("browser"))
        if route == "/api/care/rules":
            document = validate_rules(body)
            return self.start(
                lambda: (
                    atomic_json(rules_file(), document),
                    {"message": "Rules saved. Rescan to discover matching files."},
                )[1]
            )
        if route == "/api/care/allowlist/remove":
            from .settings import save_settings

            path = body.get("path")

            def remove():
                with self.service.lock:
                    updated = {
                        **self.service.settings,
                        "ghost_allowlist": [
                            p for p in self.service.settings.get("ghost_allowlist", []) if p != path
                        ],
                    }
                    if not save_settings(updated):
                        raise APIError(500, "Could not save the allowlist.")
                    self.service.settings = updated
                    if path not in updated.get("pinned", []):
                        self.service.scanner.pinned.discard(path)
                return {
                    "message": "Allowlist updated. Scan Ghost Files again to reconsider this location."
                }

            return self.start(remove)
        raise APIError(404, "Unknown Care operation.")


def export_html(items, disk, include_paths=False, locale="en"):
    """Standalone printable report in the selected interface language."""
    from .localization import item_name, load_pack, translate

    pack = load_pack(locale)
    def text(message, **values):
        return html.escape(translate(message, locale, **values))

    rows = []
    for item in sorted(items, key=lambda i: (-i.size, i.name)):
        fields = [translate(item.category, locale), item_name(item, locale), f"{item.size / 1e6:.2f} MB",
                  translate(item.safety.title(), locale), translate(item.reason, locale)]
        if include_paths:
            fields.append(item.path)
        rows.append("<tr>" + "".join("<td>" + html.escape(str(v)) + "</td>" for v in fields) + "</tr>")
    headers = ['Category', 'Name', 'Size', 'Risk', 'Explanation'] + (['Path'] if include_paths else [])
    heading = ''.join('<th>' + text(label) + '</th>' for label in headers)
    space = text('{free} GB free of {total} GB', free=f'{disk.free / 1e9:.2f}', total=f'{disk.total / 1e9:.2f}')
    privacy = text('Full paths included.' if include_paths else 'Full paths omitted; filenames may still be personal. Review before sharing.')
    return f"""<!doctype html><html lang="{html.escape(pack['locale'])}" dir="{pack.get('direction', 'ltr')}"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{text('Mac Deep Cleaner report')}</title>
<style>body{{font:15px system-ui;max-width:1100px;margin:40px auto;padding:20px;color:#182522}}table{{width:100%;border-collapse:collapse}}th,td{{padding:12px;text-align:start;border-bottom:1px solid #ccc;overflow-wrap:anywhere}}@media print{{body{{margin:0;font-size:10px}}thead{{display:table-header-group}}tr{{break-inside:avoid}}}}</style>
<h1>Mac Deep Cleaner v{__version__}</h1><p>{text('Storage review')} · {time.strftime('%Y-%m-%d %H:%M')} · {space}</p><p>{text('Findings are review candidates, not removal recommendations. Categories may overlap. Trash still occupies disk space.')} {privacy} {text('Use your browser’s Print → Save as PDF to create a PDF.')}</p><table><thead><tr>{heading}</tr></thead><tbody>{''.join(rows)}</tbody></table></html>"""
