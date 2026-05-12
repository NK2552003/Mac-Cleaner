# Mac Deep Cleaner v2.x Roadmap

Date: 2026-05-11

## Goals
- Ship a full v2.x feature set with professional-grade safety, logging, and undo support.
- Keep destructive actions opt-in and gated by explicit flags and confirmations.
- Keep new dependencies minimal and justified; document when optional.
- Add a feature module per roadmap item, grouped by domain.

## Proposed Feature Modules (one per feature)

Privacy and security
- src/scanners/browser_data.py
- src/scanners/recent_activity.py
- src/core/breach_monitor.py
- src/core/permissions_auditor.py

Storage intelligence
- src/scanners/space_map.py
- src/scanners/purgeable.py
- src/scanners/cloud_junk.py
- src/scanners/photos_analyzer.py
- src/scanners/installer_hunter.py

Performance and system
- src/core/memory_pressure.py
- src/core/dns_cache.py
- src/core/font_cache.py
- src/core/spotlight.py
- src/core/power_optimizer.py

Application management
- src/core/uninstaller.py
- src/core/update_checker.py
- src/core/brew_manager.py
- src/core/pkg_receipts.py

Simulation and development
- src/scanners/simulators.py
- src/scanners/xcode_cleaner.py

Reporting and insights
- src/reporting/weekly_digest.py
- src/reporting/storage_trend.py
- src/reporting/impact_score.py

UX and workflow
- src/core/completions.py
- src/core/tui_picker.py
- src/core/dry_run.py
- src/core/config_sync.py
- src/core/menubar.py

Safety enhancements
- src/core/time_machine_guard.py
- src/core/apfs_snapshots.py
- src/core/restore_checksums.py

## Phases and Order

P0 (baseline UX and safety)
- Global --dry-run flag (core/dry_run)
- Shell completion command (core/completions)
- Full app uninstaller (core/uninstaller)

P1 (highest demand data and visibility)
- Browser data cleaner (scanners/browser_data)
- Visual disk space map (scanners/space_map)
- Photo library analyzer (scanners/photos_analyzer)
- iOS simulator deep cleaner (scanners/simulators)

P2 (system utilities and maintenance)
- Memory pressure reliever (system/memory_pressure)
- Homebrew deep manager (apps/brew_manager)
- Storage trend tracker (reporting/storage_trend)
- Recent files and activity cleaner (privacy/recent_activity)

P3 (advanced and higher risk features)
- Permissions auditor (security/permissions_auditor)
- APFS snapshot guard (safety/apfs_snapshots)
- Menu bar companion (ux/menubar)
- Data breach monitor (security/breach_monitor)
- Cloud storage junk scanner (storage/cloud_junk)

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
