# Quality audit — 2026-11-07

This pass tested file operations against actual disposable files, reviewed failure
handling, and audited navigation, forms, dialogs, responsive layouts, and contrast.
It does not establish that every possible macOS configuration is defect-free.

The subsequent [Ghost Files system-data audit](ghost-system-audit.md) adds a live
read-only scan, app-group ownership checks, hard system exclusions, and 47 more
regression cases. The full Python suite now passes **377 tests**; the updated Ghost
browser flow also passes. The results below describe the preceding full UI audit.

## 3.0.0 release verification

- The full Python suite passes 377 tests and all nine browser flows pass.
- One shared SVG mascot loader matches the source icon, with feature-specific
  colors, symbols, and orbit timing. Storage Cleanup uses one loader inside its
  overview card; duplicate banners, old progress tracks, and skeletons are removed.
  Active-report refreshes, Care jobs, and Ghost scans/analysis use the same component.
  The header reflects current activity without adding an animated indicator.
- Progress verification passes in both Chromium and WebKit: 78 feature/theme/window
  combinations and 13 accessibility checks per engine. Checks cover completion,
  failed requests, measured percentages, cancellation, single-loader placement,
  preserved animation start times across redraws, and Reduce Motion.
- Care scheduling displays aligned day/time dropdowns without redundant visible
  labels. Tests verify accessible control names, localized time values, and draft
  persistence across navigation and polling.
- The subsequent read-only Ghost recheck found no candidates and retained warnings
  about unreadable installed apps and Application Support. This is not proof that
  inaccessible folders have no leftovers. Ghost system exclusions, review, cancel,
  and Trash/history flows pass with disposable fixtures; no host files were cleaned.
- Runtime, UI, report, package, and native bundle versions derive from one constant.
  The pending feature notes are consolidated into the 3.0.0 changelog section.
- `.gitignore` excludes generated output and local credentials; source artwork and
  complete locale packs remain tracked. Finder metadata and duplicate icons are
  removed from the index and excluded from source distributions.
- The existing build scripts produce the versioned wheel/source archive and native
  macOS app and installer. Package contents are checked for all 42 locales, the
  source icon, and both shared loader assets.

## Verified results

- **330 Python tests passed**, including 33 new filesystem/review integrity cases.
- **Eight browser flows passed**: workspace, deletion, Toolkit, Homebrew, Care,
  Ghost Files, localization, and accessibility.
- **38 WCAG A/AA audits passed** with no reported violations in the tested views,
  Care forms, application details, uninstall dialogs, and permission notices.
- The workspace flow covers **144 view/language/theme/window combinations**,
  plus all seven Care tabs at narrow width. A separate 54-view visual/layout audit
  found no horizontal overflow. Ghost Files is checked in both themes at six sizes.
- All **42 language packs cover 2,163 messages**, with no missing translations or
  damaged protected tokens. These are automated checks, not native-speaker review.
- Python error/unused-definition checks and whitespace checks pass.
- The standalone **arm64 / macOS 14+ app** builds, passes strict deep code-signature
  verification with its local ad-hoc signature, and starts its bundled engine's
  version command successfully. It is not a notarized public release.

## Findings fixed

| Area | Reproduced problem | Resulting behavior |
| --- | --- | --- |
| Safe bulk selection | Could include Trash emptying or non-Trash operations | Selects ordinary Trash moves; irreversible operations require individual review |
| Empty Trash | Could be submitted without permanent-deletion acknowledgement or mixed with new Trash moves | Separate selection and typed confirmation in the UI; backend enforces explicit acknowledgement |
| App cache cleanup | WebKit/HTTP storage was classified as disposable cache | Persistent browser/app data is retained by Clear caches |
| Exclusions | A parent scan result could contain an excluded child, especially through CLI cleanup | Both ancestors and descendants are excluded from executable scan results |
| Nested selections | Dry runs and UI totals could count parent/child bytes twice | Each selected storage subtree is counted once |
| Restore recovery | A crash before the restore rename left an intact item unavailable | Intact recorded Trash entries remain retryable |
| Journal finalization | A successful move followed by a journal write error could be reported as failed | Durable intent records recover the completed move |
| Cleanup feedback | Important results vanished into stacked transient notifications | Persistent success/failure details and direct access to restore history |
| Small files | Zero-byte successful removals could be described as no removal | Per-item outcomes determine success independently of byte totals |
| App slimming | Requested regional and legacy language resource names could be removed | Requested language families/variants and Base/English are retained in the separate copy |
| Scheduling | Malformed plists, disappearing files, and symlink lock files were mishandled | Invalid definitions fail safely; vanished candidates are skipped; lock symlinks are refused |
| Scan coverage | Denied home-folder access was silently skipped | Permission gaps are listed with a Privacy settings shortcut |
| Cached workspaces | Cleanup could leave disk/health and similar-media results stale | Relevant reports/candidates are invalidated after cleanup |
| Presentation | Icon-only desktop navigation, low-contrast badges, notification overlap | Labeled navigation, remembered preference, corrected contrast, and in-page results |

## Feature verification matrix

| Feature | What was exercised | Execution boundary |
| --- | --- | --- |
| Storage cleanup | Cancel, stale versions, invalid IDs, changed files, partial success, protected roots, exclusions, symlinks, nested selections, zero-byte files | Real temporary files; untouched siblings verified |
| Trash/history | Byte-identical file and nested-directory restore; conflicts; interrupted states; changed/emptied entries; typed emptying | Actual rename, unlink, directory removal and SQLite journal operations in a temporary home |
| Applications | Clear caches, retained WebKit/HTTP data, reviewed uninstall, retained application bytes before uninstall | Actual disposable app directory and cache data; no installed app removed |
| Large files/duplicates | Search/navigation, content revalidation, changed keeper rejection, original retention | Real duplicate file contents and UI checks |
| Disks | Physical-backed volume display, helper/image exclusion, startup protection, identity changes, typed erase acknowledgement, partition review/cancel/run | Disk commands simulated; real host topology was checked read-only in the preceding pass |
| Optimization/Homebrew | Job completion/failure, reviewed commands, protected dependencies, upgrade/tidy previews, package export, stale inspector handling | Fake command runners; no host package/service changes |
| Care profiles/rules | Selection handoff, exclusions, validated JSON, draft persistence | Temporary scan/settings data |
| Startup/schedule | Identity revalidation, enable/disable command targets, schedule install failure rollback, calendar validation, locking | Temporary plists and simulated launchctl; no real agent changed |
| Similar media | Actual image hashing, review-only pairs, Finder request wiring | Generated test images; browser Finder action mocked |
| App slimming | Language deletion occurs only inside a separate copy; source bytes retained; requested variants preserved | Actual disposable copy/filesystem edits; ditto/codesign/lipo command boundary simulated |
| Ghost Files | Off-state isolation, scan, review/cancel, Trash/history, dismissal, AI consent/cancellation/removal ownership | Temporary Library and simulated Ollama |
| Localization | All 42 selections, persistence, RTL, placeholders, dialogs, failed loading, rapid language changes | Bundled packs and isolated settings |

Real disk erasure, real launchd changes, full Ollama installation, and compatibility
of arbitrary third-party slimmed applications remain hardware/manual acceptance
tests. Automated coverage cannot establish those outcomes.

## Reproduce

```sh
.venv/bin/python -m pytest -q
.venv/bin/ruff check --select E9,F mac_deep_cleaner tests
npm install --prefix /tmp/mdc-ui-check playwright@1.64.1 @axe-core/playwright@4.14.0
/tmp/mdc-ui-check/node_modules/.bin/playwright install chromium webkit
NODE_PATH=/tmp/mdc-ui-check/node_modules .venv/bin/python tests/run_browser_checks.py
MDC_TEST_BROWSER=webkit NODE_PATH=/tmp/mdc-ui-check/node_modules .venv/bin/python tests/run_browser_checks.py progress
python3 scripts/complete_locales.py --check
bash scripts/build.sh pkg
bash scripts/build.sh build
```

The browser runner creates a fresh fixture for each flow and stops it afterward.
Evidence is written under `/tmp/mdc-care-check`, `/tmp/mdc-ui-check`, and
`/tmp/mdc-ghost-check`. Browser deletion tests refuse paths outside their temporary
fixture prefix. CI now runs static analysis, deletion, and accessibility checks in
addition to the existing feature flows.
