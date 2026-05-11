# Mac Deep Cleaner — Features (v1.2.0)

**Mac Deep Cleaner** is a professional macOS cleanup tool that safely detects and helps you remove leftover data from uninstalled apps, along with general junk that accumulates over time. It is designed to be **safe by default**, with **preview-first** workflows and **undo/restore support**.

All commands are available as both `mac-cleaner ...` and `mdc ...`.

## What it does

### 1) Smart App Orphan Detection
Detects leftover app data after uninstalling apps, including items such as:
- Application Support leftovers
- Preferences
- Caches
- Logs
- Saved State
- Group Container data (validated before acting)

### 2) General Junk Scanner
Finds common junk categories such as:
- Caches (user-owned)
- Logs
- Crash/Diagnostic reports
- Trash leftovers
- `.DS_Store` files
- Xcode derived data / device support artifacts
- Package manager caches (npm/pip/yarn/pnpm/gradle/maven/cargo/go/cocoapods)
- Browser caches (Chrome/Firefox)

### 2b) Developer Junk Scanner (opt-in)
Finds project build output and dependency directories such as:
- `node_modules`, `venv`, `__pycache__`, `target`, `bin/obj`, `dist`, `coverage`
Optionally includes global caches (e.g., `~/.npm`, `~/.gradle`, `~/.m2`, `~/.cargo`, `~/.nuget`).

### 3) Duplicate File Finder (by hash)
Identifies duplicates using **two-phase hashing** for speed and accuracy, allowing you to:
- Review duplicate groups
- Estimate wasted space
- Delete extra copies (with confirmations)

### 4) Large Files Scanner
Finds files over a configurable size threshold and presents results grouped by category.

### 5) Broken Symlink Detector
Scans common developer paths for dangling symbolic links and reports them with targets.

### 6) iOS / iPhone Backup Finder
Locates old iOS/iPhone backups and surfaces:
- Device name
- iOS version
- Age
- Size

Optionally deletes backups interactively.

### 7) Language Pack Stripper
Finds removable language pack `.lproj` directories and helps you strip unused languages to reclaim space.

### 8) Universal Binary Thinner (fat binaries)
Detects universal (fat) binaries and can thin them to your target architecture using `ditto --arch`.

### 9) Undo / Restore (staged deletions)
Instead of permanent deletion, files can be staged into:
- `~/.mac_cleaner_trash/`
with session manifests, enabling restore via:
- `mac-cleaner undo`

### 10) YAML Configuration + Profiles
Uses `~/.config/mac-cleaner/config.yaml` with profiles to control scanning behavior such as:
- whitelist / skips
- custom scan roots
- scan category toggles
- undo mode
- retention days
- large file threshold

### 11) Scan History + Diff
Supports:
- storing scan results in history
- comparing two scans to see what’s new or resolved

### 12) HTML Report Export
Exports a self-contained HTML report (with Chart.js via CDN) for offline review.

### 13) System Inspector
Checks/prints:
- Launch Agents / Launch Daemons
- Login items
- SIP and permission health hints

### 14) Scheduler
Install/remove/status management for weekly automated scans.

### 15) Self-update (PyPI)
Checks for updates from PyPI and optionally upgrades.

### 16) CI / Automation Mode
`mac-cleaner scan --ci --threshold-mb N` prints JSON to stdout and exits with
code `1` when reclaimable bytes exceed the threshold. This is intended for
dotfile repos, scheduled jobs, and GitHub Actions-style checks.

### 17) Live Dashboard
`mac-cleaner dashboard` uses Rich Live/Layout to show installed apps, protected
running apps, orphan groups, junk items, and reclaimable size while the scan is
running.

### 18) Distribution Helpers
The project includes:
- `bash scripts/build.sh build` for wheel and sdist
- `bash scripts/build.sh test` for compile and CLI smoke checks
- `bash scripts/build.sh pkg` for an unsigned local macOS package
- `Formula/mac-deep-cleaner.rb` as a Homebrew formula scaffold

## Safety-first behavior (summary)
- **Preview-first**: `scan` doesn’t modify the filesystem
- **System protection**: system-owned items are isolated and protected
- **Validation gate**: paths are validated right before staging/deletion
- **Undo supported**: staged deletions can be restored
