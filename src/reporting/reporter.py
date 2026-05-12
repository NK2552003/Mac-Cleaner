"""
Beautiful terminal output using Rich library.
Tables, trees, panels, and progress indicators.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

from config.models import DevJunkEntry, JunkEntry, OrphanEntry
from utils import bytes_human

console = Console()

# ── Category icons (Nerd Font / Unicode box-drawing) ─────────────────────────
REASON_ICONS: Dict[str, str] = {
    "App Support":      "■",
    "Preferences":      "●",
    "Cache":            "◆",
    "Logs":             "▸",
    "Launch Agent":     "▶",
    "Launch Daemon":    "▶",
    "Group Container":  "◈",
    "Container":        "◈",
    "Saved State":      "◇",
    "WebKit Data":      "◆",
    "HTTP Storage":     "◆",
    "Cookies":          "◆",
    "Synced Prefs":     "●",
    "Helper Tool":      "▶",
    "Other":            "○",
}

REASON_STYLES: Dict[str, str] = {
    "App Support":      "cyan",
    "Preferences":      "magenta",
    "Cache":            "yellow",
    "Logs":             "dim",
    "Launch Agent":     "red",
    "Launch Daemon":    "red",
    "Group Container":  "blue",
    "Container":        "blue",
    "Saved State":      "dim",
    "WebKit Data":      "yellow",
    "HTTP Storage":     "yellow",
    "Cookies":          "yellow",
    "Synced Prefs":     "magenta",
    "Helper Tool":      "red",
    "Other":            "white",
}

JUNK_ICONS: Dict[str, str] = {
    "User Cache":       "◆",
    "System Cache":     "◇",
    "Log File":         "▸",
    "Crash Report":     "▸",
    "Trash":            "■",
    ".DS_Store":        "○",
    "Xcode Junk":       "■",
    "npm Cache":        "◆",
    "pip Cache":        "◆",
    "Yarn Cache":       "◆",
    "pnpm Cache":       "◆",
    "Gradle Cache":     "◆",
    "Maven Cache":      "◆",
    "Cargo Cache":      "◆",
    "Go Build Cache":   "◆",
    "CocoaPods Cache":  "◆",
    "Chrome Cache":     "◆",
    "Firefox Cache":    "◆",
    "Package Cache":    "◆",
}

DEV_JUNK_ICONS: Dict[str, str] = {
    "Node Modules": "◆",
    "Python Venv": "■",
    "Python Cache": "◇",
    "Java Build": "■",
    "Go Build": "■",
    "Rust Target": "■",
    "Dotnet Build": "■",
    "Ruby Bundle": "■",
    "PHP Vendor": "■",
    "Build Output": "◆",
    "Coverage": "◇",
    "Global Cache (Node)": "◇",
    "Global Cache (Python)": "◇",
    "Global Cache (Java)": "◇",
    "Global Cache (Go)": "◇",
    "Global Cache (Rust)": "◇",
    "Global Cache (Dotnet)": "◇",
    "Global Cache (Ruby)": "◇",
    "Global Cache (PHP)": "◇",
}


def print_banner() -> None:
    """Print the application banner."""
    banner = Text()
    banner.append("Mac Deep Cleaner", style="bold cyan")
    banner.append("  v2.0.0", style="dim cyan")
    banner.append("  —  Professional Edition", style="dim")

    console.print()
    console.print(
        Panel(
            banner,
            border_style="cyan",
            padding=(1, 2),
            title="[bold white]◆ Smart App Orphan Detector[/bold white]",
            title_align="center",
            subtitle="[dim]macOS System Cleanup Tool[/dim]",
            subtitle_align="center",
        )
    )
    console.print()


def print_installed_apps(apps: dict, compact: bool = True) -> None:
    """Print discovered installed applications."""
    table = Table(
        title="Installed Applications",
        show_header=True,
        header_style="bold cyan",
        border_style="dim",
        title_style="bold",
        padding=(0, 1),
    )
    table.add_column("#", style="dim", width=4, justify="right")
    table.add_column("Application", style="bold white", min_width=28)
    table.add_column("Bundle ID", style="dim", min_width=35)

    sorted_apps = sorted(apps.values(), key=lambda a: a.name.lower())

    if compact and len(sorted_apps) > 30:
        for i, app in enumerate(sorted_apps[:15], 1):
            table.add_row(str(i), app.name, app.bundle_id)
        table.add_row(
            "…",
            f"[dim]… {len(sorted_apps) - 30} more apps …[/dim]",
            "",
        )
        for i, app in enumerate(sorted_apps[-15:], len(sorted_apps) - 14):
            table.add_row(str(i), app.name, app.bundle_id)
    else:
        for i, app in enumerate(sorted_apps, 1):
            table.add_row(str(i), app.name, app.bundle_id)

    console.print(table)


def print_orphan_report(orphans: Dict[str, List[OrphanEntry]]) -> int:
    """
    Print orphaned app leftovers report.
    Returns total bytes of orphan data found.
    """
    if not orphans:
        console.print(
            Panel(
                "[green]✓ No orphaned app leftovers found![/green]",
                border_style="green",
                padding=(0, 2),
            )
        )
        return 0

    sorted_apps = sorted(
        orphans.items(),
        key=lambda kv: sum(e.size for e in kv[1]),
        reverse=True,
    )

    grand = 0
    tree = Tree(
        "[bold red]Orphaned App Leftovers[/bold red]  "
        "[dim](apps no longer installed)[/dim]",
        guide_style="dim red",
    )

    for app_name, entries in sorted_apps:
        total = sum(e.size for e in entries)
        grand += total

        app_branch = tree.add(
            f"[bold red]✗[/bold red]  [bold]{app_name}[/bold]  "
            f"[yellow]{bytes_human(total)}[/yellow]  "
            f"[dim]({len(entries)} item{'s' if len(entries) != 1 else ''})[/dim]"
        )

        for e in entries:
            icon = REASON_ICONS.get(e.reason, "○")
            style = REASON_STYLES.get(e.reason, "white")
            is_dir = e.path.is_dir() if e.path.exists() else True
            type_indicator = "╸" if is_dir else "─"

            app_branch.add(
                f"[{style}]{icon}[/{style}]  "
                f"[{style}]{e.reason:16}[/{style}] "
                f"{type_indicator} [dim]{e.path}[/dim]"
            )

    console.print(tree)
    return grand


def print_junk_report(junk: List[JunkEntry]) -> int:
    """
    Print general junk report.
    Returns total bytes of user-actionable junk.
    """
    if not junk:
        console.print(
            Panel(
                "[green]✓ No general junk found![/green]",
                border_style="green",
                padding=(0, 2),
            )
        )
        return 0

    user_junk = [j for j in junk if not j.is_system]
    system_junk = [j for j in junk if j.is_system]

    # Group by category
    by_cat: Dict[str, List[JunkEntry]] = defaultdict(list)
    for j in user_junk:
        by_cat[j.category].append(j)

    grand = 0

    table = Table(
        title="General Junk",
        show_header=True,
        header_style="bold yellow",
        border_style="dim",
        title_style="bold",
        padding=(0, 1),
    )
    table.add_column("Category", style="bold", min_width=18)
    table.add_column("Items", justify="right", style="cyan", width=8)
    table.add_column("Size", justify="right", style="yellow", width=12)
    table.add_column("Top Items", style="dim", min_width=30)

    for cat in sorted(by_cat.keys()):
        items = by_cat[cat]
        cat_total = sum(j.size for j in items)
        grand += cat_total

        icon = JUNK_ICONS.get(cat, "○")
        top = ", ".join(j.path.name for j in sorted(items, key=lambda x: x.size, reverse=True)[:3])
        if len(items) > 3:
            top += f" (+{len(items) - 3} more)"

        table.add_row(
            f"{icon} {cat}",
            str(len(items)),
            bytes_human(cat_total),
            top,
        )

    console.print(table)

    # System caches (informational only)
    if system_junk:
        sys_total = sum(j.size for j in system_junk)
        console.print(
            f"\n  [dim]◇ System Caches — {len(system_junk)} items, "
            f"{bytes_human(sys_total)} (OS-owned, never deleted)[/dim]"
        )

    return grand


def print_dev_junk_report(entries: List[DevJunkEntry]) -> int:
    """
    Print developer junk report.
    Returns total bytes of detected entries.
    """
    if not entries:
        console.print(
            Panel(
                "[green]✓ No developer junk found![/green]",
                border_style="green",
                padding=(0, 2),
            )
        )
        return 0

    from collections import defaultdict

    by_cat: Dict[str, List[DevJunkEntry]] = defaultdict(list)
    for e in entries:
        by_cat[e.category].append(e)

    total = sum(e.size for e in entries)

    table = Table(
        title=f"Developer Junk  ({bytes_human(total)} total)",
        show_header=True,
        header_style="bold yellow",
        border_style="dim",
        title_style="bold",
        padding=(0, 1),
    )
    table.add_column("Category", style="bold", min_width=18)
    table.add_column("Items", justify="right", style="cyan", width=8)
    table.add_column("Size", justify="right", style="yellow", width=12)
    table.add_column("Top Item", style="dim", min_width=30)

    for cat in sorted(by_cat.keys()):
        items = by_cat[cat]
        cat_total = sum(e.size for e in items)
        icon = DEV_JUNK_ICONS.get(cat, "○")
        largest = max(items, key=lambda x: x.size)
        table.add_row(
            f"{icon} {cat}",
            str(len(items)),
            bytes_human(cat_total),
            largest.path.name,
        )

    console.print(table)
    return total


def print_summary(
    orphan_total: int,
    junk_total: int,
    dev_junk_total: int,
    running_count: int,
    whitelist_count: int,
) -> None:
    """Print the final summary panel."""
    grand = orphan_total + junk_total + dev_junk_total

    summary_lines = []
    summary_lines.append(f"[bold]Recoverable space:[/bold]  [bold green]{bytes_human(grand)}[/bold green]")
    if orphan_total:
        summary_lines.append(f"  [red]■[/red] Orphan leftovers:  [yellow]{bytes_human(orphan_total)}[/yellow]")
    if junk_total:
        summary_lines.append(f"  [yellow]◆[/yellow] General junk:      [yellow]{bytes_human(junk_total)}[/yellow]")
    if dev_junk_total:
        summary_lines.append(f"  [cyan]◆[/cyan] Developer junk:   [yellow]{bytes_human(dev_junk_total)}[/yellow]")
    if running_count:
        summary_lines.append(f"  [dim]▶ {running_count} running app(s) protected[/dim]")
    if whitelist_count:
        summary_lines.append(f"  [dim]● {whitelist_count} whitelisted path(s) skipped[/dim]")

    console.print()
    console.print(
        Panel(
            "\n".join(summary_lines),
            border_style="cyan",
            title="[bold]Summary[/bold]",
            padding=(1, 2),
        )
    )


def print_instructions() -> None:
    """Print usage instructions when in preview mode."""
    console.print()
    console.print("[yellow]Nothing was deleted — this was a preview.[/yellow]")
    console.print()

    table = Table(show_header=False, border_style="dim", padding=(0, 2))
    table.add_column("Command", style="cyan")
    table.add_column("Description", style="white")

    table.add_row("mac-cleaner clean", "Interactive — choose per app")
    table.add_row("mac-cleaner clean --auto", "Delete everything automatically")
    table.add_row("mac-cleaner scan --skip-junk", "Orphans only, skip junk scan")
    table.add_row("mac-cleaner scan --export results.json", "Export to JSON")
    table.add_row("mac-cleaner clean --whitelist PATH", "Protect a path")
    table.add_row("mac-cleaner scan --dev-junk", "Scan developer modules (node_modules, venv)")
    table.add_row("mac-cleaner scan --dev-junk-global", "Include global caches (~/.npm, ~/.gradle)")

    console.print(table)
    console.print()


# ═════════════════════════════════════════════════════════════════════════════
# v2.0.0 Additions (merged from reporter_v5.py)
# ═════════════════════════════════════════════════════════════════════════════

from typing import Any


def print_duplicate_report(groups) -> int:
    """
    Print a report of duplicate file groups.
    Returns total wasted bytes.

    Args:
        groups: List[DuplicateGroup] from duplicates.find_duplicates()
    """
    if not groups:
        console.print(
            Panel(
                "[green]✓ No duplicate files found![/green]",
                border_style="green",
                padding=(0, 2),
            )
        )
        return 0

    from scanners.duplicates import total_wasted

    wasted = total_wasted(groups)

    dup_tree = Tree(
        f"[bold yellow]Duplicate Files[/bold yellow]  "
        f"[dim]({len(groups)} groups · {bytes_human(wasted)} wasted)[/dim]",
        guide_style="dim yellow",
    )

    for i, g in enumerate(groups[:30], 1):
        group_branch = dup_tree.add(
            f"[yellow]◆[/yellow]  [bold]{g.paths[0].name}[/bold]  "
            f"[yellow]{bytes_human(g.wasted_bytes)} wasted[/yellow]  "
            f"[dim]({len(g.paths)} copies × {bytes_human(g.size)})[/dim]"
        )
        for p in g.paths:
            group_branch.add(f"[dim]{p}[/dim]")

    if len(groups) > 30:
        dup_tree.add(f"[dim]… and {len(groups) - 30} more groups[/dim]")

    console.print(dup_tree)
    return wasted


def print_large_file_report(entries) -> int:
    """
    Print a report of large files grouped by category.
    Returns total bytes across all entries.

    Args:
        entries: List[LargeFileEntry] from large_files.find_large_files()
    """
    if not entries:
        console.print(
            Panel(
                "[green]✓ No large files found![/green]",
                border_style="green",
                padding=(0, 2),
            )
        )
        return 0

    from collections import defaultdict

    by_cat: dict[str, list[Any]] = defaultdict(list)
    for e in entries:
        by_cat[e.category].append(e)

    total = sum(e.size for e in entries)

    table = Table(
        title=f"Large Files  ({bytes_human(total)} total)",
        show_header=True,
        header_style="bold cyan",
        border_style="dim",
        title_style="bold",
        padding=(0, 1),
    )
    table.add_column("Category", min_width=16)
    table.add_column("Files", justify="right", width=7)
    table.add_column("Size", justify="right", style="yellow", width=12)
    table.add_column("Largest File", style="dim")

    for cat in sorted(by_cat, key=lambda c: sum(e.size for e in by_cat[c]), reverse=True):
        items = by_cat[cat]
        cat_total = sum(e.size for e in items)
        largest = max(items, key=lambda e: e.size)
        table.add_row(cat, str(len(items)), bytes_human(cat_total), largest.path.name)

    console.print(table)
    return total


def print_symlink_report(broken_symlinks) -> int:
    """
    Print a report of broken symbolic links.
    Returns the count of broken links.

    Args:
        broken_symlinks: List[BrokenSymlink] from symlinks.find_broken_symlinks()
    """
    if not broken_symlinks:
        console.print(
            Panel(
                "[green]✓ No broken symlinks found![/green]",
                border_style="green",
                padding=(0, 2),
            )
        )
        return 0

    table = Table(
        title=f"Broken Symlinks  ({len(broken_symlinks)} found)",
        show_header=True,
        header_style="bold red",
        border_style="dim",
        title_style="bold",
        padding=(0, 1),
    )
    table.add_column("Location", style="cyan", min_width=20)
    table.add_column("Symlink", style="dim", min_width=30)
    table.add_column("→ Missing Target", style="red")

    for s in broken_symlinks:
        table.add_row(s.location, str(s.path.name), s.target)

    console.print(table)
    return len(broken_symlinks)


def print_ios_backup_report(backups) -> int:
    """
    Print a report of iOS backups.
    Returns total bytes of all backups.

    Args:
        backups: List[IOSBackup] from extras.find_ios_backups()
    """
    if not backups:
        console.print(
            Panel(
                "[green]✓ No iOS backups found.[/green]",
                border_style="green",
                padding=(0, 2),
            )
        )
        return 0

    total = sum(b.size for b in backups)

    table = Table(
        title=f"iOS Backups  ({bytes_human(total)} total)",
        show_header=True,
        header_style="bold cyan",
        border_style="dim",
        title_style="bold",
        padding=(0, 1),
    )
    table.add_column("Device", min_width=22)
    table.add_column("Model", width=14)
    table.add_column("iOS", width=8)
    table.add_column("Age", width=8, justify="right")
    table.add_column("Size", justify="right", style="yellow", width=10)

    for b in backups:
        age_days = b.age_days or 0
        age_str = f"{b.age_days}d" if b.age_days is not None else "?"
        age_color = (
            "red" if age_days > 180 else "yellow" if age_days > 60 else "green"
        )
        table.add_row(
            b.device_name,
            b.product_type,
            b.ios_version,
            f"[{age_color}]{age_str}[/{age_color}]",
            b.size_human,
        )

    console.print(table)
    return total


def print_language_pack_report(entries) -> int:
    """
    Print a report of strippable language packs.
    Returns total bytes that could be reclaimed.

    Args:
        entries: List[LanguagePackEntry] from extras.find_language_packs()
    """
    if not entries:
        console.print(
            Panel(
                "[green]✓ No removable language packs found.[/green]",
                border_style="green",
                padding=(0, 2),
            )
        )
        return 0

    total = sum(e.removable_size for e in entries)

    table = Table(
        title=f"Removable Language Packs  ({bytes_human(total)} reclaimable)",
        show_header=True,
        header_style="bold cyan",
        border_style="dim",
        title_style="bold",
        padding=(0, 1),
    )
    table.add_column("App", min_width=24)
    table.add_column("Removable Langs", justify="right", width=16)
    table.add_column("Saves", justify="right", style="yellow", width=10)
    table.add_column("Kept Langs", style="dim", width=16)

    for e in entries[:40]:
        kept_str = ", ".join(p.stem for p in e.kept_lprojs[:4])
        if len(e.kept_lprojs) > 4:
            kept_str += f" +{len(e.kept_lprojs) - 4}"
        table.add_row(
            e.app_name,
            str(len(e.removable_lprojs)),
            e.removable_size_human,
            kept_str,
        )

    if len(entries) > 40:
        console.print(f"  [dim]… and {len(entries) - 40} more apps[/dim]")

    console.print(table)
    return total


def print_diff_report(diff) -> None:
    """
    Print a rich diff comparison between two scan records.

    Args:
        diff: ScanDiff from history.diff_scans()
    """
    delta = diff.size_delta_bytes
    sign = "+" if delta >= 0 else ""
    color = "red" if delta > 0 else "green" if delta < 0 else "dim"

    console.print()
    console.print(
        Panel(
            f"  Older scan: [dim]{diff.older.scanned_at:%Y-%m-%d %H:%M}[/dim]  "
            f"({bytes_human(diff.older.total_bytes)})\n"
            f"  Newer scan: [bold]{diff.newer.scanned_at:%Y-%m-%d %H:%M}[/bold]  "
            f"({bytes_human(diff.newer.total_bytes)})\n\n"
            f"  Size delta: [{color}]{sign}{bytes_human(abs(delta))}[/{color}]",
            title="[bold]Scan Diff[/bold]",
            border_style="cyan",
            padding=(1, 2),
        )
    )

    if diff.new_orphans:
        console.print(f"\n  [red]▲ New orphans ({len(diff.new_orphans)}):[/red]")
        for name in diff.new_orphans:
            console.print(f"    [red]+[/red] {name}")

    if diff.resolved_orphans:
        console.print(f"\n  [green]▼ Resolved ({len(diff.resolved_orphans)}):[/green]")
        for name in diff.resolved_orphans:
            console.print(f"    [green]−[/green] {name}")

    if diff.persistent_orphans:
        console.print(f"\n  [yellow]· Persistent ({len(diff.persistent_orphans)}):[/yellow]")
        for name in diff.persistent_orphans[:8]:
            console.print(f"    [dim]·[/dim] {name}")
        if len(diff.persistent_orphans) > 8:
            console.print(f"    [dim]… and {len(diff.persistent_orphans)-8} more[/dim]")

    console.print()
