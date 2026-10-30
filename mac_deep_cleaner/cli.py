"""Command-line entry point."""

import argparse
import os
import subprocess
import sys
from . import __version__
from .cleanup import execute, select_level
from .common import CAUTION, IS_MAC, RISKY, SAFE, c, fmt
from .scanner import Scanner
from .server import serve
from .settings import load_settings, save_settings
from .terminal import HAVE_Q, HAVE_RICH, Session, analyze_apps, cat_by_token, export_json, flow_apps, interactive_plain, print_report_plain, render_apps, rich_report, run_scan, selected_summary, tui

def ensure_deps(args):
    # Never alter the user's Python installation from inside the application.
    if args.install_deps:
        print('Install the optional terminal UI from this source folder: python3 -m pip install ".[terminal]"')
    if not (HAVE_RICH and HAVE_Q):
        args.plain = True


def parse_args():
    # Provide backward compatibility for legacy positional subcommands like 'scan' and 'dashboard'
    argv = sys.argv[1:]
    normalized_argv = []
    for arg in argv:
        if arg in ("scan", "dashboard"):
            continue
        normalized_argv.append(arg)

    ap = argparse.ArgumentParser(prog="mac-deep-cleaner", description="Mac Deep Cleaner — local storage analysis and reviewed cleanup.")
    ap.add_argument("--web", action="store_true", help="open the local dashboard (default)")
    ap.add_argument("--terminal", action="store_true", help="use the terminal interface")
    ap.add_argument("--version", action="version", version=f"mac-deep-cleaner {__version__}")
    ap.add_argument("--idle-timeout", type=int, default=0, help="stop the server after this many idle seconds; 0 disables")
    ap.add_argument("--port", type=int, default=0, help="local port; 0 chooses a free port")
    ap.add_argument("--no-open", action="store_true", help="with --web: do not open the browser")
    ap.add_argument("--apps", action="store_true", help="jump straight to the application analyzer (no full scan)")
    ap.add_argument("--mode", choices=["normal", "dev"], help="normal (plain categories) or dev (toolchain groups, commands); saved")
    ap.add_argument("--plain", action="store_true", help="original plain-text interface (no rich / questionary)")
    ap.add_argument("--report", action="store_true", help="print the report and exit")
    ap.add_argument("--install-deps", action="store_true", help="show installation instructions for the optional terminal UI")
    ap.add_argument("--json", metavar="FILE", help="export the analysis as JSON")
    ap.add_argument("--clean", choices=["safe", "caution", "risky", "all"], help="select a level non-interactively")
    ap.add_argument("--category", help="limit --clean to one category (number or name fragment)")
    ap.add_argument("--yes", action="store_true", help="do not ask for confirmation (with --clean)")
    ap.add_argument("--i-understand", action="store_true", help="acknowledge risky items (needed for --clean risky/all)")
    ap.add_argument("--dry-run", action="store_true", help="show what would be removed")
    ap.add_argument("--permanent", action="store_true", help="delete instead of moving to Trash")
    ap.add_argument("--large-mb", type=int, default=50, help="large-file threshold (default 50)")
    ap.add_argument("--old-days", type=int, default=180)
    ap.add_argument("--dup-min-mb", type=float, default=1.0)
    ap.add_argument("--min-mb", type=float, default=None, help="hide items below this in lists (default 10; totals still count them)")
    ap.add_argument("--all", action="store_true", help="print every item in the report")
    ap.add_argument("--no-interactive", action="store_true")
    args = ap.parse_args(normalized_argv)
    if not 0 <= args.port <= 65535:
        ap.error("port must be between 0 and 65535")
    if args.large_mb <= 0 or args.old_days < 0 or not 0 < args.dup_min_mb <= 1_000_000:
        ap.error("scan thresholds must be positive (old-days may be zero)")
    if args.min_mb is not None and not 0 <= args.min_mb <= 1_000_000:
        ap.error("min-mb must be a finite non-negative number")
    if args.idle_timeout < 0:
        ap.error("idle-timeout must be non-negative")
    if not (args.terminal or args.apps or args.plain or args.report or args.json or args.clean or args.no_interactive):
        args.web = True
    return args


def main():
    args = parse_args()
    settings = load_settings()
    if args.mode:
        settings["mode"] = args.mode
        save_settings(settings)
    if args.min_mb is not None:
        settings["min_mb"] = args.min_mb
    args.min_mb = settings["min_mb"]
    ensure_deps(args)
    if not IS_MAC:
        print(c("  note: this tool targets macOS; on other systems only the generic scans work.", "33"), file=sys.stderr)
    if args.web:
        try:
            return serve(args, settings)
        except OSError as exc:
            sys.exit(f"Could not start Mac Deep Cleaner: {exc}")

    rich_ok = HAVE_RICH and not args.plain
    tty = sys.stdin.isatty() and sys.stdout.isatty() and not args.no_interactive
    fancy = rich_ok and HAVE_Q and tty and not args.report
    sc = Scanner(args.large_mb, args.old_days, args.dup_min_mb, quiet=rich_ok, pinned=settings["pinned"])
    S = Session(sc, settings, args) if rich_ok else None

    if args.apps:
        if not rich_ok:
            sys.exit("  --apps needs the new interface: python3 -m pip install --user rich questionary")
        sc.load_apps()
        if fancy:
            return flow_apps(S)
        analyze_apps(S)
        return S.say(render_apps(S))

    if rich_ok:
        run_scan(S)
    else:
        print(c("\n  Mac Deep Cleaner - scanning (nothing is deleted without your say-so)…", "1"), file=sys.stderr)
        sc.run()
    sc.pool.shutdown(wait=True)
    if sc.error:
        sys.exit(sc.error)
    items = sc.items
    if args.json:
        export_json(items, args.json)

    if args.clean:
        name = cat_by_token(args.category) if args.category else None
        if args.category and name is None:
            sys.exit(f"Unknown category: {args.category}. No files were changed.")
        pool = [i for i in items if not name or i.category == name]
        if args.clean in ("risky", "all") and not args.i_understand:
            sys.exit("  --clean risky/all needs --i-understand")
        select_level(pool, args.clean)
        sel, tot, by = selected_summary(items)
        print(f"  selected {len(sel)} items, {fmt(tot)}  (safe {fmt(by[SAFE])}, caution {fmt(by[CAUTION])}, risky {fmt(by[RISKY])})")
        if not sel:
            return
        if not (args.yes or args.dry_run) and input("  proceed? [y/N] ").strip().lower() != "y":
            return
        freed, roots, fails = execute(items, permanent=args.permanent, dry_run=args.dry_run)
        print(c(f"\n  {'would free' if args.dry_run else 'freed'} {fmt(freed)}", "1;32"))
        for r in roots:
            print("  run manually: " + r)
        return
    if fancy:
        return tui(S)
    if rich_ok:
        rich_report(S, show_all=args.all)
    else:
        print_report_plain(items, args.min_mb, show_all=args.all)
    if sys.stdin.isatty() and not args.no_interactive and not args.report and not fancy:
        interactive_plain(items, args)
