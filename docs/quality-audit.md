# Quality audit — 2026-11-07

The current 3.5.0 pass removes Care Center, preserves shared cleanup recovery and language functionality, fixes the Ghost Sort border and visible mascot blinks, centers empty states, and repairs fullscreen close/reopen handling. Version 3.5.0 remains unreleased and above main/PyPI 3.2.0. This report describes tested behavior, not a guarantee that every macOS configuration is defect-free.

## Current verification

- **370 Python tests passed**, including real temporary-file deletion/restore, protected paths, stale selections, Ghost exclusions, language validation, and version policy.
- **Nine browser flows** cover workspace navigation, deletion/restore, Toolkit, Homebrew, shared history/language controls, Ghost Files, localization, accessibility, and loading states.
- Workspace checks cover **128 theme/language/window combinations**. Old Care deep links fall back to Storage Cleanup, with no Care navigation or assets remaining.
- **24 WCAG audits passed** across workspaces, Cleanup history, application details, uninstall reviews, and permission notices in both themes.
- Loader checks cover **66 feature/theme/window combinations per engine** in Chromium and WebKit, including single-loader placement, actual percentages, cancellation, errors, centered artwork/copy, uninterrupted animation timing, and Reduce Motion. Rendered SVG snapshots verify visibly closed and reopened eyes; live polling checks observe blinking without restarting its clock. Completed empty states retain a static mascot with no active animations.
- Ghost Sort checks exercise selection and verify a single border with no wrapper padding in both themes at six window sizes.
- Native lifecycle tests cover ordinary close, fullscreen exit before hiding, repeated close, reopen during entry/exit, and fullscreen failure recovery. All native sources pass Swift typechecking. These tests exercise the state machine; they do not automate macOS fullscreen Spaces.
- All **42 bundled language packs cover 1,990 active messages**, with protected tokens intact. Removed Care strings are pruned. These are automated checks, not native-speaker review.
- Python static analysis, JavaScript syntax, and whitespace checks pass. Version policy accepts 3.5.0 above main's 3.2.0 and rejects the previous 3.0.0 downgrade.

## Removal and retained functionality

Care Center's dashboard, sidebar/settings links, HTTP routes, CLI group, schedules, profiles, custom rules, media similarity, app slimming, additional inventory screens, treemap, trends, and HTML reports are removed. Dedicated code, assets, media dependencies, translations, and tests for those removed tools are also removed.

The shared Trash journal remains intact. Storage Cleanup opens Cleanup history with identity-checked, conflict-safe restore. `mdc history` and `mdc restore ENTRY_ID` provide CLI access. Existing settings and journal files are preserved.

Settings owns language import/export and consented background generation, including progress and failure feedback. Generation tests intercept provider requests or use mocks; no paid translation is performed. Ghost allowlist removal remains in Settings and preserves any separate user exclusion of the same path.

The native menu opens safe-item selection for review and shared Cleanup history. It no longer starts the deleted minimal-profile operation. No Care weekly launch agent was installed on the development Mac.

## Safety verification

| Area | Exercised behavior | Boundary |
| --- | --- | --- |
| Storage cleanup | Cancel, stale IDs/revisions, changed files, partial failure, exclusions, protected roots, nested selections, zero-byte files | Real disposable files; retained siblings verified |
| Trash/history | Exact-byte restore, conflicts, missing/changed entries, journal recovery, permanent deletion acknowledgement | Temporary home and SQLite journal; no host cleanup |
| Applications | Cache cleanup retains persistent WebKit/HTTP storage; reviewed uninstall | Disposable application bundle and cache |
| Duplicates | Matching content and keeper identity revalidation | Real fixture files; original retained |
| Disks | Usable volume filtering, startup protection, erase/partition review and cancellation | Simulated disk commands; no real disk mutation |
| Optimize/Homebrew | Maintenance completion/failure, dependency protection, upgrade/tidy review, exports | Fake runners; no host package/service changes |
| Ghost Files | System exclusions, installed ownership, permission gaps, review/unlock/cancel, Trash/history, AI consent | Temporary Library and simulated Ollama |
| Shared Settings | Language import, generation progress/errors, key cleared from UI, allowlist exclusions | Isolated packs and intercepted translation |
| Release version | Branch regression rejected; duplicate/older PyPI versions not published | Local policy tests; no publishing or tagging |
| Native window | Exit fullscreen before hiding, reopen cancels delayed hide, failure recovery | Swift lifecycle tests and source compilation; native Space transitions require manual acceptance |

The preceding read-only host Ghost scan found no candidates and reported unreadable installed-app locations and Application Support. Inaccessible folders were not established to be free of leftovers. See [the Ghost system audit](ghost-system-audit.md).

Real hardware erase/partition operations and a fresh-account Ollama installation remain manual acceptance checks. Native UI interactions were not re-automated; browser behavior is tested separately from native compilation and launch verification.

## Build and reproduce

```sh
.venv/bin/python -m pytest -q
.venv/bin/ruff check --select E9,F mac_deep_cleaner tests scripts/version_guard.py
.venv/bin/python scripts/version_guard.py --base-ref origin/main
npm install --prefix /tmp/mdc-ui-check playwright@1.64.1 @axe-core/playwright@4.14.0
/tmp/mdc-ui-check/node_modules/.bin/playwright install chromium webkit
NODE_PATH=/tmp/mdc-ui-check/node_modules .venv/bin/python tests/run_browser_checks.py
MDC_TEST_BROWSER=webkit NODE_PATH=/tmp/mdc-ui-check/node_modules .venv/bin/python tests/run_browser_checks.py progress
.venv/bin/python scripts/complete_locales.py --check
xcrun swiftc desktop/window_presentation.swift tests/native_window_lifecycle.swift -o /tmp/mdc-window-tests
/tmp/mdc-window-tests
xcrun swiftc -typecheck desktop/main.swift desktop/window_chrome.swift desktop/window_presentation.swift
bash scripts/build.sh pkg
bash scripts/build.sh build
```

Fixtures are recreated and stopped for each flow. Evidence is stored under `/tmp/mdc-workspace-check`, `/tmp/mdc-ui-check`, and `/tmp/mdc-ghost-check`. CI runs all feature flows and separate WebKit loader coverage. Source/native packaging checks verify version 3.5.0, active assets and locale packs, and the absence of Care modules/assets. Local native bundles use ad-hoc signing, not public notarization.
