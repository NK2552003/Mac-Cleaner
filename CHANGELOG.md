# Changelog

All notable changes to **mac-deep-cleaner** will be documented in this file.

## Unreleased

## v1.5.0 (2026-05-12)
### Added
#### P0 (baseline UX and safety)
- [x] Global --dry-run flag (src/core/dry_run.py)
- [x] Shell completion command (src/core/completions.py)
- [x] Full app uninstaller (src/core/uninstaller.py)

#### P1 (highest demand data and visibility)
- [x] Browser data cleaner (src/scanners/browser_data.py)
- [x] Visual disk space map (src/scanners/space_map.py)
- [x] Photo library analyzer (src/scanners/photos_analyzer.py)
- [x] iOS simulator deep cleaner (src/scanners/simulators.py)

#### P2 (system utilities and maintenance)
- [x] Memory pressure reliever (src/core/memory_pressure.py)
- [x] Homebrew deep manager (src/core/brew_manager.py)
- [x] Storage trend tracker (src/reporting/storage_trend.py)
- [x] Recent files and activity cleaner (src/scanners/recent_activity.py)

#### P3 (advanced and higher risk features)
- [x] Permissions auditor (src/core/permissions_auditor.py)
- [x] APFS snapshot guard (src/core/apfs_snapshots.py)
- [x] Menu bar companion (src/core/menubar.py)
- [x] Data breach monitor (src/core/breach_monitor.py)
- [x] Cloud storage junk scanner (src/scanners/cloud_junk.py)

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
- Version bump to v1.5.0 across docs and UI

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
