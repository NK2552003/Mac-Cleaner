# Mac Deep Cleaner v2.x Feature Checklist

Date: 2026-05-11

Use this file as the execution order. Check items only after the feature is fully implemented, wired to CLI, and covered by tests when feasible.

## P0 (baseline UX and safety)
- [x] Global --dry-run flag (src/core/dry_run.py)
- [x] Shell completion command (src/core/completions.py)
- [x] Full app uninstaller (src/core/uninstaller.py)

## P1 (highest demand data and visibility)
- [x] Browser data cleaner (src/scanners/browser_data.py)
- [x] Visual disk space map (src/scanners/space_map.py)
- [x] Photo library analyzer (src/scanners/photos_analyzer.py)
- [x] iOS simulator deep cleaner (src/scanners/simulators.py)

## P2 (system utilities and maintenance)
- [x] Memory pressure reliever (src/core/memory_pressure.py)
- [x] Homebrew deep manager (src/core/brew_manager.py)
- [x] Storage trend tracker (src/reporting/storage_trend.py)
- [x] Recent files and activity cleaner (src/scanners/recent_activity.py)

## P3 (advanced and higher risk features)
- [x] Permissions auditor (src/core/permissions_auditor.py)
- [x] APFS snapshot guard (src/core/apfs_snapshots.py)
- [x] Menu bar companion (src/core/menubar.py)
- [x] Data breach monitor (src/core/breach_monitor.py)
- [x] Cloud storage junk scanner (src/scanners/cloud_junk.py)

## Additional (not yet scheduled)
- [ ] Purgeable space reclaimer (src/scanners/purgeable.py)
- [ ] Installer and PKG file hunter (src/scanners/installer_hunter.py)
- [ ] DNS cache flush (src/core/dns_cache.py)
- [ ] Font cache rebuild (src/core/font_cache.py)
- [ ] Spotlight re-index (src/core/spotlight.py)
- [ ] Sleep and power optimizer (src/core/power_optimizer.py)
- [ ] App update checker (src/core/update_checker.py)
- [ ] PKG receipt manager (src/core/pkg_receipts.py)
- [ ] Xcode derived data cleaner (src/scanners/xcode_cleaner.py)
- [ ] Weekly digest report (src/reporting/weekly_digest.py)
- [ ] Cleaning impact score (src/reporting/impact_score.py)
- [ ] Interactive TUI app picker (src/core/tui_picker.py)
- [ ] Multi-Mac config sync (src/core/config_sync.py)
- [ ] Time Machine backup guard (src/core/time_machine_guard.py)
- [ ] Restore checksum verification (src/core/restore_checksums.py)
