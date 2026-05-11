# Changelog

All notable changes to **mac-deep-cleaner** will be documented in this file.

## Unreleased
### Added
- Debug logging flags (`--verbose`, `--log-file`) with file rotation
- Basic test coverage for utilities and matching

### Changed
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
