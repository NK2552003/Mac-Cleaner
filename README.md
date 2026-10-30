<div align="center">

<p align="center">
  <img src="assets/app_icon.png" alt="Mac Deep Cleaner Icon" width="130" height="130" style="border-radius: 26px; box-shadow: 0 8px 24px rgba(0,0,0,0.3); margin-bottom: 12px;" />
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

**Mac Deep Cleaner v3.0** is a modern macOS storage analysis and reviewed cleanup suite combining an interactive local web dashboard, native macOS desktop integration, and powerful command-line tooling with multiple layers of safety and full Trash protection.

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
| Validated scan generations & revisions | Zero third-party cloud analytics or external leaks | Fast multi-threaded local scanning |

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
mac-cleaner --apps             # Jump straight to Application Analyzer
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

## Native macOS App Build

To build the standalone native `.app` bundle with the integrated Swift window chrome:

```bash
python3 scripts/build_mac.py
```

The resulting `Mac Deep Cleaner.app` will be placed in `dist/`.

---

## Cleanup & Safety Rules

- **Safe by Default:** Files are moved to Finder's Trash. Trash moves do not immediately increase free disk space until Trash is emptied.
- **Strict Verification:** The backend verifies scan generation tokens, exact file IDs, inode matches, and path restrictions before performing any changes.
- **System Protection:** System files (`com.apple.*`, SIP paths, running app bundles) are strictly locked and protected.
- **Privacy & Permissions:** For full analysis of user caches and containers, grant Full Disk Access to Terminal (or Mac Deep Cleaner) in **System Settings → Privacy & Security → Full Disk Access**.

---

## License

Distributed under the Apache 2.0 License. See `LICENSE` for more information.
