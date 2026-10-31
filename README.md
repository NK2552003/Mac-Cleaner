<div align="center">

<p align="center">
  <img src="assets/app_icon.png" alt="Mac Deep Cleaner Icon" width="130" height="130" />
</p>

# Mac Deep Cleaner

**Reclaim gigabytes of disk space with confidence — the safest, smartest macOS storage analyzer and cleanup suite.**

[![PyPI Version](https://img.shields.io/pypi/v/mac-deep-cleaner.svg)](https://pypi.org/project/mac-deep-cleaner/)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-Apache%202.0-green.svg)](https://github.com/NK2552003/Mac-Cleaner/blob/main/LICENSE)
[![macOS 10.15+](https://img.shields.io/badge/macOS-10.15+-silver.svg)](https://www.apple.com/macos/)
[![PyPI Downloads](https://static.pepy.tech/personalized-badge/mac-deep-cleaner?period=total&units=INTERNATIONAL_SYSTEM&left_color=BLACK&right_color=ORANGE&left_text=downloads)](https://pepy.tech/projects/mac-deep-cleaner)

</div>

---

**Mac Deep Cleaner v3.2.0** combines storage analysis, reviewed cleanup, system diagnostics, maintenance, Homebrew package management, and external-disk management in a local dashboard, native macOS app, and command-line tools. File cleanup uses Trash by default; disk formatting and selected maintenance commands are permanent and require a separate review.

Version 3.2.0 adds a dedicated **Homebrew** manager with dependency explanations, groups, reverse trees, size rankings, update checks, services, and reviewed maintenance. **Disks & volumes** now hides recovery/system records by default and uses one scrolling page.

```bash
# Three convenient commands, same powerful tool
mac-deep-cleaner    # Standard entrypoint
mac-cleaner         # Alias
mdc                 # Fast CLI shorthand
```

---

## Key Highlights

| **Safety First** | **Modern UI & Desktop App** | **Deep Local Analysis** |
| :--- | :--- | :--- |
| Never deletes without review | Responsive dashboard with dark-minimal aesthetic | Intelligent application footprints & leftovers |
| Finder Trash protection by default | Integrated macOS native window chrome & full-screen | Dev toolchains, Docker, caches, logs, Xcode |
| Protected & macOS-managed path guards | Optional Rich & Questionary interactive terminal UI | Duplicate file detection with content hashing |
| Validated scan generations & revisions | No app telemetry; Homebrew can fetch metadata | Fast multi-threaded local scanning |

---

## Installation

### Via `pip` (Recommended)

You can install **Mac Deep Cleaner** directly from PyPI:

```bash
pip install mac-deep-cleaner
```

To include the optional interactive terminal UI (`rich` + `questionary`):

```bash
pip install "mac-deep-cleaner[terminal]"
```

### From Source

```bash
git clone https://github.com/NK2552003/Mac-Cleaner.git
cd Mac-Cleaner
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

---

## Quick Start & Usage

### 1. Launch the Interactive Dashboard (Default)

Running without arguments automatically launches the local web UI dashboard on an available loopback port:

```bash
mac-deep-cleaner
# or
mac-cleaner
# or
mdc
```

Options:
```bash
mac-cleaner --port 8765        # Custom port
mac-cleaner --no-open          # Start server without automatically launching browser
mac-cleaner --apps            # Terminal Application Analyzer (optional terminal dependencies)
mac-cleaner --optimize        # Open Optimize your Mac
mac-cleaner --disks           # Open Disks & volumes
mac-cleaner --homebrew        # Open Homebrew management
```

### 2. Command-Line & Terminal Mode

Generate non-interactive reports, JSON exports, or run the interactive terminal interface:

```bash
# Generate report to stdout
mac-cleaner --report

# Export complete scan report as JSON
mac-cleaner --json storage-report.json --no-interactive

# Interactive terminal UI
mac-cleaner --terminal

# Dry-run safe clean preview
mac-cleaner --clean safe --dry-run

# Execute safe cleanup non-interactively
mac-cleaner --clean safe --yes
```

---

## Optimize your Mac

The new workspace shows memory pressure, installed memory, swap usage, free storage, battery/power state, uptime, Spotlight status, and a CPU-sorted process sample. Background launch definitions are listed for inspection; they are not presented as a count of running processes. Refresh takes a new sample, and **Export report** downloads local JSON.

- **Everyday maintenance:** rebuild Quick Look thumbnails, refresh DNS, rebuild the Spotlight index, and inspect Time Machine snapshots.
- **Developer tools:** removal of unavailable Xcode simulators, npm cache verification, and a shortcut to developer-file cleanup. Homebrew now has its own workspace.
- **macOS controls:** open Activity Monitor, Login Items, Storage, Software Update, Battery, Time Machine, Network, or Disk Utility. Settings availability depends on the macOS version.

Each command shows its effects and command details before it starts. Background jobs show completion, output, and failures. DNS and Spotlight use the macOS administrator prompt; credentials are never collected by this app. Spotlight indexing continues after the command returns and can take hours. macOS manages RAM itself; there is no synthetic “boost” score or forced memory purge.

```bash
mac-cleaner --health-report                         # Read-only JSON to stdout
mac-cleaner --health-report --json mac-health.json  # Write a health report
mac-cleaner --disk-report                           # Read-only disk inventory
mac-cleaner --tool brew-cleanup --dry-run            # Show the command and effects only
mac-cleaner --tool brew-preview --yes               # Ask Homebrew what it would remove
mac-cleaner --tool brew-cleanup --yes --i-understand # Execute permanent maintenance
```

`--tool` without `--yes` asks for terminal confirmation. Permanent maintenance additionally requires a typed phrase or `--i-understand`. A dry run never runs the maintenance command. Homebrew and npm must already be installed; simulator maintenance requires Xcode. The optional Rich terminal menu retains its cleanup workflows; use the flags above or the dashboard for the new tools.

## Homebrew management

Open **Homebrew** in the sidebar, run `mac-cleaner --homebrew`, or use `mac-cleaner brew dashboard`. This is integrated into Mac Deep Cleaner; installing `brew-why` or Textual is not required.

- Browse requested formulae, dependencies, casks, unknown installation origins, pinned packages, shared dependencies, and reviewed removal candidates.
- Open **Why installed?** for installed runtime dependencies, retaining roots, and a reverse dependency tree. Dependency groups show which requested applications share a library.
- Rank formulae by Cellar size, check available updates, inspect services, and export JSON or a Brewfile.
- Review upgrades, uninstalls, pin/unpin, install-intent changes, user services, metadata updates, and `brew doctor`.
- **Tidy** separates removal of unused dependencies from cache/old-version cleanup. Both require their own previews and confirmations.

The reference commands are available under the app’s command names (all three aliases work):

```bash
mac-cleaner brew dashboard
mac-cleaner brew overview
mac-cleaner brew explain openssl@3
mac-cleaner brew heaviest --limit 15
mac-cleaner brew reverse-tree openssl@3
mac-cleaner brew audit
mac-cleaner brew stats
mac-cleaner brew tidy --dry-run
mac-cleaner brew tidy                         # Interactive review of both steps
mac-cleaner brew export --output Brewfile
mac-cleaner brew overview --json homebrew.json
```

`audit` reports available updates using Homebrew metadata; it is **not a vulnerability scan**. Use `mac-cleaner brew update` to review a metadata refresh. Removal candidates come from Homebrew’s own autoremove dry run, with additional dependency, pin, and service checks. External scripts can still depend on these packages. See [the Homebrew guide](docs/HOMEBREW.md) for all management commands, safeguards, and measurement limits.

## Disks & volumes

The default view shows physical drives, the startup volume, and usable external containers/volumes. Recovery, boot, system-data, VM, and low-level partition records are hidden. **Show system volumes** reveals them for inspection; their protection remains enforced. Device selection and details share the page’s single scroll area.

Select a drive, APFS container, or volume to inspect capacity, usage, shared free space, mount point, filesystem, encryption, roles, UUID, connection, and SMART status where reported. Startup snapshots are shown separately. APFS space is shared: **Other volumes & metadata** is the difference between container capacity, container free space, and the selected volume’s usage. Purgeable space is not reported as free space.

| Operation | Availability and effect |
| :--- | :--- |
| Verify filesystem / partition map | Runs `diskutil verifyVolume` / `verifyDisk`; no repairs. Verification can briefly pause access. |
| Mount / unmount / eject | Eligible external volumes and disks; never force-unmounts. |
| Rename | Eligible external volumes; scripts using the old path may need updating. |
| Add APFS volume | Eligible external APFS containers; shares space without erasing existing volumes. |
| Erase disk | Eligible external physical disks; creates one APFS, case-sensitive APFS, ExFAT, or Mac OS Extended volume using GUID. Permanently erases every volume on that disk. |
| Partition disk | Eligible external physical disks; creates two to four partitions. Specify whole GB for each except the final remainder. **Replaces the entire layout and permanently erases all data.** |
| First Aid, encryption, resizing | Opens Apple Disk Utility for these advanced operations. |

Erase and partition require a fresh review, a backup acknowledgement, and typing `ERASE diskN`. Review tokens expire after five minutes and work once. The backend reads fresh disk information and checks identity, topology, eligibility, and the exact command again before execution. Jobs are serialized with cleanup, and changes wait for active scans to finish.

Internal disks, the startup and home filesystems, system-role and detected backup disks, multi-disk containers, virtual disks, read-only media, and unidentified devices cannot be changed by these disk tools. If safety metadata cannot be read, changes are disabled. A blank disk without a stable identity must be initialized in Disk Utility. Backup detection uses APFS roles, configured Time Machine destinations, and mounted legacy backup folders; it cannot identify every unmounted or manually copied backup.

Formatting is **not a secure wipe**, and it bypasses Trash. Close files, back up the entire target drive, keep the app open, and do not disconnect drives during an operation. If macOS denies ownership or permissions, inspect the error and use Disk Utility; the app does not escalate disk commands automatically. Failed or timed-out operations may have partially completed—refresh and inspect the disk before retrying.

See [Apple’s APFS volume guide](https://support.apple.com/guide/disk-utility/dskua9e6a110/mac) and [partition guide](https://support.apple.com/guide/disk-utility/dskutl14027/mac) for the difference between shared volumes and fixed partitions.

## Native macOS App Build

To build the standalone native `.app` bundle with the integrated Swift window chrome:

```bash
python3 scripts/build_mac.py
```

The resulting `Mac Deep Cleaner.app` will be placed in `dist/`.

### Shared App Icon

[`assets/app_icon.png`](assets/app_icon.png) is the single source for the app's branding. The dashboard and browser favicon serve this image directly; the native build generates its `.icns` file from it without adding another background or changing its proportions. Python distributions include the same asset inside `mac_deep_cleaner/assets/`. Replace the source PNG and rebuild to update all of these surfaces.

---

## Cleanup & Safety Rules

- **Cleanup Defaults:** Ordinary file cleanup moves files to Finder's Trash. Disk erase/repartition and explicitly reviewed maintenance commands do not use Trash. Trash moves do not immediately increase free disk space until Trash is emptied.
- **Strict Verification:** The backend verifies scan generation tokens, exact file IDs, inode matches, and path restrictions before performing any changes.
- **System Protection:** System files (`com.apple.*`, SIP paths, running app bundles) are strictly locked and protected.
- **Privacy & Permissions:** For full analysis of user caches and containers, grant Full Disk Access to Terminal (or Mac Deep Cleaner) in **System Settings → Privacy & Security → Full Disk Access**.

---

## Development & verification

```bash
python3 -m pip install -e ".[dev]"
python3 -m pytest -q
python3 -m build
```

Disk safety and job tests inject a fake command runner. They never erase, partition, unmount, or maintain the host Mac. Optional browser checks also use this fixture:

```bash
npm install --prefix /tmp/mdc-ui-check playwright
/tmp/mdc-ui-check/node_modules/.bin/playwright install chromium
PYTHONPATH=. python3 tests/toolkit_fixture.py
# In a second terminal:
NODE_PATH=/tmp/mdc-ui-check/node_modules node tests/verify_toolkit.cjs
# Restart the fixture between suites to reset its simulated installation:
NODE_PATH=/tmp/mdc-ui-check/node_modules node tests/verify_homebrew.cjs
```

The browser suites check review/execute flows, cancellation, backup acknowledgement, dependency protection, Homebrew exports, hidden system volumes, absence of nested disk scrolling, and narrow layouts. Read-only live diagnostics can be checked with `--health-report` and `--disk-report`. Destructive operations still require a disposable physical test drive for hardware validation; fixture tests cannot establish hardware reliability. The Homebrew formula source version is updated, but its existing checksum placeholder must be replaced with the published archive’s actual checksum before distribution.

## License

Distributed under the Apache 2.0 License. See `LICENSE` for more information.
