# Mac Deep Cleaner v2.x Feature Checklist

Date: 2026-05-11

Use this file as the execution order. Check items only after the feature is fully implemented, wired to CLI, and covered by tests when feasible.

## P0 (baseline UX and safety)
- [ ] Global --dry-run flag (src/features/ux/dry_run.py)
- [ ] Shell completion command (src/features/ux/completions.py)
- [ ] Full app uninstaller (src/features/apps/uninstaller.py)

## P1 (highest demand data and visibility)
- [ ] Browser data cleaner (src/features/privacy/browser_data.py)
- [ ] Visual disk space map (src/features/storage/space_map.py)
- [ ] Photo library analyzer (src/features/storage/photos_analyzer.py)
- [ ] iOS simulator deep cleaner (src/features/dev/simulators.py)

## P2 (system utilities and maintenance)
- [ ] Memory pressure reliever (src/features/system/memory_pressure.py)
- [ ] Homebrew deep manager (src/features/apps/brew_manager.py)
- [ ] Storage trend tracker (src/features/reporting/storage_trend.py)
- [ ] Recent files and activity cleaner (src/features/privacy/recent_activity.py)

## P3 (advanced and higher risk features)
- [ ] Permissions auditor (src/features/security/permissions_auditor.py)
- [ ] APFS snapshot guard (src/features/safety/apfs_snapshots.py)
- [ ] Menu bar companion (src/features/ux/menubar.py)
- [ ] Data breach monitor (src/features/security/breach_monitor.py)
- [ ] Cloud storage junk scanner (src/features/storage/cloud_junk.py)

## Additional (not yet scheduled)
- [ ] Purgeable space reclaimer (src/features/storage/purgeable.py)
- [ ] Installer and PKG file hunter (src/features/storage/installer_hunter.py)
- [ ] DNS cache flush (src/features/system/dns_cache.py)
- [ ] Font cache rebuild (src/features/system/font_cache.py)
- [ ] Spotlight re-index (src/features/system/spotlight.py)
- [ ] Sleep and power optimizer (src/features/system/power_optimizer.py)
- [ ] App update checker (src/features/apps/update_checker.py)
- [ ] PKG receipt manager (src/features/apps/pkg_receipts.py)
- [ ] Xcode derived data cleaner (src/features/dev/xcode_cleaner.py)
- [ ] Weekly digest report (src/features/reporting/weekly_digest.py)
- [ ] Cleaning impact score (src/features/reporting/impact_score.py)
- [ ] Interactive TUI app picker (src/features/ux/tui_picker.py)
- [ ] Multi-Mac config sync (src/features/ux/config_sync.py)
- [ ] Time Machine backup guard (src/features/safety/time_machine_guard.py)
- [ ] Restore checksum verification (src/features/safety/restore_checksums.py)
