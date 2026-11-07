# Automation, updates, and the menu bar (Unreleased)

This work is staged for the next release. It does not publish a release or install a scheduled release job.

## Automatic safe cleanup

Settings → Automation saves an interval of **1–720 hours** (default: 168 hours). The themed interval picker offers common presets and a Custom option with direct hour entry and plus/minus controls. Automation is off until enabled. Enabling it schedules the first run one full interval later; changing the interval resets that deadline. Closing the window keeps the app running in the macOS menu bar and removes its Dock presence. Open the workspace from the menu bar to bring back the window and Dock presence. Explicit Quit stops the service and pauses automation. Reopening after a missed deadline runs once when idle, without replaying every missed interval. No login item or launch agent is installed.

Each automatic or one-click run takes a fresh restricted scan. Only scanner-classified safe, writable, non-manual Trash candidates under the user's `Library/Caches` and `Library/Logs` are eligible. Every descendant must be unchanged for at least seven days. Unreadable, very large, or slow-to-verify trees are skipped. Running-app matches, protected Apple caches, WebKit/HTTP storage, symlinks, pinned paths, and Ghost exclusions are retained. Documents, downloads, app bundles, duplicate removal, cloud eviction, maintenance commands, and emptying Trash are excluded.

Runs share the existing operation lock. Busy scans and operations defer scheduled cleanup. File identities and exclusions are rechecked by the journaled Trash executor. Files can be restored from Cleanup history while the recorded Trash item remains unchanged and its original location is free. **Moving files to Trash does not free disk space until you empty Trash yourself.**

Settings shows the next deadline, last result, processed size, and errors. The menu bar provides one-click safe cleanup, its latest status, Settings, updates, and Cleanup history. Explicit Quit is refused while a mutation is running; successful quit preparation stops new scheduled work before termination.

## Notifications

Settings → Notifications requests macOS permission when enabled. The current permission status is shown, with a shortcut to System Settings and a test notification. Cleanup completion/failure and newly discovered releases produce native notifications when enabled. Clicking a notification opens Settings. macOS Focus modes and notification preferences can suppress banners; the application result remains available in Settings and history. Browser sessions show in-app feedback and cannot enable native macOS notifications.

## GitHub release checks

Use Check for updates in Settings, the application menu, or the status menu. Checks read the latest stable release from `https://api.github.com/repos/NK2552003/Mac-Cleaner/releases/latest`. Numeric version comparison handles versions such as 3.10.0 correctly. Drafts, prereleases, malformed responses, redirects, and oversized responses are rejected. Offline, rate-limit, and missing-release failures are displayed rather than treated as “up to date.”

The release link opens the matching GitHub release with its notes and downloadable assets. Installation remains a user action. Optional automatic checks run at most daily during a service session and are off by default. GitHub receives a normal release API request; no scan results, file paths, or document content are sent.

## Offline languages

All new feature text is bundled in the 42 supported non-English packs. The updates were authored with AI during development, without calling a cloud translation API. Runtime generation, API-key fields, and cloud translation requests have been removed. Offline import/export remains available. See [localization maintenance](localization.md).
