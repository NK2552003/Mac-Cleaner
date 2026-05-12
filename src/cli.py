#!/usr/bin/env python3
"""
Mac Deep Cleaner v1.2.0 — CLI Entry Point
=======================================
All subcommands, new and updated.

Subcommands
-----------
  scan          Preview scan (orphans + junk) — safe
  clean         Interactive or auto cleanup
  info          Safety guarantees
  completions   Generate shell completion scripts
  uninstall     Full app uninstaller
  browser-data  Clean browser caches/history/cookies
  space-map     Visual disk space map
  photos        Photo library analyzer
  simulators    iOS simulator deep cleaner
  duplicates    Find duplicate files by hash
  large-files   Find files over a size threshold
  symlinks      Find broken symbolic links
  extras        iOS backups + language packs
  binary        Detect / thin universal fat binaries
  undo          Restore files from staging area
  history       Show past scan records
  diff          Compare two scans
  system        Launch items + SIP + login items
  schedule      Install / remove / status of weekly scan
  update        Check for and apply upgrades
  config        Show / init config file
"""

from __future__ import annotations

import logging
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Optional, Tuple

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table
from rich.text import Text

try:
    from __init__ import __version__
except ModuleNotFoundError:
    try:
        __version__ = version("mac-deep-cleaner")
    except PackageNotFoundError:
        __version__ = "0.0.0"
from core.cleaner import do_cleanup
from config.config import config_file_path, init_default_config, load_config
from constants import LOG_FILE
from scanners.discovery import discover_installed_apps
from reporting.exporter import export_json, export_yaml
from reporting.html_report import export_html
from config.models import JunkEntry
from reporting.reporter import (
    console,
    print_banner,
    print_installed_apps,
    print_instructions,
    print_dev_junk_report,
    print_junk_report,
    print_orphan_report,
    print_summary,
)
from core.safety import running_bundle_ids
from core.scanner import scan_junk, scan_orphans
from core.undo import list_sessions, new_session, restore_session, stage_file
from utils import bytes_human, configure_logging

logger = logging.getLogger(__name__)


# ── Shared progress helper ─────────────────────────────────────────────────────

def _progress() -> Progress:
    return Progress(
        SpinnerColumn("dots", style="cyan"),
        TextColumn("[bold]{task.description}"),
        BarColumn(bar_width=30, style="dim", complete_style="cyan"),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    )


def _ensure_first_run_profile(profile: Optional[str], ci: bool) -> Optional[str]:
    """Prompt for a profile on first run when no config exists."""
    if ci or profile:
        return profile

    cfg_path = config_file_path()
    if cfg_path.exists():
        return profile

    choices = ["beginner", "developer", "professional", "designer", "student", "children"]
    descriptions = {
        "beginner": "Safe defaults, skips dev caches",
        "developer": "Includes dev junk scanning",
        "professional": "Aggressive dev cleanup, lower thresholds",
        "designer": "Larger file focus, no dev junk by default",
        "student": "Safe defaults for school devices",
        "children": "Minimal, safest defaults",
    }

    table = Table(show_header=True, header_style="bold cyan", border_style="dim")
    table.add_column("Profile", style="bold")
    table.add_column("Focus")
    for name in choices:
        table.add_row(name, descriptions.get(name, ""))

    console.print()
    console.print(Panel(
        "[bold cyan]First-time setup[/bold cyan]\nChoose a profile to start with.",
        border_style="cyan",
        padding=(0, 2),
    ))
    console.print(table)

    choice = click.prompt(
        "Profile",
        type=click.Choice(choices, case_sensitive=False),
        default="beginner",
        show_default=True,
    ).lower()

    init_default_config(profile=choice)
    return choice


# ── Root group ─────────────────────────────────────────────────────────────────

@click.group(invoke_without_command=True)
@click.version_option(version=__version__, prog_name="Mac Deep Cleaner")
@click.option("--verbose", is_flag=True, default=False,
              help="Enable debug logging to file.")
@click.option("--log-file", type=click.Path(), default=None,
              help="Write logs to a file (default: ~/.config/mac-cleaner/mac-cleaner.log).")
@click.option("--dry-run", is_flag=True, default=False,
              help="Do not modify anything (disables deletions and writes).")
@click.pass_context
def main(
    ctx: click.Context,
    verbose: bool,
    log_file: Optional[str],
    dry_run: bool,
) -> None:
    """Mac Deep Cleaner v1.2.0 — Professional macOS cleanup tool."""
    from core.dry_run import set_dry_run
    configure_logging(
        verbose=verbose,
        log_file=Path(log_file) if log_file else None,
    )
    set_dry_run(ctx, dry_run)
    if ctx.invoked_subcommand is None:
        ctx.invoke(scan)


# ══════════════════════════════════════════════════════════════════════════════
# SCAN
# ══════════════════════════════════════════════════════════════════════════════

@main.command()
@click.option("--skip-junk", is_flag=True, default=False)
@click.option("--export", "export_path", type=click.Path(), default=None,
              help="Export to JSON / YAML / HTML (by extension).")
@click.option("--whitelist", multiple=True, type=click.Path())
@click.option("--show-apps", is_flag=True, default=False)
@click.option("--profile", default=None, help="Config profile to use.")
@click.option("--dev-junk", is_flag=True, default=False,
              help="Scan developer junk (node_modules, venv, build dirs).")
@click.option("--dev-junk-global", is_flag=True, default=False,
              help="Include global caches (~/.npm, ~/.gradle, etc).")
@click.option("--dev-root", "dev_roots", multiple=True, type=click.Path(exists=True),
              help="Additional developer roots to scan for dev junk.")
@click.option("--root", "custom_roots", multiple=True, type=click.Path(exists=True),
              help="Additional directory to scan. Can be passed multiple times.")
@click.option("--notify", is_flag=True, default=False,
              help="Post macOS notification when scan completes.")
@click.option("--dry-run", is_flag=True, default=False,
              help="Explicit alias for scan (never deletes).")
@click.option("--save-history", is_flag=True, default=True,
              help="Save scan result to history (default: on).")
@click.option("--ci", is_flag=True, default=False,
              help="Emit machine-readable JSON summary and fail when over threshold.")
@click.option("--threshold-mb", default=0, show_default=True,
              help="CI threshold. Exit 1 when reclaimable junk exceeds this many MB.")
def scan(
    skip_junk: bool,
    export_path: Optional[str],
    whitelist: Tuple[str, ...],
    show_apps: bool,
    profile: Optional[str],
    dev_junk: bool,
    dev_junk_global: bool,
    dev_roots: Tuple[str, ...],
    custom_roots: Tuple[str, ...],
    notify: bool,
    dry_run: bool,
    save_history: bool,
    ci: bool,
    threshold_mb: int,
) -> None:
    """Scan for orphaned app leftovers and junk (preview only — safe).

    \b
    --dry-run is an explicit alias for scan behaviour.
    --profile developer|minimal|aggressive applies preset settings.
    """
    profile = _ensure_first_run_profile(profile=profile, ci=ci)
    cfg = load_config(profile=profile)

    # CLI whitelist overrides config whitelist
    wl = cfg.whitelist_set | {
        Path(p).expanduser().resolve() for p in whitelist
    }
    cfg.custom_scan_roots.extend(Path(p).expanduser().resolve() for p in custom_roots)
    cfg.dev_junk_roots.extend(Path(p).expanduser().resolve() for p in dev_roots)

    _run(
        delete=False,
        auto=False,
        skip_junk=skip_junk,
        export_path=export_path,
        whitelist_set=wl,
        show_apps=show_apps,
        profile=profile,
        notify=notify,
        save_history=save_history,
        cfg=cfg,
        dev_junk=dev_junk,
        dev_junk_global=dev_junk_global,
        ci=ci,
        threshold_mb=threshold_mb,
    )


# ══════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

@main.command("dashboard")
@click.option("--profile", default=None, help="Config profile to use.")
@click.option("--dev-junk", is_flag=True, default=False,
              help="Scan developer junk (node_modules, venv, build dirs).")
@click.option("--dev-junk-global", is_flag=True, default=False,
              help="Include global caches (~/.npm, ~/.gradle, etc).")
@click.option("--dev-root", "dev_roots", multiple=True, type=click.Path(exists=True),
              help="Additional developer roots to scan for dev junk.")
@click.option("--root", "custom_roots", multiple=True, type=click.Path(exists=True),
              help="Additional directory to scan. Can be passed multiple times.")
def cmd_dashboard(
    profile: Optional[str],
    dev_junk: bool,
    dev_junk_global: bool,
    dev_roots: Tuple[str, ...],
    custom_roots: Tuple[str, ...],
) -> None:
    """Run a live Rich dashboard scan."""
    from rich.align import Align
    from rich.layout import Layout
    from rich.live import Live

    cfg = load_config(profile=profile)
    cfg.custom_scan_roots.extend(Path(p).expanduser().resolve() for p in custom_roots)
    cfg.dev_junk_roots.extend(Path(p).expanduser().resolve() for p in dev_roots)
    cfg.scan_dev_junk = bool(cfg.scan_dev_junk or dev_junk)
    cfg.scan_dev_junk_global = bool(getattr(cfg, "scan_dev_junk_global", False) or dev_junk_global)
    whitelist_set = cfg.whitelist_set

    layout = Layout()
    layout.split_column(
        Layout(name="header", size=5),
        Layout(name="body"),
        Layout(name="footer", size=5),
    )
    layout["body"].split_row(Layout(name="left"), Layout(name="right"))

    state = {
        "apps": 0,
        "running": 0,
        "orphans": 0,
        "orphan_size": 0,
        "junk": 0,
        "junk_size": 0,
        "dev_junk": 0,
        "dev_junk_size": 0,
        "orphans_top": [],
        "junk_top": [],
        "dev_junk_top": [],
        "status": "Starting scan...",
    }

    def render() -> Layout:
        layout["header"].update(Panel(
            Align.center("[bold cyan]Mac Deep Cleaner Dashboard[/bold cyan]\n[dim]Live scan view[/dim]"),
            border_style="cyan",
        ))
        left = Table.grid(padding=(0, 2))
        left.add_column(style="bold")
        left.add_column(justify="right")
        left.add_row("Installed apps", str(state["apps"]))
        left.add_row("Running apps protected", str(state["running"]))
        left.add_row("Orphan groups", str(state["orphans"]))
        left.add_row("General junk items", str(state["junk"]))
        left.add_row("Dev junk items", str(state["dev_junk"]))
        layout["left"].update(Panel(left, title="Detection", border_style="cyan"))

        right = Table.grid(padding=(0, 1))
        right.add_column(style="bold")
        right.add_column(justify="right")
        total = state["orphan_size"] + state["junk_size"] + state["dev_junk_size"]
        right.add_row("Orphan data", bytes_human(state["orphan_size"]))
        right.add_row("General junk", bytes_human(state["junk_size"]))
        right.add_row("Dev junk", bytes_human(state["dev_junk_size"]))
        right.add_row("Total reclaimable", f"[yellow]{bytes_human(total)}[/yellow]")

        top = Table.grid(padding=(0, 1))
        top.add_column(style="bold")
        top.add_column(justify="right", style="yellow")
        if state["orphans_top"]:
            top.add_row("Top orphans", "")
            for name, sz in state["orphans_top"][:5]:
                top.add_row(f"  {name}", bytes_human(sz))
        else:
            top.add_row("Top orphans", "-")

        if state["junk_top"]:
            top.add_row("Top junk", "")
            for name, sz in state["junk_top"][:5]:
                top.add_row(f"  {name}", bytes_human(sz))
        else:
            top.add_row("Top junk", "-")

        if state["dev_junk_top"]:
            top.add_row("Top dev junk", "")
            for name, sz in state["dev_junk_top"][:5]:
                top.add_row(f"  {name}", bytes_human(sz))
        else:
            top.add_row("Top dev junk", "-")

        right_panel = Table.grid(padding=(0, 1))
        right_panel.add_row(Panel(right, title="Space", border_style="yellow"))
        right_panel.add_row(Panel(top, title="Top Findings", border_style="dim"))
        layout["right"].update(right_panel)
        layout["footer"].update(Panel(state["status"], border_style="dim"))
        return layout

    with Live(render(), console=console, refresh_per_second=8, screen=True):
        state["status"] = "Discovering installed applications..."
        apps = discover_installed_apps()
        state["apps"] = len(apps)

        state["status"] = "Checking running applications..."
        running_bids = running_bundle_ids()
        state["running"] = len(running_bids)

        state["status"] = "Detecting orphaned leftovers..."
        orphans = scan_orphans(
            apps,
            whitelist_set,
            running_bids,
            roots=cfg.custom_scan_roots,
            enabled=cfg.scan_orphans,
        )
        state["orphans"] = len(orphans)
        state["orphan_size"] = sum(sum(e.size for e in v) for v in orphans.values())
        state["orphans_top"] = [
            (name, sum(e.size for e in entries))
            for name, entries in sorted(
                orphans.items(),
                key=lambda kv: sum(e.size for e in kv[1]),
                reverse=True,
            )
        ]

        state["status"] = "Scanning caches, logs, and trash..."
        junk = scan_junk(
            whitelist_set,
            apps=apps,
            roots=cfg.custom_scan_roots,
            skip_categories=cfg.skip_categories,
            enabled=cfg.scan_junk,
        )
        user_junk = [j for j in junk if not j.is_system]
        state["junk"] = len(user_junk)
        state["junk_size"] = sum(j.size for j in user_junk)
        state["junk_top"] = [
            (j.path.name, j.size)
            for j in sorted(user_junk, key=lambda x: x.size, reverse=True)[:10]
        ]

        if cfg.scan_dev_junk:
            from scanners.dev_junk import find_dev_junk
            state["status"] = "Scanning developer modules..."
            dev_junk_entries = find_dev_junk(
                roots=cfg.dev_junk_roots or None,
                max_depth=cfg.dev_junk_max_depth,
                include_global=bool(getattr(cfg, "scan_dev_junk_global", False)),
            )
            if whitelist_set:
                dev_junk_entries = [
                    e for e in dev_junk_entries
                    if e.path not in whitelist_set and not any(wl in e.path.parents for wl in whitelist_set)
                ]
            state["dev_junk"] = len(dev_junk_entries)
            state["dev_junk_size"] = sum(e.size for e in dev_junk_entries)
            state["dev_junk_top"] = [
                (e.path.name, e.size)
                for e in sorted(dev_junk_entries, key=lambda x: x.size, reverse=True)[:10]
            ]
        state["status"] = "Scan complete. Use mac-cleaner scan for the full report."

    print_summary(
        orphan_total=state["orphan_size"],
        junk_total=state["junk_size"],
        dev_junk_total=state["dev_junk_size"],
        running_count=state["running"],
        whitelist_count=len(whitelist_set),
    )


# ══════════════════════════════════════════════════════════════════════════════
# CLEAN
# ══════════════════════════════════════════════════════════════════════════════

@main.command()
@click.option("--auto", is_flag=True, default=False)
@click.option("--skip-junk", is_flag=True, default=False)
@click.option("--whitelist", multiple=True, type=click.Path())
@click.option("--export", "export_path", type=click.Path(), default=None)
@click.option("--profile", default=None)
@click.option("--dev-junk", is_flag=True, default=False,
              help="Scan and clean developer junk (node_modules, venv, build dirs).")
@click.option("--dev-junk-global", is_flag=True, default=False,
              help="Include global caches (~/.npm, ~/.gradle, etc).")
@click.option("--dev-root", "dev_roots", multiple=True, type=click.Path(exists=True),
              help="Additional developer roots to scan for dev junk.")
@click.option("--root", "custom_roots", multiple=True, type=click.Path(exists=True),
              help="Additional directory to scan. Can be passed multiple times.")
@click.option("--notify", is_flag=True, default=False)
@click.option("--no-undo", is_flag=True, default=False,
              help="Permanently delete instead of staging for undo.")
@click.pass_context
def clean(
    ctx: click.Context,
    auto: bool,
    skip_junk: bool,
    whitelist: Tuple[str, ...],
    export_path: Optional[str],
    profile: Optional[str],
    dev_junk: bool,
    dev_junk_global: bool,
    dev_roots: Tuple[str, ...],
    custom_roots: Tuple[str, ...],
    notify: bool,
    no_undo: bool,
) -> None:
    """Interactively clean orphaned app leftovers and junk.

    \b
    By default, deleted files are staged in ~/.mac_cleaner_trash/
    and can be restored with: mac-cleaner undo
    Pass --no-undo to permanently delete (faster, no recovery).
    """
    from core.dry_run import dry_run_enabled
    profile = _ensure_first_run_profile(profile=profile, ci=False)
    cfg = load_config(profile=profile)
    wl = cfg.whitelist_set | {
        Path(p).expanduser().resolve() for p in whitelist
    }
    cfg.custom_scan_roots.extend(Path(p).expanduser().resolve() for p in custom_roots)
    cfg.dev_junk_roots.extend(Path(p).expanduser().resolve() for p in dev_roots)
    undo_mode = cfg.undo_mode and not no_undo
    dry_run = dry_run_enabled(ctx)
    if dry_run:
        console.print("[yellow]Dry-run enabled; clean will run in preview mode.[/yellow]")

    _run(
        delete=not dry_run,
        auto=auto,
        skip_junk=skip_junk,
        export_path=export_path,
        whitelist_set=wl,
        show_apps=False,
        profile=profile,
        notify=notify,
        save_history=True,
        cfg=cfg,
        undo_mode=undo_mode,
        dev_junk=dev_junk,
        dev_junk_global=dev_junk_global,
    )


# ══════════════════════════════════════════════════════════════════════════════
# INFO
# ══════════════════════════════════════════════════════════════════════════════

@main.command()
def info() -> None:
    """Show tool information and safety guarantees."""
    print_banner()
    console.print("[bold]Safety Guarantees:\n")
    guarantees = [
        ("System Protection", "com.apple.* files are NEVER deleted"),
        ("Running App Guard", "Files of currently-running apps are protected"),
        ("Group Container Validation", "Team IDs resolved against known vendor DB"),
        ("System Cache Isolation", "OS-owned caches require explicit flag"),
        ("Preview by Default", "'scan' never modifies the filesystem"),
        ("Undo / Restore", "Deletions staged in ~/.mac_cleaner_trash/ by default"),
        ("Audit Logging", f"All deletions logged to {LOG_FILE}"),
        ("Final Safety Gate", "Every path validated before deletion"),
    ]
    table = Table(show_header=True, header_style="bold cyan", border_style="dim")
    table.add_column("Feature", style="bold")
    table.add_column("Description")
    for feat, desc in guarantees:
        table.add_row(f"■ {feat}", desc)
    console.print(table)
    console.print()


# ══════════════════════════════════════════════════════════════════════════════
# COMPLETIONS
# ══════════════════════════════════════════════════════════════════════════════

@main.command("completions")
@click.option("--shell", default=None,
              type=click.Choice(["bash", "zsh", "fish"], case_sensitive=False),
              help="Shell type (bash, zsh, fish).")
@click.option("--instructions", is_flag=True, default=False,
              help="Show install instructions for your shell.")
def cmd_completions(shell: Optional[str], instructions: bool) -> None:
    """Generate shell completion scripts."""
    from core.completions import completion_script, detect_shell, install_instructions

    resolved_shell = (shell or detect_shell()).lower()
    script = completion_script(resolved_shell, "mac-cleaner", main)
    console.print(script)
    if instructions:
        console.print()
        console.print(install_instructions(resolved_shell, "mac-cleaner"))


# ══════════════════════════════════════════════════════════════════════════════
# UNINSTALL
# ══════════════════════════════════════════════════════════════════════════════

@main.command("uninstall")
@click.argument("app_query")
@click.option("--yes", is_flag=True, default=False,
              help="Skip confirmation and uninstall immediately.")
@click.option("--no-undo", is_flag=True, default=False,
              help="Permanently delete instead of staging for undo.")
@click.option("--keep-preferences", is_flag=True, default=False,
              help="Keep Preferences and Saved State data.")
@click.option("--force", is_flag=True, default=False,
              help="Allow uninstall even if the app appears to be running.")
@click.pass_context
def cmd_uninstall(
    ctx: click.Context,
    app_query: str,
    yes: bool,
    no_undo: bool,
    keep_preferences: bool,
    force: bool,
) -> None:
    """Remove an app and its data (full uninstall)."""
    from core.uninstaller import build_uninstall_plan, execute_uninstall, find_app_candidates
    from core.dry_run import dry_run_enabled

    apps = discover_installed_apps()
    matches = find_app_candidates(app_query, apps)

    if not matches:
        console.print(f"[yellow]No installed app matched '{app_query}'.[/yellow]")
        return

    app = matches[0]
    if len(matches) > 1:
        table = Table(show_header=True, header_style="bold cyan", border_style="dim")
        table.add_column("#", style="dim", width=4, justify="right")
        table.add_column("App")
        table.add_column("Bundle ID", style="dim")
        table.add_column("Path", style="dim")
        for i, a in enumerate(matches, 1):
            table.add_row(str(i), a.name, a.bundle_id, str(a.path))
        console.print(table)
        choice = click.prompt("Select app", type=click.IntRange(1, len(matches)))
        app = matches[choice - 1]

    running = running_bundle_ids()
    if app.bundle_id.lower() in running and not force:
        console.print(
            "[yellow]App appears to be running. Quit it or pass --force to continue.[/yellow]"
        )
        return

    cfg = load_config()
    plan = build_uninstall_plan(
        app=app,
        whitelist_set=cfg.whitelist_set,
        keep_preferences=keep_preferences,
    )

    if not plan.deletable_items and not plan.protected_items:
        console.print("[yellow]No removable data found for this app.[/yellow]")
        return

    console.print()
    console.print(Panel(
        f"[bold cyan]Uninstall Plan[/bold cyan]  [dim]{app.name}[/dim]",
        border_style="cyan", padding=(0, 2),
    ))

    table = Table(show_header=True, header_style="bold cyan", border_style="dim")
    table.add_column("#", style="dim", width=4, justify="right")
    table.add_column("Category", width=16)
    table.add_column("Size", justify="right", style="yellow", width=10)
    table.add_column("Path", style="dim")

    for i, item in enumerate(plan.deletable_items[:50], 1):
        table.add_row(str(i), item.category, bytes_human(item.size), str(item.path))

    console.print(table)
    if len(plan.deletable_items) > 50:
        console.print(f"  [dim]... {len(plan.deletable_items) - 50} more items omitted[/dim]")
    if plan.protected_items:
        console.print(
            f"  [dim]{len(plan.protected_items)} item(s) protected by safety checks[/dim]"
        )

    console.print(
        f"\n  Total removable: [yellow]{bytes_human(plan.total_size)}[/yellow]"
    )

    if dry_run_enabled(ctx):
        console.print("[yellow]Dry-run enabled; uninstall skipped.[/yellow]")
        return

    do_it = yes
    if not do_it:
        from rich.prompt import Confirm
        do_it = Confirm.ask("Proceed with uninstall?", default=False)
    if not do_it:
        return

    session = None
    if cfg.undo_mode and not no_undo:
        session = new_session()

    result = execute_uninstall(plan, session=session)

    if session and result.staged > 0:
        session.save()
        console.print(
            f"\n  [green]Staged {bytes_human(result.bytes_freed)} for undo[/green]"
        )
        console.print(
            f"  [dim]Restore with: mac-cleaner undo --session {session.session_id[:8]}[/dim]"
        )
    else:
        console.print(
            f"\n  [green]Removed {bytes_human(result.bytes_freed)}[/green]"
        )


# ══════════════════════════════════════════════════════════════════════════════
# BROWSER DATA CLEANER
# ══════════════════════════════════════════════════════════════════════════════

@main.command("browser-data")
@click.option("--browser", "browsers", multiple=True,
              type=click.Choice(["safari", "chrome", "firefox", "edge", "brave"],
                                case_sensitive=False),
              help="Limit to specific browsers.")
@click.option("--category", "categories", multiple=True,
              type=click.Choice(["cache", "cookies", "history", "downloads", "site-data", "sessions"],
                                case_sensitive=False),
              help="Limit to specific data categories.")
@click.option("--clean", is_flag=True, default=False,
              help="Delete selected data (requires --category or --all).")
@click.option("--all", "clean_all", is_flag=True, default=False,
              help="Delete all supported categories for selected browsers.")
@click.option("--yes", is_flag=True, default=False,
              help="Skip confirmation for deletions.")
@click.pass_context
def cmd_browser_data(
    ctx: click.Context,
    browsers: Tuple[str, ...],
    categories: Tuple[str, ...],
    clean: bool,
    clean_all: bool,
    yes: bool,
) -> None:
    """Analyze and optionally clean browser data."""
    from scanners.browser_data import (
        collect_browser_data,
        delete_browser_data,
        summarize_browser_data,
    )
    from core.dry_run import dry_run_enabled

    items = collect_browser_data(browsers=list(browsers) or None)
    if not items:
        console.print("[green]No browser data found.[/green]")
        return

    summary = summarize_browser_data(items)
    table = Table(show_header=True, header_style="bold cyan", border_style="dim")
    table.add_column("Browser", width=14)
    table.add_column("Category", width=14)
    table.add_column("Items", justify="right", width=7)
    table.add_column("Size", justify="right", style="yellow", width=12)

    for row in summary:
        table.add_row(row[0], row[1], str(row[2]), bytes_human(row[3]))

    console.print()
    console.print(Panel("[bold cyan]Browser Data Summary[/bold cyan]",
                        border_style="cyan", padding=(0, 2)))
    console.print(table)

    if not (clean or clean_all):
        return

    if dry_run_enabled(ctx):
        console.print("[yellow]Dry-run enabled; browser data cleanup skipped.[/yellow]")
        return

    target_categories = [c.lower() for c in categories]
    if not clean_all and not target_categories:
        console.print("[yellow]Specify --category or use --all to clean.[/yellow]")
        return

    if clean_all:
        target_categories = []  # empty means all in delete_browser_data

    if not yes:
        from rich.prompt import Confirm
        if not Confirm.ask("Proceed with browser data deletion?", default=False):
            return

    result = delete_browser_data(items, categories=target_categories)
    console.print(
        f"\n  [green]Deleted {result.deleted} item(s), freed {bytes_human(result.bytes_freed)}[/green]"
    )
    if result.skipped:
        console.print(f"  [dim]{result.skipped} item(s) skipped by safety checks[/dim]")


# ══════════════════════════════════════════════════════════════════════════════
# SPACE MAP
# ══════════════════════════════════════════════════════════════════════════════

@main.command("space-map")
@click.option("--root", "roots", multiple=True, type=click.Path(exists=True),
              help="Root directories to map (default: HOME).")
@click.option("--depth", default=2, show_default=True,
              help="Folder depth to include.")
@click.option("--limit", default=12, show_default=True,
              help="Maximum child entries shown per directory.")
@click.option("--min-mb", default=1, show_default=True,
              help="Minimum size per entry (MB).")
@click.option("--export", "export_path", type=click.Path(), default=None,
              help="Export map to JSON.")
def cmd_space_map(
    roots: Tuple[str, ...],
    depth: int,
    limit: int,
    min_mb: int,
    export_path: Optional[str],
) -> None:
    """Visual disk space map."""
    from scanners.space_map import build_usage_tree, render_usage_tree
    from constants import HOME

    min_bytes = min_mb * 1024 * 1024
    root_paths = [Path(p).expanduser().resolve() for p in roots] or [HOME]

    trees = []
    for root in root_paths:
        node = build_usage_tree(root, max_depth=depth, min_size=min_bytes)
        trees.append(node)
        console.print()
        console.print(Panel(
            f"[bold cyan]Space Map[/bold cyan]  [dim]{root}[/dim]",
            border_style="cyan", padding=(0, 2),
        ))
        console.print(render_usage_tree(node, limit=limit))

    if export_path:
        import json
        data = [t.to_dict() for t in trees]
        with open(export_path, "w") as f:
            json.dump(data, f, indent=2, default=str)
        console.print(f"\n  [green]Exported to {export_path}[/green]")


# ══════════════════════════════════════════════════════════════════════════════
# PHOTOS ANALYZER
# ══════════════════════════════════════════════════════════════════════════════

@main.command("photos")
@click.option("--root", "roots", multiple=True, type=click.Path(exists=True),
              help="Search roots for Photos libraries (default: ~/Pictures).")
@click.option("--details", is_flag=True, default=False,
              help="Show file type breakdown for originals.")
@click.option("--export", "export_path", type=click.Path(), default=None,
              help="Export analysis to JSON.")
def cmd_photos(
    roots: Tuple[str, ...],
    details: bool,
    export_path: Optional[str],
) -> None:
    """Analyze Photos libraries and storage usage."""
    from scanners.photos_analyzer import analyze_photo_library, find_photo_libraries
    from constants import HOME

    search_roots = [Path(p).expanduser().resolve() for p in roots] or [HOME / "Pictures"]
    libs = find_photo_libraries(search_roots=search_roots)
    if not libs:
        console.print("[yellow]No Photos libraries found in the selected roots.[/yellow]")
        return

    reports = [analyze_photo_library(p) for p in libs]

    console.print()
    console.print(Panel("[bold cyan]Photos Library Analysis[/bold cyan]",
                        border_style="cyan", padding=(0, 2)))

    table = Table(show_header=True, header_style="bold cyan", border_style="dim")
    table.add_column("Library", min_width=22)
    table.add_column("Total", justify="right", style="yellow", width=10)
    table.add_column("Originals", justify="right", width=10)
    table.add_column("Previews", justify="right", width=10)
    table.add_column("Database", justify="right", width=10)
    table.add_column("Originals Count", justify="right", width=16)

    for r in reports:
        table.add_row(
            r.name,
            bytes_human(r.size),
            bytes_human(r.originals_size),
            bytes_human(r.previews_size),
            bytes_human(r.database_size),
            str(r.originals_count),
        )

    console.print(table)

    if details:
        for r in reports:
            console.print(f"\n  [bold]{r.name}[/bold]")
            for ext, count, size in r.top_extensions(8):
                console.print(f"    {ext:>6}  {count:>6} files  {bytes_human(size)}")

    if export_path:
        import json
        with open(export_path, "w") as f:
            json.dump([r.to_dict() for r in reports], f, indent=2, default=str)
        console.print(f"\n  [green]Exported to {export_path}[/green]")


# ══════════════════════════════════════════════════════════════════════════════
# SIMULATOR CLEANER
# ══════════════════════════════════════════════════════════════════════════════

@main.command("simulators")
@click.option("--purge-unavailable", is_flag=True, default=False,
              help="Delete data for unavailable simulators only.")
@click.option("--purge-all", is_flag=True, default=False,
              help="Delete data for all simulators (destructive).")
@click.option("--purge-caches", is_flag=True, default=False,
              help="Delete CoreSimulator caches and logs.")
@click.option("--yes", is_flag=True, default=False,
              help="Skip confirmation prompts.")
@click.pass_context
def cmd_simulators(
    ctx: click.Context,
    purge_unavailable: bool,
    purge_all: bool,
    purge_caches: bool,
    yes: bool,
) -> None:
    """Inspect and clean iOS Simulator data."""
    from scanners.simulators import (
        find_simulator_caches,
        find_simulator_devices,
        purge_simulator_caches,
        purge_simulator_devices,
    )
    from core.dry_run import dry_run_enabled

    devices = find_simulator_devices()
    caches = find_simulator_caches()

    console.print()
    console.print(Panel("[bold cyan]iOS Simulator Data[/bold cyan]",
                        border_style="cyan", padding=(0, 2)))

    if devices:
        table = Table(show_header=True, header_style="bold cyan", border_style="dim")
        table.add_column("Name", min_width=20)
        table.add_column("Runtime", width=18)
        table.add_column("State", width=12)
        table.add_column("Available", width=10)
        table.add_column("Size", justify="right", style="yellow", width=10)
        for d in devices:
            table.add_row(d.name, d.runtime, d.state, "yes" if d.is_available else "no", bytes_human(d.size))
        console.print(table)
    else:
        console.print("  [dim]No simulator devices found.[/dim]")

    if caches:
        cache_total = sum(c.size for c in caches)
        console.print(f"\n  Caches: {bytes_human(cache_total)}")
        for c in caches:
            console.print(f"    {c.category}: {bytes_human(c.size)}")

    if not (purge_unavailable or purge_all or purge_caches):
        return

    if dry_run_enabled(ctx):
        console.print("[yellow]Dry-run enabled; simulator cleanup skipped.[/yellow]")
        return

    if purge_unavailable or purge_all:
        targets = devices if purge_all else [d for d in devices if not d.is_available]
        if targets:
            if not yes:
                from rich.prompt import Confirm
                if not Confirm.ask(
                    f"Delete simulator data for {len(targets)} device(s)?",
                    default=False,
                ):
                    targets = []
            if targets:
                result = purge_simulator_devices(targets)
                console.print(
                    f"\n  [green]Deleted {result.deleted} device(s), freed {bytes_human(result.bytes_freed)}[/green]"
                )
        else:
            console.print("  [dim]No devices matched purge criteria.[/dim]")

    if purge_caches and caches:
        if yes:
            proceed = True
        else:
            from rich.prompt import Confirm
            proceed = Confirm.ask("Delete CoreSimulator caches?", default=False)
        if proceed:
            result = purge_simulator_caches(caches)
            console.print(
                f"  [green]Deleted {result.deleted} cache item(s), freed {bytes_human(result.bytes_freed)}[/green]"
            )

# ══════════════════════════════════════════════════════════════════════════════
# DUPLICATES
# ══════════════════════════════════════════════════════════════════════════════

@main.command("duplicates")
@click.option("--path", "paths", multiple=True, type=click.Path(exists=True),
              help="Directories to scan (default: ~/Downloads, ~/Documents, ~/Desktop, ~/Pictures).")
@click.option("--min-size", default=100, show_default=True,
              help="Minimum file size in KB to consider.")
@click.option("--export", "export_path", type=click.Path(), default=None,
              help="Export results to JSON.")
@click.option("--delete", is_flag=True, default=False,
              help="Interactively delete duplicates (keeps the first copy).")
@click.pass_context
def cmd_duplicates(
    ctx: click.Context,
    paths: Tuple[str, ...],
    min_size: int,
    export_path: Optional[str],
    delete: bool,
) -> None:
    """Find duplicate files by content hash.

    \b
    Scans for byte-identical files wasting space.
    Only user directories are scanned — never /System.
    """
    from scanners.duplicates import find_duplicates, total_wasted, DEFAULT_SCAN_ROOTS

    roots = [Path(p).expanduser().resolve() for p in paths] or None
    min_bytes = min_size * 1024

    console.print()
    console.print(Panel(
        "[bold cyan]Duplicate File Finder[/bold cyan]",
        border_style="cyan", padding=(0, 2),
    ))

    scanned_count = [0]
    def _cb(n: int) -> None:
        scanned_count[0] = n

    with _progress() as prog:
        task = prog.add_task(f"Scanning for duplicates (min {min_size} KB)…", total=None)
        groups = find_duplicates(roots=roots, min_size=min_bytes, progress_callback=_cb)
        prog.update(task, completed=100, total=100)

    if not groups:
        console.print("[green]✓ No duplicate files found![/green]")
        return

    wasted = total_wasted(groups)
    console.print(
        f"  Found [bold red]{len(groups)}[/bold red] duplicate groups "
        f"wasting [yellow]{bytes_human(wasted)}[/yellow]\n"
    )

    table = Table(
        title="Duplicate Groups",
        show_header=True, header_style="bold cyan",
        border_style="dim", title_style="bold",
    )
    table.add_column("#", style="dim", width=4, justify="right")
    table.add_column("Copies", justify="right", width=7)
    table.add_column("Wasted", justify="right", style="yellow", width=10)
    table.add_column("Size Each", justify="right", style="dim", width=10)
    table.add_column("First Path", style="dim")

    for i, g in enumerate(groups[:50], 1):
        table.add_row(
            str(i),
            str(len(g.paths)),
            bytes_human(g.wasted_bytes),
            bytes_human(g.size),
            str(g.paths[0]),
        )

    console.print(table)

    if export_path:
        import json
        data = {
            "generated_at": __import__("datetime").datetime.now().isoformat(),
            "total_wasted_bytes": wasted,
            "total_wasted_human": bytes_human(wasted),
            "groups": [g.to_dict() for g in groups],
        }
        with open(export_path, "w") as f:
            json.dump(data, f, indent=2, default=str)
        console.print(f"\n  [green]✓ Exported to {export_path}[/green]")

    if delete:
        from core.dry_run import skip_if_dry_run
        if skip_if_dry_run(ctx, console, "duplicate deletions"):
            return
        from rich.prompt import Confirm
        console.print()
        for g in groups:
            total_g = bytes_human(g.wasted_bytes)
            console.print(f"  [bold]Duplicates of:[/bold] {g.paths[0].name} ({total_g} wasted)")
            for extra in g.paths[1:]:
                console.print(f"    [dim]{extra}[/dim]")
            if Confirm.ask(f"  Delete {len(g.paths)-1} extra copy/copies?", default=False):
                for extra in g.paths[1:]:
                    try:
                        extra.unlink()
                        console.print(f"  [green]✓ Deleted[/green] {extra.name}")
                    except OSError as e:
                        console.print(f"  [yellow]⚠ Failed[/yellow] {extra.name}: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# LARGE FILES
# ══════════════════════════════════════════════════════════════════════════════

@main.command("large-files")
@click.option("--path", "paths", multiple=True, type=click.Path(exists=True))
@click.option("--min-mb", default=100, show_default=True,
              help="Minimum file size in MB (default: 100).")
@click.option("--limit", default=100, show_default=True,
              help="Maximum results to show.")
@click.option("--export", "export_path", type=click.Path(), default=None)
def cmd_large_files(
    paths: Tuple[str, ...],
    min_mb: int,
    limit: int,
    export_path: Optional[str],
) -> None:
    """Find large files (default ≥100 MB) anywhere on disk, sorted by size."""
    from scanners.large_files import find_large_files, group_by_category

    roots = [Path(p).expanduser().resolve() for p in paths] or None
    min_bytes = min_mb * 1024 * 1024

    console.print()
    console.print(Panel(
        "[bold cyan]Large File Scanner[/bold cyan]",
        border_style="cyan", padding=(0, 2),
    ))

    with _progress() as prog:
        task = prog.add_task(f"Scanning for files ≥{min_mb} MB…", total=None)
        entries = find_large_files(roots=roots, min_bytes=min_bytes, limit=limit)
        prog.update(task, completed=100, total=100)

    if not entries:
        console.print(f"[green]✓ No files larger than {min_mb} MB found.[/green]")
        return

    total_bytes = sum(e.size for e in entries)
    console.print(
        f"  Found [bold]{len(entries)}[/bold] large file(s) "
        f"totalling [yellow]{bytes_human(total_bytes)}[/yellow]\n"
    )

    table = Table(
        title=f"Large Files (≥{min_mb} MB)",
        show_header=True, header_style="bold cyan",
        border_style="dim", padding=(0, 1),
    )
    table.add_column("#", style="dim", width=5, justify="right")
    table.add_column("Size", justify="right", style="yellow", width=10)
    table.add_column("Category", style="cyan", width=14)
    table.add_column("Path", style="dim")

    for i, e in enumerate(entries, 1):
        table.add_row(str(i), e.size_human, e.category, str(e.path))

    console.print(table)

    if export_path:
        import json
        data = {
            "generated_at": __import__("datetime").datetime.now().isoformat(),
            "min_mb": min_mb,
            "total_bytes": total_bytes,
            "total_human": bytes_human(total_bytes),
            "files": [e.to_dict() for e in entries],
        }
        with open(export_path, "w") as f:
            json.dump(data, f, indent=2, default=str)
        console.print(f"\n  [green]✓ Exported to {export_path}[/green]")


# ══════════════════════════════════════════════════════════════════════════════
# SYMLINKS
# ══════════════════════════════════════════════════════════════════════════════

@main.command("symlinks")
@click.option("--path", "paths", multiple=True, type=click.Path())
@click.option("--delete", is_flag=True, default=False,
              help="Delete broken symlinks after confirmation.")
@click.pass_context
def cmd_symlinks(ctx: click.Context, paths: Tuple[str, ...], delete: bool) -> None:
    """Find broken (dangling) symbolic links in developer directories."""
    from scanners.symlinks import find_broken_symlinks, DEFAULT_ROOTS

    roots = [Path(p).expanduser() for p in paths] or None

    console.print()
    console.print(Panel(
        "[bold cyan]Broken Symlink Detector[/bold cyan]",
        border_style="cyan", padding=(0, 2),
    ))

    with _progress() as prog:
        task = prog.add_task("Scanning for broken symlinks…", total=None)
        broken = find_broken_symlinks(roots=roots)
        prog.update(task, completed=100, total=100)

    if not broken:
        console.print("[green]✓ No broken symlinks found![/green]")
        return

    console.print(f"  Found [bold red]{len(broken)}[/bold red] broken symlink(s)\n")

    table = Table(
        show_header=True, header_style="bold cyan", border_style="dim",
    )
    table.add_column("Location", style="cyan", width=20)
    table.add_column("Symlink", style="dim")
    table.add_column("→ Target (missing)", style="red")

    for s in broken:
        table.add_row(s.location, str(s.path), s.target)

    console.print(table)

    if delete:
        from core.dry_run import skip_if_dry_run
        if skip_if_dry_run(ctx, console, "symlink deletions"):
            return
        from rich.prompt import Confirm
        if Confirm.ask(f"\n  Delete all {len(broken)} broken symlinks?", default=False):
            deleted = 0
            for s in broken:
                try:
                    s.path.unlink()
                    deleted += 1
                except OSError as e:
                    console.print(f"  [yellow]⚠ Failed[/yellow] {s.path}: {e}")
            console.print(f"  [green]✓ Deleted {deleted} broken symlink(s)[/green]")


# ══════════════════════════════════════════════════════════════════════════════
# EXTRAS (iOS backups + language packs)
# ══════════════════════════════════════════════════════════════════════════════

@main.command("extras")
@click.option("--ios-backups", is_flag=True, default=False,
              help="Scan for old iOS/iPhone backups.")
@click.option("--language-packs", is_flag=True, default=False,
              help="Scan for removable language packs in /Applications.")
@click.option("--all", "all_extras", is_flag=True, default=False,
              help="Run all extra scans.")
@click.option("--delete-backups", is_flag=True, default=False,
              help="Interactively delete old iOS backups.")
@click.option("--strip-languages", is_flag=True, default=False,
              help="Interactively strip unused language packs.")
@click.pass_context
def cmd_extras(
    ctx: click.Context,
    ios_backups: bool,
    language_packs: bool,
    all_extras: bool,
    delete_backups: bool,
    strip_languages: bool,
) -> None:
    """Scan for iOS backups and removable language packs.

    \b
    Examples:
      mac-cleaner extras --all
      mac-cleaner extras --ios-backups --delete-backups
      mac-cleaner extras --language-packs --strip-languages
    """
    from core.dry_run import dry_run_enabled
    from scanners.extras import find_ios_backups, find_language_packs

    dry_run = dry_run_enabled(ctx)
    if dry_run and (delete_backups or strip_languages):
        console.print("[yellow]Dry-run enabled; delete actions are skipped.[/yellow]")

    do_ios = ios_backups or all_extras
    do_lang = language_packs or all_extras

    if not do_ios and not do_lang:
        console.print("[yellow]Specify --ios-backups, --language-packs, or --all[/yellow]")
        raise click.Abort()

    console.print()
    console.print(Panel("[bold cyan]Extras Scanner[/bold cyan]",
                        border_style="cyan", padding=(0, 2)))

    # ── iOS backups ──────────────────────────────────────────────────────
    if do_ios:
        with _progress() as prog:
            task = prog.add_task("Scanning for iOS backups…", total=None)
            backups = find_ios_backups()
            prog.update(task, completed=100, total=100)

        if not backups:
            console.print("  [green]✓ No iOS backups found.[/green]")
        else:
            total = sum(b.size for b in backups)
            console.print(
                f"  Found [bold]{len(backups)}[/bold] iOS backup(s) "
                f"using [yellow]{bytes_human(total)}[/yellow]\n"
            )
            table = Table(show_header=True, header_style="bold cyan", border_style="dim")
            table.add_column("Device", min_width=20)
            table.add_column("iOS", width=10)
            table.add_column("Age", width=10)
            table.add_column("Size", justify="right", style="yellow", width=10)
            table.add_column("Path", style="dim")
            for b in backups:
                age = f"{b.age_days}d" if b.age_days else "?"
                table.add_row(b.device_name, b.ios_version, age, b.size_human, str(b.path))
            console.print(table)

            if delete_backups and not dry_run:
                from rich.prompt import Confirm
                console.print()
                for b in backups:
                    if Confirm.ask(
                        f"  Delete backup of [bold]{b.device_name}[/bold] "
                        f"({b.size_human}, {b.age_days}d old)?",
                        default=False,
                    ):
                        from utils import safe_remove
                        ok, freed = safe_remove(b.path)
                        if ok:
                            console.print(f"  [green]✓ Deleted[/green] — freed {bytes_human(freed)}")
                        else:
                            console.print(f"  [yellow]⚠ Failed[/yellow]")

    # ── Language packs ───────────────────────────────────────────────────
    if do_lang:
        with _progress() as prog:
            task = prog.add_task("Scanning language packs…", total=None)
            lang_entries = find_language_packs()
            prog.update(task, completed=100, total=100)

        if not lang_entries:
            console.print("  [green]✓ No removable language packs found.[/green]")
        else:
            total = sum(e.removable_size for e in lang_entries)
            console.print(
                f"\n  Found language packs saving [yellow]{bytes_human(total)}[/yellow] "
                f"across [bold]{len(lang_entries)}[/bold] app(s)\n"
            )
            table = Table(show_header=True, header_style="bold cyan", border_style="dim")
            table.add_column("App", min_width=22)
            table.add_column("Removable", justify="right", width=8)
            table.add_column("Saves", justify="right", style="yellow", width=10)
            for e in lang_entries[:30]:
                table.add_row(e.app_name, str(len(e.removable_lprojs)), e.removable_size_human)
            console.print(table)

            if strip_languages and not dry_run:
                from rich.prompt import Confirm
                console.print()
                for e in lang_entries:
                    if Confirm.ask(
                        f"  Strip {len(e.removable_lprojs)} language(s) from "
                        f"[bold]{e.app_name}[/bold] (saves {e.removable_size_human})?",
                        default=False,
                    ):
                        removed = 0
                        for lproj in e.removable_lprojs:
                            from utils import safe_remove
                            ok, _ = safe_remove(lproj)
                            if ok:
                                removed += 1
                        console.print(f"  [green]✓ Removed {removed} lproj(s)[/green]")


# ══════════════════════════════════════════════════════════════════════════════
# BINARY THINNER
# ══════════════════════════════════════════════════════════════════════════════

@main.command("binary")
@click.option("--path", "paths", multiple=True, type=click.Path(exists=True))
@click.option("--arch", default=None,
              help="Target arch: arm64 or x86_64. Defaults to current CPU.")
@click.option("--thin", is_flag=True, default=False,
              help="Interactively thin fat binaries.")
@click.option("--no-backup", is_flag=True, default=False,
              help="Skip .fat_backup copy (irreversible!).")
@click.pass_context
def cmd_binary(
    ctx: click.Context,
    paths: Tuple[str, ...],
    arch: Optional[str],
    thin: bool,
    no_backup: bool,
) -> None:
    """Detect universal (fat) binaries and optionally thin them.

    \b
    Universal binaries contain both arm64 and x86_64 slices.
    Thinning keeps only the slice matching your CPU, saving space.
    Uses `ditto --arch` — the Apple-recommended method.
    """
    from scanners.binary_thinner import (
        find_fat_binaries, thin_binary, current_architecture,
    )

    current_arch = arch or current_architecture()
    roots = [Path(p).expanduser().resolve() for p in paths] or None

    console.print()
    console.print(Panel(
        f"[bold cyan]Universal Binary Scanner[/bold cyan]  "
        f"[dim](current arch: {current_arch})[/dim]",
        border_style="cyan", padding=(0, 2),
    ))

    with _progress() as prog:
        task = prog.add_task("Scanning for fat binaries…", total=None)
        fat_bins = find_fat_binaries(roots=roots)
        prog.update(task, completed=100, total=100)

    if not fat_bins:
        console.print("[green]✓ No universal binaries found in scanned paths.[/green]")
        return

    total_saving = sum(b.estimated_saving() for b in fat_bins)
    console.print(
        f"  Found [bold]{len(fat_bins)}[/bold] universal binary/ies — "
        f"estimated saving: [yellow]{bytes_human(total_saving)}[/yellow]\n"
    )

    table = Table(show_header=True, header_style="bold cyan", border_style="dim")
    table.add_column("#", style="dim", width=4, justify="right")
    table.add_column("Size", justify="right", style="yellow", width=10)
    table.add_column("Est. Saving", justify="right", style="dim", width=12)
    table.add_column("Path", style="dim")
    for i, b in enumerate(fat_bins, 1):
        table.add_row(str(i), b.size_human, bytes_human(b.estimated_saving()), str(b.path))
    console.print(table)

    if thin:
        from core.dry_run import skip_if_dry_run
        if skip_if_dry_run(ctx, console, "binary thinning"):
            return
        from rich.prompt import Confirm
        keep_backup = not no_backup
        freed = 0
        console.print()
        for b in fat_bins:
            if Confirm.ask(
                f"  Thin [bold]{b.path.name}[/bold] to {current_arch} "
                f"(saves ~{bytes_human(b.estimated_saving())})?",
                default=False,
            ):
                result = thin_binary(b, arch=current_arch, keep_backup=keep_backup)
                if result.success:
                    freed += result.bytes_freed
                    console.print(
                        f"  [green]✓ Thinned[/green] — freed {bytes_human(result.bytes_freed)}"
                    )
                else:
                    console.print(f"  [yellow]⚠ Failed:[/yellow] {result.error}")

        if freed:
            console.print(f"\n  [bold green]Total freed: {bytes_human(freed)}[/bold green]")


# ══════════════════════════════════════════════════════════════════════════════
# UNDO
# ══════════════════════════════════════════════════════════════════════════════

@main.command("undo")
@click.option("--list", "list_only", is_flag=True, default=False,
              help="List available sessions without restoring.")
@click.option("--session", "session_id", default=None,
              help="Session ID prefix to restore (default: latest).")
@click.option("--purge", is_flag=True, default=False,
              help="Permanently purge old staged files beyond retention period.")
@click.option("--purge-all", "purge_all", is_flag=True, default=False,
              help="Permanently purge ALL staged sessions regardless of age.")
@click.pass_context
def cmd_undo(
    ctx: click.Context,
    list_only: bool,
    session_id: Optional[str],
    purge: bool,
    purge_all: bool,
) -> None:
    """Restore files from the staging area (undo a clean operation).

    \b
    Files are staged in ~/.mac_cleaner_trash/ during clean.
    Sessions older than 30 days are purged automatically.
    """
    from core.dry_run import dry_run_enabled
    from core.undo import list_sessions, restore_session, purge_old_sessions, purge_all_sessions

    dry_run = dry_run_enabled(ctx)
    if dry_run and (purge or purge_all or not list_only):
        console.print("[yellow]Dry-run enabled; restore and purge actions are skipped.[/yellow]")
        purge = False
        purge_all = False
        list_only = True

    sessions = list_sessions()

    if purge_all:
        from rich.prompt import Confirm
        total = len(sessions)
        if total == 0:
            console.print("  [dim]No staged sessions found. Nothing to purge.[/dim]")
            return
        if Confirm.ask(
            f"  Delete all [bold red]{total}[/bold red] backed-up session(s) "
            f"permanently? This cannot be undone.",
            default=False,
        ):
            purged = purge_all_sessions()
            console.print(f"  [green]✓ Purged all {purged} session(s) permanently[/green]")
        return

    if purge:
        purged = purge_old_sessions()
        console.print(f"  [green]✓ Purged {purged} old session(s)[/green]")
        return

    console.print()
    console.print(Panel("[bold cyan]Undo — Staged Deletions[/bold cyan]",
                        border_style="cyan", padding=(0, 2)))

    if not sessions:
        console.print("  [dim]No staged sessions found. Nothing to restore.[/dim]")
        return

    table = Table(show_header=True, header_style="bold cyan", border_style="dim")
    table.add_column("#", style="dim", width=4, justify="right")
    table.add_column("Session ID", style="dim", width=12)
    table.add_column("Date", width=20)
    table.add_column("Files", justify="right", width=7)
    table.add_column("Size", justify="right", style="yellow", width=10)

    for i, s in enumerate(sessions, 1):
        table.add_row(
            str(i),
            s.session_id[:8],
            s.created_at[:19],
            str(len(s.files)),
            s.total_size_human,
        )

    console.print(table)

    if list_only:
        return

    # Find session to restore
    target = None
    if session_id:
        for s in sessions:
            if s.session_id.startswith(session_id):
                target = s
                break
        if not target:
            console.print(f"  [red]Session {session_id!r} not found.[/red]")
            return
    else:
        target = sessions[0]  # latest

    from rich.prompt import Confirm
    if Confirm.ask(
        f"\n  Restore session [bold]{target.session_id[:8]}[/bold] "
        f"({len(target.files)} files, {target.total_size_human})?",
        default=False,
    ):
        result = restore_session(target)
        console.print(
            f"\n  [green]✓ Restored {result.restored} file(s) "
            f"({bytes_human(result.bytes_restored)})[/green]"
        )
        if result.failed:
            console.print(f"  [yellow]⚠ {result.failed} file(s) could not be restored[/yellow]")
        for err in result.errors:
            console.print(f"    [dim]{err}[/dim]")


# ══════════════════════════════════════════════════════════════════════════════
# HISTORY
# ══════════════════════════════════════════════════════════════════════════════

@main.command("history")
@click.option("--limit", default=10, show_default=True)
def cmd_history(limit: int) -> None:
    """Show past scan records stored in ~/.config/mac-cleaner/history/."""
    from config.history import list_history

    records = list_history(limit=limit)

    console.print()
    console.print(Panel("[bold cyan]Scan History[/bold cyan]",
                        border_style="cyan", padding=(0, 2)))

    if not records:
        console.print("  [dim]No scan history yet. Run 'mac-cleaner scan' first.[/dim]")
        return

    table = Table(show_header=True, header_style="bold cyan", border_style="dim")
    table.add_column("#", style="dim", width=4, justify="right")
    table.add_column("Date", width=20)
    table.add_column("Profile", width=12)
    table.add_column("Orphans", justify="right", width=9)
    table.add_column("Junk", justify="right", width=9)
    table.add_column("Total", justify="right", style="yellow", width=10)

    for i, r in enumerate(records, 1):
        table.add_row(
            str(i),
            r.scanned_at.strftime("%Y-%m-%d %H:%M"),
            r.profile or "default",
            bytes_human(r.orphan_bytes),
            bytes_human(r.junk_bytes),
            bytes_human(r.total_bytes),
        )

    console.print(table)


# ══════════════════════════════════════════════════════════════════════════════
# DIFF
# ══════════════════════════════════════════════════════════════════════════════

@main.command("diff")
@click.argument("scan_a", required=False)
@click.argument("scan_b", required=False)
def cmd_diff(scan_a: Optional[str], scan_b: Optional[str]) -> None:
    """Compare two scan records.

    \b
    SCAN_A and SCAN_B are scan ID prefixes from 'mac-cleaner history'.
    If omitted, compares the two most recent scans.
    """
    from config.history import list_history, diff_scans

    records = list_history(limit=50)
    if len(records) < 2:
        console.print("[yellow]Need at least 2 scan records to diff.[/yellow]")
        return

    def _find(prefix: str):
        for r in records:
            if r.scan_id.startswith(prefix):
                return r
        return None

    if scan_a and scan_b:
        older = _find(scan_a)
        newer = _find(scan_b)
    else:
        newer, older = records[0], records[1]

    if not older or not newer:
        console.print("[red]Could not find requested scans.[/red]")
        return

    diff = diff_scans(older=older, newer=newer)

    console.print()
    console.print(Panel(
        f"[bold]Diff:[/bold]  {older.scanned_at:%Y-%m-%d %H:%M}  →  {newer.scanned_at:%Y-%m-%d %H:%M}",
        border_style="cyan", padding=(0, 2),
    ))

    delta = diff.size_delta_bytes
    sign = "+" if delta > 0 else ""
    color = "red" if delta > 0 else "green"
    console.print(f"\n  Size delta: [{color}]{sign}{bytes_human(abs(delta))}[/{color}]")

    if diff.new_orphans:
        console.print(f"\n  [red]New orphans ({len(diff.new_orphans)}):[/red]")
        for name in diff.new_orphans:
            console.print(f"    [dim]+[/dim] {name}")

    if diff.resolved_orphans:
        console.print(f"\n  [green]Resolved orphans ({len(diff.resolved_orphans)}):[/green]")
        for name in diff.resolved_orphans:
            console.print(f"    [dim]−[/dim] {name}")

    if diff.persistent_orphans:
        console.print(f"\n  [yellow]Still present ({len(diff.persistent_orphans)}):[/yellow]")
        for name in diff.persistent_orphans[:10]:
            console.print(f"    [dim]·[/dim] {name}")
        if len(diff.persistent_orphans) > 10:
            console.print(f"    [dim]… and {len(diff.persistent_orphans)-10} more[/dim]")

    console.print()


# ══════════════════════════════════════════════════════════════════════════════
# SYSTEM (launch items + SIP + login items)
# ══════════════════════════════════════════════════════════════════════════════

@main.command("system")
@click.option("--launch-items", is_flag=True, default=False)
@click.option("--login-items", is_flag=True, default=False)
@click.option("--health", is_flag=True, default=False)
@click.option("--all", "all_checks", is_flag=True, default=False)
def cmd_system(
    launch_items: bool,
    login_items: bool,
    health: bool,
    all_checks: bool,
) -> None:
    """Inspect startup items, login items, and system security health.

    \b
    mac-cleaner system --all
    mac-cleaner system --launch-items
    mac-cleaner system --health
    """
    from core.system_inspector import (
        list_launch_items, list_login_items, check_system_health,
    )

    do_launch = launch_items or all_checks
    do_login = login_items or all_checks
    do_health = health or all_checks

    if not (do_launch or do_login or do_health):
        console.print("[yellow]Specify --launch-items, --login-items, --health, or --all[/yellow]")
        raise click.Abort()

    console.print()
    console.print(Panel("[bold cyan]System Inspector[/bold cyan]",
                        border_style="cyan", padding=(0, 2)))

    if do_health:
        h = check_system_health()
        sip_color = "green" if h.sip_enabled else "red"
        sip_label = "Enabled ✓" if h.sip_enabled else "DISABLED ✗"
        console.print(f"\n  [bold]macOS {h.os_version}[/bold]")
        console.print(f"  SIP: [{sip_color}]{sip_label}[/{sip_color}]")
        fda_color = "green" if h.full_disk_access_hint else "yellow"
        fda_label = "Available" if h.full_disk_access_hint else "May be missing"
        console.print(f"  Full Disk Access: [{fda_color}]{fda_label}[/{fda_color}]")
        for w in h.warnings:
            console.print(f"\n  [yellow]⚠  {w}[/yellow]")

    if do_launch:
        items = list_launch_items()
        console.print(f"\n  [bold]LaunchAgents / LaunchDaemons[/bold] ({len(items)} total)\n")
        table = Table(show_header=True, header_style="bold cyan", border_style="dim")
        table.add_column("Label", min_width=30)
        table.add_column("Source", width=16)
        table.add_column("RunAtLoad", width=11, justify="center")
        table.add_column("Status", width=10)
        for item in items:
            status = (
                "[green]active[/green]" if item.run_at_load and not item.disabled
                else "[dim]inactive[/dim]"
            )
            table.add_row(
                item.label,
                item.source,
                "✓" if item.run_at_load else "–",
                status,
            )
        console.print(table)

    if do_login:
        login_items_list = list_login_items()
        console.print(f"\n  [bold]Login Items[/bold] ({len(login_items_list)} found)\n")
        if not login_items_list:
            console.print("  [dim]None found (or Full Disk Access required).[/dim]")
        else:
            table = Table(show_header=True, header_style="bold cyan", border_style="dim")
            table.add_column("Name", min_width=24)
            table.add_column("Enabled", width=9, justify="center")
            table.add_column("Source", width=20)
            table.add_column("Path", style="dim")
            for item in login_items_list:
                enabled = "[green]✓[/green]" if item.enabled else "[dim]–[/dim]"
                table.add_row(item.name, enabled, item.source, item.path)
            console.print(table)

    console.print()


# ══════════════════════════════════════════════════════════════════════════════
# SCHEDULE
# ══════════════════════════════════════════════════════════════════════════════

@main.group("schedule")
def cmd_schedule() -> None:
    """Manage weekly automatic scan schedule."""


@cmd_schedule.command("install")
@click.option("--no-notify", is_flag=True, default=False)
@click.pass_context
def schedule_install(ctx: click.Context, no_notify: bool) -> None:
    """Install a weekly LaunchAgent to run scans automatically."""
    from core.dry_run import skip_if_dry_run
    if skip_if_dry_run(ctx, console, "schedule install"):
        return
    from core.scheduler import install_schedule
    ok, msg = install_schedule(notify=not no_notify)
    color = "green" if ok else "red"
    console.print(f"\n  [{color}]{msg}[/{color}]\n")


@cmd_schedule.command("remove")
@click.pass_context
def schedule_remove(ctx: click.Context) -> None:
    """Remove the weekly scan LaunchAgent."""
    from core.dry_run import skip_if_dry_run
    if skip_if_dry_run(ctx, console, "schedule removal"):
        return
    from core.scheduler import remove_schedule
    ok, msg = remove_schedule()
    color = "green" if ok else "yellow"
    console.print(f"\n  [{color}]{msg}[/{color}]\n")


@cmd_schedule.command("status")
def schedule_status() -> None:
    """Show whether the weekly scan is scheduled and loaded."""
    from core.scheduler import schedule_status
    loaded, detail = schedule_status()
    if loaded:
        console.print(f"\n  [green]✓ Weekly scan is active[/green]")
        if detail:
            console.print(f"  [dim]{detail}[/dim]")
    else:
        console.print("\n  [yellow]Weekly scan is not scheduled.[/yellow]")
        console.print("  Run: [cyan]mac-cleaner schedule install[/cyan]")
    console.print()


# ══════════════════════════════════════════════════════════════════════════════
# UPDATE
# ══════════════════════════════════════════════════════════════════════════════

@main.command("update")
@click.option("--check", is_flag=True, default=False,
              help="Check only — do not upgrade.")
@click.option("--yes", "-y", is_flag=True, default=False,
              help="Upgrade without prompting.")
@click.pass_context
def cmd_update(ctx: click.Context, check: bool, yes: bool) -> None:
    """Check for a newer version on PyPI and optionally upgrade."""
    from core.updater import check_for_update, perform_upgrade
    from core.dry_run import dry_run_enabled

    console.print()
    console.print(f"  Current version: [bold cyan]{__version__}[/bold cyan]")

    with _progress() as prog:
        task = prog.add_task("Checking PyPI…", total=None)
        update_available, latest = check_for_update(__version__)
        prog.update(task, completed=100, total=100)

    if latest is None:
        console.print("  [yellow]⚠ Could not reach PyPI — check your internet connection.[/yellow]")
        return

    if not update_available:
        console.print(f"  [green]✓ You are on the latest version ({__version__}).[/green]")
        return

    console.print(f"  [yellow]Update available:[/yellow] {__version__} → [bold]{latest}[/bold]")

    if check:
        return

    if dry_run_enabled(ctx):
        console.print("  [yellow]Dry-run enabled; upgrade skipped.[/yellow]")
        return

    do_it = yes
    if not do_it:
        from rich.prompt import Confirm
        do_it = Confirm.ask(f"  Upgrade to {latest}?", default=True)

    if do_it:
        with _progress() as prog:
            task = prog.add_task(f"Upgrading to {latest}…", total=None)
            ok, msg = perform_upgrade(latest)
            prog.update(task, completed=100, total=100)

        color = "green" if ok else "red"
        console.print(f"  [{color}]{msg}[/{color}]")
        if ok:
            console.print("  [dim]Restart mac-cleaner to use the new version.[/dim]")
    console.print()


# ══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════════════════════

@main.command("config")
@click.option("--init", is_flag=True, default=False,
              help="Create a default config file if none exists.")
@click.option("--show", is_flag=True, default=False,
              help="Print the resolved config.")
@click.option("--profile", default=None)
def cmd_config(init: bool, show: bool, profile: Optional[str]) -> None:
    """Manage the configuration file (~/.config/mac-cleaner/config.yaml).

    \b
    mac-cleaner config --init       create default config
    mac-cleaner config --show       print resolved settings
    """
    cfg_path = config_file_path()

    if init:
        from config.config import init_default_config
        cfg = init_default_config(profile=profile)
        console.print(f"  [green]✓ Config written to {cfg_path}[/green]")
        return

    cfg = load_config(profile=profile)

    console.print()
    console.print(Panel(
        f"[bold cyan]Configuration[/bold cyan]  [dim]{cfg_path}[/dim]",
        border_style="cyan", padding=(0, 2),
    ))

    if show:
        import json
        console.print_json(json.dumps(cfg.to_dict(), indent=2, default=str))
    console.print()


# ══════════════════════════════════════════════════════════════════════════════
# CORE SCAN + CLEAN ENGINE  (_run)
# ══════════════════════════════════════════════════════════════════════════════

def _run(
    delete: bool,
    auto: bool,
    skip_junk: bool,
    export_path: Optional[str],
    whitelist_set,
    show_apps: bool,
    profile: Optional[str],
    notify: bool,
    save_history: bool,
    cfg,
    undo_mode: bool = True,
    dev_junk: bool = False,
    dev_junk_global: bool = False,
    ci: bool = False,
    threshold_mb: int = 0,
) -> None:
    """Core scan + optional cleanup logic (shared by scan and clean)."""
    # Local import to satisfy static analysis and avoid name-resolution issues.
    from utils import bytes_human

    if not ci:
        print_banner()

    prog = _progress()

    def _run_step(description: str, fn):
        if ci:
            return fn()
        with prog:
            task = prog.add_task(description, total=None)
            value = fn()
            prog.update(task, completed=100, total=100)
            return value

    dev_junk_enabled = bool(cfg.scan_dev_junk or dev_junk or dev_junk_global)
    dev_junk_global_enabled = bool(getattr(cfg, "scan_dev_junk_global", False) or dev_junk_global)
    total_steps = 5 if dev_junk_enabled else 4

    # Step 1: discover apps
    apps = _run_step("Scanning installed applications…", discover_installed_apps)

    if not ci:
        console.print(
            f"  [green]■[/green]  [bold]Step 1/{total_steps}[/bold]  "
            f"Found [green]{len(apps)}[/green] installed applications"
        )
    if show_apps and not ci:
        print_installed_apps(apps)

    # Step 2: running apps
    running_bids = _run_step("Checking running processes…", running_bundle_ids)

    if not ci:
        console.print(
            f"  [cyan]■[/cyan]  [bold]Step 2/{total_steps}[/bold]  "
            f"[cyan]{len(running_bids)}[/cyan] app(s) currently running (protected)"
        )

    # Step 3: orphans
    orphans = _run_step(
        "Detecting orphaned leftovers…",
        lambda: scan_orphans(
            apps,
            whitelist_set,
            running_bids,
            roots=cfg.custom_scan_roots,
            enabled=cfg.scan_orphans,
        ),
    )

    orphan_size = sum(sum(e.size for e in v) for v in orphans.values())
    oc = "red" if orphans else "green"
    if not ci:
        console.print(
            f"  [{oc}]■[/{oc}]  [bold]Step 3/{total_steps}[/bold]  "
            f"[{oc}]{len(orphans)}[/{oc}] orphaned app(s) "
            f"• [{oc}]{bytes_human(orphan_size)}[/{oc}]"
        )

    # Step 4: junk
    junk: list = []
    if not skip_junk:
        junk = _run_step(
            "Scanning caches, logs, trash…",
            lambda: scan_junk(
                whitelist_set,
                apps=apps,
                roots=cfg.custom_scan_roots,
                skip_categories=cfg.skip_categories,
                enabled=cfg.scan_junk,
            ),
        )

        user_junk = [j for j in junk if not j.is_system]
        junk_size = sum(j.size for j in user_junk)
        if not ci:
            console.print(
                f"  [yellow]■[/yellow]  [bold]Step 4/{total_steps}[/bold]  "
                f"[yellow]{len(user_junk)}[/yellow] user junk item(s) "
                f"• [yellow]{bytes_human(junk_size)}[/yellow]"
            )
    elif not ci:
        console.print(
            f"  [dim]■[/dim]  [bold]Step 4/{total_steps}[/bold]  "
            "[dim]Junk scan skipped (--skip-junk)[/dim]"
        )

    # Step 5: dev junk (optional)
    dev_junk_entries: list = []
    dev_junk_size = 0
    if dev_junk_enabled:
        from scanners.dev_junk import find_dev_junk

        dev_junk_entries = _run_step(
            "Scanning developer modules…",
            lambda: find_dev_junk(
                roots=cfg.dev_junk_roots or None,
                max_depth=cfg.dev_junk_max_depth,
                include_global=dev_junk_global_enabled,
            ),
        )
        if whitelist_set:
            dev_junk_entries = [
                e for e in dev_junk_entries
                if e.path not in whitelist_set and not any(wl in e.path.parents for wl in whitelist_set)
            ]
        dev_junk_size = sum(e.size for e in dev_junk_entries)
        if not ci:
            console.print(
                f"  [cyan]■[/cyan]  [bold]Step 5/{total_steps}[/bold]  "
                f"[cyan]{len(dev_junk_entries)}[/cyan] dev junk item(s) "
                f"• [cyan]{bytes_human(dev_junk_size)}[/cyan]"
            )

    if ci:
        import json
        user_junk = [j for j in junk if not j.is_system]
        junk_size = sum(j.size for j in user_junk)
        grand = orphan_size + junk_size + dev_junk_size
        payload = {
            "version": __version__,
            "profile": profile,
            "orphan_count": len(orphans),
            "orphan_bytes": orphan_size,
            "junk_count": len(user_junk),
            "junk_bytes": junk_size,
            "dev_junk_count": len(dev_junk_entries),
            "dev_junk_bytes": dev_junk_size,
            "total_bytes": grand,
            "total_human": bytes_human(grand),
            "threshold_mb": threshold_mb,
            "exceeds_threshold": threshold_mb > 0 and grand > threshold_mb * 1024 * 1024,
        }
        click.echo(json.dumps(payload, indent=2))
        if payload["exceeds_threshold"]:
            raise click.exceptions.Exit(1)
        return

    # Reports
    console.print()
    console.rule("[bold]Orphaned App Leftovers", style="red")
    orphan_total = print_orphan_report(orphans)

    console.print()
    console.rule("[bold]General Junk", style="yellow")
    junk_total = print_junk_report(junk)

    console.print()
    console.rule("[bold]Developer Junk", style="cyan")
    dev_junk_total = print_dev_junk_report(dev_junk_entries)

    print_summary(
        orphan_total=orphan_total,
        junk_total=junk_total,
        dev_junk_total=dev_junk_total,
        running_count=len(running_bids),
        whitelist_count=len(whitelist_set),
    )

    # Save history
    if save_history:
        try:
            from config.history import build_scan_record
            record = build_scan_record(orphans, junk, dev_junk=dev_junk_entries, profile=profile)
            record.save()
        except Exception as exc:
            logger.debug("Failed to save scan history: %s", exc)

    # Export
    if export_path:
        if export_path.endswith((".yaml", ".yml")):
            export_yaml(orphans, junk, dev_junk_entries, export_path)
        elif export_path.endswith(".html"):
            try:
                export_html(orphans, junk, dev_junk_entries, export_path)
                console.print(f"  [green]✓ HTML report: {export_path}[/green]")
            except Exception as e:
                logger.debug("HTML export failed: %s", e)
                console.print(f"  [red]✗ HTML export failed: {e}[/red]")
        else:
            export_json(orphans, junk, dev_junk_entries, export_path)

    grand = orphan_total + junk_total + dev_junk_total

    # Notification
    if notify and grand > 0:
        try:
            from core.scheduler import post_notification
            from utils import bytes_human
            post_notification(
                f"Found {bytes_human(grand)} to clean",
                subtitle=(
                    f"Orphans: {bytes_human(orphan_total)} · "
                    f"Junk: {bytes_human(junk_total)} · "
                    f"Dev: {bytes_human(dev_junk_total)}"
                ),
            )
        except Exception as exc:
            logger.debug("Failed to send notification: %s", exc)

    if grand == 0:
        console.print("\n[bold green]✓ Your Mac is spotless! Nothing to clean.[/bold green]\n")
        return

    # Diff hint
    try:
        from config.history import list_history, diff_scans
        records = list_history(limit=2)
        if len(records) >= 2:
            diff = diff_scans(records[1], records[0])
            if diff.new_orphans:
                console.print(
                    f"  [dim]↑ {len(diff.new_orphans)} new orphan(s) since last scan. "
                    f"Run 'mac-cleaner diff' to see details.[/dim]"
                )
    except Exception as exc:
        logger.debug("Diff hint failed: %s", exc)

    if delete:
        if auto:
            console.print()
            console.print("[bold red]AUTO MODE[/bold red] — deleting all detected items…")

        if undo_mode:
            # Stage files instead of permanent delete
            session = new_session()
            freed = 0

            for app_name, entries in sorted(
                orphans.items(),
                key=lambda kv: sum(e.size for e in kv[1]),
                reverse=True,
            ):
                total = sum(e.size for e in entries)
                do_del = auto
                if not do_del:
                    from rich.prompt import Confirm
                    do_del = Confirm.ask(
                        f"  Stage [bold red]{app_name}[/bold red] "
                        f"([yellow]{bytes_human(total)}[/yellow])?",
                        default=False,
                    )
                if do_del:
                    for e in entries:
                        from core.safety import validate_path_for_deletion
                        safe, _ = validate_path_for_deletion(e.path)
                        if safe:
                            ok, sz = stage_file(e.path, session, category="Orphan")
                            if ok:
                                freed += sz

            user_junk = [j for j in junk if not j.is_system]
            if user_junk:
                do_del = auto
                if not do_del:
                    from rich.prompt import Confirm
                    do_del = Confirm.ask(
                        f"  Stage all user junk "
                        f"([yellow]{bytes_human(sum(j.size for j in user_junk))}[/yellow])?",
                        default=False,
                    )
                if do_del:
                    for j in user_junk:
                        from core.safety import validate_path_for_deletion
                        safe, _ = validate_path_for_deletion(j.path)
                        if safe:
                            ok, sz = stage_file(j.path, session, category="Junk")
                            if ok:
                                freed += sz

            if dev_junk_entries:
                do_del = auto
                if not do_del:
                    from rich.prompt import Confirm
                    do_del = Confirm.ask(
                        f"  Stage all developer junk "
                        f"([yellow]{bytes_human(sum(e.size for e in dev_junk_entries))}[/yellow])?",
                        default=False,
                    )
                if do_del:
                    for e in dev_junk_entries:
                        from core.safety import validate_path_for_deletion
                        safe, _ = validate_path_for_deletion(e.path)
                        if safe:
                            ok, sz = stage_file(e.path, session, category="Dev Junk")
                            if ok:
                                freed += sz

            session.save()

            # Log
            from core.cleaner import write_deletion_log
            write_deletion_log([(f.original_path, f.size) for f in session.files])

            console.print()
            console.print(
                f"[bold green]✓ Done! Staged {bytes_human(freed)} "
                f"(session: {session.session_id[:8]})[/bold green]"
            )
            console.print(
                f"[dim]Restore with: mac-cleaner undo --session {session.session_id[:8]}[/dim]"
            )
        else:
            freed = do_cleanup(orphans, junk, auto=auto)
            if dev_junk_entries:
                from rich.prompt import Confirm
                do_del = auto or Confirm.ask(
                    f"  Delete all developer junk "
                    f"([yellow]{bytes_human(sum(e.size for e in dev_junk_entries))}[/yellow])?",
                    default=False,
                )
                if do_del:
                    from utils import safe_remove
                    from core.cleaner import write_deletion_log
                    deleted = []
                    for e in dev_junk_entries:
                        from core.safety import validate_path_for_deletion
                        safe, _ = validate_path_for_deletion(e.path)
                        if safe:
                            ok, sz = safe_remove(e.path)
                            if ok:
                                freed += sz
                                deleted.append((str(e.path), sz))
                    if deleted:
                        write_deletion_log(deleted)
            console.print(f"\n[bold green]✓ Done! Freed {bytes_human(freed)}[/bold green]")
            console.print(f"[dim]Deletion log: {LOG_FILE}[/dim]")

        console.print()
    else:
        print_instructions()


if __name__ == "__main__":
    main()
