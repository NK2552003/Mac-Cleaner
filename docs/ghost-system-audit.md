# Ghost Files system-data audit — 2026-11-07

The original finder was run against the real user's eight Library locations,
installed applications, Spotlight, processes, developer tools, and Homebrew
inventory. The scan was read-only; no host file was deleted, moved, restored,
unlocked, or submitted to an AI service.

## Observed results

The original scan returned **15 candidates**. The corrected scan returned **zero
candidates in the accessible locations**. It retained warnings for incomplete
application inventory and unreadable Application Support data. Zero results do
not establish that inaccessible locations contain no leftovers.

| Original result | Finding and correction |
| --- | --- |
| Animoji, SESStorage, Categories, CloudDocs, DifferentialPrivacy, IntelligenceFlow, locationaccessstored | macOS service/shared infrastructure names were missing from the exclusions. They now remain outside Ghost Files. |
| `group.is.workflow.my.app` | The installed Shortcuts app's signed entitlements explicitly declare this group. Legacy Workflow namespaces and normalized group/team IDs are protected. |
| `default.store`, `default.store-shm`, `default.store-wal` | Loose support/database files with no app identity were being treated as possible uninstalls. They are excluded. |
| `com.plausiblelabs.crashreporter.data`, `main.kts.compiled.cache` | Shared crash-reporting and Kotlin scripting caches do not have standalone owner apps. They are excluded from orphan discovery. |
| OneDrive | Installed Microsoft applications may share this service's state. It is retained while that vendor is installed. Without an installed vendor, a name-only folder remains locked for review. |
| BraveSoftware | A denied subtree was silently counted as empty. Measurement now fails closed and reports the permission gap. |

The new scan additionally reads `com.apple.security.application-groups` from
installed apps' code-signing metadata, so a shared group's namespace need not
resemble its owning app's bundle identifier. These claims can only suppress a
candidate, never authorize removal. Unsigned apps and missing entitlements are
handled without failing the scan. Cancellation is checked between apps, and each
code-signing query has a two-second timeout. The measured real scan took about
six seconds with this ownership check.

## Regression coverage

Verification passed: **377 Python tests**, including **164 Ghost/API tests** and
**47 new regression cases** in this pass. The Ghost Files browser flow and Python
static-analysis checks also passed.

- System service names, preference suffixes, legacy Shortcuts groups, group/team
  prefix order and case, shared SDK/runtime identifiers, and namespace boundaries.
- Genuine abandoned bundles remain discoverable beside protected entries; a
  name containing `apple` or `workflow` is not excluded by a loose substring match.
- Installed app-group claims with unrelated namespaces suppress their owned data;
  malformed or absent entitlements fail safely.
- Unknown support files are excluded, while name-only app folders retain the
  existing locked-review workflow.
- Permission-denied subtrees are skipped with a visible warning.
- Simulated old system results are omitted from the report and cannot be unlocked
  or moved to Trash, even with a previously unlocked ID and a confirmed request.
- Browser fixtures include nine protected entries alongside three genuine review
  candidates. The browser verifies that only the three candidates appear and that
  the protected files retain identical bytes after a reviewed candidate Trash move.

All deletion checks use a temporary Library and Trash. The browser also exercises
unlock, cancel, history, dismissal, AI consent, model vetoes, and both themes at six
window sizes. These checks complement the live read-only scan; they do not erase
or change actual user data.

## Reproduce

```sh
.venv/bin/python -m pytest -q tests/test_ghosts.py tests/test_ghost_api.py
NODE_PATH=/tmp/mdc-ui-check/node_modules .venv/bin/python tests/run_browser_checks.py ghosts
```

After opening the rebuilt application, run **Ghost Files → Find ghosts** to replace
results produced by an older running copy.
