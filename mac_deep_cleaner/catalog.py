"""macOS scan locations and category definitions."""

import re
from .common import CAUTION, RISKY, SAFE, c
from .models import Spec

CATS = [
    ("System Junk", "Caches, logs and temporary files your Mac and your apps rebuild by themselves."),
    ("Trash", "Files you already deleted. They still take up space until the Trash is emptied."),
    ("Large & Old Files", "The biggest files on your Mac, and the ones you have not changed in a long time."),
    ("Duplicate Files", "The same file saved more than once. Keep one copy, remove the rest."),
    ("Downloads & Installers", "Old app installers, disk images and downloads you never went back to."),
    ("Unused Apps & Leftovers", "Apps you stopped opening, older copies of apps, and data left behind by apps you removed."),
    ("App Caches", "Space taken by Spotify, WhatsApp, Zoom, Office, Slack and other everyday apps."),
    ("Mail & Message Attachments", "Attachment copies from Mail (originals stay in your email) and photos/videos sent in Messages."),
    ("Screenshots & Podcasts", "Screenshots piling up on the Desktop, downloaded podcasts and books, screensaver videos macOS fetched."),
    ("Backups & Updates", "iPhone/iPad backups, downloaded iOS updates, macOS installers, local snapshots."),
    ("Cloud Files on This Mac", "Downloaded copies of iCloud / Dropbox / Drive files that also live in the cloud."),
    ("Developer & Pro Tools", "Build artifacts, package caches, SDKs, and creative-app caches (Adobe, DaVinci, Steam...)."),
    ("Photos, Music & Media", "Your media libraries. Shown so you can see them, always protected."),
    ("System Data", "The 'mystery bar' in macOS Storage: device support, simulators, snapshots, diagnostics, updates."),
]


CAT_NAMES = [c[0] for c in CATS]


CAT_DESC = dict(CATS)


L = "~/Library"


SPECS = [
    # ---- System Junk --------------------------------------------------------------
    Spec("System Junk", f"{L}/Logs/DiagnosticReports/*", SAFE, "Crash/diagnostic reports; only useful for bug reports.", "Created again if an app crashes.", "Crash report"),
    Spec("System Junk", f"{L}/Logs/*", SAFE, "Old log files written by apps and the system.", "Apps write fresh logs.", "Logs"),
    Spec("System Junk", f"{L}/Saved Application State/*", SAFE, "Window positions apps use to reopen where you left off.", "Apps reopen with default windows.", "Saved window state"),
    Spec("System Junk", f"{L}/Application Support/CrashReporter/*", SAFE, "Crash reporter history.", "Recreated on demand."),
    Spec("System Junk", f"{L}/Caches/com.apple.QuickLook.thumbnailcache", SAFE, "Finder preview thumbnails.", "Rebuilt as you browse folders."),
    Spec("System Junk", f"{L}/Containers/*/Data/Library/Caches", SAFE, "Sandboxed app caches.", "Apps rebuild them.", "Container cache"),
    # ---- Trash ---------------------------------------------------------------------
    # (handled in code: ~/.Trash)
    # ---- Backups & Updates -------------------------------------------------------
    Spec("Backups & Updates", f"{L}/Application Support/MobileSync/Backup/*", RISKY, "Local iPhone/iPad backup. If it is your ONLY backup, deleting it loses that restore point.", "Make a new one in Finder > device > Back Up Now.", "iOS device backup"),
    Spec("Backups & Updates", f"{L}/iTunes/iPhone Software Updates/*", SAFE, "Downloaded iOS update files.", "Re-downloaded when you update."),
    Spec("Backups & Updates", f"{L}/iTunes/iPad Software Updates/*", SAFE, "Downloaded iPadOS update files.", "Re-downloaded when you update."),
    Spec("Backups & Updates", "/Applications/Install macOS*.app", CAUTION, "Full macOS installer (often ~12 GB) you downloaded once.", "Re-download from the App Store / softwareupdate.", "macOS installer"),
    Spec("Backups & Updates", "/Library/Updates", SAFE, "Leftover macOS update payloads.", "macOS downloads them again when needed.", root=True, cmd='sudo rm -rf /Library/Updates/*'),
    # ---- Mail & Messages -----------------------------------------------------------
    Spec("Mail & Message Attachments", f"{L}/Containers/com.apple.mail/Data/Library/Mail Downloads/*", SAFE, "Copies of attachments you opened from Mail. Originals stay in your mailbox.", "Mail downloads them again when opened.", "Mail attachment copy"),
    Spec("Mail & Message Attachments", f"{L}/Mail Downloads/*", SAFE, "Copies of attachments you opened from Mail.", "Mail downloads them again when opened.", "Mail attachment copy"),
    Spec("Mail & Message Attachments", f"{L}/Messages/Attachments", CAUTION, "Photos/videos people sent you in Messages. If Messages in iCloud is off these may be the only copies.", "Re-downloaded from iCloud if Messages in iCloud is on.", "Messages attachments"),
    # ---- System Data (explained) -------------------------------------------------
    Spec("System Data", f"{L}/Developer/Xcode/iOS DeviceSupport/*", SAFE, "Symbols Xcode copied from a connected iPhone/iPad (one per iOS version).", "Re-created automatically when you plug the device in.", "iOS DeviceSupport"),
    Spec("System Data", f"{L}/Developer/Xcode/watchOS DeviceSupport/*", SAFE, "Symbols copied from an Apple Watch.", "Re-created when the watch is connected.", "watchOS DeviceSupport"),
    Spec("System Data", f"{L}/Developer/Xcode/tvOS DeviceSupport/*", SAFE, "Symbols copied from an Apple TV.", "Re-created when the device is connected.", "tvOS DeviceSupport"),
    Spec("System Data", f"{L}/Developer/Xcode/Archives/*", CAUTION, "App archives (with dSYMs) from your builds. Needed to symbolicate old crash logs.", "Cannot be rebuilt identically - re-archive from source.", "Xcode archive"),
    Spec("System Data", f"{L}/Developer/CoreSimulator/Caches", SAFE, "Simulator cache.", "Rebuilt on next simulator launch."),
    Spec("System Data", "/Library/Logs/DiagnosticReports", SAFE, "System-wide diagnostic reports.", "Created again if something crashes.", root=True, cmd="sudo rm -rf /Library/Logs/DiagnosticReports/*"),
    Spec("System Data", "/Library/Caches", CAUTION, "System-wide caches. Safe, but some need a restart to rebuild.", "macOS and apps rebuild them.", root=True, cmd='sudo find /Library/Caches -mindepth 1 -delete'),
    Spec("System Data", "/private/var/log/asl", SAFE, "Old Apple System Log archives.", "New logs are written.", root=True, cmd="sudo rm -f /private/var/log/asl/*.asl"),
    # ---- Developer & Pro tools --------------------------------------------------
    Spec("Developer & Pro Tools", f"{L}/Developer/Xcode/DerivedData/*", SAFE, "Xcode build output / indexes.", "Rebuilt on next build (first build is slower).", "Xcode DerivedData"),
    Spec("Developer & Pro Tools", f"{L}/Developer/Xcode/UserData/Previews", SAFE, "SwiftUI preview cache.", "Rebuilt by previews."),
    Spec("Developer & Pro Tools", "~/.npm/_cacache", SAFE, "npm download cache.", "npm re-downloads packages on install.", "npm cache", cmd="npm cache clean --force"),
    Spec("Developer & Pro Tools", "~/.npm/_logs", SAFE, "npm log files.", "New logs are written."),
    Spec("Developer & Pro Tools", f"{L}/Caches/Yarn", SAFE, "Yarn package cache.", "yarn re-downloads on install.", cmd="yarn cache clean"),
    Spec("Developer & Pro Tools", "~/.pnpm-store", SAFE, "pnpm content store.", "pnpm re-downloads on install.", cmd="pnpm store prune"),
    Spec("Developer & Pro Tools", f"{L}/pnpm/store", SAFE, "pnpm content store.", "pnpm re-downloads on install.", cmd="pnpm store prune"),
    Spec("Developer & Pro Tools", "~/.bun/install/cache", SAFE, "Bun package cache.", "Re-downloaded on install."),
    Spec("Developer & Pro Tools", f"{L}/Caches/Homebrew", SAFE, "Homebrew downloaded bottles/casks.", "brew re-downloads when needed.", cmd="brew cleanup -s"),
    Spec("Developer & Pro Tools", f"{L}/Caches/pip", SAFE, "pip wheel cache.", "pip re-downloads."),
    Spec("Developer & Pro Tools", "~/.cache/pip", SAFE, "pip wheel cache.", "pip re-downloads."),
    Spec("Developer & Pro Tools", "~/.cache/go-build", SAFE, "Go build cache.", "Rebuilt on next build.", cmd="go clean -cache"),
    Spec("Developer & Pro Tools", f"{L}/Caches/CocoaPods", SAFE, "CocoaPods download cache.", "pod install re-downloads."),
    Spec("Developer & Pro Tools", "~/.cocoapods/repos", CAUTION, "CocoaPods spec repos (slow to clone again).", "pod repo update re-clones."),
    Spec("Developer & Pro Tools", "~/.gradle/caches", CAUTION, "Gradle dependency + build caches.", "Re-downloaded on next Gradle sync (can take a while).", cmd=""),
    Spec("Developer & Pro Tools", "~/.gradle/daemon", SAFE, "Gradle daemon logs.", "Recreated."),
    Spec("Developer & Pro Tools", "~/.gradle/wrapper/dists/*", CAUTION, "A Gradle distribution used by wrapper-based projects.", "Wrapper downloads it again if a project needs it.", "Gradle distribution", check="gradle"),
    Spec("Developer & Pro Tools", "~/.m2/repository", CAUTION, "Maven local repository.", "Maven re-downloads dependencies.", cmd=""),
    Spec("Developer & Pro Tools", "~/.cargo/registry", SAFE, "Cargo crate downloads.", "cargo re-downloads.", cmd=""),
    Spec("Developer & Pro Tools", "~/.cargo/git", CAUTION, "Cargo git dependencies.", "cargo re-clones."),
    Spec("Developer & Pro Tools", "~/go/pkg/mod", CAUTION, "Go module cache.", "go re-downloads.", cmd="go clean -modcache"),
    Spec("Developer & Pro Tools", "~/.pub-cache", CAUTION, "Dart/Flutter pub cache.", "flutter pub get re-downloads."),
    Spec("Developer & Pro Tools", "~/.android/cache", SAFE, "Android SDK manager cache.", "Re-downloaded."),
    Spec("Developer & Pro Tools", "~/.android/avd/*", CAUTION, "An Android emulator image with its data.", "Recreate it in Device Manager (apps/data inside are lost).", "Android emulator"),
    Spec("Developer & Pro Tools", f"{L}/Android/sdk/system-images/*", CAUTION, "Android emulator system images.", "Re-download via SDK Manager.", "Android system image"),
    Spec("Developer & Pro Tools", f"{L}/Android/sdk/ndk/*", CAUTION, "An Android NDK version.", "Re-download via SDK Manager.", "Android NDK", check="ndk"),
    Spec("Developer & Pro Tools", "~/.conda/pkgs", SAFE, "Conda package cache.", "conda re-downloads.", cmd="conda clean -a"),
    Spec("Developer & Pro Tools", "~/miniconda3/pkgs", SAFE, "Conda package cache.", "conda re-downloads.", cmd="conda clean -a"),
    Spec("Developer & Pro Tools", "~/anaconda3/pkgs", SAFE, "Conda package cache.", "conda re-downloads.", cmd="conda clean -a"),
    Spec("Developer & Pro Tools", "~/.nvm/.cache", SAFE, "nvm download cache.", "Re-downloaded."),
    Spec("Developer & Pro Tools", "~/.nvm/versions/node/*", CAUTION, "An installed Node.js version.", "nvm install <version>.", "Node version"),
    Spec("Developer & Pro Tools", "~/.pyenv/versions/*", CAUTION, "An installed Python version (venvs may depend on it).", "pyenv install <version>.", "Python version"),
    Spec("Developer & Pro Tools", "~/.cache/*", CAUTION, "Per-tool cache folder under ~/.cache.", "The tool rebuilds/redownloads it (ML models can be slow).", ".cache"),
    # creative / pro tools
    Spec("Developer & Pro Tools", f"{L}/Application Support/Adobe/Common/Media Cache Files", SAFE, "Premiere / After Effects media cache.", "Regenerated when you reopen projects.", "Adobe media cache"),
    Spec("Developer & Pro Tools", f"{L}/Application Support/Adobe/Common/Media Cache", SAFE, "Premiere / After Effects media cache database.", "Regenerated."),
    Spec("Developer & Pro Tools", f"{L}/Caches/Adobe Camera Raw*", SAFE, "Camera Raw cache.", "Rebuilt on next use."),
    Spec("Developer & Pro Tools", "~/Movies/CacheClip", CAUTION, "DaVinci Resolve render cache & proxies.", "Re-render / re-generate proxies.", "DaVinci cache"),
    Spec("Developer & Pro Tools", "~/Movies/ProxyMedia", CAUTION, "DaVinci Resolve proxy media.", "Regenerate proxies.", "DaVinci proxies"),
    Spec("Developer & Pro Tools", f"{L}/Application Support/Blackmagic Design/DaVinci Resolve/CacheClip", CAUTION, "DaVinci Resolve render cache.", "Re-render.", "DaVinci cache"),
    Spec("Developer & Pro Tools", "~/Movies/Final Cut Backups", CAUTION, "Automatic Final Cut Pro library backups.", "Only matters if you need to roll back a library.", "Final Cut backups"),
    Spec("Developer & Pro Tools", "~/Pictures/*/*Previews.lrdata", CAUTION, "Lightroom previews cache.", "Lightroom rebuilds previews (slow on big catalogs).", "Lightroom previews"),
    Spec("Developer & Pro Tools", "~/Pictures/*/*Smart Previews.lrdata", CAUTION, "Lightroom smart previews (used for offline editing).", "Rebuilt if the originals are online.", "Lightroom smart previews"),
    Spec("Developer & Pro Tools", f"{L}/Caches/com.captureone*", SAFE, "Capture One cache.", "Rebuilt."),
    Spec("Developer & Pro Tools", f"{L}/Caches/com.bohemiancoding.sketch*", SAFE, "Sketch cache.", "Rebuilt."),
    Spec("Developer & Pro Tools", f"{L}/Application Support/Figma/*Cache*", SAFE, "Figma desktop cache.", "Rebuilt."),
    Spec("Developer & Pro Tools", f"{L}/Application Support/Steam/steamapps/shadercache", SAFE, "Steam shader caches.", "Rebuilt when games launch."),
    Spec("Developer & Pro Tools", f"{L}/Application Support/Steam/steamapps/common/*", CAUTION, "An installed Steam game.", "Re-download from Steam (saves in Steam Cloud are kept).", "Steam game"),
    Spec("Developer & Pro Tools", f"{L}/Caches/*shader*", SAFE, "GPU shader cache.", "Rebuilt."),
    Spec("Developer & Pro Tools", "/Library/Application Support/Logic", CAUTION, "Logic Pro sound library.", "Re-download in Logic > Sound Library.", root=True, cmd="sudo rm -rf '/Library/Application Support/Logic'"),
    Spec("Developer & Pro Tools", "/Library/Application Support/GarageBand", CAUTION, "GarageBand sound library.", "Re-download in GarageBand.", root=True, cmd="sudo rm -rf '/Library/Application Support/GarageBand'"),
    # ---- Photos, Music & Media (always protected) --------------------------------
    Spec("Photos, Music & Media", "~/Pictures/*.photoslibrary", RISKY, "Your Photos library.", "Not rebuildable - protected.", "Photos library", protected=True, min_size=0),
    Spec("Photos, Music & Media", "~/Music/Music", RISKY, "Your Music library.", "Protected.", "Music library", protected=True, min_size=0),
    Spec("Photos, Music & Media", "~/Movies/TV", RISKY, "Your TV library.", "Protected.", "TV library", protected=True, min_size=0),
    # ---- managed by macOS (shown, never deleted, not counted as freeable) --------
    Spec("System Data", "/private/var/db/diagnostics", CAUTION, "macOS unified-logging store. macOS prunes it itself.", "Managed by macOS.", managed=True, protected=True),
    Spec("System Data", "/private/var/db/uuidtext", CAUTION, "Log symbol tables used by macOS.", "Managed by macOS.", managed=True, protected=True),
]


EXTRA_SPECS = [
    # browsers
    Spec("App Caches", f"{L}/Caches/Google/Chrome", SAFE, "Chrome cache.", "Rebuilt as you browse.", "Chrome cache"),
    Spec("App Caches", f"{L}/Caches/com.apple.Safari", SAFE, "Safari cache (sizing it needs Full Disk Access).", "Rebuilt as you browse.", "Safari cache"),
    Spec("App Caches", f"{L}/Caches/Firefox", SAFE, "Firefox cache.", "Rebuilt as you browse.", "Firefox cache"),
    Spec("App Caches", f"{L}/Caches/BraveSoftware", SAFE, "Brave cache.", "Rebuilt as you browse.", "Brave cache"),
    Spec("App Caches", f"{L}/Caches/Microsoft Edge", SAFE, "Edge cache.", "Rebuilt as you browse.", "Edge cache"),
    Spec("App Caches", f"{L}/Caches/company.thebrowser.Browser", SAFE, "Arc cache.", "Rebuilt as you browse.", "Arc cache"),
    # editors / IDEs
    Spec("Developer & Pro Tools", f"{L}/Application Support/Code/CachedData", SAFE, "VS Code compiled-code cache.", "Rebuilt on next launch.", "VS Code cache"),
    Spec("Developer & Pro Tools", f"{L}/Application Support/Code/CachedExtensionVSIXs", SAFE, "Downloaded VS Code extension packages.", "Re-downloaded when needed.", "VS Code VSIX cache"),
    Spec("Developer & Pro Tools", f"{L}/Application Support/Code/Cache", SAFE, "VS Code web cache.", "Rebuilt on next launch.", "VS Code web cache"),
    Spec("Developer & Pro Tools", f"{L}/Application Support/Code/logs", SAFE, "VS Code logs.", "New logs are written.", "VS Code logs"),
    Spec("Developer & Pro Tools", f"{L}/Application Support/Cursor/CachedData", SAFE, "Cursor compiled-code cache.", "Rebuilt on next launch.", "Cursor cache"),
    Spec("Developer & Pro Tools", f"{L}/Application Support/Cursor/logs", SAFE, "Cursor logs.", "New logs are written.", "Cursor logs"),
    # Xcode / device images
    Spec("System Data", f"{L}/Developer/DeveloperDiskImages/*", SAFE, "Developer disk image for a connected-device iOS version.", "Re-mounted/downloaded when the device connects.", "Developer disk image"),
    Spec("System Data", f"{L}/MobileDevice/Software Images/*", SAFE, "Device restore images.", "Downloaded again when restoring a device.", "Device restore image"),
    # AI & ML
    Spec("Developer & Pro Tools", "~/.cache/huggingface", CAUTION, "Hugging Face model and dataset downloads.", "Re-downloaded on demand (large, can be slow).", "Hugging Face cache"),
    Spec("Developer & Pro Tools", "~/.cache/torch", CAUTION, "PyTorch hub / model weights.", "Re-downloaded on demand.", "PyTorch cache"),
    Spec("Developer & Pro Tools", "~/.cache/whisper", CAUTION, "Whisper model weights.", "Re-downloaded on demand.", "Whisper models"),
    Spec("Developer & Pro Tools", "~/.ollama/models", CAUTION, "Ollama local LLM models.", "`ollama pull <model>` downloads them again.", "Ollama models"),
    Spec("Developer & Pro Tools", "~/.lmstudio/models", CAUTION, "LM Studio local models.", "Re-download inside LM Studio.", "LM Studio models"),
    Spec("Developer & Pro Tools", "~/.cache/lm-studio/models", CAUTION, "LM Studio local models.", "Re-download inside LM Studio.", "LM Studio models"),
    # games & engines
    Spec("Developer & Pro Tools", f"{L}/Unity/cache", SAFE, "Unity package / asset cache.", "Re-downloaded by the Unity Hub.", "Unity cache"),
    Spec("Developer & Pro Tools", f"{L}/Unity/Asset Store*", CAUTION, "Unity Asset Store downloads.", "Re-download from the Asset Store.", "Unity Asset Store"),
    Spec("Developer & Pro Tools", f"{L}/Application Support/Epic/EpicGamesLauncher/VaultCache", SAFE, "Epic Games launcher vault cache.", "Re-downloaded when needed.", "Epic vault cache"),
    # virtual machines (never rebuildable)
    Spec("Developer & Pro Tools", "~/Parallels/*.pvm", RISKY, "Parallels virtual machine - holds a whole guest OS.", "Not rebuildable.", "Parallels VM"),
    Spec("Developer & Pro Tools", "~/Virtual Machines.localized/*", RISKY, "VMware Fusion virtual machine.", "Not rebuildable.", "VMware VM"),
    Spec("Developer & Pro Tools", "~/VirtualBox VMs/*", RISKY, "VirtualBox virtual machine.", "Not rebuildable.", "VirtualBox VM"),
    Spec("Developer & Pro Tools", f"{L}/Containers/com.utmapp.UTM/Data/Documents/*.utm", RISKY, "UTM virtual machine.", "Not rebuildable.", "UTM VM"),
    # personal clutter
    Spec("Screenshots & Podcasts", f"{L}/Group Containers/*.groups.com.apple.podcasts/Library/Cache", CAUTION, "Downloaded podcast episodes.", "Re-download from the Podcasts app.", "Podcast downloads"),
    Spec("Screenshots & Podcasts", f"{L}/Containers/com.apple.BKAgentService/Data/Documents/iBooks/Books", CAUTION, "Books you downloaded in Apple Books.", "Re-download from iCloud / the Books store.", "Apple Books downloads"),
    Spec("Screenshots & Podcasts", "/Library/Application Support/com.apple.idleassetsd/Customer", CAUTION, "Aerial screensaver / wallpaper videos macOS downloaded in the background.", "macOS downloads them again when the screensaver needs them.", "Screensaver videos",
         root=True, cmd="sudo rm -rf '/Library/Application Support/com.apple.idleassetsd/Customer'/*"),
    # explainers (shown, never deleted, not counted)
    Spec("System Data", "/private/var/vm", CAUTION, "Swap files macOS uses when memory is full. A restart clears them.", "Managed by macOS.", "Swap / virtual memory", managed=True, protected=True, min_size=1),
    Spec("System Data", "/System/Volumes/Data/.Spotlight-V100", CAUTION, "Spotlight search index. Rebuild with: sudo mdutil -E /", "Managed by macOS.", "Spotlight index", managed=True, protected=True, min_size=1),
]


SPECS = EXTRA_SPECS + SPECS


ART = {
    "node_modules": (("package.json",), SAFE, "npm/yarn/pnpm install"),
    ".next": (("package.json",), SAFE, "next build / next dev"),
    ".nuxt": (("package.json",), SAFE, "nuxt build / dev"),
    ".svelte-kit": (("package.json",), SAFE, "vite dev / build"),
    ".turbo": (("package.json",), SAFE, "turbo run"),
    ".parcel-cache": (("package.json",), SAFE, "parcel build"),
    ".angular": (("angular.json",), SAFE, "ng build / serve"),
    ".expo": (("package.json",), SAFE, "expo start"),
    ".vite": (("package.json",), SAFE, "vite dev"),
    "dist": (("package.json", "pyproject.toml", "setup.py", "tsconfig.json"), CAUTION, "Re-run the project's build"),
    "out": (("package.json", "next.config.js", "next.config.mjs"), CAUTION, "Re-run the project's build"),
    "build": (("package.json", "build.gradle", "build.gradle.kts", "CMakeLists.txt", "pom.xml", "setup.py", "pubspec.yaml", "Makefile"), SAFE, "Re-run the project's build"),
    "coverage": (("package.json",), SAFE, "Re-run tests with coverage"),
    "Pods": (("Podfile",), SAFE, "pod install"),
    "target": (("Cargo.toml", "pom.xml", "build.sbt"), SAFE, "cargo build / mvn package"),
    ".build": (("Package.swift",), SAFE, "swift build"),
    ".gradle": (("build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts"), SAFE, "Gradle sync"),
    ".dart_tool": (("pubspec.yaml",), SAFE, "flutter pub get"),
    ".terraform": (("*.tf",), SAFE, "terraform init"),
    ".stack-work": (("stack.yaml",), SAFE, "stack build"),
    "elm-stuff": (("elm.json",), SAFE, "elm make"),
    "bower_components": (("bower.json",), SAFE, "bower install"),
    "vendor": (("composer.json", "Gemfile", "go.mod"), CAUTION, "composer/bundle/go mod vendor"),
    "_build": (("mix.exs",), SAFE, "mix compile"),
    "deps": (("mix.exs",), SAFE, "mix deps.get"),
    "__pycache__": (None, SAFE, "Python recreates bytecode"),
    ".pytest_cache": (None, SAFE, "pytest recreates it"),
    ".mypy_cache": (None, SAFE, "mypy recreates it"),
    ".ruff_cache": (None, SAFE, "ruff recreates it"),
    ".tox": (("tox.ini", "pyproject.toml", "setup.cfg"), SAFE, "tox recreates environments"),
    ".ipynb_checkpoints": (None, SAFE, "Jupyter recreates it"),
    ".venv": ("VENV", CAUTION, "Recreate: python -m venv .venv && pip install -r requirements.txt"),
    "venv": ("VENV", CAUTION, "Recreate: python -m venv venv && pip install -r requirements.txt"),
    "env": ("VENV", CAUTION, "Recreate the virtualenv and reinstall requirements"),
}


SKIP_DIRS = {".Trash", ".git", ".svn", ".hg", "Library", ".Spotlight-V100", ".fseventsd", ".DS_Store",
             ".gradle", ".npm", ".cache", ".cargo", ".rustup", ".m2", ".android", ".cocoapods", ".docker",
             ".nvm", ".pyenv", ".pnpm-store", ".bun", ".conda", "miniconda3", "anaconda3", "go", ".pub-cache",
             ".vscode", ".ollama", ".local", "Applications"}


BUNDLE_SKIP = (".app", ".framework", ".bundle", ".plugin", ".xcodeproj", ".xcworkspace", ".xcassets", ".lproj", ".kext")


MEDIA_BUNDLES = (".photoslibrary", ".musiclibrary", ".tvlibrary", ".imovielibrary", ".fcpbundle", ".logicx", ".band", ".sparsebundle")


GRADLE_FILES = {"build.gradle", "build.gradle.kts", "local.properties", "gradle-wrapper.properties"}


DEFAULT_KEEP = {"addressbook", "cloudkit", "clouddocs", "icloud", "mobilesync", "syncservices", "knowledge", "dock",
                "com.apple", "apple", "caches", "crashreporter", "differentialprivacy", "fileprovider", "google",
                "code", "claude", "homebrew", "jetbrains", "androidstudio", "docker", "ollama", "git", "ssh",
                "quicklook", "preferencepanes", "colorsync", "audio", "mail", "messages", "safari", "photos",
                "music", "tv", "notes", "reminders", "calendar", "contacts", "steam", "adobe", "microsoft", "firefox",
                "chrome", "slack", "discord", "zoom", "spotify", "whatsapp"}


TOOLCHAINS = [
    ("AI & ML", r"huggingface|ollama|/torch|lmstudio|lm-studio|whisper"),
    ("Docker & VMs", r"docker|Docker|Parallels|\.pvm|VMware|Virtual Machines|VirtualBox|\.utm"),
    ("Games & Engines", r"Steam|Unity|Unreal|Epic"),
    ("Creative & Pro Apps", r"Adobe|DaVinci|Final Cut|Lightroom|Capture ?One|Sketch|Figma|Logic|GarageBand|CacheClip|ProxyMedia|shader"),
    ("IDEs & Editors", r"JetBrains|AndroidStudio|/Code/|VS Code|/Cursor|old IDE"),
    ("Xcode & iOS", r"/Developer/|Xcode|CocoaPods|\.cocoapods|/Pods\b|simulator|DeviceSupport"),
    ("Flutter & Dart", r"\.pub-cache|\.dart_tool|flutter|pubspec"),
    ("Android & JVM", r"\.gradle|/\.android|/Android/|/\.m2|Gradle|NDK|\.apk|\.aab"),
    ("JavaScript & Node", r"node_modules|\.npm|pnpm|Yarn|yarn|\.bun|\.nvm|\.next|\.nuxt|\.svelte|\.turbo|\.parcel|\.angular|\.expo|\.vite|Node version"),
    ("Python", r"\.venv|/venv|/env$|__pycache__|/pip|conda|\.pyenv|\.pytest|\.mypy|\.ruff|\.tox|ipynb|Python version"),
    ("Go, Rust & Other", r"go-build|/go/pkg|\.cargo|/target$|\.build|\.terraform|\.stack|elm-stuff|/vendor|/_build|/deps$|Homebrew"),
]


TOOLCHAIN_RE = [(n, re.compile(p)) for n, p in TOOLCHAINS]


TOOLCHAIN_NAMES = [n for n, _ in TOOLCHAINS] + ["Other Developer Data"]


def toolchain(it):
    blob = f"{it.path} {it.name}"
    for n, rx in TOOLCHAIN_RE:
        if rx.search(blob):
            return n
    return "Other Developer Data"


def group_name(it, mode):
    """Group label of an item: the plain category, or (developer mode) the toolchain."""
    if mode == "dev" and it.category == "Developer & Pro Tools":
        return toolchain(it)
    return it.category
