# Changelog

All notable changes to **mac-deep-cleaner** will be documented in this file.

## v3.0.0 (2026-10-30)

### Added
- **Modern Local Dashboard**: Complete redesign featuring a local web-based interface with dark-minimal styling, real-time scanning radar animation, and instant category filters.
- **Native macOS Desktop Shell**: Bundled Swift window chrome with custom window controls (`desktop/window_chrome.swift`), seamless full-screen handling, and matching sRGB dark background.
- **Dark Minimal Totoro Mascot & Branding**: High-resolution dark minimal mascot icon (`assets/icon.png`, `desktop/AppIcon.icns`, and `web/mascot.png`).
- **Flexible Entry Points**: Seamless execution via `mac-deep-cleaner`, `mac-cleaner`, or `mdc` aliases across both CLI, web dashboard, and terminal UI modes.
- **Enhanced Overlay & Drawer Animations**: Smooth left-to-right drawer slide animations and scrollbar-hidden overlays for reviewing cleanup details.
- **Interactive Terminal UI**: Optional Rich and Questionary terminal workflows (`mac-cleaner --terminal`).

### Changed
- Refactored core engine into modern `mac_deep_cleaner` module with zero mandatory third-party runtime dependencies.
- Standardized Trash moves by default with multi-step review and verification.

## v2.5.0 (2026-10-16)

### Added
- **Docker Bloat Cleaner**: Added scanner and cleanup for unused Docker containers, dangling images, build caches, and volumes via `mac-cleaner clean --docker` and `mac-cleaner scan --docker`.
- **Interactive Terminal User Interface (TUI)**: Added `mac-cleaner tui` interactive dashboard powered by Textual.
- **Deep App Uninstaller**: Added `mac-cleaner uninstall <app>` with multi-root scanning across Preferences, Containers, Group Containers, Application Scripts, and DiagnosticReports crash logs.
- **Expanded Browser Support**: Added data and cache detection for Arc, Zen Browser, Opera, Vivaldi, and Orion, alongside Safari, Google Chrome, Microsoft Edge, and Firefox.
- **Dedicated Browser Cache Cleaning**: Added discovery and cleanup of `~/Library/Caches` for Chrome, Edge, Brave, and Firefox.
- **Modern Dev Junk Ecosystem**: Added project-level clean detection for Dart/Flutter (`.dart_tool`), Zig (`.zig-cache`, `zig-out`), and Swift (`.build`), plus global caches for Bun, CocoaPods, SwiftPM, Dart/Flutter Pub, Hugging Face, Torch, Deno, and Ollama models.
- **Xcode Deep Cleaner**: Added specialized cache and derived data scanner/cleaner (`mac-cleaner xcode-cleaner`).
- **Installer Hunter**: Added scanner to identify obsolete `.dmg`, `.pkg`, `.iso`, and archive files with installed app detection (`mac-cleaner installer-hunter`).
- **Background Scheduled Cleaning**: Added `--clean` option to `mac-cleaner schedule install` to run automatic unattended weekly cleanups.
- **DNS Cache Flushing**: Added `mac-cleaner flush-dns` / `mac-cleaner dns-cache --flush`.
- **System Caches Cleaning Option**: Added `--auto-with-cache` flag to `clean` command to safely prompt for system cache clearing.
- **Modern UI Styling**: Beautified terminal reporting with rounded Unicode boxes, badges, and colors.
- **Extensive App Ecosystem Registry**: Added dozens of modern developer tools, AI applications, and productivity apps to `src/constants/aliases.py` and system safelists.

### Fixed
- **Safety Gate Temporary Paths**: Fixed `validate_path_for_deletion` falsely blocking user temporary directories under `/private/var/folders/` and `/var/folders/` while preserving protection for OS directories and temporary roots.
- **Crash Log Matching in Uninstaller**: Resolved crash report matching in `DiagnosticReports` by supporting app names, identifier tokens, and bundle ID prefix separators (`_`, `.`, `-`).
- **Decimal Precision in Size Formatting**: Fixed `bytes_human` decimal truncation so sizes like `1.5 MB` and `2.5 GB` report correct fractional values.
- **Disk Usage Fallback**: Fixed `actual_disk_usage` falling back to `st_size` when block allocation is 0 (mock files, small files, sparse files).
- **Missing `os` Import in CLI**: Fixed `NameError: name 'os' is not defined` during CI first-run profile checks.
- **CLI Options Validation**: Added missing browsers (`arc`, `zen`, `opera`, `vivaldi`, `orion`) and cloud providers (`icloud`, `icloud-drive`) to Click choice options.
- **Cloud Junk iCloud Logs**: Corrected iCloud logs path from live state `Application Support/CloudDocs` to `Library/Logs/CloudDocs`.
- **Dynamic Versioning in Reports**: Replaced static hardcoded versions in deletion logs, HTML reports, and JSON/YAML exports with dynamic package version.
- **Empty Junk Table UI**: Replaced empty tables with a clean success panel when no user junk is found.
- **Category Filter Normalization**: Allowed flexible category inputs (`derived-data`, `deriveddata`, `Derived Data`, `site_data`, `site-data`) in browser and Xcode cleaners.

### Changed
- **Modular Constants Architecture**: Refactored monolithic `src/constants.py` into a modular package (`aliases.py`, `paths.py`, `system.py`, `team_ids.py`, `vendors.py`).
- **Updated Package Metadata**: Bumped version to `2.5.0` across `pyproject.toml`, `Formula/mac-deep-cleaner.rb`, `src/__init__.py`, `scripts/build.sh`, and documentation.

## v2.0.1 (2026-05-22)

### Added
- APFS clone-aware duplicate detection (opt-in) with sampling profiles
- Duplicate export fields for logical vs physical wasted space when available

### Changed
- Duplicates CLI output shows physical group counts and estimated wasted space

## v2.0.0 (2026-05-14)

### Added

## Cross-cutting Work
- Add new CLI subcommands and options in src/cli.py
- Extend config schema in src/config/config.py for new features
- Add logging and safe-path validation in src/core/safety.py where needed
- Expand reporting exports in src/reporting for new outputs
- Add tests for parsers and non-destructive scanners in tests/

## External Dependencies (tentative)
- textual or prompt_toolkit for interactive TUI picker
- rumps for menu bar companion
- requests or urllib for HIBP API (prefer urllib to avoid new deps)
- pandas/pyarrow NOT planned (keep lightweight)

## Safety Gates
- All destructive operations honor --dry-run and undo staging.
- Time Machine guard before bulk deletes.
- APFS snapshot support behind explicit flags.
- Restore checksum verification for staged files.

## Open Decisions (needs confirmation)
- Preferred TUI library (textual vs prompt_toolkit)
- Whether to add optional dependencies vs strict core only
- Handling sudo-required operations (auto prompt vs printed instructions)
- HIBP API key provisioning and storage
- Minimum supported macOS version for system commands
- CI mode via `mdc uninstall-cli` ti uninstall this package

##DOUCMENTATIONS
-Added the documentations for the command references and architecture


### Changed 
- CLI wiring for new feature commands
- Added reporting utilities
- Updated Readme for new features
- Version bump to v2.0.0 across docs and UI
- Updated the ci/cd pipelining to publish the newer version to pypi directly
- Updated the readme.md file for the references too

## v1.5.0 (2026-05-12)
### Added
- Global --dry-run flag (src/core/dry_run.py)
- Shell completion command (src/core/completions.py)
- Full app uninstaller (src/core/uninstaller.py)
- Browser data cleaner (src/scanners/browser_data.py)
- Visual disk space map (src/scanners/space_map.py)
- Photo library analyzer (src/scanners/photos_analyzer.py)
- iOS simulator deep cleaner (src/scanners/simulators.py)
- Memory pressure reliever (src/core/memory_pressure.py)
- Homebrew deep manager (src/core/brew_manager.py)
- Storage trend tracker (src/reporting/storage_trend.py)
- Recent files and activity cleaner (src/scanners/recent_activity.py)
- Permissions auditor (src/core/permissions_auditor.py)
- APFS snapshot guard (src/core/apfs_snapshots.py)
- Menu bar companion (src/core/menubar.py)
- Data breach monitor (src/core/breach_monitor.py)
- Cloud storage junk scanner (src/scanners/cloud_junk.py)

### Changed
- CLI wiring for new P0/P1 commands and dry-run behavior
- Module layout aligned to core/scanners (removed features package)
- README, checklist, and roadmap paths updated for the new layout
- Improved error handling with debug logs across filesystem and subprocess paths
- Dev junk scanner traversal now uses a deque for better performance

## v1.2.0 (2026-05-11)
### Added
- Developer junk scanner for project caches (node_modules, venv, build outputs)
- Global dev cache opt-in via `--dev-junk-global` (e.g., ~/.npm, ~/.gradle)
- First-run profile selection for new installs
- Expanded app aliases for photography, editors, and common tools

### Changed
- Live dashboard now shows top findings and dev junk totals
- Scan history schema extended with developer junk totals
- Version bump to v1.2.0 across docs and UI

## v1.0.0 (2026-05-10)
### Added
- Full CLI command set and scan/clean workflow documentation
- Structured feature documentation (`FEATURES.md`)
- PyPI publishing guide (`PYPI_PUBLISHING.md`)
- Self-update workflow documentation (PyPI-based update)
- CI mode via `mac-cleaner scan --ci --threshold-mb N`
- Live Rich dashboard via `mac-cleaner dashboard`
- Short CLI alias `mdc` for every `mac-cleaner` command
- Custom scan roots through `--root` and `custom_scan_roots`
- Homebrew formula scaffold in `Formula/mac-deep-cleaner.rb`
- Unsigned local `.pkg` builder with explicit installer-access prompt
- Expanded app aliases, team IDs, scanner roots, and system safelists

### Changed
- Release branding updated to **v1.0.0** across project docs
- README “What’s New” section updated to v1.0.0
- Build script now supports `test` and `pkg` modes and installs a working venv package

### Fixed
- Reduced confusing version references in documentation (no more v4/v5 wording in README; now aligned to v1.0.0)
- Fixed package entry points so `mac-cleaner` works from wheels, venvs, and global installs
- Fixed distribution scripts so both `mac-cleaner` and `mdc` are installed and smoke-tested
- Fixed scanner data model mismatches that crashed orphan and junk scans
- Fixed permission-denied handling while scanning protected cache entries
- Fixed version imports when the app is installed as top-level modules
