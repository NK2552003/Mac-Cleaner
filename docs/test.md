# Mac Deep Cleaner (mac_cleaner)

> Project version: **1.0.0**

This document explains **how the tool works** and provides **command-by-command documentation** for the CLI.

---

## How it works

Mac Deep Cleaner is a macOS cleanup tool focused on identifying:
1. **Orphaned app leftovers** (files left behind after apps are removed)
2. **User-junk** (caches/logs/trash items) — preview first
3. Optional categories and “extras” (duplicates, large files, symlinks, iOS backups, etc.)

### Safety model (high level)
- **Preview mode** is the default behavior: it reports what would be removed.
- When you run **`clean`**, you can choose interactive cleanup or auto cleanup.
- **Undo mode (staging)** is enabled by default for delete operations performed via `clean`.
  - Staged files are stored under: `~/.mac_cleaner_trash/`
  - You can restore them using: `mac-cleaner undo`
- Some system paths are protected by validation and policy checks in the safety layer (SIP/system protections, running app protections, and path validation).

---

## CLI usage

### Top-level command
All subcommands live under the Click CLI:

```bash
python -m mac_cleaner.cli --help
```

(If installed, you can also use `mac-cleaner --help`.)

---

## Commands

### 1) `scan`
Preview scan for **orphaned app leftovers** and **(optionally)** general junk.

```bash
mac-cleaner scan [OPTIONS]
```

Options:
- `--skip-junk`  
  Only scan orphaned leftovers; skip junk scanning.
- `--export PATH`  
  Export results by extension:
  - `.json` → JSON
  - `.yaml` / `.yml` → YAML
  - `.html` → HTML report
- `--whitelist PATH` *(multiple allowed)*  
  Add paths to the protection whitelist (in addition to config whitelist).
- `--show-apps`  
  Show discovered installed apps list.
- `--profile PROFILE`  
  Use a config profile (e.g. `developer`, `minimal`, `aggressive` depending on config).
- `--notify`  
  Post macOS notification when scan completes.
- `--dry-run`  
  Explicit alias for scan (never deletes).
- `--save-history / --no-save-history`  
  Save scan results to history (default: on).

Behavior:
- Discovers installed applications.
- Checks running processes (protected apps).
- Detects orphaned app leftovers.
- Optionally scans caches/logs/trash for junk.

---

### 2) `clean`
Interactive or auto cleanup of orphaned leftovers + junk.

```bash
mac-cleaner clean [OPTIONS]
```

Options:
- `--auto`  
  Delete automatically without per-item confirmation.
- `--skip-junk`  
  Clean only orphaned leftovers; skip junk clean.
- `--whitelist PATH` *(multiple allowed)*  
  Protect these paths.
- `--export PATH`  
  Export scan results after scanning (before deletion).
- `--profile PROFILE`  
  Use a config profile.
- `--notify`  
  Post macOS notification when scan completes.
- `--no-undo`  
  Permanently delete instead of staging for undo.

Undo behavior:
- Default: deletions are **staged** (undoable).
- With `--no-undo`: deletions are **permanent**.

---

### 3) `info`
Show tool information and safety guarantees.

```bash
mac-cleaner info
```

No options.

---

### 4) `duplicates`
Find duplicate files by content hash.

```bash
mac-cleaner duplicates [OPTIONS]
```

Options:
- `--path PATH` *(multiple allowed)*  
  Directories to scan.
- `--min-size KB` (default: `100`)  
  Ignore smaller files.
- `--export PATH`  
  Export results to JSON.
- `--delete`  
  Interactively delete duplicate copies (keeps the first copy).

Notes:
- Scans user directories (intended behavior is to avoid `/System`).

---

### 5) `large-files`
Find large files and group results by category.

```bash
mac-cleaner large-files [OPTIONS]
```

Options:
- `--path PATH` *(multiple allowed)*  
  Roots to scan (if provided).
- `--min-mb MB` (default: `100`)  
  Minimum file size in MB.
- `--limit N` (default: `100`)  
  Maximum results to show.
- `--export PATH`  
  Export results to JSON.

Output:
- Table of largest files by category.

---

### 6) `symlinks`
Find broken (dangling) symbolic links.

```bash
mac-cleaner symlinks [OPTIONS]
```

Options:
- `--path PATH` *(multiple allowed)*  
  Roots to scan.
- `--delete`  
  Delete broken symlinks after confirmation.

---

### 7) `extras`
Additional scans:
- iOS backups (old devices)
- removable language packs in `/Applications`

```bash
mac-cleaner extras [OPTIONS]
```

Options:
- `--ios-backups`  
  Run iOS backup scan.
- `--language-packs`  
  Run language pack scan.
- `--all`  
  Run both extras scans.
- `--delete-backups`  
  Interactively delete old iOS backups.
- `--strip-languages`  
  Interactively strip removable language packs from matching apps.

Notes:
- If you do not specify `--ios-backups`, `--language-packs`, or `--all`, the command aborts.

---

### 8) `binary`
Detect universal (“fat”) binaries and optionally thin them.

```bash
mac-cleaner binary [OPTIONS]
```

Options:
- `--path PATH` *(multiple allowed)*  
  Roots to scan.
- `--arch {arm64|x86_64}`  
  Target arch. Defaults to current CPU.
- `--thin`  
  Interactively thin fat binaries to target arch.
- `--no-backup`  
  Skip `.fat_backup` copy (irreversible).

Behavior:
- Uses Apple recommended method (`ditto --arch`) behind the scenes.

---

### 9) `undo`
Restore staged files from staging area.

```bash
mac-cleaner undo [OPTIONS]
```

Options:
- `--list`  
  List available sessions without restoring.
- `--session PREFIX`  
  Restore a specific session by ID prefix (default: latest).
- `--purge`  
  Permanently purge old staged files beyond retention period.

---

### 10) `history`
Show past scan records stored in history config directory.

```bash
mac-cleaner history [OPTIONS]
```

Options:
- `--limit N` (default: `10`)

---

### 11) `diff`
Compare two scan records.

```bash
mac-cleaner diff [SCAN_A] [SCAN_B]
```

- `SCAN_A`, `SCAN_B` are scan ID prefixes from `history`.

If omitted:
- compares the two most recent scans.

Output:
- Size delta
- new/resolved/persistent orphan lists.

---

### 12) `system`
Inspect startup items, login items, and system security health.

```bash
mac-cleaner system [OPTIONS]
```

Options:
- `--launch-items`  
  Inspect LaunchAgents/LaunchDaemons.
- `--login-items`  
  Inspect login items.
- `--health`  
  Check SIP + related hints.
- `--all`  
  Run all checks.

If none of the above flags are supplied, the command aborts with guidance.

---

### 13) `schedule`
Manage weekly automatic scan schedule.

```bash
mac-cleaner schedule COMMAND
```

Subcommands:
- `install --no-notify`
- `remove`
- `status`

Notes:
- The underlying implementation sets up a LaunchAgent/weekly runner.

---

### 14) `update`
Check for newer version and optionally upgrade.

```bash
mac-cleaner update [OPTIONS]
```

Options:
- `--check`  
  Check only (no upgrade).
- `--yes` / `-y`  
  Upgrade without prompting.

---

### 15) `config`
Show or initialize config.

```bash
mac-cleaner config [OPTIONS]
```

Options:
- `--init`  
  Create a default config file if none exists.
- `--show`  
  Print the resolved config.
- `--profile PROFILE`  
  Use a config profile while resolving.

Default behavior:
- shows the resolved configuration panel (and shows JSON if `--show` is specified).

---

## Notes / tips
- Use `scan` first to preview what would be removed.
- Use `clean` with undo enabled for safer cleanup.
- Use `undo --list` to view staging sessions and `undo --session <prefix>` to restore.
- rg -0 -l "v1\.2\.0" -g '!build/**' -g '!.venv/**' | xargs -0 perl -pi -e 's/v1\.2\.0/v2.0.0/g'  ( to change the v directly with finding patterns)