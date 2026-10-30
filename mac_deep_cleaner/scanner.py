"""Read-only storage discovery."""

from concurrent.futures import ThreadPoolExecutor
import glob
import hashlib
import json
import os
import plistlib
import re
import shlex
import shutil
import sys
import threading
import time
from .catalog import ART, BUNDLE_SKIP, CAT_NAMES, DEFAULT_KEEP, GRADLE_FILES, MEDIA_BUNDLES, SKIP_DIRS, SPECS
from .cleanup import eligible
from .common import CAUTION, DAY, HOME, IS_MAC, NOW, RISKY, SAFE, WORKERS, c, dir_size, expand, is_readonly, newest_mtime, norm, run
from .models import Item
from .common import fingerprint
from pathlib import Path

class Scanner:
    def __init__(self, large_mb=50, old_days=180, dup_min_mb=1, quiet=False, deep_cloud=True, pinned=()):
        self.items = []
        self._nid = 0
        self.log = []                 # every progress message, for the UI
        self.pinned = set(pinned) | {str(Path(__file__).resolve().parent.parent)}
        if getattr(sys, "frozen", False):
            bundle = next((p for p in Path(sys.executable).parents if p.suffix == ".app"), None)
            if bundle:
                self.pinned.add(str(bundle))     # paths the user chose to keep out of every scan
        self.walk_files = []          # raw file list of the home walk (used by 'biggest files')
        self.app_meta = {}            # app path -> Info.plist facts
        self.seen = set()
        self.lock = threading.RLock()
        self.large = large_mb * 1_000_000
        self.old_days = old_days
        self.dup_min = int(dup_min_mb * 1_000_000)
        self.quiet = quiet
        self.progress = "starting"
        self.done = False
        self.error = ""
        self.cancelled = threading.Event()
        self.apps_ready = threading.Event()
        self.started_at = time.time()
        self.managed_total = 0
        self.gradle_pins = {"ndk": {}, "gradle": {}}
        self.installed = []     # (name, bundle_id, path)
        self.running = set()
        self.pool = ThreadPoolExecutor(max_workers=WORKERS)

    # ---- plumbing -------------------------------------------------------------
    def say(self, msg):
        self.progress = msg
        self.log.append((time.time(), msg))
        if not self.quiet:
            print(c(f"  - {msg}", "2"), file=sys.stderr, flush=True)

    def add(self, **kw):
        path = kw.get("path", "")
        with self.lock:
            key = (kw.get("action", "trash"), path or kw.get("cmd", ""))
            if path and path in self.seen:
                return None
            if path and self.pinned and any(path == p or path.startswith(p + os.sep) for p in self.pinned):
                return None
            if path:
                self.seen.add(path)
            kw.setdefault("fingerprint", fingerprint(path) if path else ())
            if kw.get("keep"):
                kw.setdefault("keeper_fingerprint", fingerprint(kw["keep"]))
            it = Item(id=self._nid, **kw)
            self._nid += 1
            if path and os.path.exists(path):
                it.readonly = is_readonly(path)
            self.items.append(it)
            return it

    # ---- main entry -------------------------------------------------------------
    def run(self):
        try:
            return self._run()
        except Exception as exc:
            self.error = f"Scan interrupted: {exc}"
            self.say(self.error)
            return self.items
        finally:
            self.apps_ready.set()
            self.done = True

    def close(self):
        self.cancelled.set()
        self.pool.shutdown(wait=False, cancel_futures=True)

    def _run(self):
        t0 = time.time()
        self.say("reading installed apps and running processes")
        self.load_apps()
        self.apps_ready.set()
        self.say("scanning known locations (caches, logs, SDKs, creative tools)")
        self.scan_trash()
        self.say("walking your home folder once (large files, duplicates, project artifacts)")
        walk = self.walk_home()
        self.walk_files = walk["files"]
        self.say("checking Gradle / NDK pins from your real projects")
        self.parse_gradle(walk["gradle"])
        self.scan_specs()
        self.say("analysing project artifacts")
        self.scan_artifacts(walk["artifacts"])
        self.say("finding large & old files")
        self.scan_binaries(walk["files"])
        self.scan_large(walk["files"], walk["bundles"])
        self.say("hashing duplicate candidates")
        self.scan_dups(walk["files"])
        self.say("downloads, screenshots & Docker")
        self.scan_downloads()
        self.scan_screenshots()
        self.scan_docker()
        self.say("app caches")
        self.scan_app_caches()
        self.say("unused apps and leftovers")
        self.scan_unused_apps()
        self.scan_leftovers()
        self.say("old IDE versions, orphaned simulators, snapshots, cloud files")
        self.scan_ide_versions()
        self.scan_simulators()
        self.scan_snapshots()
        self.scan_cloud()
        self.scan_media_and_managed()
        with self.lock:
            self.finalize()
        self.say(f"done in {time.time() - t0:.1f}s")
        return self.items

    # ---- apps / processes -----------------------------------------------------
    def load_apps(self):
        roots = ["/Applications", expand("~/Applications"), "/Applications/Utilities"]
        paths = []
        for r in roots:
            paths += glob.glob(os.path.join(r, "*.app"))
            if r != "/Applications/Utilities":
                paths += glob.glob(os.path.join(r, "*", "*.app"))      # vendor sub-folders
        seen = set()
        for p in sorted(paths):
            if p in seen or "/Utilities/" in p and p.count("/Utilities/") > 1:
                continue
            seen.add(p)
            info = {}
            try:
                with open(os.path.join(p, "Contents", "Info.plist"), "rb") as f:
                    info = plistlib.load(f)
            except Exception:
                pass
            bid = info.get("CFBundleIdentifier", "") or ""
            self.installed.append((os.path.basename(p)[:-4], bid, p))
            self.app_meta[p] = {
                "display": info.get("CFBundleDisplayName") or info.get("CFBundleName") or os.path.basename(p)[:-4],
                "version": str(info.get("CFBundleShortVersionString") or info.get("CFBundleVersion") or ""),
                "category": str(info.get("LSApplicationCategoryType") or ""),
                "icon": str(info.get("CFBundleIconFile") or ""),
                "mas": os.path.exists(os.path.join(p, "Contents", "_MASReceipt")),
            }
        out = run(["ps", "-axo", "comm="])
        for line in out.splitlines():
            m = re.search(r"/([^/]+)\.app/", line)
            if m:
                self.running.add(m.group(1).lower())

    # ---- ONE walk over $HOME ----------------------------------------------------
    def walk_home(self):
        res = {"files": [], "artifacts": [], "bundles": [], "gradle": []}
        tasks = []
        try:
            top = list(os.scandir(HOME))
        except OSError:
            top = []
        for e in top:
            try:
                if e.is_symlink():
                    continue
                if e.is_dir(follow_symlinks=False):
                    if e.name in SKIP_DIRS or e.name.startswith("."):
                        continue
                    try:
                        subs = list(os.scandir(e.path))
                    except OSError:
                        continue
                    tasks.append(("dir", e.path, False))      # artifacts / files directly in this dir
                    names = {x.name for x in subs}
                    for s in subs:
                        if s.is_symlink() or not s.is_dir(follow_symlinks=False):
                            continue
                        if s.name in SKIP_DIRS or s.name.startswith(".") and s.name not in ART:
                            continue
                        if s.name.endswith(BUNDLE_SKIP + MEDIA_BUNDLES) or self._is_artifact(s.path, s.name, names):
                            continue
                        tasks.append(("dir", s.path, True))
                elif e.is_file(follow_symlinks=False):
                    self._file(e, res)
            except OSError:
                pass
        futs = [self.pool.submit(self._walk_dir, p, recurse, res) for _, p, recurse in tasks]
        for f in futs:
            f.result()
        return res

    def _file(self, e, res):
        try:
            st = e.stat(follow_symlinks=False)
        except OSError:
            return
        if e.name in GRADLE_FILES:
            res["gradle"].append(e.path)
        if st.st_size >= min(self.dup_min, self.large):
            res["files"].append((e.path, st.st_blocks * 512, st.st_size, st.st_mtime, st.st_atime, st.st_ino, st.st_dev))

    def _is_artifact(self, path, name, siblings):
        if name not in ART:
            return False
        gates = ART[name][0]
        if gates is None:
            return True
        if gates == "VENV":
            return os.path.exists(os.path.join(path, "pyvenv.cfg"))
        return any(any(re.fullmatch(re.escape(g).replace(r"\*", ".*"), s) for s in siblings) for g in gates)

    def _walk_dir(self, root, recurse, res):
        """If recurse is False only look at the direct children of `root` (files + artifact dirs)."""
        stack = [root]
        local = {"files": [], "artifacts": [], "bundles": [], "gradle": []}
        first = True
        while stack:
            if self.cancelled.is_set():
                return
            d = stack.pop()
            try:
                entries = list(os.scandir(d))
            except OSError:
                continue
            names = {e.name for e in entries}
            for e in entries:
                if any(e.path == pin or e.path.startswith(pin + os.sep) for pin in self.pinned):
                    continue
                try:
                    if e.is_symlink():
                        continue
                    if e.is_dir(follow_symlinks=False):
                        n = e.name
                        if n in SKIP_DIRS and not (n in ART):
                            continue
                        if self._is_artifact(e.path, n, names):
                            local["artifacts"].append((e.path, n, d))
                            continue
                        if n.endswith(MEDIA_BUNDLES):
                            local["bundles"].append(e.path)
                            continue
                        if n.endswith(BUNDLE_SKIP):
                            continue
                        if recurse or not first:
                            stack.append(e.path)
                    elif e.is_file(follow_symlinks=False):
                        self._file(e, local)
                except OSError:
                    pass
            first = False
            if not recurse:
                break
        with self.lock:
            for k in res:
                res[k].extend(local[k])

    # ---- gradle pins ------------------------------------------------------------
    def parse_gradle(self, files):
        for f in files:
            try:
                with open(f, "r", errors="ignore") as fh:
                    txt = fh.read(200_000)
            except OSError:
                continue
            proj = os.path.dirname(f)
            for m in re.finditer(r"ndkVersion\s*=?\s*[\"']([\d.]+)[\"']", txt):
                self.gradle_pins["ndk"].setdefault(m.group(1), proj)
            for m in re.finditer(r"ndk\.dir\s*=\s*.*/ndk/([\d.]+)", txt):
                self.gradle_pins["ndk"].setdefault(m.group(1), proj)
            for m in re.finditer(r"gradle-([\d.]+)-(?:bin|all)\.zip", txt):
                self.gradle_pins["gradle"].setdefault(m.group(1), proj)

    # ---- fixed-path specs -------------------------------------------------------
    def scan_specs(self):
        jobs = []
        for sp in SPECS:
            if sp.root:
                paths = [sp.path] if os.path.exists(sp.path) else []
            else:
                paths = sorted(glob.glob(expand(sp.path)))
            for p in paths:
                jobs.append((sp, p))
        sizes = list(self.pool.map(lambda j: dir_size(j[1]), jobs))
        for (sp, p), sz in zip(jobs, sizes):
            if sz < max(sp.min_size, 1) and not (sp.protected and sz > 0):
                continue
            base = os.path.basename(p)
            name = sp.label or base
            if sp.label and "*" in sp.path and not sp.label.endswith(base):
                name = f"{sp.label}: {base}"
            safety, reason = sp.safety, sp.reason
            manual = False
            if sp.check in ("ndk", "gradle"):
                ver = re.search(r"(\d+\.\d+(?:\.\d+)*)", base)
                pin = self.gradle_pins[sp.check].get(ver.group(1)) if ver else None
                if pin:
                    safety, manual = RISKY, True
                    reason = f"PINNED: {sp.check.upper()} {ver.group(1)} is required by {pin}. " + reason
            action = "root" if sp.root else "trash"
            cmd = sp.cmd if sp.root else ""
            self.add(category=sp.cat, name=name, path=p, size=sz, safety=safety, reason=reason, regen=sp.regen,
                     action=action, cmd=cmd or (f"(alt) {sp.cmd}" if sp.cmd else ""), protected=sp.protected,
                     managed=sp.managed, manual=manual)

    # ---- trash ---------------------------------------------------------------------
    def scan_trash(self):
        t = os.path.join(HOME, ".Trash")
        try:
            n = len(os.listdir(t))
        except OSError:
            n = 0
        sz = dir_size(t)
        self.add(category="Trash", name=f"Trash ({n} item{'s' if n != 1 else ''})", path=t, size=sz, safety=SAFE,
                 reason="Already deleted by you; still using disk space.",
                 regen="Gone for good once emptied - check it first.", action="empty")

    # ---- project artifacts -------------------------------------------------------
    def scan_artifacts(self, arts):
        def work(a):
            path, name, parent = a
            return a, dir_size(path), self.project_mtime(parent, name)
        for (path, name, parent), sz, pm in self.pool.map(work, arts):
            if sz < 5_000_000:
                continue
            _, safety, regen = ART[name]
            gates = ART[name][0]
            if name in ("venv", "env", ".venv"):
                has_req = any(os.path.exists(os.path.join(parent, r)) for r in ("requirements.txt", "pyproject.toml", "Pipfile", "poetry.lock", "setup.py"))
                safety = SAFE if has_req else CAUTION
            active = (NOW - pm) < 14 * DAY
            reason = f"{name} inside '{os.path.basename(parent)}' - rebuildable project output."
            manual = False
            if active:
                safety, manual = CAUTION, True
                reason += " ACTIVE PROJECT (touched in the last 14 days): pick by hand."
            self.add(category="Developer & Pro Tools", name=f"{os.path.basename(parent)}/{name}", path=path, size=sz,
                     safety=safety, reason=reason, regen=regen, active_project=active, manual=manual, mtime=pm)

    def project_mtime(self, proj, skip):
        newest = 0
        try:
            for e in os.scandir(proj):
                if e.name in ART or e.name == skip:
                    continue
                newest = max(newest, e.stat(follow_symlinks=False).st_mtime)
        except OSError:
            pass
        for g in (".git/index", ".git/HEAD", ".git/logs/HEAD"):
            newest = max(newest, newest_mtime(os.path.join(proj, g)))
        return newest

    # ---- large & old -------------------------------------------------------------
    def scan_large(self, files, bundles):
        old_cut = NOW - self.old_days * DAY
        recent_cut = NOW - 30 * DAY
        for path, blocks, size, mtime, atime, ino, dev in files:
            if blocks < self.large:
                continue
            if path.startswith(os.path.join(HOME, "Downloads") + os.sep):
                continue      # Downloads has its own category
            is_old = max(mtime, atime) < old_cut
            ext = os.path.splitext(path)[1].lower()
            protected = ext in (".photoslibrary", ".musiclibrary") or "/Music/Music/" in path
            if mtime > recent_cut:
                safety, why = RISKY, "Modified in the last 30 days - you are probably using it."
            else:
                safety, why = CAUTION, "Large file."
            if is_old:
                why = f"Not touched for {int((NOW - max(mtime, atime)) / DAY)} days. Large file."
            if ext in (".dmg", ".iso", ".pkg", ".xip") and is_old:
                safety, why = SAFE, "Old installer/disk image."
            self.add(category="Large & Old Files", name=os.path.basename(path), path=path, size=blocks, safety=safety,
                     reason=why, regen="Not rebuildable - only restore from your backup or the original source.",
                     protected=protected, mtime=mtime)
        for b in bundles:
            sz = dir_size(b)
            if sz < self.large:
                continue
            lib = b.endswith((".photoslibrary", ".musiclibrary", ".tvlibrary", ".imovielibrary", ".fcpbundle"))
            self.add(category="Large & Old Files" if not lib else "Photos, Music & Media", name=os.path.basename(b), path=b,
                     size=sz, safety=RISKY, reason="Media/project library - holds originals." if lib else "Large bundle.",
                     regen="Not rebuildable.", protected=lib)

    # ---- duplicates --------------------------------------------------------------
    def scan_dups(self, files):
        by_size = {}
        seen_inodes = set()
        for f in files:
            path, blocks, size, mtime, atime, ino, dev = f
            if size < self.dup_min or (dev, ino) in seen_inodes:
                continue
            if "/node_modules/" in path:
                continue
            seen_inodes.add((dev, ino))
            by_size.setdefault(size, []).append(f)
        cands = [g for g in by_size.values() if len(g) > 1]

        def partial(f):
            try:
                with open(f[0], "rb") as fh:
                    h = hashlib.sha1(fh.read(65536))
                    if f[2] > 131072:
                        fh.seek(-65536, 2)
                        h.update(fh.read(65536))
                return h.hexdigest()
            except OSError:
                return None

        def full(f):
            try:
                h = hashlib.sha256()
                with open(f[0], "rb") as fh:
                    while True:
                        b = fh.read(1 << 20)
                        if not b:
                            break
                        h.update(b)
                return h.hexdigest()
            except OSError:
                return None

        flat = [f for g in cands for f in g]
        ph = dict(zip([f[0] for f in flat], self.pool.map(partial, flat)))
        stage2 = {}
        for g in cands:
            for f in g:
                p = ph.get(f[0])
                if p:
                    stage2.setdefault((f[2], p), []).append(f)
        stage2 = [g for g in stage2.values() if len(g) > 1]
        flat2 = [f for g in stage2 for f in g]
        fh = dict(zip([f[0] for f in flat2], self.pool.map(full, flat2)))
        final = {}
        for g in stage2:
            for f in g:
                h = fh.get(f[0])
                if h:
                    final.setdefault(h, []).append(f)
        n = 0
        for h, g in final.items():
            if len(g) < 2:
                continue
            n += 1
            sid = f"set{n}"
            g.sort(key=self._keeper_rank)
            keeper = g[0]
            for f in g[1:]:
                self.add(category="Duplicate Files", name=os.path.basename(f[0]), path=f[0], size=f[1], safety=CAUTION,
                         reason=f"Identical content (SHA-256) to the kept copy. Set {sid}, {len(g)} copies.",
                         regen=f"Identical copy kept at: {keeper[0]}", set_id=sid, keep=keeper[0], mtime=f[3])

    @staticmethod
    def _keeper_rank(f):
        p = f[0]
        penalty = 0
        for bad in ("/Downloads/", "/Desktop/", "/tmp/", "copy", " (1)", " 2."):
            if bad in p:
                penalty += 1
        return (penalty, f[3], len(p))

    # ---- additional scans ------------------------------------------------------------
    def scan_screenshots(self):
        d = os.path.join(HOME, "Desktop")
        pat = re.compile(r"^(Screenshot|Screen Shot|Screen Recording|CleanShot)\b", re.I)
        try:
            entries = list(os.scandir(d))
        except OSError:
            return
        for e in entries:
            try:
                if not pat.match(e.name) or not e.is_file(follow_symlinks=False):
                    continue
                st = e.stat(follow_symlinks=False)
            except OSError:
                continue
            sz, age = st.st_blocks * 512, (NOW - st.st_mtime) / DAY
            if sz < 200_000 or age < 7:
                continue
            self.add(category="Screenshots & Podcasts", name=e.name, path=e.path, size=sz, safety=CAUTION,
                     reason=f"Screenshot / recording left on the Desktop for {int(age)} days.",
                     regen="Not rebuildable - open it first if you still need it.", mtime=st.st_mtime)

    def scan_binaries(self, files):
        for path, blocks, size, mtime, atime, ino, dev in files:
            ext = os.path.splitext(path)[1].lower()
            if ext not in (".apk", ".aab", ".ipa") or blocks < 5_000_000:
                continue
            age = int((NOW - mtime) / DAY)
            self.add(category="Developer & Pro Tools", name=os.path.basename(path), path=path, size=blocks,
                     safety=SAFE if age > 60 else CAUTION, reason=f"Built app binary ({ext[1:]}) last changed {age} days ago.",
                     regen="Rebuild from source.", mtime=mtime)

    def scan_docker(self):
        pats = ["~/Library/Containers/com.docker.docker/Data/vms/*/data/Docker.raw",
                "~/Library/Containers/com.docker.docker/Data/vms/*/Docker.raw"]
        for pat in pats:
            for p in glob.glob(expand(pat)):
                try:
                    sz = os.stat(p).st_blocks * 512
                except OSError:
                    continue
                if sz < 100_000_000:
                    continue
                self.add(category="Developer & Pro Tools", name="Docker disk image (Docker.raw)", path="", size=sz, safety=CAUTION,
                         reason="Docker Desktop's VM disk. Pruning removes stopped containers, unused networks and dangling images; the file may need a Docker restart to shrink.",
                         regen="Images are pulled again when needed (volumes are NOT touched).",
                         action="cmd", cmd="docker system prune -f")

    def biggest(self, n=100):
        """Largest files across the home folder (including Downloads/Movies/Music/Pictures), largest first."""
        by_path = {i.path: i for i in self.items if i.path}
        parents = [i.path for i in self.items if i.path and eligible(i)]       # selectable folders: never list their insides twice
        out = []
        for path, blocks, size, mtime, atime, ino, dev in sorted(self.walk_files, key=lambda f: -f[1])[:n]:
            it = by_path.get(path)
            if it is None:
                if not os.path.exists(path) or any(i.keep and (path == i.keep or i.keep.startswith(path + os.sep)) for i in self.items):
                    continue
                if any(path.startswith(p + os.sep) for p in parents):
                    continue
                self.seen.discard(path)          # an earlier item for this file may have been folded into a protected parent
                recent = mtime > NOW - 30 * DAY
                it = self.add(category="Large & Old Files", name=os.path.basename(path), path=path, size=blocks,
                              safety=RISKY if recent else CAUTION,
                              reason="Modified in the last 30 days - you are probably using it." if recent
                              else f"Not changed for {int((NOW - mtime) / DAY)} days.",
                              regen="Not rebuildable - only restore from your backup or the original source.", mtime=mtime)
                if it is None:           # pinned or already claimed by another category
                    continue
            out.append(it)
        return out

    # ---- downloads -------------------------------------------------------------
    def scan_downloads(self):
        d = os.path.join(HOME, "Downloads")
        try:
            entries = list(os.scandir(d))
        except OSError:
            return
        for e in entries:
            try:
                st = e.stat(follow_symlinks=False)
            except OSError:
                continue
            age = (NOW - max(st.st_mtime, st.st_atime)) / DAY
            ext = os.path.splitext(e.name)[1].lower()
            installer = ext in (".dmg", ".pkg", ".mpkg", ".iso", ".xip")
            if not (installer or age > 90):
                continue
            sz = dir_size(e.path)
            if sz < 1_000_000:
                continue
            if installer and age > 30:
                safety, why = SAFE, f"Installer/disk image untouched for {int(age)} days - the app is already installed or can be re-downloaded."
            elif installer:
                safety, why = CAUTION, "Recent installer - you may still need it."
            else:
                safety, why = CAUTION, f"Download untouched for {int(age)} days."
            self.add(category="Downloads & Installers", name=e.name, path=e.path, size=sz, safety=safety, reason=why,
                     regen="Download it again from the original source.", mtime=st.st_mtime)

    # ---- app caches --------------------------------------------------------------
    def scan_app_caches(self):
        base = expand("~/Library/Caches")
        try:
            entries = [e for e in os.scandir(base) if e.is_dir(follow_symlinks=False)]
        except OSError:
            return
        sizes = list(self.pool.map(lambda e: dir_size(e.path), entries))
        for e, sz in zip(entries, sizes):
            if sz < 5_000_000 or e.path in self.seen:
                continue
            running = norm(e.name.split(".")[-1]) in {norm(r) for r in self.running}
            safety = CAUTION if running else SAFE
            why = "App cache - the app rebuilds it."
            if running:
                why = "App is running right now; quit it first, then this is safe."
            self.add(category="App Caches", name=e.name, path=e.path, size=sz, safety=safety, reason=why,
                     regen="The app recreates it (first launch after may be slower).")

    # ---- unused apps ---------------------------------------------------------
    def last_used(self, app):
        out = run(["mdls", "-name", "kMDItemLastUsedDate", "-raw", app], 10).strip() if IS_MAC else ""
        m = re.match(r"(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)", out)
        if m:
            try:
                return time.mktime(time.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")) - time.timezone
            except Exception:
                pass
        try:
            return os.stat(app).st_atime
        except OSError:
            return NOW

    def scan_unused_apps(self):
        apps = [a for a in self.installed if not a[1].startswith("com.apple.") and not a[2].startswith("/System")]
        lasts = list(self.pool.map(lambda a: self.last_used(a[2]), apps))
        sizes = list(self.pool.map(lambda a: dir_size(a[2]), apps))
        seen_names = {}
        for (name, bid, path), lu, sz in zip(apps, lasts, sizes):
            idle = (NOW - lu) / DAY
            if idle > 180 and name.lower() not in self.running and sz >= 1_000_000:
                self.add(category="Unused Apps & Leftovers", name=f"{name}.app", path=path, size=sz, safety=CAUTION,
                         reason=f"Not opened for {int(idle)} days (Spotlight last-used date).",
                         regen="Reinstall from the App Store / vendor website. Data in ~/Library is untouched.", mtime=lu)
            key = re.sub(r"[\s_-]*\d+(\.\d+)*$", "", name.lower())
            seen_names.setdefault(key, []).append((name, path, sz, lu))
        for key, lst in seen_names.items():     # duplicate installs / older copies
            if len(lst) > 1:
                lst.sort(key=lambda x: -x[3])
                for name, path, sz, lu in lst[1:]:
                    self.add(category="Unused Apps & Leftovers", name=f"{name}.app", path=path, size=sz, safety=CAUTION,
                             reason=f"Older copy of '{lst[0][0]}', which was used more recently.", regen="Reinstall the version you need.")

    def scan_leftovers(self):
        names = {norm(n) for n, _, _ in self.installed}
        bids = {b.lower() for _, b, _ in self.installed if b}
        brew = {norm(x) for x in (os.listdir("/opt/homebrew/Caskroom") if os.path.isdir("/opt/homebrew/Caskroom") else [])}
        roots = [expand("~/Library/Application Support"), expand("~/Library/Containers"), expand("~/Library/Group Containers")]
        cands = []
        for r in roots:
            try:
                cands += [e for e in os.scandir(r) if e.is_dir(follow_symlinks=False)]
            except OSError:
                pass

        def orphan(e):
            n = e.name
            nl = n.lower()
            if nl.startswith(("com.apple.", "group.com.apple.")) or nl in DEFAULT_KEEP or nl.startswith("."):
                return None
            if any(nl.startswith(k + ".") for k in DEFAULT_KEEP if k not in ("apple",)) and nl.startswith("com.apple"):
                return None
            rev = re.match(r"^(group\.)?[a-z0-9-]+\.[a-z0-9-]+\.", nl) is not None
            if rev:
                core = nl[len("group."):] if nl.startswith("group.") else nl
                if any(core == b or core.startswith(b) or b.startswith(core) for b in bids):
                    return None
                tail = norm(core.split(".")[-1])
                if tail in names or tail in brew or any(len(x) >= 4 and (x in tail or tail in x) for x in names):
                    return None
                return CAUTION
            nn = norm(n)
            if nn in names or nn in brew or any(len(x) >= 4 and (x in nn or nn in x) for x in names | brew):
                return None
            return RISKY

        orphans = [(e, orphan(e)) for e in cands]
        orphans = [(e, s) for e, s in orphans if s]
        sizes = list(self.pool.map(lambda x: dir_size(x[0].path), orphans))
        for (e, s), sz in zip(orphans, sizes):
            if sz < 5_000_000 or e.path in self.seen:
                continue
            why = ("No installed app owns this bundle identifier - data left behind by an uninstalled app."
                   if s == CAUTION else
                   "No installed app matches this name. It may belong to a CLI tool or something you still use - check before deleting.")
            self.add(category="Unused Apps & Leftovers", name=e.name, path=e.path, size=sz, safety=s, reason=why,
                     regen="Not rebuildable: settings/documents the app stored are lost.")

    # ---- IDE versions -----------------------------------------------------------
    def scan_ide_versions(self):
        patterns = ["~/Library/Application Support/JetBrains/*", "~/Library/Caches/JetBrains/*", "~/Library/Logs/JetBrains/*",
                    "~/Library/Application Support/Google/AndroidStudio*", "~/Library/Caches/Google/AndroidStudio*",
                    "~/Library/Logs/Google/AndroidStudio*"]
        groups = {}
        for pat in patterns:
            for p in glob.glob(expand(pat)):
                base = os.path.basename(p)
                m = re.match(r"^(.*?)(\d{4}\.\d+(?:\.\d+)?|\d+\.\d+(?:\.\d+)?)$", base)
                if m:
                    groups.setdefault((os.path.dirname(p), m.group(1)), []).append((tuple(int(x) for x in m.group(2).split(".")), p, base))
        for (parent, prod), lst in groups.items():
            if len(lst) < 2:
                continue
            lst.sort(reverse=True)
            for ver, p, base in lst[1:]:
                sz = dir_size(p)
                if sz >= 1_000_000:
                    self.add(category="Developer & Pro Tools", name=f"{base} (old IDE version)", path=p, size=sz, safety=CAUTION,
                             reason=f"Older version folder; newest installed settings are '{lst[0][2]}'.",
                             regen="The IDE can import settings from the newest version. Per-version plugins/settings here are lost.")

    def scan_simulators(self):
        if not IS_MAC or not shutil.which("xcrun"):
            return
        out = run(["xcrun", "simctl", "list", "devices", "unavailable", "-j"], 20)
        try:
            data = json.loads(out)
        except Exception:
            return
        total = 0
        base = expand("~/Library/Developer/CoreSimulator/Devices")
        n = 0
        for devs in data.get("devices", {}).values():
            for d in devs:
                p = os.path.join(base, d.get("udid", ""))
                if os.path.isdir(p):
                    total += dir_size(p)
                    n += 1
        if total > 1_000_000:
            self.add(category="System Data", name=f"Orphaned iOS simulators ({n})", path="", size=total, safety=SAFE,
                     reason="Simulators whose runtime is no longer installed - they can never boot.",
                     regen="Create new ones in Xcode if needed.", action="cmd", cmd="xcrun simctl delete unavailable")

    def scan_snapshots(self):
        if not IS_MAC or not shutil.which("tmutil"):
            return
        out = run(["tmutil", "listlocalsnapshotdates", "/"], 15)
        dates = [l.strip() for l in out.splitlines() if re.match(r"\d{4}-\d\d-\d\d-\d{6}", l.strip())]
        for dt in dates:
            self.add(category="System Data", name=f"Time Machine local snapshot {dt}", path="", size=0, safety=CAUTION,
                     reason="Local APFS snapshot kept by Time Machine (size is reclaimed lazily; macOS also thins these itself).",
                     regen="Time Machine makes a new one hourly while enabled.", action="root",
                     cmd=f"sudo tmutil deletelocalsnapshots {dt}")

    def scan_cloud(self):
        icloud = expand("~/Library/Mobile Documents/com~apple~CloudDocs")
        if os.path.isdir(icloud):
            for root, dirs, files in os.walk(icloud):
                for fn in files:
                    p = os.path.join(root, fn)
                    try:
                        st = os.lstat(p)
                    except OSError:
                        continue
                    if st.st_blocks * 512 >= self.large:
                        self.add(category="Cloud Files on This Mac", name=fn, path=p, size=st.st_blocks * 512, safety=SAFE,
                                 reason="Downloaded copy of an iCloud Drive file. Evicting keeps it in iCloud (Mac keeps a placeholder).",
                                 regen="Opening the file downloads it again.", action="evict", cmd=f"brctl evict {shlex.quote(p)}")
        for p in glob.glob(expand("~/Library/CloudStorage/*")):
            sz = dir_size(p)
            if sz > 100_000_000:
                self.add(category="Cloud Files on This Mac", name=os.path.basename(p), path=p, size=sz, safety=CAUTION,
                         reason="Synced provider folder. Use the provider's 'Online only / Free up space' option instead of deleting here.",
                         regen="Provider re-downloads on demand.", protected=True)

    def scan_media_and_managed(self):
        for p in glob.glob(expand("~/Pictures/*.photoslibrary")) + [expand("~/Music/Music"), expand("~/Movies")]:
            if os.path.exists(p) and p not in self.seen:
                sz = dir_size(p)
                if sz:
                    self.add(category="Photos, Music & Media", name=os.path.basename(p), path=p, size=sz, safety=RISKY,
                             reason="Your media. Protected - manage it from its own app.", regen="Not rebuildable.", protected=True)
        # macOS-managed user cache / temp dirs
        for key in ("DARWIN_USER_CACHE_DIR", "DARWIN_USER_TEMP_DIR"):
            d = run(["getconf", key]).strip() if IS_MAC else ""
            if d and os.path.isdir(d):
                sz = dir_size(d)
                if sz:
                    self.add(category="System Data", name=f"System-managed user {'cache' if 'CACHE' in key else 'temp'} ({d})",
                             path=d, size=sz, safety=CAUTION, reason="macOS and apps manage this themselves; this tool never deletes it.",
                             regen="Managed by macOS.", managed=True, protected=True)

    # ---- post-processing ---------------------------------------------------------
    def finalize(self):
        # drop nested duplicates: if a parent is also an item, keep the parent (never double count)
        paths = sorted((i.path for i in self.items if i.path and i.action in ("trash", "empty", "root", "evict")), key=len)
        parents = []
        drop = set()
        for it in sorted(self.items, key=lambda i: len(i.path)):
            if not it.path:
                continue
            if any(it.path.startswith(p + os.sep) for p in parents) and it.category not in ("Duplicate Files",):
                drop.add(it.id)
                continue
            parents.append(it.path)
        self.items = [i for i in self.items if i.id not in drop]
        for n, it in enumerate(self.items):
            it.id = n
            if not it.reason:
                it.reason = "-"
        # never offer a duplicate keeper or anything inside one of the kept paths
        keepers = {i.keep for i in self.items if i.keep}
        self.items = [i for i in self.items if not i.path or not any(k == i.path or k.startswith(i.path + os.sep) for k in keepers)]
        for n, it in enumerate(self.items):
            it.id = n
        self.items.sort(key=lambda i: (CAT_NAMES.index(i.category) if i.category in CAT_NAMES else 99, -i.size))
        for n, it in enumerate(self.items):
            it.id = n
        self._nid = len(self.items)
