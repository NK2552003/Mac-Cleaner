# Security Policy

## Local maintenance and disk operations

Version 3.1.0 exposes its tool APIs only through the existing authenticated loopback session, Host/Origin checks, and same-site cookie. The command catalogue accepts fixed action identifiers; disk names and formats are validated and passed as subprocess argument arrays. No arbitrary command, filesystem path, URL, or administrator password is accepted by these APIs.

Disk mutation plans are held server-side, expire after five minutes, and are consumed once. Execution checks the exact typed phrase and backup acknowledgement for erase/repartition, then re-reads disk identity, topology, and eligibility. Internal/startup/home, detected backup, system-role, RAID, multi-store, virtual, unidentified, or read-only devices are protected. Missing safety metadata disables changes. Like any device-identifier-based tool, a reconnect at the instant between final validation and macOS opening a device cannot be made atomic by this app; never connect or disconnect storage during an operation.

DNS and Spotlight use a fixed AppleScript command with the native administrator prompt. Disk commands run as the current user. Maintenance output is kept only in session memory (last 20 jobs); exported health reports can contain process names and launch-agent locations, so review them before sharing.

## Homebrew management (3.2.0)

Homebrew mutations accept only fixed action identifiers and installed package identities resolved from fresh JSON. Formula/cask namespaces and tap names are preserved. Tidy intersects Homebrew’s autoremove preview with the recorded dependency graph, requested/unknown roots, pins, and registered services. Missing dependency receipts, ambiguous identities, or unreadable service checks disable package removal. An unused Homebrew dependency may still be needed by software outside Homebrew; no universal “safe to delete” claim is made.

Plans are session-bound, expire after five minutes, and are consumed once. Execution rechecks the package graph, installed/available versions, service states, eligibility, and cleanup/upgrade preview. Uninstall uses neither force nor ignore-dependencies; cask zap and raw filesystem deletion are not exposed. Automatic autoremove, install cleanup, and dependent upgrades are disabled in the subprocess environment. Homebrew and package installation scripts retain their normal capabilities; selected upgrades may install dependencies listed in their preview. Other terminals may change Homebrew between checks, so avoid concurrent package operations.

Exported reports include package and service names and installation paths. Brewfile exports are package lists, not version lockfiles. No passwords or sudo shell access are accepted by this API.

## Reporting a Vulnerability

### Security contact
For security issues, please report privately by opening a GitHub issue on the project with the label `security` (or describing it as a security report in the issue title).

**Where to report:**
- https://github.com/NK2552003/Mac-Cleaner/issues

### What to include
When reporting, please include:
- A clear description of the vulnerability
- Steps to reproduce (if applicable)
- Expected vs actual behavior
- Impact (e.g., data exposure, privilege escalation, remote code execution)
- Affected versions (if known)

### Disclosure expectations
- We will acknowledge receipt of your report as soon as possible (typically within **2–3 business days**).
- We will provide a response on whether the report is accepted and what the remediation plan/timeline looks like.
- If accepted, we’ll work to release a fix in a subsequent release for the supported versions listed above.

### Responsible disclosure
- Do **not** publish exploit details publicly until a fix is released (or we confirm the issue is non-actionable).
- Do **not** attempt to cause real-world damage.
- Avoid including sensitive personal data or credentials in the report.

### If you can’t use GitHub issues
If GitHub issues are not appropriate, add a note in your report explaining why and include as much of the above information as possible.


## Ghost Files

Ghost Files is disabled by default. The deterministic scanner and safety gate have authority over candidate status; model text cannot authorize removal. Ghost deletion uses the same scan revision, path, identity, exclusion, and Trash validators as other cleanup. AI inference is fixed to loopback with proxies and redirects disabled; no cloud fallback exists. Setup requires separate consent for installation, starting Ollama, and downloading a supported model. Downloaded apps must pass signature, pinned TeamIdentifier, and Gatekeeper checks. Removal verifies recorded component identity and never recursively deletes the shared Ollama data directory.

All dashboard mutations require the per-session `X-MDC-Token`, session cookie, exact local Origin and Host. See [Ghost Files](docs/ghost-files.md) for lifecycle, data locations, limitations, and manual release acceptance checks.
