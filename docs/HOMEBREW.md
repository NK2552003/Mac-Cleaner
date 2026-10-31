# Homebrew management in Mac Deep Cleaner 3.2.0

This workspace adapts the dependency-explanation workflow described by [brew-why](https://github.com/NK2552003/brew-why) into the existing local dashboard and CLI. It is independently implemented using Homebrew JSON and built-in commands; no brew-why, Textual, or extra runtime package is installed.

## Explore

| Command | Result |
| --- | --- |
| `mac-cleaner brew dashboard` | Open the app’s Homebrew workspace. Also available as `--homebrew`. |
| `mac-cleaner brew overview` | Categorized installed formulae and casks. |
| `mac-cleaner brew explain PACKAGE` | Install intent, dependencies, retaining roots, and reverse tree. |
| `mac-cleaner brew reverse-tree PACKAGE` | Traverse installed dependents, with cycle/repeat markers. |
| `mac-cleaner brew heaviest --limit 15` | Largest formula racks by allocated Cellar size. |
| `mac-cleaner brew audit` | Available updates according to local metadata; not a CVE/OSV/security audit. |
| `mac-cleaner brew stats` | Unique package counts and measured directory space. |
| `mac-cleaner brew export --output Brewfile` | Requested/unknown formulae and installed casks; dependency packages are normally restored by Homebrew. |

Read commands support `--json` for stdout or `--json FILE`. Use qualified identities such as `formula:openssl@3`, `formula:owner/tap/name`, or `cask:name` if names are ambiguous. Commands also work through `mdc` and `mac-deep-cleaner`.

The dashboard offers Packages, Dependency groups, Heaviest, Updates, Tidy, and Services views. Search includes package names, descriptions, and taps. Open a package’s inspector for its explanation and management actions.

## Manage

Every change shows its description and exact command. Mutating commands ask for terminal confirmation unless `--yes` is supplied. Permanent removal additionally needs a typed `REMOVE`, or `--i-understand` with `--yes`. Use `--dry-run` first to inspect the plan without running the maintenance command.

```bash
mac-cleaner brew tidy --dry-run
mac-cleaner brew tidy
mac-cleaner brew cleanup --dry-run
mac-cleaner brew upgrade formula:git --dry-run
mac-cleaner brew uninstall formula:git --dry-run
mac-cleaner brew pin formula:git
mac-cleaner brew unpin formula:git
mac-cleaner brew keep formula:some-library
mac-cleaner brew mark-dependency formula:some-library
mac-cleaner brew service-start formula:postgresql@15
mac-cleaner brew service-stop formula:postgresql@15
mac-cleaner brew service-restart formula:postgresql@15
mac-cleaner brew update
mac-cleaner brew doctor
```

Tidy’s first stage reviews unused dependencies, then its second stage obtains a fresh cleanup preview for old versions and cached downloads. Cancelling either stage stops the wizard. If a stage fails, later stages do not run. In the dashboard these are separate buttons so you can inspect the result between steps.

`keep` changes Homebrew’s installed-on-request receipt, keeping a formula out of autoremove. `mark-dependency` makes it eligible for future dependency cleanup if unneeded; it removes nothing immediately. Pinning prevents Homebrew upgrades, and can prevent dependents from upgrading. User services may start at login; system-wide services requiring sudo must be managed separately. Cask installers that require an interactive terminal or administrator authentication may need to be run in Terminal after reviewing the command.

The older `--tool brew-doctor`, `--tool brew-preview`, and `--tool brew-cleanup` aliases remain supported through the same backend. `brew-preview` executes no cleanup command.

## What the graph means

Installation receipts supply recorded runtime dependencies, including dependencies from older installed kegs. Declared direct dependencies form the displayed reverse tree. The retention graph also includes transitive runtime and applicable build dependencies, and cask-to-formula/cask dependencies. Requested packages, casks, unknown origins, pins, and registered active/uncertain services retain their dependencies. Shared dependencies can appear in several groups, but summary totals count each package once.

Removal candidates must also appear in `brew autoremove --dry-run`. Tidy submits only the exact reviewed candidate names to `brew uninstall --formula`; it does not run an unconstrained autoremove. Packages needed by retained dependents, pins, and registered services are blocked. Missing receipts or incomplete service checks disable removal. Scripts, manually installed software, and manually launched services outside Homebrew are not fully discoverable, so review candidates before removal.

## Freshness, space, and execution

- Refresh reads the active Homebrew installation selected by PATH, with standard Apple Silicon/Intel path fallbacks. The prefix is visible. Multiple independent installations are not merged.
- Update metadata explicitly runs `brew update`; ordinary inventory reads disable auto-update, but Homebrew may still download missing API data. No package is upgraded just by opening this page.
- `audit` follows Homebrew’s default outdated behavior. Self-updating/latest-version casks may be omitted. An outdated version is not proof of a vulnerability.
- Sizes come from `du -sk` on Cellar/Caskroom directories. Formula sizes include old installed versions. Cask application bundles moved outside Caskroom are excluded. Missing measurements remain “Unknown”, and APFS sharing means these totals are not guaranteed immediately reclaimable bytes.
- A Brewfile records package choices, not exact versions, application data, pins, or service state. Review it before using `brew bundle` on another machine.
- Background jobs serialize with other app maintenance. Reviews expire after five minutes and work once. Fresh graph and preview changes require another review.
- Automatic autoremove, installation cleanup, and installed-dependent upgrade checks are disabled for app-issued commands. Explicit upgrades may still install/upgrade necessary dependencies, as shown by Homebrew’s preview.
- Commands run under your account without sudo. Permission errors, missing tools, and failed commands appear in operation results. A failed command may have partially completed; inspect and refresh before retrying.

Command semantics follow the [Homebrew manual](https://docs.brew.sh/Manpage), particularly `info`, `autoremove`, `outdated`, `uninstall`, `upgrade`, `tab`, and `services`. Tests use synthetic receipts and fake command runners. Live validation is limited to inventory, explanations, and other reads; it does not uninstall or upgrade your packages.
