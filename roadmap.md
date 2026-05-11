# Mac Deep Cleaner v2.x Roadmap

Date: 2026-05-11

## Goals
- Ship a full v2.x feature set with professional-grade safety, logging, and undo support.
- Keep destructive actions opt-in and gated by explicit flags and confirmations.
- Keep new dependencies minimal and justified; document when optional.
- Add a feature module per roadmap item, grouped by domain.

## Proposed Feature Modules (one per feature)

Privacy and security
- src/features/privacy/browser_data.py
- src/features/privacy/recent_activity.py
- src/features/security/breach_monitor.py
- src/features/security/permissions_auditor.py

Storage intelligence
- src/features/storage/space_map.py
- src/features/storage/purgeable.py
- src/features/storage/cloud_junk.py
- src/features/storage/photos_analyzer.py
- src/features/storage/installer_hunter.py

Performance and system
- src/features/system/memory_pressure.py
- src/features/system/dns_cache.py
- src/features/system/font_cache.py
- src/features/system/spotlight.py
- src/features/system/power_optimizer.py

Application management
- src/features/apps/uninstaller.py
- src/features/apps/update_checker.py
- src/features/apps/brew_manager.py
- src/features/apps/pkg_receipts.py

Simulation and development
- src/features/dev/simulators.py
- src/features/dev/xcode_cleaner.py

Reporting and insights
- src/features/reporting/weekly_digest.py
- src/features/reporting/storage_trend.py
- src/features/reporting/impact_score.py

UX and workflow
- src/features/ux/completions.py
- src/features/ux/tui_picker.py
- src/features/ux/dry_run.py
- src/features/ux/config_sync.py
- src/features/ux/menubar.py

Safety enhancements
- src/features/safety/time_machine_guard.py
- src/features/safety/apfs_snapshots.py
- src/features/safety/restore_checksums.py

## Phases and Order

P0 (baseline UX and safety)
- Global --dry-run flag (ux/dry_run)
- Shell completion command (ux/completions)
- Full app uninstaller (apps/uninstaller)

P1 (highest demand data and visibility)
- Browser data cleaner (privacy/browser_data)
- Visual disk space map (storage/space_map)
- Photo library analyzer (storage/photos_analyzer)
- iOS simulator deep cleaner (dev/simulators)

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
