"""Read-only, explainable orphan discovery. Absence is evidence, never proof."""
import os
import plistlib
import re
import stat
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from ..common import fingerprint

LIB = Path.home() / 'Library'
LEFTOVER_DIRS = {name: LIB / directory for name, directory in (
    ('Application Support', 'Application Support'), ('Caches', 'Caches'),
    ('Preferences', 'Preferences'), ('Containers', 'Containers'),
    ('Group Containers', 'Group Containers'), ('Saved State', 'Saved Application State'),
    ('Logs', 'Logs'), ('HTTPStorages', 'HTTPStorages'))}
APP_DIRS = [Path('/Applications'), Path.home() / 'Applications', Path('/System/Applications'),
            Path('/System/Library/CoreServices')]
BUNDLE_RE = re.compile(r'(?:[A-Za-z0-9-]+\.){2,}[A-Za-z0-9-]+')
SUFFIXES = ('.savedState', '.plist', '.binarycookies', '.helper')
GENERIC = {'client', 'desktop', 'mac', 'macos', 'osx', 'app', 'helper', 'agent', 'main', 'gui', 'mas',
           'release', 'stable', 'electron', 'cli', 'launcher', 'updater', 'shipit', 'daemon', 'service', 'github', 'gitlab'}
TLDS = {'com', 'org', 'net', 'io', 'app', 'me', 'co', 'dev', 'ai', 'us', 'uk', 'de', 'fr', 'jp', 'cn', 'ru'}
KIND_HINT = {'Application Support': 'saved data and settings', 'Caches': 'temporary cache files',
             'Preferences': 'a preferences file', 'Containers': 'a sandboxed app container',
             'Group Containers': 'shared app-group data', 'Saved State': 'saved window state',
             'Logs': 'log files', 'HTTPStorages': 'saved network session data'}
ALIASES = {
    'com.microsoft.vscode': {'code'},
    'com.microsoft.vscodeinsiders': {'code - insiders'},
    'com.openai.chat': {'chatgpt', 'sky'},
    'com.google.chrome': {'chrome', 'google chrome', 'googleupdater'},
}

SYSTEM_PREFIXES = (
    'com.apple.', 'org.swift.', 'org.llvm.', 'org.webkit.', 'com.apple.dt.'
)

SYSTEM_DIRS = {
    'addressbook', 'callhistorydb', 'callhistorytransactions', 'crashreporter',
    'quick look', 'quicklook', 'cloudkit', 'accounts', 'accountsd', 'syncservices',
    'coredata', 'audio', 'bluetooth', 'wifi', 'coreservices', 'security', 'keychains',
    'sharing', 'sidecar', 'airdrop', 'knowledge', 'duet', 'biome', 'feedbackassistant',
    'diagnosticreports', 'systempolicy', 'screencapture', 'dock', 'finder', 'safari',
    'mail', 'messages', 'notes', 'reminders', 'photos', 'calendar', 'music',
    'podcasts', 'tv', 'news', 'stocks', 'voicememos', 'books', 'shortcuts',
    'freeform', 'weather', 'clock', 'calculator', 'maps', 'preview', 'textedit',
    'fontbook', 'terminal', 'activity monitor', 'console', 'disk utility',
    'keychain access', 'system settings', 'app store', 'applepersistence',
    'applepushservice', 'spotlight', 'metadata', 'mobileosinstall', 'containermanager',
    'notificationcenter', 'siri', 'assistant', 'cloudstorage', 'fileprovider',
    'bird', 'cloudd', 'identityservices', 'imagent', 'lsd', 'passd', 'pkd',
    'sharingd', 'softwareupdate', 'trustd', 'useractivityd', 'touchid'
}

KNOWN_TOOLS_AND_PACKAGES = {
    # Cloud, DevOps & Containers
    'cloud-code', 'cloudcode', 'docker', 'docker-desktop', 'containerd', 'podman',
    'colima', 'k3s', 'minikube', 'kubernetes', 'helm', 'kubectl', 'terraform',
    'ansible', 'pulumi', 'packer', 'vault', 'vagrant', 'consul', 'aws', 'awscli',
    'azure', 'az', 'gcloud', 'google-cloud-sdk', 'firebase', 'supabase', 'vercel',
    'netlify', 'cloudflare', 'cloudflared', 'ngrok', 'tailscale', 'wireguard',
    # Languages, Runtimes & Package Managers
    'git', 'github', 'gh', 'hub', 'git-lfs', 'subversion', 'mercurial',
    'node', 'nodejs', 'npm', 'npx', 'pnpm', 'yarn', 'nvm', 'deno', 'bun',
    'python', 'python3', 'pip', 'pipx', 'pipenv', 'pypa', 'poetry', 'virtualenvs',
    'virtualenv', 'venv', 'conda', 'miniconda', 'anaconda', 'mamba',
    'rust', 'rustup', 'cargo', 'rustc', 'go', 'golang', 'gopls',
    'ruby', 'gem', 'bundle', 'bundler', 'rbenv', 'rvm',
    'java', 'javac', 'jdk', 'jre', 'openjdk', 'oracle', 'corretto', 'temurin',
    'graalvm', 'maven', 'mvn', 'gradle', 'sbt', 'ant',
    'kotlin', 'scala', 'clojure', 'leiningen', 'groovy',
    'elixir', 'erlang', 'rebar3', 'mix', 'haskell', 'ghc', 'cabal', 'stack',
    'ocaml', 'opam', 'dune', 'racket', 'julia', 'perl', 'cpan', 'r',
    'dotnet', 'mono', 'nuget', 'powershell', 'pwsh',
    'php', 'composer', 'dart', 'flutter',
    'homebrew', 'brew', 'cask', 'mas', 'asdf', 'mise', 'proto', 'fnm', 'volta',
    # Editors, IDEs & Extensions
    'vscode', 'code', 'cursor', 'sublime text', 'sublime_text', 'sublimetext',
    'zed', 'fleet', 'eclipse', 'netbeans', 'atom', 'brackets', 'nova',
    'neovim', 'nvim', 'vim', 'emacs', 'nano', 'micro', 'helix',
    'xcode', 'simulator', 'instruments', 'lldb', 'gdb', 'cmake', 'ninja', 'meson',
    'clang', 'gcc', 'llvm', 'swig', 'protobuf', 'grpc',
    # AI & ML
    'ollama', 'llama', 'vllm', 'huggingface', 'torch', 'pytorch', 'tensorflow',
    'tensorboard', 'keras', 'onnx', 'cuda', 'antigravity', 'gemini', 'claude',
    'chatgpt', 'copilot', 'github-copilot', 'tabnine', 'codeium', 'openai',
    # Databases & Servers
    'postgres', 'postgresql', 'psql', 'mysql', 'mariadb', 'sqlite', 'sqlite3',
    'redis', 'mongodb', 'mongod', 'cassandra', 'elasticsearch', 'elastic',
    'kafka', 'rabbitmq', 'nats', 'memcached', 'couchdb', 'neo4j',
    'nginx', 'caddy', 'apache', 'httpd', 'traefik', 'envoy',
    # Networking & Terminal
    'postman', 'insomnia', 'httpie', 'curl', 'wget', 'wireshark', 'charles',
    'iterm2', 'iterm', 'warp', 'alacritty', 'kitty', 'hyper', 'tmux', 'screen',
    'zsh', 'fish', 'bash', 'starship', 'oh-my-zsh',
    'ffmpeg', 'ffprobe', 'imagemagick', 'graphviz', 'pandoc',
    'raycast', 'alfred', 'cleanmymac', 'mac-cleaner', 'mac-deep-cleaner'
}


@dataclass
class Ghost:
    path: str
    kind: str
    bundle_id: str  # empty when ownership is unverified
    name_guess: str
    size_bytes: int
    age_days: int
    confidence: str
    identity: tuple = ()

    def to_dict(self):
        result = asdict(self)
        result.pop('identity', None)
        return result


def extract_bundle_id(name):
    for suffix in SUFFIXES:
        name = name.removesuffix(suffix)
    name = re.sub(r'^[A-Z0-9]{10}\.', '', name)
    name = re.sub(r'^group\.', '', name)
    return name.lower() if BUNDLE_RE.fullmatch(name) else None


def squash(value):
    return re.sub(r'[^a-z0-9]', '', str(value).lower())


def vendor_prefixes(bundle_id):
    """Returns vendor root identifiers, e.g. 'com.google' from 'com.google.chrome'."""
    parts = [p for p in bundle_id.split('.') if p]
    if len(parts) >= 2:
        yield f"{parts[0]}.{parts[1]}"
    if len(parts) >= 3 and parts[1] in GENERIC:
        yield f"{parts[0]}.{parts[1]}.{parts[2]}"


def friendly_name(bundle_id, fallback=''):
    """Readable app name from a reverse-DNS id: com.spotify.client -> Spotify."""
    parts = [p for p in bundle_id.split('.') if p]
    if parts and parts[0] in TLDS:
        parts = parts[1:]
    useful = [p for p in parts if p not in GENERIC] or parts
    if not useful:
        return fallback
    if len(useful) > 2:
        useful = useful[:2]
    return ' '.join(w.capitalize() for p in useful for w in re.split(r'[-_]', p) if w) or fallback


def product_names(bundle_id):
    parts = [p for p in bundle_id.split('.') if p]
    if parts and parts[0] in TLDS:
        parts = parts[1:]
    return {squash(p) for p in parts if p not in GENERIC and len(squash(p)) >= 4}


def ide_extensions():
    """Scans installed extensions for VS Code, Cursor, Antigravity, and JetBrains."""
    names = set()
    home = Path.home()
    extension_dirs = [
        home / '.vscode/extensions',
        home / '.vscode-insiders/extensions',
        home / '.cursor/extensions',
        home / '.gemini/antigravity/extensions',
        home / '.antigravity/extensions',
        home / '.windsurf/extensions',
    ]
    for ext_root in extension_dirs:
        try:
            if not ext_root.is_dir():
                continue
            for entry in os.listdir(ext_root):
                if entry.startswith('.'):
                    continue
                # Extension folder format: publisher.extension-name-version
                base = re.sub(r'-\d+(\.\d+)*$', '', entry).lower()
                names.add(base)
                parts = base.split('.')
                for p in parts:
                    names.add(p)
                    for sub in re.split(r'[-_]', p):
                        if len(sub) >= 3:
                            names.add(sub)
        except OSError:
            pass
    # JetBrains plugins
    jb_base = home / 'Library/Application Support/JetBrains'
    try:
        if jb_base.is_dir():
            for root, dirs, _ in os.walk(jb_base):
                if 'plugins' in Path(root).parts:
                    for d in dirs:
                        names.add(d.lower())
    except OSError:
        pass
    return names


def path_executables():
    """Collects executable command names from PATH."""
    commands = set()
    path_dirs = os.environ.get('PATH', '').split(':') + [
        '/opt/homebrew/bin', '/usr/local/bin', str(Path.home() / '.cargo/bin'),
        str(Path.home() / '.local/bin')
    ]
    for p in path_dirs:
        try:
            d = Path(p)
            if not d.is_dir():
                continue
            for f in os.listdir(d):
                if not f.startswith('.'):
                    commands.add(f.lower())
        except OSError:
            pass
    return commands


def running_processes():
    """Best-effort scan of running process names to avoid flagging active background services."""
    procs = set()
    try:
        out = subprocess.run(['ps', '-axo', 'comm='], capture_output=True, text=True, timeout=2).stdout
        for line in out.splitlines():
            line = line.strip()
            if line:
                procs.add(os.path.basename(line).lower())
    except (OSError, subprocess.SubprocessError):
        pass
    return procs


def brew_packages():
    """Collects installed Homebrew formula and cask names."""
    packages = set()
    for room in ('/opt/homebrew/Cellar', '/usr/local/Cellar', '/opt/homebrew/Caskroom', '/usr/local/Caskroom'):
        try:
            packages.update(n.lower() for n in os.listdir(room) if not n.startswith('.'))
        except OSError:
            pass
    return packages


def extra_app_sources(ids_or_names, maybe_names=None):
    """Homebrew casks, formulas, and Spotlight find apps outside the standard folders. Best effort, read-only."""
    if maybe_names is not None:
        ids, names = ids_or_names, maybe_names
    else:
        ids, names = set(), ids_or_names

    names.update(brew_packages())

    try:
        out = subprocess.run(['mdfind', 'kMDItemContentType == "com.apple.application-bundle"'],
                             capture_output=True, text=True, timeout=8).stdout
        for line in out.splitlines():
            if not line.endswith('.app'):
                continue
            name = os.path.basename(line)[:-4].lower()
            names.add(name)
            try:
                plist_path = Path(line) / 'Contents/Info.plist'
                if plist_path.is_file():
                    with open(plist_path, 'rb') as handle:
                        info = plistlib.load(handle)
                    bid = str(info.get('CFBundleIdentifier') or '').lower()
                    if bid:
                        ids.add(bid)
                        names.update(ALIASES.get(bid, set()))
                    for key in ('CFBundleName', 'CFBundleDisplayName'):
                        if info.get(key):
                            names.add(str(info[key]).lower())
            except (OSError, ValueError, TypeError, AttributeError, plistlib.InvalidFileException):
                pass
    except (OSError, ValueError, subprocess.SubprocessError):
        pass


def installed_apps(app_dirs=None, warnings=None):
    ids, names = set(), set()
    warnings = warnings if warnings is not None else []
    def failed(error):
        warnings.append('Some installed applications could not be read; candidates are locked.')
    for root in APP_DIRS if app_dirs is None else app_dirs:
        if not root.exists():
            continue
        for directory, dirs, _files in os.walk(root, followlinks=False, onerror=failed):
            if len(Path(directory).relative_to(root).parts) > 5:
                dirs[:] = []
                continue
            for name in list(dirs):
                if not name.endswith('.app'):
                    continue
                dirs.remove(name)
                names.add(name[:-4].lower())
                try:
                    with open(Path(directory) / name / 'Contents/Info.plist', 'rb') as handle:
                        info = plistlib.load(handle)
                    bid = str(info.get('CFBundleIdentifier') or '').lower()
                    if bid:
                        ids.add(bid)
                        names.update(ALIASES.get(bid, set()))
                    for key in ('CFBundleName', 'CFBundleDisplayName'):
                        if info.get(key):
                            names.add(str(info[key]).lower())
                except (OSError, ValueError, TypeError, AttributeError, plistlib.InvalidFileException):
                    failed(None)
    if app_dirs is None:
        extra_app_sources(ids, names)
    return ids, names


def measure(path, cancelled=None):
    total, newest = 0, path.lstat().st_mtime
    if path.is_file():
        return path.lstat().st_size, newest
    for directory, dirs, files in os.walk(path, followlinks=False):
        if cancelled and cancelled.is_set():
            break
        dirs[:] = [d for d in dirs if not os.path.islink(os.path.join(directory, d))]
        for name in dirs + files:
            try:
                st = os.lstat(os.path.join(directory, name))
                if stat.S_ISLNK(st.st_mode):
                    continue
                newest = max(newest, st.st_mtime)
                if stat.S_ISREG(st.st_mode):
                    total += st.st_size
            except OSError:
                continue
    return total, newest


def find_ghosts(leftover_dirs=None, app_ids_names=None, warnings=None, cancelled=None):
    warnings = warnings if warnings is not None else []
    ids, names = installed_apps(warnings=warnings) if app_ids_names is None else app_ids_names
    ids, names = {i.lower() for i in ids}, {n.lower() for n in names}
    incomplete = bool(warnings)
    squashed = {squash(n) for n in names if len(squash(n)) >= 3}

    # Extract all vendor root domains from installed applications
    installed_vendors = set()
    for i in ids:
        for vp in vendor_prefixes(i):
            installed_vendors.add(vp)

    # Dynamic detection of tools, extensions, commands, and processes
    known_tools = set(KNOWN_TOOLS_AND_PACKAGES)
    if app_ids_names is None:
        try:
            known_tools.update(ide_extensions())
            known_tools.update(path_executables())
            known_tools.update(running_processes())
            known_tools.update(brew_packages())
        except Exception:
            pass

    squashed_tools = {squash(t) for t in known_tools if len(squash(t)) >= 3}

    ghosts = []
    for kind, base in (LEFTOVER_DIRS if leftover_dirs is None else leftover_dirs).items():
        base = Path(base)
        if not base.exists():
            continue
        if base.is_symlink() or base.resolve() != base.absolute():
            warnings.append(f'Skipped linked {kind} location.')
            continue
        try:
            entries = list(base.iterdir())
        except OSError:
            warnings.append(f'Cannot read {kind}. Check Full Disk Access if needed.')
            continue
        for entry in entries:
            if cancelled and cancelled.is_set():
                return ghosts
            if entry.is_symlink() or entry.name.startswith('.'):
                continue

            entry_lower = entry.name.lower()
            entry_squashed = squash(entry.name)

            # System namespaces & known system directories
            if entry_lower in SYSTEM_DIRS or entry_squashed in SYSTEM_DIRS:
                continue

            bid = extract_bundle_id(entry.name)

            # Apple, Swift, LLVM, WebKit, CoreServices namespaces are never ghosts
            if bid and any(bid.startswith(p) or bid == p.rstrip('.') for p in SYSTEM_PREFIXES):
                continue
            if not bid and any(entry_lower.startswith(p) for p in SYSTEM_PREFIXES):
                continue

            # Shared vendor components (e.g. GoogleUpdater, Sky/CUAService, Microsoft AutoUpdate)
            if bid:
                entry_vendors = set(vendor_prefixes(bid))
                if entry_vendors & installed_vendors:
                    continue  # Owned by a vendor that has installed applications

            # Known developer tools, CLI utilities, and IDE packages
            if entry_lower in known_tools or entry_squashed in squashed_tools:
                continue

            # Subword tokens (e.g. 'cloud-code' -> 'cloud', 'code')
            tokens = [t for t in re.split(r'[-_ .]', entry_lower) if len(t) >= 3]
            if any(t in names or t in squashed or t in known_tools for t in tokens):
                continue

            # Exact or squashed installed app match
            if entry_lower in names or entry_squashed in squashed:
                continue
            if bid and product_names(bid) & squashed:
                continue  # Same product under a renamed vendor id: treat as still installed

            if bid:
                if any(bid == i or bid.startswith(i + '.') or i.startswith(bid + '.') for i in ids):
                    continue
                confidence = 'low' if incomplete else 'high'
            else:
                if kind != 'Application Support':
                    continue
                folded = entry_squashed
                if len(folded) >= 5 and any(len(n) >= 5 and (n in folded or folded in n) for n in squashed):
                    continue  # e.g. "Google Chrome" data for an installed "Chrome"
                # Name-only matching must not match any vendor of installed apps (e.g. "Google", "Microsoft")
                if any(folded == squash(v.split('.')[-1]) for v in installed_vendors if len(v.split('.')[-1]) >= 4):
                    continue
                confidence = 'low'

            try:
                identity = fingerprint(str(entry))
                if not identity or not (entry.is_file() or entry.is_dir()):
                    continue
                size, newest = measure(entry, cancelled)
                if identity != fingerprint(str(entry)):
                    continue
            except OSError:
                continue
            ghosts.append(Ghost(str(entry), kind, bid or '', friendly_name(bid, entry.name) if bid else entry.name,
                                size, max(0, int((time.time() - newest) / 86400)), confidence, identity))
    return sorted(ghosts, key=lambda g: (-g.size_bytes, g.path))
