<div align="center">
  
# Mac Deep Cleaner v1.5.0

**Professional macOS cleanup tool — Smart App Orphan Detector**

![GitHub license](https://img.shields.io/github/license/NK2552003/Mac-Cleaner?style=flat-square)
![GitHub last commit](https://img.shields.io/github/last-commit/NK2552003/Mac-Cleaner?style=flat-square)
![GitHub repo size](https://img.shields.io/github/repo-size/NK2552003/Mac-Cleaner?style=flat-square)
![Platform](https://img.shields.io/badge/platform-macOS-lightgrey?style=flat-square&logo=apple)
[![PyPI Downloads](https://static.pepy.tech/personalized-badge/mac-deep-cleaner?period=total&units=INTERNATIONAL_SYSTEM&left_color=BLACK&right_color=ORANGE&left_text=downloads)](https://pepy.tech/projects/mac-deep-cleaner)

---

</div>

Detects and removes leftover files from uninstalled apps, stale caches, crash reports, logs, and other system junk — safely, with multiple layers of protection and full undo support.

Use either command name:
```bash
mac-cleaner scan
mdc scan
```
`mdc` is a shorter alias for every command, for example `mdc dashboard`,
`mdc clean`, and `mdc scan --ci --threshold-mb 500`.

---

## Features (All)

- **Smart orphan detection** — finds leftover app data after uninstalling apps
- **General junk scan** — caches, logs, crash reports, Trash, `.DS_Store`, Xcode artefacts, package manager caches
- **Developer junk scan** — `node_modules`, `venv`, build outputs, coverage dirs (opt-in)
- **Global dev caches** — `~/.npm`, `~/.gradle`, `~/.m2`, `~/.cargo`, `~/.nuget` (opt-in)
- **Duplicate finder** — SHA-256 content hashing, two-phase (head + full), sorted by wasted space
- **Large file scanner** — finds files ≥100 MB (configurable), categorised by type
- **Broken symlink detector** — walks `/usr/local`, `/opt/homebrew`, `~/bin`, etc.
- **Browser data cleaner** — cache, cookies, history, sessions (opt-in delete)
- **Space map** — disk usage overview by folder tree
- **Photos analyzer** — summaries of Photos libraries and originals
- **iOS simulator cleaner** — shows simulator sizes and can purge
- **Full app uninstaller** — remove app bundle plus known data
- **Shell completions** — bash, zsh, fish
- **iOS backup finder** — parses `MobileSync/Backup` manifests, shows device/age/size
- **Language pack stripper** — detects removable `.lproj` dirs in every installed app
- **Universal binary thinner** — uses `ditto --arch` safely; creates `.fat_backup` by default
- **Undo / restore** — files staged in `~/.mac_cleaner_trash/` instead of permanent delete
- **Config file** — `~/.config/mac-cleaner/config.yaml` with profile support
- **Scan history** — JSON records in `~/.config/mac-cleaner/history/`
- **Diff** — compare any two scans to see what's new or resolved
- **HTML report** — self-contained with Chart.js doughnut + collapsible sections
- **System inspector** — LaunchAgents, LaunchDaemons, login items, SIP status
- **Memory pressure reliever** — reports pressure, optional cache purge
- **Homebrew manager** — cache sizes, outdated list, cleanup and autoremove
- **Storage trend tracker** — snapshots disk usage over time
- **Recent activity cleaner** — scans recent-items files (safe clear)
- **Permissions auditor** — TCC privacy access audit (read-only)
- **APFS snapshot guard** — list and prune local snapshots
- **Menu bar companion** — SwiftBar/xbar plugin for last scan summary
- **Data breach monitor** — checks emails via HIBP API (opt-in)
- **Cloud storage junk** — scans Dropbox/Drive/OneDrive/Box caches
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
pip install mac-deep-cleaner
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

# Developer junk scan
mac-cleaner scan --dev-junk

# Developer junk + global caches
mac-cleaner scan --dev-junk --dev-junk-global

# Interactive cleanup (files staged for undo by default)
mac-cleaner clean

# Auto-delete everything detected
mac-cleaner clean --auto

# Force preview mode (no deletes anywhere)
mac-cleaner --dry-run clean

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

### Logging
```bash
# Enable debug logging (writes to ~/.config/mac-cleaner/mac-cleaner.log)
mac-cleaner scan --verbose

# Use a custom log file
mac-cleaner scan --log-file ~/mac-cleaner.log
```

### New scanners
```bash
# Shell completions
mac-cleaner completions --shell zsh --instructions

# Full app uninstall
mac-cleaner uninstall "Slack"

# Browser data cleanup
mac-cleaner browser-data
mac-cleaner browser-data --browser chrome --category cache --clean

# Disk usage map
mac-cleaner space-map --depth 2 --limit 12

# Photos library analyzer
mac-cleaner photos --details

# iOS simulator cleaner
mac-cleaner simulators
mac-cleaner simulators --purge-unavailable --yes

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

### P2/P3 system utilities
```bash
# Memory pressure
mac-cleaner memory-pressure
mac-cleaner memory-pressure --relieve

# Homebrew manager
mac-cleaner brew --outdated
mac-cleaner brew --cleanup --yes

# Storage trend snapshots
mac-cleaner storage-trend --record
mac-cleaner storage-trend --days 7

# Recent activity cleanup (Recent Items folder only)
mac-cleaner recent-activity
mac-cleaner recent-activity --clear

# Permissions audit (TCC)
mac-cleaner permissions
mac-cleaner permissions --system --export tcc.json

# APFS snapshots
mac-cleaner snapshots
mac-cleaner snapshots --delete-older-than 14 --yes

# Menu bar companion
mac-cleaner menubar install --interval 15
mac-cleaner menubar status --format swiftbar

# Breach monitor (HIBP)
mac-cleaner breach --email you@example.com --api-key $HIBP_API_KEY

# Cloud storage junk
mac-cleaner cloud-junk
mac-cleaner cloud-junk --provider dropbox --clean
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

scan_dev_junk: false
scan_dev_junk_global: false
dev_junk_roots:
  - ~/Projects
dev_junk_max_depth: 6

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
