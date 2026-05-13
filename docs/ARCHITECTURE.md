# Mac Deep Cleaner — Architecture & Implementation Guide

**Version:** 2.0.0

This document provides a comprehensive overview of the internal architecture, module structure, and implementation details of Mac Deep Cleaner.

---

## Table of Contents

1. [Project Structure](#project-structure)
2. [Core Modules](#core-modules)
3. [Scanner Modules](#scanner-modules)
4. [Reporting Modules](#reporting-modules)
5. [Configuration System](#configuration-system)
6. [Safety Mechanisms](#safety-mechanisms)
7. [Data Flow](#data-flow)
8. [Extension Points](#extension-points)

---

## Project Structure

```
mac-deep-cleaner/
├── src/
│   ├── __init__.py          # Package initialization, version
│   ├── cli.py               # Main CLI entry point (Click-based)
│   ├── constants.py         # Global constants, paths, defaults
│   ├── utils.py             # Utility functions (logging, bytes formatting)
│   │
│   ├── config/
│   │   ├── __init__.py
│   │   ├── config.py        # Configuration loading, profiles
│   │   ├── history.py       # Scan history management
│   │   └── models.py        # Data models (JunkEntry, etc.)
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── scanner.py       # Orphan and junk scanning logic
│   │   ├── cleaner.py       # Cleanup execution engine
│   │   ├── safety.py        # Safety checks, path validation
│   │   ├── dry_run.py       # Dry-run mode handling
│   │   ├── undo.py          # Undo/restore session management
│   │   ├── uninstaller.py   # App uninstallation logic
│   │   ├── system_inspector.py  # Launch items, SIP checks
│   │   ├── memory_pressure.py   # Memory stats, purge
│   │   ├── brew_manager.py      # Homebrew integration
│   │   ├── completions.py       # Shell completion generation
│   │   ├── scheduler.py         # LaunchAgent scheduling
│   │   ├── updater.py           # PyPI update checking
│   │   ├── menubar.py           # SwiftBar/xbar plugin
│   │   ├── config_sync.py       # Multi-Mac config sync
│   │   ├── permissions_auditor.py  # TCC database audit
│   │   ├── apfs_snapshots.py    # APFS snapshot management
│   │   ├── breach_monitor.py    # HIBP API integration
│   │   ├── dns_cache.py         # DNS flush operations
│   │   ├── font_cache.py        # Font cache rebuild
│   │   ├── spotlight.py         # Spotlight index management
│   │   ├── power_optimizer.py   # Power settings management
│   │   ├── update_checker.py    # App update detection
│   │   ├── pkg_receipts.py      # PKG receipt management
│   │   └── time_machine_guard.py  # Time Machine status
│   │
│   ├── scanners/
│   │   ├── __init__.py
│   │   ├── discovery.py     # App discovery (bundle IDs)
│   │   ├── matching.py      # Bundle ID matching logic
│   │   ├── dev_junk.py      # Developer junk detection
│   │   ├── duplicates.py    # Duplicate file finder
│   │   ├── large_files.py   # Large file scanner
│   │   ├── symlinks.py      # Broken symlink detector
│   │   ├── space_map.py     # Disk usage tree builder
│   │   ├── photos_analyzer.py  # Photos library analyzer
│   │   ├── simulators.py    # iOS simulator data scanner
│   │   ├── extras.py        # iOS backups, language packs
│   │   ├── binary_thinner.py  # Fat binary detector
│   │   ├── browser_data.py  # Browser cache scanner
│   │   ├── cloud_junk.py    # Cloud storage caches
│   │   ├── installer_hunter.py  # Installer file finder
│   │   ├── xcode_cleaner.py  # Xcode derived data
│   │   ├── purgeable.py     # Purgeable space analysis
│   │   └── recent_activity.py  # Recent items scanner
│   │
│   └── reporting/
│       ├── __init__.py
│       ├── reporter.py      # Console report formatting
│       ├── exporter.py      # JSON/YAML export
│       ├── html_report.py   # HTML report generation
│       ├── weekly_digest.py  # Weekly digest reports
│       ├── impact_score.py  # Impact score calculation
│       └── storage_trend.py  # Storage trend tracking
│
├── tests/
│   ├── test_scanner.py
│   ├── test_features_p0_p1.py
│   └── test_features_p2_p3.py
│
├── docs/
│   ├── COMMAND_REFERENCE.md
│   ├── FEATURES.md
│   ├── ARCHITECTURE.md (this file)
│   └── PYPI_PUBLISHING.md
│
├── scripts/
│   ├── build.sh
│   └── build_pkg.sh
│
├── Formula/
│   └── mac-deep-cleaner.rb
│
├── pyproject.toml
├── setup.py
├── requirements.txt
├── README.md
├── CHANGELOG.md
├── LICENSE
└── SECURITY.md
```

---

## Core Modules

### `cli.py` — Command-Line Interface

**Purpose:** Main entry point for all CLI commands using Click framework.

**Key Components:**
- `@main` group: Root command group with global options
- Subcommands: 45+ individual commands organized by function
- Shared helpers: `_progress()`, `_ensure_first_run_profile()`, `_run()`

**Global Options:**
```python
--verbose      # Enable debug logging
--log-file     # Custom log file path
--dry-run      # Preview mode (no modifications)
--version      # Show version info
```

**Command Categories:**
1. **Core:** scan, clean, dashboard, info
2. **Scanning:** duplicates, large-files, symlinks, space-map, photos, simulators, extras, binary
3. **Cleaning:** uninstall, browser-data, developer, xcode-cleaner, installer-hunter, purgeable, cloud-junk
4. **System:** system, memory-pressure, brew, permissions, snapshots, time-machine
5. **Maintenance:** dns-cache, font-cache, spotlight, power-optimizer, app-updates, pkg-receipts
6. **Monitoring:** history, diff, storage-trend, weekly-digest, impact-score, breach, recent-activity
7. **Configuration:** config, config-sync, schedule, update, completions
8. **Utilities:** tui-picker, menubar, undo

**The `_run()` Function:**
Shared engine for scan/clean operations:
- Step 1: Discover installed applications
- Step 2: Check running processes
- Step 3: Detect orphaned leftovers
- Step 4: Scan general junk
- Step 5: (Optional) Scan developer junk
- Generates reports, exports, saves history
- Handles undo staging or direct deletion

---

### `core/scanner.py` — Scanning Engine

**Purpose:** Core scanning logic for orphans and junk.

**Functions:**

#### `scan_orphans(apps, whitelist_set, running_bids, roots, enabled)`
Detects leftover data from uninstalled apps.

**Algorithm:**
1. Collect all known bundle IDs from installed apps
2. Scan standard macOS locations:
   - `~/Library/Application Support/`
   - `~/Library/Caches/`
   - `~/Library/Preferences/`
   - `~/Library/Logs/`
   - `~/Library/Saved Application State/`
   - `~/Library/Group Containers/`
3. For each found item, check if bundle ID matches any installed app
4. Exclude running apps (protected)
5. Apply whitelist filters
6. Return grouped entries by app name

#### `scan_junk(whitelist_set, apps, roots, skip_categories, enabled)`
Finds general junk files across categories.

**Categories:**
- User caches (`~/Library/Caches/*`)
- Logs (`~/Library/Logs/*`)
- Crash reports (`~/Library/Logs/DiagnosticReports/*`)
- Trash leftovers
- `.DS_Store` files
- Xcode derived data
- Package manager caches (npm, pip, yarn, pnpm, gradle, maven, cargo, go, cocoapods)
- Browser caches (Chrome, Firefox)

**Safety Checks:**
- Excludes system-owned items
- Respects skip_categories from config
- Applies whitelist filters

---

### `core/cleaner.py` — Cleanup Engine

**Purpose:** Execute cleanup operations safely.

**Functions:**

#### `do_cleanup(orphans, junk, auto=False)`
Main cleanup function called by `clean` command.

**Process:**
1. If `auto=True`: Delete all without prompting
2. If `auto=False`: Interactive confirmation per item
3. For each item:
   - Validate path via `validate_path_for_deletion()`
   - Stage in `~/.mac_cleaner_trash/` (if undo_mode enabled)
   - Or delete directly via `safe_remove()`
4. Write deletion log
5. Return total freed bytes

#### `write_deletion_log(deleted_items)`
Records all deletions to audit log file.

---

### `core/safety.py` — Safety Mechanisms

**Purpose:** Protect system integrity during cleanup.

**Key Functions:**

#### `validate_path_for_deletion(path)`
Final safety gate before any deletion.

**Checks:**
- Path exists and is accessible
- Not under `/System`, `/Library`, `/usr`
- Not owned by `com.apple.*`
- Not currently in use by running process
- Group container team ID validated

#### `running_bundle_ids()`
Returns set of bundle IDs for currently running applications.

**Implementation:**
- Uses `psutil` or `subprocess` to query running processes
- Extracts bundle IDs from app paths
- Cached for performance

#### `resolve_team_id(bundle_id)`
Resolves Apple Team ID for group container validation.

---

### `core/undo.py` — Undo/Restore System

**Purpose:** Manage staged deletions for recovery.

**Data Structures:**

#### `UndoSession`
```python
class UndoSession:
    session_id: str      # UUID prefix
    created_at: str      # ISO timestamp
    files: List[StagedFile]
    total_size: int
    
    def save(self) -> None
    def restore(self) -> RestoreResult
```

#### `StagedFile`
```python
class StagedFile:
    original_path: Path
    staged_path: Path
    size: int
    category: str        # "Orphan", "Junk", "Dev Junk"
    checksum: str        # SHA256 for verification
```

**Functions:**

#### `new_session()`
Creates new undo session with unique ID.

#### `stage_file(path, session, category)`
Moves file to staging area with metadata.

#### `restore_session(session)`
Restores all files from session to original locations.

#### `purge_old_sessions(days=30)`
Removes sessions older than retention period.

---

### `core/uninstaller.py` — App Uninstaller

**Purpose:** Complete app removal with data cleanup.

**Functions:**

#### `find_app_candidates(query, apps)`
Finds installed apps matching search query.

**Matching Strategy:**
- Case-insensitive substring match on app name
- Bundle ID match
- Fuzzy matching for typos

#### `build_uninstall_plan(app, whitelist_set, keep_preferences=False)`
Creates detailed uninstall plan.

**Plan Includes:**
- Application bundle path
- All associated data:
  - Application Support
  - Caches
  - Preferences (optional)
  - Saved State
  - Group Containers
  - Logs
- Protected items (excluded by safety checks)

#### `execute_uninstall(plan, session=None)`
Executes uninstall plan.

**Process:**
1. Display plan to user
2. Confirm deletion
3. Stage or delete each item
4. Update launch services database
5. Return result summary

---

## Scanner Modules

### `scanners/discovery.py` — App Discovery

**Purpose:** Discover all installed macOS applications.

**Scan Locations:**
- `/Applications`
- `~/Applications`
- `/Users/*/Applications`
- Custom roots from config

**Output:** Dictionary mapping bundle IDs to `AppInfo` objects.

```python
class AppInfo:
    name: str
    bundle_id: str
    path: Path
    version: str
    team_id: Optional[str]
```

---

### `scanners/dev_junk.py` — Developer Junk

**Purpose:** Find project-specific build artifacts and dependencies.

**Patterns Detected:**

| Pattern | Type | Typical Size |
|---------|------|--------------|
| `node_modules` | Dependencies | 100MB - 2GB |
| `venv`, `.venv` | Python env | 50MB - 500MB |
| `__pycache__` | Python cache | 10MB - 100MB |
| `target` | Rust build | 100MB - 1GB |
| `bin`, `obj` | C#/Unity | 50MB - 500MB |
| `dist`, `build` | Build output | 10MB - 200MB |
| `coverage` | Test coverage | 5MB - 50MB |

**Global Caches (Optional):**
- `~/.npm`
- `~/.gradle`
- `~/.m2`
- `~/.cargo`
- `~/.nuget`
- `~/.ivy2`
- `~/.sbt`

**Function:** `find_dev_junk(roots, max_depth, limit, include_global)`

---

### `scanners/duplicates.py` — Duplicate Finder

**Purpose:** Find byte-identical files using hashing.

**Algorithm:**

**Phase 1: Quick Filter**
- Group files by size
- Skip unique sizes
- Only hash files with matching sizes

**Phase 2: Hash Comparison**
- Compute SHA256 for candidates
- Group by hash value
- Report groups with 2+ files

**Optimization:**
- Minimum size threshold (default: 100KB)
- Progress callback for UI updates
- Skip system directories

**Output:** List of `DuplicateGroup` objects.

```python
class DuplicateGroup:
    hash: str
    size: int
    paths: List[Path]
    
    @property
    def wasted_bytes(self) -> int:
        return self.size * (len(self.paths) - 1)
```

---

### `scanners/large_files.py` — Large File Scanner

**Purpose:** Find files exceeding size threshold.

**Categories:**
- Videos (.mp4, .mov, .avi, .mkv)
- Archives (.zip, .tar, .gz, .rar, .7z)
- Disk Images (.dmg, .iso, .cdr)
- Applications (.app bundles)
- Documents (.pdf, .psd, .ai, .sketch)
- Other

**Function:** `find_large_files(roots, min_bytes, limit)`

---

### `scanners/symlinks.py` — Symlink Checker

**Purpose:** Find broken symbolic links.

**Scan Roots:**
- Developer directories
- Homebrew prefixes
- Custom paths

**Output:** List of `BrokenSymlink` objects.

```python
class BrokenSymlink:
    path: Path           # Link location
    target: str          # Missing target path
    location: str        # Parent directory
```

---

### `scanners/space_map.py` — Disk Usage Map

**Purpose:** Build tree visualization of disk usage.

**Algorithm:**
1. Walk directory tree up to max_depth
2. Aggregate sizes per folder
3. Sort children by size descending
4. Filter by minimum size threshold

**Output:** `UsageNode` tree structure.

```python
class UsageNode:
    path: Path
    size: int
    children: List[UsageNode]
    
    def render(limit=12) -> str:
        # Returns ASCII tree visualization
```

---

### `scanners/photos_analyzer.py` — Photos Library Analyzer

**Purpose:** Analyze Photos library storage usage.

**Analysis:**
- Library bundle size
- Originals folder (masters)
- Previews folder
- Database file
- File type breakdown

**Function:** `analyze_photo_library(library_path)`

**Output:** `PhotosReport` object.

```python
class PhotosReport:
    name: str
    path: Path
    size: int
    originals_size: int
    previews_size: int
    database_size: int
    originals_count: int
    
    def top_extensions(n=8) -> List[Tuple[str, int, int]]:
        # Returns [(ext, count, size), ...]
```

---

### `scanners/simulators.py` — Simulator Cleaner

**Purpose:** Manage iOS Simulator data.

**Components:**

#### Device Data
- Runtime support files
- App installations
- User data

#### Caches
- CoreSimulator caches
- Device logs
- Temporary files

**Functions:**
- `find_simulator_devices()` — List available simulators
- `find_simulator_caches()` — Find cache directories
- `purge_simulator_devices(devices)` — Delete device data
- `purge_simulator_caches(caches)` — Delete caches

---

### `scanners/extras.py` — Extra Scanners

**iOS Backups:**
- Location: `~/Library/Application Support/MobileSync/Backup/`
- Info extracted: device name, iOS version, backup date, size

**Language Packs:**
- Scan `/Applications/*.app/Contents/Resources/*.lproj`
- Identify removable language directories
- Calculate potential savings

---

### `scanners/binary_thinner.py` — Binary Thinner

**Purpose:** Detect and thin universal binaries.

**Detection:**
- Use `lipo -info` to check architectures
- Identify fat binaries (arm64 + x86_64)

**Thinning:**
- Use `ditto --arch <arch>` (Apple-recommended)
- Create backup before modification
- Calculate estimated savings

---

### `scanners/browser_data.py` — Browser Data Scanner

**Supported Browsers:**
- Safari
- Chrome
- Firefox
- Edge
- Brave

**Data Categories:**
- Cache files
- Cookies (SQLite databases)
- History (SQLite databases)
- Downloads history
- Site data (LocalStorage, IndexedDB)
- Session data

**Safety:**
- Browser must be closed for safe deletion
- Some files may be locked

---

### `scanners/cloud_junk.py` — Cloud Storage Junk

**Providers:**
- Dropbox (`~/Library/Application Support/Dropbox/`)
- Google Drive (`~/Library/Application Support/Google/Drive/`)
- OneDrive (`~/Library/Containers/com.microsoft.OneDrive-mac/`)
- Box (`~/Library/Application Support/Box/`)

**Data Types:**
- Cache files
- Log files
- Temporary downloads

---

### `scanners/installer_hunter.py` — Installer Hunter

**File Types:**
- `.pkg` — Package installer
- `.dmg` — Disk image
- `.mpkg` — Meta-package

**Optional:**
- `.zip`, `.tar`, `.gz` — Archives

**Filters:**
- Minimum age (days)
- Minimum size (MB)
- Scan roots (Downloads, Desktop, Documents)

---

### `scanners/xcode_cleaner.py` — Xcode Cleaner

**Categories:**
- DerivedData (`~/Library/Developer/Xcode/DerivedData/`)
- DeviceSupport (`~/Library/Developer/Xcode/iOS DeviceSupport/`)
- Archives (`~/Library/Developer/Xcode/Archives/`)
- Caches (`~/Library/Caches/com.apple.dt.Xcode/`)
- Documentation

---

### `scanners/purgeable.py` — Purgeable Space

**Purpose:** Analyze and reclaim purgeable space.

**Sources:**
- Local Time Machine snapshots
- Optimized Storage files
- iCloud cached data

**Actions:**
- `tmutil thinlocalsnapshots` — Reclaim space
- Delete old snapshots by policy

---

### `scanners/recent_activity.py` — Recent Activity

**Location:** `~/Library/Recent Items/`

**Categories:**
- Recent documents
- Recent applications
- Recent servers
- Recent volumes

---

## Reporting Modules

### `reporting/reporter.py` — Console Reports

**Purpose:** Format and display results in terminal.

**Functions:**
- `print_banner()` — Show tool header
- `print_orphan_report(orphans)` — Format orphan findings
- `print_junk_report(junk)` — Format junk findings
- `print_dev_junk_report(entries)` — Format dev junk
- `print_summary(...)` — Show totals and hints
- `print_instructions()` — Next steps guidance

---

### `reporting/exporter.py` — Data Export

**Formats:**
- JSON (`.json`)
- YAML (`.yaml`, `.yml`)
- HTML (`.html`)

**Functions:**
- `export_json(orphans, junk, dev_junk, path)`
- `export_yaml(orphans, junk, dev_junk, path)`
- `export_html(orphans, junk, dev_junk, path)`

---

### `reporting/html_report.py` — HTML Reports

**Features:**
- Self-contained HTML file
- Chart.js via CDN for visualizations
- Interactive tables
- Responsive design

**Sections:**
- Summary dashboard
- Orphan details
- Junk breakdown
- Dev junk list
- Charts (pie, bar)

---

### `reporting/weekly_digest.py` — Weekly Digest

**Purpose:** Generate periodic summary reports.

**Metrics:**
- Scan count in period
- Total reclaimable
- Average per scan
- Top orphaned apps
- Top junk categories
- Trends vs previous period

---

### `reporting/impact_score.py` — Impact Score

**Purpose:** Calculate cleaning effectiveness score.

**Factors:**
- Total bytes reclaimed
- Item counts
- Category diversity
- Historical comparison

**Score Range:** 0-100

**Labels:**
- 0-20: Minimal
- 21-40: Low
- 41-60: Moderate
- 61-80: High
- 81-100: Excellent

---

### `reporting/storage_trend.py` — Storage Trends

**Purpose:** Track disk usage over time.

**Storage:**
- Snapshots saved to `~/.config/mac-cleaner/storage_trends.json`

**Metrics:**
- Used space
- Free space
- Delta between snapshots
- Trend direction

---

## Configuration System

### `config/config.py` — Configuration Management

**Config File:** `~/.config/mac-cleaner/config.yaml`

**Structure:**
```yaml
profile: beginner

whitelist:
  - ~/important-folder

skip_categories:
  - browser-cache

custom_scan_roots:
  - ~/Projects

dev_junk_roots:
  - ~/Development

scan_orphans: true
scan_junk: true
scan_dev_junk: false
scan_dev_junk_global: false

undo_mode: true
retention_days: 30

large_file_threshold_mb: 100
dev_junk_max_depth: 5
```

**Profiles:**
- `beginner` — Safe defaults
- `developer` — Dev junk enabled
- `professional` — Aggressive thresholds
- `designer` — Large file focus
- `student` — School device safe
- `children` — Maximum safety

---

### `config/history.py` — Scan History

**Storage:** `~/.config/mac-cleaner/history/*.json`

**Record Structure:**
```python
class ScanRecord:
    scan_id: str           # UUID
    scanned_at: datetime
    profile: str
    orphan_bytes: int
    junk_bytes: int
    dev_junk_bytes: int
    summary: dict
    
    def save(self) -> None
    def load(scan_id) -> ScanRecord
```

**Functions:**
- `list_history(limit=10)` — Get recent records
- `diff_scans(older, newer)` — Compare two scans
- `build_scan_record(orphans, junk, dev_junk, profile)` — Create record

---

### `config/models.py` — Data Models

**Key Classes:**

#### `JunkEntry`
```python
class JunkEntry:
    path: Path
    size: int
    category: str
    is_system: bool
    app_name: Optional[str]
    
    def to_dict() -> dict
```

#### `OrphanEntry`
```python
class OrphanEntry:
    path: Path
    size: int
    bundle_id: str
    category: str  # "Application Support", "Caches", etc.
```

---

## Safety Mechanisms

### Protection Layers

1. **Preview First:** `scan` never modifies filesystem
2. **System Protection:** `com.apple.*` items excluded
3. **Running App Guard:** Active apps protected
4. **Group Container Validation:** Team ID verification
5. **System Cache Isolation:** OS caches require explicit flag
6. **Path Validation:** Every path checked before deletion
7. **Undo Support:** Staging area for recovery
8. **Audit Logging:** All deletions recorded

### Dry-Run Mode

```python
from core.dry_run import dry_run_enabled, skip_if_dry_run

if dry_run_enabled(ctx):
    console.print("[yellow]Dry-run enabled; action skipped.[/yellow]")
    return

if skip_if_dry_run(ctx, console, "operation name"):
    return
```

---

## Data Flow

### Scan Flow

```
User runs: mac-cleaner scan
    ↓
cli.main() → ctx.invoke(scan)
    ↓
_ensure_first_run_profile() → load_config()
    ↓
discover_installed_apps()
    ↓
running_bundle_ids()
    ↓
scan_orphans() → validate against running apps
    ↓
scan_junk() → filter by categories
    ↓
(Optional) find_dev_junk()
    ↓
Generate reports (console, export)
    ↓
Save to history
    ↓
Display summary
```

### Clean Flow

```
User runs: mac-cleaner clean
    ↓
Same scan steps as above
    ↓
For each item:
    ↓
validate_path_for_deletion()
    ↓
If undo_mode:
    stage_file() → ~/.mac_cleaner_trash/
Else:
    safe_remove()
    ↓
write_deletion_log()
    ↓
Display result
```

### Undo Flow

```
User runs: mac-cleaner undo --session ABCD
    ↓
list_sessions() → find matching session
    ↓
Confirm restoration
    ↓
For each staged file:
    ↓
Verify checksum (if --verify)
    ↓
Move back to original path
    ↓
Update session status
    ↓
Display result
```

---

## Extension Points

### Adding New Scanners

1. Create new module in `src/scanners/`
2. Implement discovery function returning list of entries
3. Add CLI command in `cli.py`:
   ```python
   @main.command("new-scanner")
   def cmd_new_scanner(...):
       from scanners.new_scanner import find_items
       items = find_items(...)
       # Display and handle results
   ```

### Adding New Cleaners

1. Implement cleanup logic in `src/core/` or `src/scanners/`
2. Add safety checks via `core/safety.py`
3. Integrate with undo system if needed
4. Add CLI command with `--delete` flag

### Adding New Export Formats

1. Create exporter in `src/reporting/`
2. Implement export function
3. Add to `cli.py` export logic:
   ```python
   if export_path.endswith(".newformat"):
       from reporting.new_exporter import export_newformat
       export_newformat(orphans, junk, dev_junk, export_path)
   ```

### Adding New Profiles

1. Edit `src/config/config.py`
2. Add profile to `DEFAULT_PROFILES` dict
3. Define settings for new profile

---

## Testing

### Test Structure

```
tests/
├── test_scanner.py          # Unit tests for scanner logic
├── test_features_p0_p1.py   # Priority 0/1 feature tests
└── test_features_p2_p3.py   # Priority 2/3 feature tests
```

### Running Tests

```bash
pytest tests/
pytest tests/test_scanner.py -v
pytest tests/test_features_p0_p1.py -k "test_orphan_detection"
```

---

## Performance Considerations

### Optimization Strategies

1. **Two-Phase Hashing:** Size pre-filter before hashing
2. **Parallel Scanning:** Thread pools for I/O-bound operations
3. **Caching:** Bundle ID resolution cached
4. **Progressive Display:** Live updates during long scans
5. **Size Thresholds:** Skip tiny files in duplicate/large-file scans
6. **Depth Limits:** Configurable recursion limits

### Memory Management

- Stream file walks instead of loading all paths
- Limit result sets with `--limit` flags
- Generator patterns for large datasets

---

## Security Considerations

### Input Validation

- All paths resolved and validated
- Symlinks followed safely
- No shell injection in subprocess calls

### Privilege Escalation

- No sudo/admin privileges required
- Limited to user-accessible paths
- SIP-protected areas excluded

### Data Privacy

- No telemetry by default
- Optional breach monitoring uses official HIBP API
- Local-only operation unless explicitly configured

---

*Documentation generated for Mac Deep Cleaner v2.0.0*
