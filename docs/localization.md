# Localization maintenance

The application ships 42 non-English locale files and an English source catalog.
All 42 packs cover all **2,163 messages** (90,846 locale entries), completed on
2026-11-07 with Google Cloud Translation and targeted terminology corrections.
The coverage audit reports **zero missing entries and zero damaged protected
tokens**. Product names, acronyms and terms shared between languages can legitimately
match English; these are listed separately for review. Machine translation and
automated validation do not constitute a native-speaker review of every message.

## Audit and complete packs

```sh
NODE_PATH=/tmp/mdc-i18n/node_modules node scripts/extract_messages.cjs
python3 scripts/complete_locales.py --check --report /tmp/mdc-localization-audit.json
```

The extractor requires `acorn`. It collects static source messages and templates
from JavaScript, Python and native menu labels. Code identifiers, SQL, selectors,
and standalone commands are excluded. Runtime filenames, paths and scan results
are never part of translation requests. After removing source messages, use
`--prune-stale` to remove their retired keys from packs without networking.

To fill missing translations, use the hidden terminal prompt (or configure
`MDC_TRANSLATE_API_KEY` in the process environment):

```sh
python3 scripts/complete_locales.py --generate --key-prompt --workers 3
python3 scripts/complete_locales.py --check
```

This explicitly uses Google Cloud Translation and may incur provider charges.
The key is sent only to Google in an API-key header and is not saved. Placeholders,
product names, quantities and `I UNDERSTAND` are protected during translation;
the response is converted back to plain text and validated before saving.
Successful batches are saved atomically. Transient quota/network errors use bounded
backoff; credential errors stop the run with a specific diagnostic. Rerun the same
command to resume. `--retry-unchanged` asks Google to reconsider unchanged entries;
`--retranslate 'exact source message'` refreshes a particular entry. Existing entries
with damaged protected tokens are automatically repaired on the next generation.
`enrich_locales.py` forwards to this tool instead of padding packs with English text.

If Google reports `API_KEY_SERVICE_BLOCKED`, allow **Cloud Translation API**
(`translate.googleapis.com`) in that key's API restrictions in Google Cloud Console.
If it reports `SERVICE_DISABLED`, enable the API in the project. Keep credentials
out of source files, command-line arguments, and Git.

## Runtime behavior

Language activation loads the pack before saving the selection, then updates the
UI, native menus and AI language together. Switches are serialized. Text nodes
and accessibility attributes retain their English source so switching back to
English restores them. Catalog templates preserve named or numbered placeholders.
Numbers, relative dates and timestamps use the selected locale.

Both local AI requests receive the selected language. Narration and inspector
caches include the language. Opening the Ghost inspector only examines local
files; its web-search links require an explicit click. Recommendations retain the
scanner's verdict, including a previous AI veto. Private names, paths, commands
and typed confirmation phrases are preserved.

## Verification

```sh
.venv/bin/python -m pytest -q
swift build
```

`NODE_PATH=/path/to/node_modules python3 tests/run_browser_checks.py` runs all
nine Playwright flows against fresh isolated fixture servers and stops each server
after its check. It includes workspace, deletion, Toolkit, Homebrew, Care, Ghost Files,
localization, and accessibility checks. Install `playwright` and `@axe-core/playwright`
in that Node module directory. Pass one or more flow names to run a subset.
The Python regressions enforce complete catalog coverage and intact protected text
for every bundled locale. The localization browser flow checks all 42 selections, persistence, direction,
interpolation, repeated language changes, failed pack loading and the cardless
Ghost inspector at desktop and mobile widths. Run each browser flow against fresh
fixtures so a prior scan or settings change cannot affect the next flow.
