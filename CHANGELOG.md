# Changelog

All notable changes to **mac-deep-cleaner** will be documented in this file.

## Unreleased

## v1.3.0 (2026-05-12)
### Added
- Global dry-run flag that blocks destructive actions (`--dry-run`)
- Shell completions command for bash/zsh/fish
- Full app uninstaller command with undo staging support
- Browser data cleaner command (cache, cookies, history, sessions)
- Disk space map command for folder usage summaries
- Photos library analyzer command for Photos bundles
- iOS simulator cleaner command (devices, caches, logs)
- P0/P1 modules in core/scanners with CLI wiring
- Tests for the new P0/P1 features
- Debug logging flags (`--verbose`, `--log-file`) with file rotation
- Basic test coverage for utilities and matching

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
