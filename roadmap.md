# Mac Deep Cleaner v2.x Roadmap

Date: 2026-05-11

## Goals
- Ship a full v2.x feature set with professional-grade safety, logging, and undo support.
- Keep destructive actions opt-in and gated by explicit flags and confirmations.
- Keep new dependencies minimal and justified; document when optional.
- Add a feature module per roadmap item, grouped by domain.

## Proposed Feature Modules (one per feature)

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
