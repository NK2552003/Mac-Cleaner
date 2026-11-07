# Localization maintenance

The application includes 42 non-English packs and an English catalog of **1,990 messages** (83,580 bundled locale entries). All new automation, notification, and update messages were translated with AI during development, without a cloud translation API. Existing translations are retained. Complete coverage and protected-token checks pass; these checks are not a native-speaker review.

## Audit and update packs offline

```sh
NODE_PATH=/path/to/node_modules node scripts/extract_messages.cjs
python3 scripts/complete_locales.py --check --report /tmp/mdc-localization-audit.json
python3 scripts/complete_locales.py --merge /path/to/ai-authored-fr.json
```

The extractor uses `acorn` and reads static JavaScript, Python, and native menu messages. Runtime filenames, paths, scan results, and documents are never included. To add translations, give the missing static messages to the AI author and save the result as a JSON pack with `locale` and `messages`. Merge each pack, then run the audit. Merging rejects unknown messages, wrong locale tags, HTML, altered placeholders, product names, quantities, and typed confirmation phrases before replacing the existing pack. Retired messages are pruned during a successful merge. Writes are atomic.

No translation API, API key, or network generation is supported by the application or maintenance tool. The Settings language controls load bundled packs, import validated offline JSON, and export the current pack or English template. Unavailable translations fall back to English. Product names and shared technical terms may legitimately match English; the audit lists unchanged entries separately.

## Runtime behavior

Activation loads the selected pack before saving the choice, then updates the UI, native menus, and local Ghost AI language together. Switches are serialized. Source text is retained for switching back to English. Dates and numbers follow the selected locale. Both local Ghost AI requests and their caches include the language.

Private filenames, paths, command output, and typed safety phrases remain unchanged. User packs are stored under `~/Library/Application Support/Mac Deep Cleaner/locales`.

## Verification

```sh
.venv/bin/python -m pytest -q
NODE_PATH=/path/to/node_modules .venv/bin/python tests/run_browser_checks.py support workspace localization
```

The Python regressions check all bundled packs, protected text, and offline merge rejection. Browser checks exercise language switching, import/export, RTL layout, saved settings, update links, and actual safe cleanup using disposable fixtures. The fixtures never clean host files.
