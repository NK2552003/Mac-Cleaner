# Mac Deep Cleaner v1.0.0

**Professional macOS cleanup tool — Smart App Orphan Detector**

Detects and removes leftover files from uninstalled apps, stale caches, crash reports, logs, and other system junk — safely, with multiple layers of protection and full undo support.

Use either command name:
```bash
mac-cleaner scan
mdc scan
```

---

## What's New in v1.0.0

| Feature | Command |
|---|---|
| Duplicate file finder (by hash) | `mac-cleaner duplicates` |
| Large file scanner (sortable) | `mac-cleaner large-files` |
| Broken symlink detector | `mac-cleaner symlinks` |
| iOS/iPhone backup finder | `mac-cleaner extras --ios-backups` |
| Language pack stripper | `mac-cleaner extras --language-packs` |
| Universal binary thinner | `mac-cleaner binary` |
| Undo / restore staged deletions | `mac-cleaner undo` |
| YAML config + profiles | `~/.config/mac-cleaner/config.yaml` |
| Scan history & diff | `mac-cleaner history` / `mac-cleaner diff` |
| HTML report export | `--export report.html` |
| Launch item manager | `mac-cleaner system --launch-items` |
| Login items viewer | `mac-cleaner system --login-items` |
| SIP & permission health check | `mac-cleaner system --health` |
| Weekly auto-scan scheduler | `mac-cleaner schedule install` |
| macOS notifications | `--notify` flag |
| CI mode / JSON threshold gate | `mac-cleaner scan --ci --threshold-mb 500` |
| Live TUI dashboard | `mac-cleaner dashboard` |
| Custom scan roots | `mac-cleaner scan --root ~/Projects` |
| Self-update from PyPI | `mac-cleaner update` |
| Homebrew formula + .pkg builder | `Formula/mac-deep-cleaner.rb`, `bash scripts/build.sh pkg` |

`mdc` is a shorter alias for every command, for example `mdc dashboard`,
`mdc clean`, and `mdc scan --ci --threshold-mb 500`.

---

## Features (All)

- **Smart orphan detection** — finds leftover app data after uninstalling apps
- **General junk scan** — caches, logs, crash reports, Trash, `.DS_Store`, Xcode artefacts, package manager caches
- **Duplicate finder** — SHA-256 content hashing, two-phase (head + full), sorted by wasted space
- **Large file scanner** — finds files ≥100 MB (configurable), categorised by type
- **Broken symlink detector** — walks `/usr/local`, `/opt/homebrew`, `~/bin`, etc.
- **iOS backup finder** — parses `MobileSync/Backup` manifests, shows device/age/size
- **Language pack stripper** — detects removable `.lproj` dirs in every installed app
- **Universal binary thinner** — uses `ditto --arch` safely; creates `.fat_backup` by default
- **Undo / restore** — files staged in `~/.mac_cleaner_trash/` instead of permanent delete
- **Config file** — `~/.config/mac-cleaner/config.yaml` with profile support
- **Scan history** — JSON records in `~/.config/mac-cleaner/history/`
- **Diff** — compare any two scans to see what's new or resolved
- **HTML report** — self-contained with Chart.js doughnut + collapsible sections
- **System inspector** — LaunchAgents, LaunchDaemons, login items, SIP status
- **Scheduler** — installs a LaunchAgent for weekly auto-scans
- **macOS notifications** — via `osascript`, no dependencies
- **CI mode** — JSON-only scan summary with threshold-based exit code
- **Live TUI dashboard** — Rich Live/Layout summary while a scan is running
- **Custom roots** — scan project folders or external directories via config or `--root`
- **Distribution helpers** — wheel/sdist, Homebrew formula scaffold, and unsigned local `.pkg` builder
- **Self-update** — checks PyPI, upgrades via pip
- **Safety first** — system files (`com.apple.*`) are *never* touched; running apps are protected

---

## Installation

### From PyPI (recommended)
```bash
pip install mac-deep-cleaner #will be available soon
```

### From source (venv)
```bash
git clone https://github.com/NK2552003/Mac-Cleaner.git
cd mac_deep_cleaner
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

---

## Usage

### Core scan & clean
```bash
# Preview scan (safe — never deletes)
mac-cleaner scan
mdc scan

# Live dashboard scan
mac-cleaner dashboard

# Interactive cleanup (files staged for undo by default)
mac-cleaner clean

# Auto-delete everything detected
mac-cleaner clean --auto

# Permanently delete (skip undo staging)
mac-cleaner clean --no-undo

# Skip general junk; orphans only
mac-cleaner scan --skip-junk

# Export results to JSON / YAML / HTML
mac-cleaner scan --export results.json
mac-cleaner scan --export results.html

# Protect a path from deletion
mac-cleaner clean --whitelist ~/Library/Application\ Support/MyApp

# Show all discovered apps
mac-cleaner scan --show-apps

# Use a profile
mac-cleaner scan --profile developer
mac-cleaner scan --profile minimal

# Add a custom scan root
mac-cleaner scan --root ~/Projects

# CI / automation mode: JSON to stdout, exit 1 when over threshold
mac-cleaner scan --ci --threshold-mb 500

# Post macOS notification when done
mac-cleaner scan --notify
```

### New scanners
```bash
# Find duplicate files (default: ~/Downloads, ~/Documents, ~/Desktop, ~/Pictures)
mac-cleaner duplicates
mac-cleaner duplicates --path ~/Movies --min-size 500

# Find large files (≥100 MB by default)
mac-cleaner large-files
mac-cleaner large-files --min-mb 50 --export large.json

# Find broken symlinks
mac-cleaner symlinks
mac-cleaner symlinks --delete

# iOS backups
mac-cleaner extras --ios-backups
mac-cleaner extras --ios-backups --delete-backups

# Language packs
mac-cleaner extras --language-packs
mac-cleaner extras --language-packs --strip-languages

# All extras
mac-cleaner extras --all

# Universal binary thinner
mac-cleaner binary
mac-cleaner binary --thin
mac-cleaner binary --thin --arch arm64
```

### History & diff
```bash
# Show past scans
mac-cleaner history

# Compare two most recent scans
mac-cleaner diff

# Compare specific scans (by ID prefix from history)
mac-cleaner diff abc12345 def67890
```

### Undo
```bash
# List staged deletion sessions
mac-cleaner undo --list

# Restore the latest session
mac-cleaner undo

# Restore a specific session
mac-cleaner undo --session abc12345

# Purge old staged files
mac-cleaner undo --purge
```

### System inspection
```bash
mac-cleaner system --all
mac-cleaner system --launch-items
mac-cleaner system --login-items
mac-cleaner system --health
```

### Scheduler
```bash
mac-cleaner schedule install
mac-cleaner schedule install --no-notify
mac-cleaner schedule status
mac-cleaner schedule remove
```


### Self-update
```bash
mac-cleaner update          # check and prompt
mac-cleaner update --yes    # upgrade without prompting
mac-cleaner update --check  # check only, no upgrade
```

### Config
```bash
mac-cleaner config --init    # create default config file
mac-cleaner config --show    # print resolved settings
```

---

## Configuration (`~/.config/mac-cleaner/config.yaml`)

```yaml
whitelist:
  - ~/Library/Application Support/Slack
  - ~/Library/Caches/MyApp

skip_categories:
  - "System Cache"
  - "Log File"

custom_scan_roots:
  - ~/Projects

scan_orphans: true
scan_junk: true
undo_mode: true
retention_days: 30
notify_after_scan: false

large_file_threshold_mb: 100
duplicate_min_size_kb: 4

profile: developer    # active profile

profiles:
  minimal:
    skip_categories:
      - Xcode Junk
      - npm Cache
      - Cargo Cache
  developer:
    skip_categories: []
    large_file_threshold_mb: 50
```

---

## Safety Guarantees

| Feature | Description |
|---|---|
| System Protection | `com.apple.*` files are NEVER deleted |
| Running App Guard | Files of currently-running apps are protected |
| Group Container Validation | Team IDs resolved against known vendor DB |
| System Cache Isolation | OS-owned caches skipped automatically |
| Preview by Default | `scan` never modifies the filesystem |
| Undo / Restore | Files staged in `~/.mac_cleaner_trash/` by default |
| Audit Logging | All deletions logged to `~/.mac_cleaner_deleted.log` |
| Final Safety Gate | Every path validated immediately before deletion |
| Binary Backup | Fat binaries backed up as `.fat_backup` before thinning |

---

## Requirements

- macOS 10.15+
- Python 3.9+
- `rich`, `click`, `pyyaml` (auto-installed)

---

## License

Apache 2.0
