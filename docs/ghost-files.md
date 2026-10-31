# Ghost Files

Ghost Files is an experimental, opt-in mode for Mac Deep Cleaner. It finds possible leftovers from removed apps, gives them gentle haunting descriptions, and records successful Trash moves in an Ofrenda. It is inspired by Halloween and Día de los Muertos.

## Enable it

Open **Settings → Experimental → Ghost Files**. The default is **Off**. Enabling it first selects **Ghosts (no AI)**; **Open Ghost Files → Find ghosts** starts a read-only scan after the main scan finishes.

| Mode | Behavior |
| --- | --- |
| Off | No Ghost modules or browser assets load on a fresh launch. No Ghost sockets, detection, or scanning. |
| Ghosts (no AI) | Deterministic scanner and descriptions; no network or LLM imports. |
| Ghosts + AI narration | The same scanner with optional inference at `http://127.0.0.1:11434`. Only approved setup steps download software/models. |

Ghost Files does not change the networking behavior of separate tools such as Homebrew.

## Set up local AI

Choose **Ghosts + AI narration** or **Set up AI narration**. The wizard shows the detected installation, available models, RAM, free storage, and each required step. All consent boxes start unchecked. Check each required step and choose **Run approved steps**:

1. Install Ollama only if missing: a Homebrew formula when Homebrew is available, otherwise the official app in `~/Applications`. No `sudo`, privilege escalation, or automatic fallback to a different installation method.
2. Start Ollama on `127.0.0.1:11434` only with start consent. Mac Deep Cleaner launches and retains its own `ollama serve` child; it does not launch or quit the Ollama GUI.
3. Download the selected model only if missing. Existing models are reused without claiming ownership.
4. Run a self-test using a fictional ghost, then display its narration.

| Model | Approximate download | Suggested RAM | Minimum free disk before model pull |
| --- | ---: | ---: | ---: |
| `llama3.2:1b` (Light) | 1.3 GB | 4 GB | 3.0 GB |
| `llama3.2:3b` (Balanced) | 2.0 GB | 8 GB | 4.0 GB |
| `gemma3:4b` (Richer) | 3.4 GB | 8 GB | 6.1 GB |

Ollama itself requires an additional download. Sizes are estimates and model tags can change. Macs below 8 GB RAM are recommended Light; 8 GB and above are recommended Balanced. The picker always lets you choose. Current official Ollama app releases require macOS Sonoma or later; an unavailable Homebrew bottle or unsupported OS fails visibly without elevating privileges.

The first narration pass covers the 25 largest visible ghosts. **Narrate the rest** processes the remaining entries. Changing the model allows a new pass; an earlier cautious verdict stays cautious until a new scan. **Cancel** stops further work and terminates setup subprocesses owned by the job. An in-flight local model request may take up to 45 seconds to time out; download reads have 15–20 second timeouts. A cancelled pull may leave Ollama's resumable partial download in `~/.ollama`; Mac Deep Cleaner does not erase that shared directory.

If setup or its self-test fails, Ghost Files returns to level 1. Completed installation/download steps remain recorded so they can be reused or explicitly removed. If Ollama disappears during narration or returns malformed data, the remaining entries use plain descriptions. There is no cloud fallback.

## Review and banish

The scanner compares reverse-DNS bundle identifiers and app names in eight user Library locations with standard application directories, including system applications. Installed bundle prefixes (helpers/extensions), Apple namespaces, and known VS Code folder aliases are excluded. Symlink roots and entries are skipped. Incomplete installed-app inventory makes candidates locked. Sizes are file-content estimates; age uses the newest readable modification time beneath an entry.

| Verdict | Review behavior |
| --- | --- |
| Likely safe | Unmatched regenerable data. Still requires an individual final Trash review. |
| Review first | Settings, containers, or application data. No automatic selection. |
| Locked | Unverified ownership. Inspect it, type `UNLOCK`, then complete a separate Trash review. |

No ghost is preselected. **Inspect this leftover** exposes the full path locally and **Show in Finder** reveals it. **Let it rest** hides an entry for the current scan; **Show resting ghosts** brings it back. A new scan resets hidden entries, unlocks, and previous verdicts.

The model can only make the deterministic verdict more cautious. Its text is sanitized, length-limited, and HTML-escaped; it cannot submit paths or issue actions. Prompts contain only bounded name, bundle ID, kind, size, age, and confidence fields—never the full path or home directory.

Ghosts are normal scanner items, assigned the current scan ID, revision, and filesystem fingerprint. **Banish to Trash** calls the existing `/api/clean` endpoint and shared `execute` validators. Stale revisions, changed identities, exclusions, protected items, and unsafe paths are rejected. Parent or app cleanup cannot bypass a ghost review. Generic Cleanup links these entries back to Ghost Files. Permanent deletion is disallowed for ghost items.

The Ofrenda records only successful moves, with name, size, UTC date, and a farewell. Export it as `ofrenda.md` from the Ghosts screen; the native shell opens a Save dialog. Files still consume space while in Trash. Restore them with Finder before emptying Trash if needed.

## Turn it off or remove AI

Turning the feature off stops its UI polling and keeps AI installations/models intact. The stop-on-exit option applies only to the exact process started by this running Mac Deep Cleaner instance. Persisted PIDs are never used to stop processes.

**Settings → Remove AI components** lists only models pulled by Mac Deep Cleaner and the installation it created. Select and confirm the components to remove. A recorded model digest and installation fingerprint must still match; changed or user-owned components are refused. Models use Ollama's delete API; the owned app uses the shared Trash executor; an owned Homebrew formula uses `brew uninstall ollama` without dependency autoremove. If Ollama is stopped, start it with your approved setup flow before deleting its models.

The shared `~/.ollama` directory is always retained, including models and partial downloads belonging to other workflows. Remove it manually only if you have independently reviewed everything it contains. A replaced or updated installation may need to be removed manually because ownership can no longer be proven.

## CLI

```sh
mdc ghosts enable --level 1
mdc ghosts scan --no-llm
mdc ghosts scan --json
mdc ghosts enable --level 2 --model llama3.2:1b
mdc ghosts setup --model gemma3:4b
mdc ghosts status
mdc ghosts ofrenda > ofrenda.md
mdc ghosts remove-ai
mdc ghosts disable
```

Every required install/start/pull step prompts `y/N`; `--yes` is available on `enable`, `setup`, and `remove-ai` for scripts. CLI scanning is read-only; use the dashboard to review and banish. No scan implicitly enables Ghost Files. `status` reads settings only and never probes Ollama.

## Local data and transport

- Feature configuration and component ownership: `~/.config/mac-deep-cleaner/config.json`.
- Narration cache: `~/.cache/mac-deep-cleaner/ghosts.json` (at most 1,000 entries, hashed identity keys).
- Ofrenda: `~/.local/share/mac-deep-cleaner/ofrenda.json`.
- JSON files are written atomically with owner-only permissions. Corrupt optional caches fall back safely.
- Local inference ignores environment proxies and `OLLAMA_HOST`, refuses redirects, and uses an allowlist of loopback API paths and supported local model names.
- Dashboard mutations require the launch session's HttpOnly cookie, `X-MDC-Token` header, exact loopback Host/Origin, and JSON. No permissive CORS headers are returned. This also protects the existing cleanup and maintenance routes.
- Official app downloads are checked by `codesign --verify --deep --strict`, pinned to Ollama Inc. team `3MU9H2V9Y9`, and assessed with Gatekeeper before installation. A signing-team rotation fails closed; no quarantine bypass is used.

## Verification and remaining release checks

Automated tests use fake Library trees and mock downloads, commands, and local-model responses. They cover the finder, false-positive locks, verdict gates, prompt injection, cache/fallback, lifecycle states, install signing failures, pull errors, ownership, cancellation, no-network/off imports, HTTP protections, stale review tokens, fingerprint failures, and real shared Trash execution in an isolated temporary home.

```sh
python -m pytest -q
swift build -c debug
python tests/ghosts_fixture.py
# In another terminal, with Playwright available:
node tests/verify_ghosts.cjs
```

The browser fixture does not use the host Ollama, installed apps, or user Library. It exercises settings, consent, scanner cards, unlock/review/cancel, Trash, Ofrenda export, narration, removal, and six viewport sizes. CI runs this fixture separately and uploads screenshots.

Before publishing a release, run the actual download/install/self-test on a clean supported macOS user account, and repeat with an already running user-owned Ollama. Automated fixture success is not proof of a real model download or fresh-account installation. Verify native Save-dialog interaction and Finder Put Back in that account as well.

Known discovery limits: applications installed outside standard directories, renamed vendors, shared app-group containers, command-line tools, and login helpers may own apparently orphaned data. Name-only entries remain locked; inspect every proposed removal.

References checked during implementation (2026-10-31): [pull API](https://docs.ollama.com/api/pull), [delete API](https://docs.ollama.com/api/delete), [structured output](https://docs.ollama.com/capabilities/structured-outputs), [Llama 1B](https://ollama.com/library/llama3.2:1b), [Llama 3B](https://ollama.com/library/llama3.2:3b), [Gemma 4B](https://ollama.com/library/gemma3:4b), [official macOS build layout](https://github.com/ollama/ollama/blob/main/scripts/build_darwin.sh), [signing-team reference](https://github.com/Installomator/Installomator/blob/main/fragments/labels/ollama.sh).
