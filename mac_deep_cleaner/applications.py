"""Installed application and associated data analysis."""

import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from .common import WORKERS, fingerprint
from .common import CAUTION, HOME, RISKY, SAFE, dir_size, expand
from .models import AppInfo, AppPart, Item

APP_PART_RULES = [
    ("Caches", "cache", "Caches", "id"),
    ("HTTP storage", "cache", "HTTPStorages", "id"),
    ("WebKit data", "cache", "WebKit", "id"),
    ("Logs", "cache", "Logs", "name"),
    ("Saved window state", "cache", "Saved Application State", "state"),
    ("Application Support", "data", "Application Support", "name"),
    ("Sandbox container", "data", "Containers", "id"),
    ("Group container", "data", "Group Containers", "group"),
    ("App scripts", "data", "Application Scripts", "id"),
    ("Launch agents", "data", "LaunchAgents", "plist"),
    ("Preferences", "prefs", "Preferences", "plist"),
    ("Cookies", "prefs", "Cookies", "cookie"),
]


APP_CATEGORY = {
    "developer-tools": "Developer", "graphics-design": "Graphics & Design", "photography": "Photography",
    "video": "Video", "music": "Music", "productivity": "Productivity", "business": "Business",
    "utilities": "Utilities", "social-networking": "Social", "games": "Games", "entertainment": "Entertainment",
    "education": "Education", "finance": "Finance", "lifestyle": "Lifestyle", "news": "News", "reference": "Reference",
    "medical": "Health", "healthcare-fitness": "Health", "weather": "Weather", "travel": "Travel", "sports": "Sports",
}


APPLE_KEEP = {"com.apple.Safari", "com.apple.finder", "com.apple.systempreferences"}


def human_category(raw):
    m = re.search(r"app-category\.(?:games\.)?([a-z-]+)$", raw or "")
    return APP_CATEGORY.get(m.group(1), "") if m else ""


class AppAnalyzer:
    """Sizes every installed app and finds the data it keeps in ~/Library (matched by bundle id, never by guesswork)."""

    def __init__(self, scanner):
        self.sc = scanner
        self.apps = []
        self.progress = 0
        self.total = 0
        self.done = False
        self.error = ""
        self.lock = threading.Lock()

    def _index(self):
        lib = expand("~/Library")
        idx = {}
        for _, _, folder, _ in APP_PART_RULES:
            if folder in idx:
                continue
            try:
                idx[folder] = os.listdir(os.path.join(lib, folder))
            except OSError:
                idx[folder] = []
        return idx

    @staticmethod
    def _match(mode, entry, bid, names, longer):
        e = entry.lower()
        if any(e == lg or e.startswith(lg + ".") for lg in longer):      # belongs to a more specific app
            return False
        if mode == "id":
            return bool(bid) and (e == bid or e.startswith(bid + "."))
        if mode == "name":
            return e in names or (bool(bid) and (e == bid or e.startswith(bid + ".")))
        if mode == "state":
            return bool(bid) and e == bid + ".savedstate"
        if mode == "plist":
            return bool(bid) and e.endswith(".plist") and (e == bid + ".plist" or e.startswith(bid + "."))
        if mode == "cookie":
            return bool(bid) and e == bid + ".binarycookies"
        if mode == "group":
            return bool(bid) and (e == bid or e == "group." + bid or e.endswith("." + bid))
        return False

    def analyze_one(self, rec, idx, all_bids):
        name, bid, path = rec
        meta = self.sc.app_meta.get(path, {})
        b = bid.lower()
        names = {name.lower(), meta.get("display", name).lower()}
        longer = [o for o in all_bids if b and o != b and o.startswith(b + ".")]
        parts = []
        lib = expand("~/Library")
        for label, kind, folder, mode in APP_PART_RULES:
            for entry in idx.get(folder, []):
                if self._match(mode, entry, b, names, longer):
                    parts.append(AppPart(label, kind, os.path.join(lib, folder, entry)))
        for p in parts:
            p.fingerprint = fingerprint(p.path)
            p.size = dir_size(p.path)
        parts = [p for p in parts if p.size > 0]
        parts.sort(key=lambda p: -p.size)
        apple = b.startswith("com.apple.")
        in_apps = path.startswith("/Applications/") or path.startswith(HOME + "/Applications/")
        info = AppInfo(name=meta.get("display", name), path=path, bundle_id=bid, version=meta.get("version", ""),
                       category=human_category(meta.get("category", "")), source="App Store" if meta.get("mas") else "Direct",
                       size=dir_size(path), parts=parts, last_used=self.sc.last_used(path),
                       running=name.lower() in self.sc.running or os.path.basename(path)[:-4].lower() in self.sc.running,
                       fingerprint=fingerprint(path), apple=apple, removable=in_apps and bid not in APPLE_KEEP)
        with self.lock:
            self.progress += 1
        return info

    def run(self):
        try:
            return self._run()
        except Exception as exc:
            self.error = f"Application analysis interrupted: {exc}"
            return []
        finally:
            self.done = True

    def _run(self):
        if not self.sc.installed:
            self.sc.load_apps()
        recs = list(self.sc.installed)
        self.total = len(recs)
        idx = self._index()
        all_bids = {b.lower() for _, b, _ in recs if b}
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            apps = list(pool.map(lambda r: self.analyze_one(r, idx, all_bids), recs))
        apps.sort(key=lambda a: -a.total)
        for n, a in enumerate(apps):
            a.id = n
        self.apps = apps
        self.done = True
        return apps


def app_items(app, mode="caches", picked=None):
    """Turn an app (or a chosen subset of its parts) into ready-to-run cleanup items.

    mode: caches    -> caches, logs and window state only (always safe)
          uninstall -> the app bundle plus everything it stored
          pick      -> exactly the paths in `picked` (bundle path and/or part paths)
    """
    out = []

    def mk(label, path, size, safety, why, regen):
        out.append(Item(id=len(out), category="Applications", name=label, path=path, size=size, safety=safety,
                        reason=why, regen=regen, selected=True,
                        fingerprint=app.fingerprint if path == app.path else next((p.fingerprint for p in app.parts if p.path == path), ())))

    want = set(picked or [])
    if mode == "uninstall" or (mode == "pick" and app.path in want):
        if app.removable:
            mk(f"{app.name}.app", app.path, app.size, CAUTION, "The application itself.",
               "Reinstall from the App Store or the vendor website.")
    for p in app.parts:
        if mode == "caches" and p.kind != "cache":
            continue
        if mode == "pick" and p.path not in want:
            continue
        if p.kind == "cache":
            mk(f"{app.name}: {p.label.lower()}", p.path, p.size, SAFE, "Rebuilt by the app.", "The app recreates it.")
        elif p.kind == "prefs":
            mk(f"{app.name}: {p.label.lower()}", p.path, p.size, CAUTION, "Settings the app saved.", "Settings reset to defaults.")
        else:
            mk(f"{app.name}: {p.label.lower()}", p.path, p.size, CAUTION if mode == "uninstall" else RISKY,
               "Documents, accounts or settings the app stored.", "Not rebuildable - sign-ins and local data are lost.")
    return out
