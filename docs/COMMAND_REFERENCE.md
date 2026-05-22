# Mac Deep Cleaner — Command Reference

**Version:** 2.0.1  
**CLI Commands:** `mac-cleaner` or `mdc`

This document provides comprehensive reference documentation for all available commands in Mac Deep Cleaner.

---

## Table of Contents

1. [Core Commands](#core-commands)
2. [Scanning Commands](#scanning-commands)
3. [Cleaning Commands](#cleaning-commands)
4. [System Commands](#system-commands)
5. [Developer Tools](#developer-tools)
6. [Maintenance Commands](#maintenance-commands)
7. [Monitoring & Reporting](#monitoring--reporting)
8. [Configuration](#configuration)

---

## Core Commands

### `scan`

Preview scan for orphaned app leftovers and junk (safe, read-only).

```bash
mac-cleaner scan [OPTIONS]
```

**Options:**
- `--skip-junk` — Skip general junk scanning
- `--export PATH` — Export results to JSON/YAML/HTML (by extension)
- `--whitelist PATH` — Add paths to whitelist (can be repeated)
- `--show-apps` — Show installed applications list
- `--profile NAME` — Use specified config profile
- `--dev-junk` — Scan developer junk (node_modules, venv, build dirs)
- `--dev-junk-global` — Include global caches (~/.npm, ~/.gradle, etc.)
- `--dev-root PATH` — Additional developer roots to scan
- `--root PATH` — Additional directories to scan
- `--notify` — Post macOS notification when scan completes
- `--dry-run` — Explicit alias for scan behavior (never deletes)
- `--save-history` — Save scan result to history (default: on)
- `--ci` — Emit machine-readable JSON summary
- `--threshold-mb N` — CI threshold; exit 1 when reclaimable exceeds N MB

**Examples:**
```bash
mac-cleaner scan
mac-cleaner scan --dev-junk --export report.html
mac-cleaner scan --ci --threshold-mb 500
mac-cleaner scan --profile developer --notify
```

---

### `clean`

Interactively clean orphaned app leftovers and junk.

```bash
mac-cleaner clean [OPTIONS]
```

**Options:**
- `--auto` — Auto-delete all detected items without prompting
- `--skip-junk` — Skip general junk cleaning
- `--whitelist PATH` — Add paths to whitelist
- `--export PATH` — Export results before cleaning
- `--profile NAME` — Use specified config profile
- `--dev-junk` — Clean developer junk
- `--dev-junk-global` — Include global caches
- `--dev-root PATH` — Additional developer roots
- `--root PATH` — Additional directories to scan
- `--notify` — Post notification when complete
- `--no-undo` — Permanently delete instead of staging for undo

**Behavior:**
- By default, deleted files are staged in `~/.mac_cleaner_trash/`
- Staged files can be restored with `mac-cleaner undo`
- Pass `--no-undo` for permanent deletion (faster, no recovery)

**Examples:**
```bash
mac-cleaner clean --auto
mac-cleaner clean --dev-junk --no-undo
mac-cleaner clean --profile aggressive
```

---

### `dashboard`

Run a live Rich dashboard showing scan progress in real-time.

```bash
mac-cleaner dashboard [OPTIONS]
```

**Options:**
- `--profile NAME` — Config profile to use
- `--dev-junk` — Scan developer junk
- `--dev-junk-global` — Include global caches
- `--dev-root PATH` — Additional developer roots
- `--root PATH` — Additional directories to scan

**Display:**
- Installed apps count
- Running apps (protected)
- Orphan groups and size
- General junk items and size
- Dev junk items and size
- Total reclaimable space
- Top findings by category

---

### `info`

Show tool information and safety guarantees.

```bash
mac-cleaner info
```

**Safety Guarantees:**
- **System Protection:** com.apple.* files are NEVER deleted
- **Running App Guard:** Files of currently-running apps are protected
- **Group Container Validation:** Team IDs resolved against known vendor DB
- **System Cache Isolation:** OS-owned caches require explicit flag
- **Preview by Default:** 'scan' never modifies the filesystem
- **Undo / Restore:** Deletions staged in ~/.mac_cleaner_trash/ by default
- **Audit Logging:** All deletions logged
- **Final Safety Gate:** Every path validated before deletion

---

## Scanning Commands

### `duplicates`

Find duplicate files by content hash.

```bash
mac-cleaner duplicates [OPTIONS]
```

**Options:**
- `--path PATH` — Directories to scan (default: ~/Downloads, ~/Documents, ~/Desktop, ~/Pictures)
- `--min-size KB` — Minimum file size in KB to consider (default: 100)
- `--clone-aware/--no-clone-aware` — Estimate APFS shared extents (macOS only)
- `--clone-sampling` — Sampling profile: fast, balanced, thorough (default: balanced)
- `--export PATH` — Export results to JSON
- `--delete` — Interactively delete duplicates (keeps first copy)

**Algorithm:**
- Two-phase hashing for speed and accuracy
- Only scans user directories (never /System)
- Groups identical files by hash
- Optional APFS clone-aware estimates to avoid overstating wasted space

**Examples:**
```bash
mac-cleaner duplicates
mac-cleaner duplicates --path ~/Photos --min-size 1024
mac-cleaner duplicates --delete --export dupes.json
mac-cleaner duplicates --clone-aware --clone-sampling balanced
```

---

### `large-files`

Find large files anywhere on disk, sorted by size.

```bash
mac-cleaner large-files [OPTIONS]
```

**Options:**
- `--path PATH` — Directories to scan
- `--min-mb MB` — Minimum file size in MB (default: 100)
- `--limit N` — Maximum results to show (default: 100)
- `--export PATH` — Export results to JSON

**Categories:**
- Videos
- Archives
- Disk Images
- Applications
- Documents
- Other

**Examples:**
```bash
mac-cleaner large-files
mac-cleaner large-files --min-mb 500 --limit 50
mac-cleaner large-files --path /Volumes/External --export large.json
```

---

### `symlinks`

Find broken (dangling) symbolic links in developer directories.

```bash
mac-cleaner symlinks [OPTIONS]
```

**Options:**
- `--path PATH` — Directories to scan (default: common dev paths)
- `--delete` — Delete broken symlinks after confirmation

**Default Scan Roots:**
- ~/Projects
- ~/Development
- ~/Code
- /usr/local
- Homebrew prefixes

**Examples:**
```bash
mac-cleaner symlinks
mac-cleaner symlinks --path ~/projects --delete
```

---

### `space-map`

Visual disk space map showing folder usage.

```bash
mac-cleaner space-map [OPTIONS]
```

**Options:**
- `--root PATH` — Root directories to map (default: HOME)
- `--depth N` — Folder depth to include (default: 2)
- `--limit N` — Maximum child entries per directory (default: 12)
- `--min-mb MB` — Minimum size per entry in MB (default: 1)
- `--export PATH` — Export map to JSON

**Output:**
- Tree visualization of disk usage
- Size annotations per folder
- Configurable depth and filtering

---

### `photos`

Analyze Photos libraries and storage usage.

```bash
mac-cleaner photos [OPTIONS]
```

**Options:**
- `--root PATH` — Search roots for Photos libraries (default: ~/Pictures)
- `--anywhere` — Search recursively under roots or home folder
- `--depth N` — Max recursion depth for --anywhere (default: 6)
- `--details` — Show file type breakdown for originals
- `--export PATH` — Export analysis to JSON

**Analysis Includes:**
- Library total size
- Originals size and count
- Previews size
- Database size
- File type breakdown (HEIC, JPEG, PNG, etc.)

---

### `simulators`

Inspect and clean iOS Simulator data.

```bash
mac-cleaner simulators [OPTIONS]
```

**Options:**
- `--purge-unavailable` — Delete data for unavailable simulators only
- `--purge-all` — Delete data for all simulators (destructive)
- `--purge-caches` — Delete CoreSimulator caches and logs
- `--yes` — Skip confirmation prompts

**Data Types:**
- Simulator device data
- Runtime support files
- CoreSimulator caches
- Device logs

---

### `extras`

Scan for iOS backups and removable language packs.

```bash
mac-cleaner extras [OPTIONS]
```

**Options:**
- `--ios-backups` — Scan for old iOS/iPhone backups
- `--language-packs` — Scan for removable language packs in /Applications
- `--all` — Run all extra scans
- `--delete-backups` — Interactively delete old iOS backups
- `--strip-languages` — Interactively strip unused language packs

**iOS Backup Info:**
- Device name
- iOS version
- Age (days)
- Size

**Language Packs:**
- Identifies removable .lproj directories
- Shows potential space savings per app

---

### `binary`

Detect universal (fat) binaries and optionally thin them.

```bash
mac-cleaner binary [OPTIONS]
```

**Options:**
- `--path PATH` — Directories to scan
- `--arch ARCH` — Target arch: arm64 or x86_64 (defaults to current CPU)
- `--thin` — Interactively thin fat binaries
- `--no-backup` — Skip .fat_backup copy (irreversible!)

**How It Works:**
- Detects binaries containing both arm64 and x86_64 slices
- Uses `ditto --arch` (Apple-recommended method)
- Creates backup before thinning (unless --no-backup)

---

## Cleaning Commands

### `uninstall`

Remove an app and its data (full uninstall).

```bash
mac-cleaner uninstall APP_QUERY [OPTIONS]
```

**Options:**
- `--yes` — Skip confirmation and uninstall immediately
- `--no-undo` — Permanently delete instead of staging
- `--keep-preferences` — Keep Preferences and Saved State data
- `--force` — Allow uninstall even if app appears running

**Uninstall Plan Includes:**
- Application bundle
- Application Support leftovers
- Caches
- Logs
- Group Container data (validated)

**Examples:**
```bash
mac-cleaner uninstall "Google Chrome"
mac-cleaner uninstall Safari --keep-preferences
mac-cleaner uninstall Xcode --yes --no-undo
```

---

### `browser-data`

Analyze and optionally clean browser data.

```bash
mac-cleaner browser-data [OPTIONS]
```

**Options:**
- `--browser NAME` — Limit to specific browsers (safari, chrome, firefox, edge, brave)
- `--category TYPE` — Limit to categories (cache, cookies, history, downloads, site-data, sessions)
- `--clean` — Delete selected data
- `--all` — Delete all supported categories for selected browsers
- `--yes` — Skip confirmation

**Supported Browsers:**
- Safari
- Chrome
- Firefox
- Edge
- Brave

**Data Categories:**
- Cache files
- Cookies
- Browsing history
- Download history
- Site data (localStorage, IndexedDB)
- Session data

---

### `developer`

Scan and optionally clean developer junk.

```bash
mac-cleaner developer [OPTIONS]
```

**Options:**
- `--root PATH` — Roots to scan (default: config + common project folders)
- `--max-depth N` — Max depth for scanning
- `--global` — Include global caches (~/.npm, ~/.gradle, etc.)
- `--limit N` — Limit number of items returned (0 = no limit)
- `--delete` — Delete detected developer junk
- `--no-undo` — Permanently delete instead of staging
- `--yes` — Skip confirmation prompts
- `--export PATH` — Export report to JSON
- `--profile NAME` — Config profile to use

**Detected Patterns:**
- node_modules
- venv, .venv, __pycache__
- target (Rust)
- bin, obj (C#/Unity)
- dist, build
- coverage
- .gradle, .m2, .cargo, .nuget (global caches)

---

### `xcode-cleaner`

Inspect and clean Xcode derived data and caches.

```bash
mac-cleaner xcode-cleaner [OPTIONS]
```

**Options:**
- `--category NAME` — Limit cleanup to matching categories
- `--delete` — Delete selected Xcode data
- `--yes` — Skip confirmation prompts
- `--export PATH` — Export results to JSON

**Categories:**
- DerivedData
- DeviceSupport
- Archives
- Caches
- Documentation

---

### `installer-hunter`

Find old installers and PKG files.

```bash
mac-cleaner installer-hunter [OPTIONS]
```

**Options:**
- `--root PATH` — Roots to scan (default: Downloads/Desktop/Documents)
- `--min-age-days N` — Only show installers older than N days
- `--min-mb MB` — Minimum size in MB
- `--include-archives` — Include .zip/.tar archives
- `--limit N` — Maximum results to show (default: 200)
- `--delete` — Delete installers under allowed roots
- `--yes` — Skip confirmation prompts
- `--export PATH` — Export results to JSON

**File Types Detected:**
- .pkg
- .dmg
- .mpkg
- Optional: .zip, .tar, .gz

---

### `purgeable`

Inspect purgeable space and reclaim via snapshot thinning.

```bash
mac-cleaner purgeable [OPTIONS]
```

**Options:**
- `--volume PATH` — Volume path to inspect (default: /)
- `--thin-gb GB` — Reclaim at least this many GB using tmutil thinning
- `--thin-mb MB` — Reclaim at least this many MB
- `--delete-older-than N` — Delete local snapshots older than N days
- `--keep N` — Keep the newest N snapshots
- `--yes` — Skip confirmation prompts
- `--export PATH` — Export summary to JSON

---

### `cloud-junk`

Scan cloud storage caches and logs.

```bash
mac-cleaner cloud-junk [OPTIONS]
```

**Options:**
- `--provider NAME` — Limit to provider (dropbox, google-drive, onedrive, box)
- `--clean` — Delete detected cache/log directories
- `--yes` — Skip confirmation for deletions

**Providers Supported:**
- Dropbox
- Google Drive
- OneDrive
- Box

---

## System Commands

### `system`

Inspect startup items, login items, and system security health.

```bash
mac-cleaner system [OPTIONS]
```

**Options:**
- `--launch-items` — Show LaunchAgents / LaunchDaemons
- `--login-items` — Show Login Items
- `--health` — Check system health (SIP, Full Disk Access)
- `--all` — Run all checks

**Health Checks:**
- SIP (System Integrity Protection) status
- Full Disk Access availability
- macOS version
- Security warnings

---

### `memory-pressure`

Inspect memory pressure and optionally purge caches.

```bash
mac-cleaner memory-pressure [OPTIONS]
```

**Options:**
- `--relieve` — Run purge to relieve memory pressure
- `--yes` — Skip confirmation for purge

**Metrics Displayed:**
- Total memory
- Used memory
- Free memory
- Compressed memory
- Free percentage
- Pressure level
- Swap used/free

---

### `brew`

Manage Homebrew caches and maintenance.

```bash
mac-cleaner brew [OPTIONS]
```

**Options:**
- `--outdated` — Check for outdated formulae and casks
- `--cleanup` — Run brew cleanup
- `--prune-all` — Run brew cleanup --prune=all
- `--autoremove` — Run brew autoremove
- `--doctor` — Run brew doctor
- `--update` — Run brew update
- `--yes` — Skip confirmation for maintenance actions

**Information Displayed:**
- Homebrew version
- Prefix location
- Cache size
- Cellar size
- Formulae count
- Casks count

---

### `permissions`

Audit macOS privacy permissions (TCC database).

```bash
mac-cleaner permissions [OPTIONS]
```

**Options:**
- `--system` — Include system-wide TCC database (may require privileges)
- `--export PATH` — Export entries to JSON

**Permissions Audited:**
- Camera access
- Microphone access
- Screen recording
- Accessibility
- Full Disk Access
- Contacts, Calendar, Reminders
- Photos library access

---

### `snapshots`

Inspect and prune APFS local snapshots.

```bash
mac-cleaner snapshots [OPTIONS]
```

**Options:**
- `--volume PATH` — Volume path to inspect (default: /)
- `--delete-older-than N` — Delete snapshots older than N days
- `--keep N` — Keep the newest N snapshots
- `--yes` — Skip confirmation for deletions

---

### `time-machine`

Inspect and guard Time Machine status.

```bash
mac-cleaner time-machine [OPTIONS]
```

**Options:**
- `--enable` — Enable Time Machine backups
- `--disable` — Disable Time Machine backups
- `--warn-days N` — Warn if last backup is older than N days (default: 7)
- `--export PATH` — Export status to JSON

**Status Information:**
- Backup destinations
- Local snapshot count
- Last backup timestamp
- Backup age warning

---

## Maintenance Commands

### `dns-cache`

Flush DNS caches.

```bash
mac-cleaner dns-cache [OPTIONS]
```

**Options:**
- `--flush` — Flush DNS caches
- `--yes` — Skip confirmation prompts

---

### `font-cache`

Rebuild font caches.

```bash
mac-cleaner font-cache [OPTIONS]
```

**Options:**
- `--rebuild` — Rebuild font caches using atsutil
- `--clear-user` — Delete user font cache folders before rebuild
- `--yes` — Skip confirmation prompts

---

### `spotlight`

Inspect or rebuild Spotlight index.

```bash
mac-cleaner spotlight [OPTIONS]
```

**Options:**
- `--volume PATH` — Volume path to inspect (default: /)
- `--reindex` — Rebuild Spotlight index
- `--enable` — Enable Spotlight indexing
- `--disable` — Disable Spotlight indexing
- `--yes` — Skip confirmation prompts

---

### `power-optimizer`

Show or apply power optimization settings.

```bash
mac-cleaner power-optimizer [OPTIONS]
```

**Options:**
- `--apply` — Apply recommended power settings
- `--restore` — Restore last saved power profile
- `--scope SCOPE` — all, battery, or ac (default: all)
- `--yes` — Skip confirmation prompts

**Settings Managed:**
- Standby delay
- Power nap
- Wake on LAN
- Display sleep timers
- Hard disk sleep

---

### `app-updates`

Check for app updates across system, brew, and App Store.

```bash
mac-cleaner app-updates [OPTIONS]
```

**Options:**
- `--system` — Check macOS software updates
- `--brew` — Check Homebrew updates
- `--mas` — Check Mac App Store updates (requires mas)
- `--all` — Run all checks (default)
- `--export PATH` — Export results to JSON

---

### `pkg-receipts`

Inspect and manage pkg receipts.

```bash
mac-cleaner pkg-receipts [OPTIONS]
```

**Options:**
- `--search STRING` — Filter receipts by substring
- `--limit N` — Limit results (default: 30)
- `--details` — Show detailed receipt info
- `--forget ID` — Forget a pkg receipt by identifier
- `--yes` — Skip confirmation prompts
- `--export PATH` — Export receipts to JSON

---

## Monitoring & Reporting

### `history`

Show past scan records stored in ~/.config/mac-cleaner/history/.

```bash
mac-cleaner history [OPTIONS]
```

**Options:**
- `--limit N` — Number of records to show (default: 10)

**Information Displayed:**
- Scan date
- Profile used
- Orphan bytes
- Junk bytes
- Total reclaimable

---

### `diff`

Compare two scan records.

```bash
mac-cleaner diff [SCAN_A] [SCAN_B]
```

**Arguments:**
- `SCAN_A` — Older scan ID prefix (optional, defaults to second most recent)
- `SCAN_B` — Newer scan ID prefix (optional, defaults to most recent)

**Comparison Shows:**
- Size delta between scans
- New orphans
- Resolved orphans
- Persistent orphans

---

### `storage-trend`

Track disk usage trends over time.

```bash
mac-cleaner storage-trend [OPTIONS]
```

**Options:**
- `--record` — Record a new snapshot before showing results
- `--limit N` — Maximum snapshots to display (default: 12)
- `--days N` — Summarize only the last N days
- `--export PATH` — Export snapshots to JSON
- `--volume PATH` — Volume path to record (default: /)

---

### `weekly-digest`

Generate a weekly scan digest report.

```bash
mac-cleaner weekly-digest [OPTIONS]
```

**Options:**
- `--days N` — Number of days to include (default: 7)
- `--export PATH` — Export digest to JSON

**Report Includes:**
- Date range
- Scan count
- Total reclaimable
- Average per scan
- Top orphaned apps
- Top junk categories
- Top dev junk categories

---

### `impact-score`

Compute a cleaning impact score from scan history.

```bash
mac-cleaner impact-score [OPTIONS]
```

**Options:**
- `--scan-id PREFIX` — Scan ID prefix to score (default: latest)
- `--export PATH` — Export impact score to JSON

**Score Factors:**
- Total reclaimable bytes
- Item counts
- Category distribution
- Historical trends

---

### `breach`

Check emails against Have I Been Pwned.

```bash
mac-cleaner breach [OPTIONS]
```

**Options:**
- `--email ADDRESS` — Email address to check (can be repeated)
- `--api-key KEY` — HIBP API key (or set HIBP_API_KEY env var)
- `--delay SECONDS` — Delay between requests (default: 1.6)
- `--use-watchlist` — Check addresses saved in watchlist
- `--save` — Save provided emails to watchlist
- `--export PATH` — Export results to JSON

---

### `recent-activity`

Scan and optionally clear recent activity files.

```bash
mac-cleaner recent-activity [OPTIONS]
```

**Options:**
- `--clear` — Clear items under ~/Library/Recent Items
- `--yes` — Skip confirmation for clearing

**Categories:**
- Recent documents
- Recent applications
- Recent servers
- Recent volumes

---

## Configuration

### `config`

Manage the configuration file (~/.config/mac-cleaner/config.yaml).

```bash
mac-cleaner config [OPTIONS]
```

**Options:**
- `--init` — Create a default config file if none exists
- `--show` — Print the resolved config
- `--profile NAME` — Use specified profile

**Usage:**
```bash
mac-cleaner config --init           # Create default config
mac-cleaner config --show           # Print resolved settings
mac-cleaner config --profile dev    # Show dev profile config
```

---

### `config-sync`

Sync configuration across multiple Macs.

```bash
mac-cleaner config-sync SUBCOMMAND [OPTIONS]
```

**Subcommands:**

#### `export`
Export config to sync directory.
```bash
mac-cleaner config-sync export [--dest DIR] [--include-history] [--no-icloud]
```

#### `import`
Import config from sync directory.
```bash
mac-cleaner config-sync import [--src DIR] [--no-icloud] [--no-backup]
```

#### `status`
Show sync metadata.
```bash
mac-cleaner config-sync status [--dir DIR] [--no-icloud]
```

---

### `schedule`

Manage weekly automatic scan schedule.

```bash
mac-cleaner schedule SUBCOMMAND
```

**Subcommands:**

#### `install`
Install a weekly LaunchAgent to run scans automatically.
```bash
mac-cleaner schedule install [--no-notify]
```

#### `remove`
Remove the weekly scan LaunchAgent.
```bash
mac-cleaner schedule remove
```

#### `status`
Show whether the weekly scan is scheduled and loaded.
```bash
mac-cleaner schedule status
```

---

### `update`

Check for a newer version on PyPI and optionally upgrade.

```bash
mac-cleaner update [OPTIONS]
```

**Options:**
- `--check` — Check only, do not upgrade
- `--yes, -y` — Upgrade without prompting

---

### `completions`

Generate shell completion scripts.

```bash
mac-cleaner completions [OPTIONS]
```

**Options:**
- `--shell TYPE` — Shell type: bash, zsh, fish
- `--instructions` — Show install instructions for your shell

**Installation:**
```bash
# Bash
mac-cleaner completions --shell bash >> ~/.bash_completions

# Zsh
mac-cleaner completions --shell zsh > ~/.zfunc/_mac-cleaner

# Fish
mac-cleaner completions --shell fish > ~/.config/fish/completions/mac-cleaner.fish
```

---

### `tui-picker`

Interactive app picker for uninstall operations.

```bash
mac-cleaner tui-picker [OPTIONS]
```

**Options:**
- `--uninstall` — Uninstall the selected app
- `--no-undo` — Permanently delete instead of staging
- `--reveal` — Reveal the app in Finder
- `--open` — Open the app after selection
- `--yes` — Skip confirmation prompts

---

### `menubar`

Menu bar companion for SwiftBar/xbar.

```bash
mac-cleaner menubar SUBCOMMAND
```

**Subcommands:**

#### `status`
Emit status for menu bar tools.
```bash
mac-cleaner menubar status [--format plain|swiftbar]
```

#### `install`
Install a menu bar plugin script.
```bash
mac-cleaner menubar install [--target swiftbar|xbar] [--interval MIN] [--dir PATH]
```

#### `remove`
Remove menu bar plugin scripts.
```bash
mac-cleaner menubar remove [--target swiftbar|xbar] [--dir PATH]
```

---

### `undo`

Restore files from the staging area (undo a clean operation).

```bash
mac-cleaner undo [OPTIONS]
```

**Options:**
- `--list` — List available sessions without restoring
- `--session ID` — Session ID prefix to restore (default: latest)
- `--purge` — Permanently purge old staged files beyond retention period
- `--purge-all` — Permanently purge ALL staged sessions regardless of age
- `--verify` — Verify checksums after restore

**Session Management:**
- Sessions stored in ~/.mac_cleaner_trash/
- Sessions older than 30 days auto-purged
- Each session has unique ID for restoration

---

### `uninstall-cli`

Uninstall mac-cleaner CLI and data.

> Note: This command removes the mac-cleaner installation itself along with all configuration and history data.

---

## Global Options

These options are available on most commands:

- `--verbose` — Enable debug logging
- `--log-file PATH` — Write logs to specified file
- `--dry-run` — Do not modify anything (preview mode)
- `--yes` — Skip confirmation prompts
- `--help` — Show command help

---

## Exit Codes

- `0` — Success
- `1` — Error or threshold exceeded (in CI mode)
- `2` — Invalid arguments

---

## Environment Variables

- `HIBP_API_KEY` — Have I Been Pwned API key for breach monitoring
- `MAC_CLEANER_CONFIG` — Override config file location
- `NO_COLOR` — Disable colored output

---

## Configuration Profiles

Built-in profiles for different user types:

| Profile | Focus | Recommended For |
|---------|-------|-----------------|
| `beginner` | Safe defaults, skips dev caches | General users |
| `developer` | Includes dev junk scanning | Software developers |
| `professional` | Aggressive dev cleanup, lower thresholds | Power users |
| `designer` | Larger file focus, no dev junk | Creative professionals |
| `student` | Safe defaults for school devices | Students |
| `children` | Minimal, safest defaults | Children's devices |

---

*Documentation generated for Mac Deep Cleaner v2.0.0*
