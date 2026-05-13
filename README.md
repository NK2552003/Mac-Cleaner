<div align="center">

# Mac Deep Cleaner

**Reclaim gigabytes of disk space with confidence — the safest, smartest macOS cleanup tool ever built.**

[![PyPI Version](https://img.shields.io/pypi/v/mac-deep-cleaner.svg)](https://pypi.org/project/mac-deep-cleaner/)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-Apache%202.0-green.svg)](LICENSE)
[![macOS 10.15+](https://img.shields.io/badge/macOS-10.15+-silver.svg)](https://www.apple.com/macos/)
[![PyPI Downloads](https://static.pepy.tech/personalized-badge/mac-deep-cleaner?period=total&units=INTERNATIONAL_SYSTEM&left_color=BLACK&right_color=ORANGE&left_text=downloads)](https://pepy.tech/projects/mac-deep-cleaner)

</div>

**Mac Deep Cleaner** is a professional-grade macOS utility that intelligently detects and removes leftover files from uninstalled apps, stale caches, crash reports, logs, and system junk — with **multiple layers of protection** and **full undo support**.

```bash
# Two commands, same powerful tool
mac-cleaner scan    # Full-featured
mdc scan            # Quick alias
```

---

## Why Mac Deep Cleaner?

| **Safety First** | **Lightning Fast** | **Smart Detection** |
|---------------------|----------------------|------------------------|
| Never touches system files (`com.apple.*`) | Multi-threaded scanning | Bundle ID matching technology |
| Running apps are protected | Progressively displays results | Team ID validation for containers |
| Full undo/restore capability | Optimized hashing algorithms | Cross-references 45+ locations |
| Audit logging for every action | Minimal memory footprint | AI-powered orphan detection |

---

## Installation

### Quick Install (Recommended)
```bash
pip install mac-deep-cleaner
```

###  From Source
```bash
git clone https://github.com/NK2552003/Mac-Cleaner.git
cd Mac-Cleaner
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

---

## Quick Start

### Scan Your System (Safe Preview)
```bash
mac-cleaner scan
```

### Review the Dashboard
```bash
mac-cleaner dashboard
```

### Clean Up (with Undo Support)
```bash
mac-cleaner clean          # Interactive mode
mac-cleaner clean --auto   # Auto-delete detected items
```

### Need to Restore?
```bash
mac-cleaner undo           # Restore last cleanup
```

---

## Documentation

Comprehensive guides for every use case:

| Document | Description |
|----------|-------------|
| **[Features Guide](docs/FEATURES.md)** | Complete list of all 60+ features with examples |
| **[Command Reference](docs/COMMAND_REFERENCE.md)** | Detailed CLI documentation for every command |
| **[Architecture Guide](docs/ARCHITECTURE.md)** | Internal structure, modules, and extension points |
| **[PyPI Publishing](docs/PYPI_PUBLISHING.md)** | Build and publish instructions |

---

## Core Features

### Smart Scanning
- **Orphan Detection** — Finds leftover data from uninstalled apps using bundle ID matching
- **General Junk** — Caches, logs, crash reports, `.DS_Store`, Xcode artifacts, package manager caches
- **Developer Junk** — `node_modules`, `venv`, build outputs, coverage dirs (opt-in)
- **Global Dev Caches** — `~/.npm`, `~/.gradle`, `~/.m2`, `~/.cargo`, `~/.nuget` (opt-in)
- **Duplicate Finder** — SHA-256 hashing with two-phase optimization
- **Large File Scanner** — Find files ≥100 MB, categorized by type
- **Broken Symlink Detector** — Scans Homebrew, `/usr/local`, `~/bin`, and more

###  Advanced Cleaning
- **Browser Data Cleaner** — Cache, cookies, history, sessions (Chrome, Firefox, Safari, Edge, Brave)
- **iOS Simulator Cleaner** — Manage simulator data and caches
- **Photos Library Analyzer** — Breakdown of Photos library storage
- **iOS Backup Finder** — Parse MobileSync backups with device info
- **Language Pack Stripper** — Remove unused `.lproj` directories
- **Universal Binary Thinner** — Safely thin fat binaries with `ditto --arch`
- **Full App Uninstaller** — Remove app bundles plus all associated data

###  Reporting & Monitoring
- **Space Map** — Visual disk usage tree
- **HTML Reports** — Self-contained reports with interactive charts
- **Scan History** — JSON records with diff comparison
- **Weekly Digest** — Aggregated weekly summaries
- **Impact Score** — Measure cleaning effectiveness (0-100)
- **Storage Trends** — Track disk usage over time

###  System Utilities
- **System Inspector** — LaunchAgents, LaunchDaemons, login items, SIP status
- **Memory Pressure Reliever** — Report and purge memory caches
- **Homebrew Manager** — Cache cleanup, outdated list, autoremove
- **DNS Cache Flush** — Refresh name resolution
- **Font Cache Rebuild** — Safely rebuild ATS caches
- **Spotlight Re-index** — Rebuild metadata index
- **Power Optimizer** — Apply recommended `pmset` settings
- **App Update Checker** — System, Homebrew, and App Store updates
- **PKG Receipt Manager** — List and forget pkgutil receipts
- **Permissions Auditor** — TCC privacy access audit (read-only)
- **Time Machine Guard** — Status, age checks, local snapshots
- **APFS Snapshot Guard** — List and prune local snapshots

###  User Experience
- **Live TUI Dashboard** — Real-time Rich layout during scans
- **Interactive TUI Picker** — Keyboard-driven app selection
- **Shell Completions** — Bash, zsh, fish support
- **macOS Notifications** — Native notifications via `osascript`
- **Menu Bar Companion** — SwiftBar/xbar plugin integration
- **CI Mode** — JSON output with threshold-based exit codes
- **Undo/Restore** — Staged deletions with checksum verification

###  Cloud & Security
- **Cloud Storage Junk** — Dropbox, Google Drive, OneDrive, Box caches
- **Data Breach Monitor** — HIBP API integration for email checks
- **Multi-Mac Config Sync** — Export/import configurations
- **Scheduler** — LaunchAgent for automated weekly scans

---

## Safety Guarantees

Mac Deep Cleaner implements **7 layers of protection**:

| Layer | Protection |
|-------|------------|
|  **System Protection** | `com.apple.*` files are **NEVER** deleted |
|  **Running App Guard** | Active applications are automatically protected |
|  **Group Container Validation** | Team IDs verified against vendor database |
|  **System Cache Isolation** | OS-owned caches skipped by default |
|  **Preview by Default** | `scan` command never modifies filesystem |
|  **Undo/Restore** | Files staged in `~/.mac_cleaner_trash/` for recovery |
|  **Audit Logging** | Every deletion logged to `~/.mac_cleaner_deleted.log` |
|  **Final Safety Gate** | Path validation immediately before deletion |
|  **Binary Backup** | Fat binaries backed up as `.fat_backup` before thinning |

---

##  Common Workflows

### Daily Maintenance
```bash
# Quick scan with live dashboard
mdc dashboard

# Clean up detected items interactively
mdc clean

# Check system health
mdc system --health
```

###  Developer Cleanup
```bash
# Scan with developer junk detection
mdc scan --dev-junk --dev-junk-global

# Clean Xcode derived data
mdc xcode-cleaner --delete --yes

# Find large project files
mdc large-files --min-mb 50 --root ~/Projects
```

### iOS Developer Tools
```bash
# List simulators and their sizes
mdc simulators

# Purge unavailable simulators
mdc simulators --purge-unavailable --yes

# Manage iOS backups
mdc extras --ios-backups
```

### Targeted Cleaning
```bash
# Uninstall an app completely
mdc uninstall "Slack"

# Clean specific browser data
mdc browser-data --browser chrome --category cache --clean

# Find and remove old installers
mdc installer-hunter --min-age-days 30 --delete --yes
```

### Reporting & Automation
```bash
# Export scan results
mdc scan --export report.html

# CI/CD integration
mdc scan --ci --threshold-mb 500

# Weekly digest
mdc weekly-digest --days 7

# Compare scans
mdc diff
```

---

## Configuration

Create a config file at `~/.config/mac-cleaner/config.yaml`:

```yaml
# Active profile
profile: developer

# Protected paths
whitelist:
  - ~/Library/Application Support/ImportantApp
  - ~/Projects/critical-folder

# Categories to skip
skip_categories:
  - "System Cache"
  - "Log File"

# Custom scan locations
custom_scan_roots:
  - ~/Development
  - /Volumes/ExternalDrive/Projects

# Scan behavior
scan_orphans: true
scan_junk: true
undo_mode: true
retention_days: 30

# Thresholds
large_file_threshold_mb: 100
duplicate_min_size_kb: 4

# Developer options
scan_dev_junk: true
scan_dev_junk_global: false
dev_junk_roots:
  - ~/Projects
dev_junk_max_depth: 6

# Custom profiles
profiles:
  minimal:
    skip_categories:
      - Xcode Junk
      - npm Cache
  aggressive:
    skip_categories: []
    large_file_threshold_mb: 50
    scan_dev_junk_global: true
```

### Profile Types

| Profile | Best For | Settings |
|---------|----------|----------|
| `beginner` | First-time users | Maximum safety, conservative defaults |
| `developer` | Software engineers | Dev junk enabled, lower thresholds |
| `professional` | Power users | Aggressive cleaning, all features |
| `designer` | Creative professionals | Large file focus, media optimization |
| `minimal` | School/shared devices | Maximum protection, limited scope |

---

## Advanced Commands

### History & Comparison
```bash
# View scan history
mdc history

# Compare last two scans
mdc diff

# Compare specific scans
mdc diff abc12345 def67890
```

### Undo Operations
```bash
# List all undo sessions
mdc undo --list

# Restore latest session
mdc undo

# Restore specific session
mdc undo --session abc12345

# Verify checksums during restore
mdc undo --verify

# Clean old sessions
mdc undo --purge
```

### System Management
```bash
# Full system inspection
mdc system --all

# Memory management
mdc memory-pressure --relieve

# Purgeable space
mdc purgeable --thin-gb 10 --yes

# Storage trends
mdc storage-trend --record
mdc storage-trend --days 7
```

### Scheduling & Automation
```bash
# Install weekly scan scheduler
mdc schedule install

# Check scheduler status
mdc schedule status

# Remove scheduler
mdc schedule remove
```

### Self-Update
```bash
# Check for updates
mdc update --check

# Update automatically
mdc update --yes
```

### Config Management
```bash
# Initialize config
mdc config --init

# Show current config
mdc config --show

# Sync across Macs
mdc config-sync export
mdc config-sync import
```

---

## Example Output

### Scan Summary
```
╔══════════════════════════════════════════════════╗
║         Mac Deep Cleaner - Scan Results          ║
╠══════════════════════════════════════════════════╣
║      Orphaned Apps:    23 items  (1.2 GB)        ║
║      General Junk:     156 items (3.4 GB)        ║
║      Developer Junk:   42 items  (2.1 GB)        ║
╠══════════════════════════════════════════════════╣
║           Total Reclaimable: 6.7 GB              ║
╚══════════════════════════════════════════════════╝

Safe to clean: 6.5 GB
Review recommended: 0.2 GB
```

### Space Map
```
/Users (256 GB)
├── Library (45 GB)
│   ├── Caches (12 GB)
│   ├── Application Support (18 GB)
│   └── Logs (2.3 GB)
├── Documents (89 GB)
└── Downloads (34 GB)
```

---

## Requirements

- **macOS:** 10.15 (Catalina) or later
- **Python:** 3.9 or higher
- **Dependencies:** `rich`, `click`, `pyyaml` (auto-installed)

---

## Contributing

We welcome contributions! Please read our contributing guidelines before submitting PRs.

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `pytest tests/`
5. Submit a pull request

---

## License

Copyright © 2024 Mac Deep Cleaner Contributors

Licensed under the [Apache License 2.0](LICENSE).

---

## Support

-  **Documentation:** [docs/](docs/)
-  **Issues:** [GitHub Issues](https://github.com/NK2552003/Mac-Cleaner/issues)
---

<div align="center">

**Made with ❤️ for the macOS community**

[⭐ Star this repo](https://github.com/NK2552003/Mac-Cleaner) 
[Read the COMMAND REFERENCE](docs/COMMAND_REFERENCE.md) 
[Report an issue](https://github.com/NK2552003/Mac-Cleaner/issues)

</div>
