"""Command-line entry point."""

import argparse
import json
import sys
import threading
import time
from pathlib import Path

from . import __version__
from .cleanup import execute, select_level
from .common import CAUTION, IS_MAC, RISKY, SAFE, c, fmt
from .errors import APIError
from .scanner import Scanner
from .server import serve
from .settings import load_settings, save_settings
from .system_tools import TOOLS
from .terminal import (
    HAVE_Q,
    HAVE_RICH,
    Session,
    analyze_apps,
    cat_by_token,
    export_json,
    flow_apps,
    interactive_plain,
    print_report_plain,
    render_apps,
    rich_report,
    run_scan,
    selected_summary,
    tui,
)
from .toolkit import Toolkit


def ensure_deps(args):
    # Never alter the user's Python installation from inside the application.
    if args.install_deps:
        print('Install the optional terminal UI from this source folder: python3 -m pip install ".[terminal]"')
    if not (HAVE_RICH and HAVE_Q):
        args.plain = True


def parse_args():
    # Provide backward compatibility for legacy positional subcommands like 'scan' and 'dashboard'
    argv = sys.argv[1:]
    normalized_argv = argv[1:] if argv and argv[0] in ("scan", "dashboard") else argv

    ap = argparse.ArgumentParser(prog="mac-deep-cleaner", description="Mac Deep Cleaner — cleanup, optimization, disks, and Homebrew management.", epilog="Homebrew commands: mac-cleaner brew --help")
    ap.add_argument("--web", action="store_true", help="open the local dashboard (default)")
    ap.add_argument("--terminal", action="store_true", help="use the terminal interface")
    ap.add_argument("--version", action="version", version=f"mac-deep-cleaner {__version__}")
    ap.add_argument("--idle-timeout", type=int, default=0, help="stop the server after this many idle seconds; 0 disables")
    ap.add_argument("--port", type=int, default=0, help="local port; 0 chooses a free port")
    ap.add_argument("--no-open", action="store_true", help="with --web: do not open the browser")
    ap.add_argument("--apps", action="store_true", help="jump straight to the application analyzer (no full scan)")
    start = ap.add_mutually_exclusive_group()
    start.add_argument("--homebrew", action="store_true", help="open the Homebrew package manager")
    start.add_argument("--optimize", action="store_true", help="open Optimize your Mac in the dashboard")
    start.add_argument("--disks", action="store_true", help="open disk and volume management in the dashboard")
    start.add_argument("--health-report", action="store_true", help="print a read-only system health report as JSON")
    start.add_argument("--disk-report", action="store_true", help="print a read-only disk inventory as JSON")
    start.add_argument("--tool", choices=sorted(TOOLS), help="review and run a maintenance task; --dry-run only shows its plan")
    ap.add_argument("--mode", choices=["normal", "dev"], help="normal (plain categories) or dev (toolchain groups, commands); saved")
    ap.add_argument("--plain", action="store_true", help="original plain-text interface (no rich / questionary)")
    ap.add_argument("--report", action="store_true", help="print the report and exit")
    ap.add_argument("--install-deps", action="store_true", help="show installation instructions for the optional terminal UI")
    ap.add_argument("--json", metavar="FILE", help="export the analysis as JSON")
    ap.add_argument("--clean", choices=["safe", "caution", "risky", "all"], help="select a level non-interactively")
    ap.add_argument("--category", help="limit --clean to one category (number or name fragment)")
    ap.add_argument("--yes", action="store_true", help="confirm --clean or --tool without an interactive prompt")
    ap.add_argument("--i-understand", action="store_true", help="acknowledge risky cleanup or permanent maintenance tasks")
    ap.add_argument("--dry-run", action="store_true", help="preview cleanup or a maintenance command without executing it")
    ap.add_argument("--permanent", action="store_true", help="delete instead of moving to Trash")
    ap.add_argument("--large-mb", type=int, default=50, help="large-file threshold (default 50)")
    ap.add_argument("--old-days", type=int, default=180)
    ap.add_argument("--dup-min-mb", type=float, default=1.0)
    ap.add_argument("--min-mb", type=float, default=None, help="hide items below this in lists (default 10; totals still count them)")
    ap.add_argument("--all", action="store_true", help="print every item in the report")
    ap.add_argument("--no-interactive", action="store_true")
    args = ap.parse_args(normalized_argv)
    toolkit_mode = args.homebrew or args.optimize or args.disks or args.health_report or args.disk_report or args.tool
    if toolkit_mode and (args.clean or args.apps or args.terminal or args.report):
        ap.error("use optimization/disk tools separately from cleanup, applications, and terminal reports")
    if (args.homebrew or args.optimize or args.disks) and (args.json or args.no_interactive):
        ap.error("use --health-report or --disk-report for non-interactive JSON output")
    if args.tool and args.json:
        ap.error("--tool prints its review/result to stdout; --json is for reports")
    if args.homebrew or args.optimize or args.disks:
        args.web = True
    args.view = 'homebrew' if args.homebrew else 'optimize' if args.optimize else 'disks' if args.disks else 'clean'
    if not 0 <= args.port <= 65535:
        ap.error("port must be between 0 and 65535")
    if args.large_mb <= 0 or args.old_days < 0 or not 0 < args.dup_min_mb <= 1_000_000:
        ap.error("scan thresholds must be positive (old-days may be zero)")
    if args.min_mb is not None and not 0 <= args.min_mb <= 1_000_000:
        ap.error("min-mb must be a finite non-negative number")
    if args.idle_timeout < 0:
        ap.error("idle-timeout must be non-negative")
    if not (toolkit_mode or args.terminal or args.apps or args.plain or args.report or args.json or args.clean or args.no_interactive):
        args.web = True
    return args


def run_toolkit_cli(args):
    toolkit = Toolkit(threading.Lock())
    try:
        if args.health_report or args.disk_report:
            report = toolkit.health() if args.health_report else toolkit.disks()
            encoded = json.dumps({'version': __version__, **report}, indent=2) + '\n'
            if args.json:
                Path(args.json).write_text(encoded, encoding='utf-8')
            else:
                print(encoded, end='')
            return
        plan = toolkit.prepare('tool', {'action': args.tool})
        print(json.dumps(plan, indent=2))
        if args.dry_run:
            return
        if args.no_interactive and not args.yes:
            raise APIError(400, 'Use --dry-run to preview, or --yes to run the reviewed maintenance task.')
        if not args.yes:
            if not sys.stdin.isatty():
                raise APIError(400, 'A terminal confirmation or --yes is required.')
            if input('Run this task? [y/N] ').strip().lower() != 'y':
                return
        if plan['danger'] and not args.i_understand:
            if args.yes or not sys.stdin.isatty():
                raise APIError(400, 'This task permanently removes data. Add --i-understand after reviewing --dry-run.')
            if input(f'Type {plan["phrase"]} to continue: ') != plan['phrase']:
                return
        job = toolkit.start({'token': plan['token'], 'confirmed': True, 'phrase': plan['phrase']})
        while job['status'] == 'running':
            time.sleep(0.2)
            job = toolkit.history()['jobs'][-1]
        print(job['output'])
        if job['status'] == 'failed':
            raise APIError(400, job['error'])
    except (APIError, OSError) as exc:
        sys.exit(str(exc))


def main():
    if len(sys.argv) > 1 and sys.argv[1] == 'brew':
        from .brew_cli import main as brew_main
        def dashboard(options):
            sys.argv = [sys.argv[0], '--homebrew', '--port', str(options.port), *(['--no-open'] if options.no_open else [])]
            return main()
        return brew_main(sys.argv[2:], dashboard)
    args = parse_args()
    if args.health_report or args.disk_report or args.tool:
        return run_toolkit_cli(args)
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
        freed, roots, _fails = execute(items, permanent=args.permanent, dry_run=args.dry_run)
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
