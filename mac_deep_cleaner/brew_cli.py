"""`mac-cleaner brew …`: the same inventory and reviewed jobs as the dashboard."""
import argparse
import json
import shlex
import sys
import threading
import time
from pathlib import Path

from .common import fmt
from .errors import APIError
from .homebrew import reverse_tree
from .toolkit import Toolkit


def parser():
    ap = argparse.ArgumentParser(prog='mac-cleaner brew', description='Explain and manage installed Homebrew packages.')
    sub = ap.add_subparsers(dest='command', required=True)
    dash = sub.add_parser('dashboard', help='open the Homebrew workspace')
    dash.add_argument('--no-open', action='store_true')
    dash.add_argument('--port', type=int, default=0)
    for name in ('overview', 'explain', 'heaviest', 'reverse-tree', 'audit', 'stats', 'export'):
        cmd = sub.add_parser(name)
        cmd.add_argument('--json', nargs='?', const='-', metavar='FILE', help='JSON to stdout or a file')
        if name in ('explain', 'reverse-tree'):
            cmd.add_argument('package', help='name, formula:name, or cask:name')
        if name == 'heaviest':
            cmd.add_argument('--limit', type=int, default=15)
        if name == 'export':
            cmd.add_argument('--output', default='-', help='Brewfile path; default stdout')
    for name in ('tidy', 'cleanup', 'upgrade', 'uninstall', 'pin', 'unpin', 'keep', 'mark-dependency', 'update', 'doctor', 'service-start', 'service-stop', 'service-restart'):
        cmd = sub.add_parser(name)
        if name not in ('tidy', 'cleanup', 'update', 'doctor'):
            cmd.add_argument('package')
        cmd.add_argument('--dry-run', action='store_true', help='show the plan; execute nothing')
        cmd.add_argument('--yes', action='store_true', help='confirm the displayed operation')
        cmd.add_argument('--i-understand', action='store_true', help='acknowledge permanent removals with --yes')
    return ap


def emit_json(data, destination):
    encoded = json.dumps(data, indent=2) + '\n'
    if destination == '-':
        print(encoded, end='')
    else:
        Path(destination).write_text(encoded, encoding='utf-8')


def table(packages):
    try:
        from rich.console import Console
        from rich.table import Table
        output = Table('Package', 'Installed', 'Group', 'Required by', 'Size', 'Update')
        for p in packages:
            output.add_row(f'{p["full_name"]} ({p["kind"]})', ', '.join(p['versions']), p['group'],
                           str(len(p['required_by'])), fmt(p['size']) if p['size'] is not None else 'Unknown',
                           p['latest'] if p['outdated'] else '—')
        Console(highlight=False, markup=False).print(output)
    except ImportError:
        for p in packages:
            print(f'{p["id"]:45} {", ".join(p["versions"]):18} {p["group"]:20} '
                  f'{fmt(p["size"]) if p["size"] is not None else "Unknown":>12}'
                  f'{"  → " + p["latest"] if p["outdated"] else ""}')


def run_plan(toolkit, action, args):
    plan = toolkit.prepare('brew', {'action': action, 'target': getattr(args, 'package', None)})
    print(f'\n{plan["title"]}\n{plan["description"]}')
    for p in plan['packages']:
        print(f'  {p["kind"]}: {p["full_name"]} ({", ".join(p["versions"])})')
    if plan['preview']:
        print(plan['preview'])
    for command in plan['commands']:
        print('Command: ' + shlex.join(command))
    if args.dry_run:
        return True
    if plan['changes']:
        if not args.yes:
            if not sys.stdin.isatty():
                raise APIError(400, 'Use --dry-run to inspect the plan or --yes to confirm it.')
            if input('Continue? [y/N] ').strip().lower() != 'y':
                return False
        if plan['danger'] and not args.i_understand:
            if args.yes:
                raise APIError(400, 'Permanent removal also requires --i-understand. Review --dry-run first.')
            if input(f'Type {plan["phrase"]}: ') != plan['phrase']:
                return False
    job = toolkit.start({'token': plan['token'], 'confirmed': True, 'phrase': plan['phrase']})
    while job['status'] == 'running':
        time.sleep(0.2)
        job = toolkit.history()['jobs'][-1]
    print(job['output'])
    if job['status'] != 'succeeded':
        raise APIError(400, job['error'])
    return True


def main(argv, dashboard):
    ap = parser()
    args = ap.parse_args(argv)
    if args.command == 'dashboard':
        return dashboard(args)
    if args.command == 'heaviest' and not 1 <= args.limit <= 1000:
        ap.error('--limit must be between 1 and 1000')
    toolkit = Toolkit(threading.Lock())
    try:
        if args.command in ('tidy', 'cleanup', 'upgrade', 'uninstall', 'pin', 'unpin', 'keep', 'mark-dependency', 'update', 'doctor', 'service-start', 'service-stop', 'service-restart'):
            if args.command == 'tidy':
                report = toolkit.brew.report()
                if not report['available']:
                    raise APIError(400, report['message'])
                if not report['removal_checks']:
                    raise APIError(409, 'Dependency/service checks are incomplete; tidy is disabled.')
                if any(p['orphan'] for p in report['packages']):
                    if not run_plan(toolkit, 'tidy', args):
                        return
                else:
                    print('No eligible unused dependencies. Reviewing caches and old versions next.')
                return run_plan(toolkit, 'cleanup', args)
            return run_plan(toolkit, args.command, args)
        report = toolkit.brew.report()
        if not report['available']:
            raise APIError(400, report['message'])
        packages = report['packages']
        if args.command in ('explain', 'reverse-tree'):
            data = toolkit.brew.explain(args.package)
        elif args.command == 'heaviest':
            data = sorted((p for p in packages if p['kind'] == 'formula'), key=lambda p: p['size'] or 0, reverse=True)[:args.limit]
        elif args.command == 'audit':
            if not report['update_status']:
                raise APIError(502, 'Update checks failed. Refresh Homebrew metadata and try again.')
            data = [p for p in packages if p['outdated']]
        elif args.command == 'stats':
            data = report['stats']
        elif args.command == 'export':
            data = {'brewfile': toolkit.brew.brewfile()}
        else:
            data = report
        if args.json:
            return emit_json(data, args.json)
        if args.command != "export":
            print(f'Homebrew: {report["prefix"]}')
        if args.command in ('explain', 'reverse-tree'):
            p = data['package']
            if args.command == 'explain':
                print(f'\n{p["full_name"]} — {p["description"]}\nGroup: {p["group"]}')
                print('Installed: ' + ', '.join(p['versions']))
                print('Needed by requested/protected roots: ' + (', '.join(p['roots']) or 'None recorded'))
                print('Dependencies: ' + (', '.join(p['dependencies']) or 'None recorded'))
                print('Unknown external scripts and applications may still use this package.')
            print('\nReverse dependency tree (packages above this one depend on it):')
            for row in reverse_tree(packages, p['id'])['rows']:
                print('  ' * row['depth'] + row['name'] + (' [cycle]' if row['cycle'] else ' [shown above]' if row['repeated'] else ''))
            if data['tree']['truncated']:
                print('Tree limited to 250 rows; use JSON for the full inventory.')
        elif args.command == 'stats':
            for key, value in data.items():
                print(f'{key.replace("_", " ").capitalize()}: {fmt(value) if "size" in key else value}')
        elif args.command == 'export':
            if args.output == '-':
                print(data['brewfile'], end='')
            else:
                Path(args.output).write_text(data['brewfile'], encoding='utf-8')
                print(f'Wrote {args.output}')
        else:
            if args.command == 'audit':
                print('Available updates from local Homebrew metadata; not a vulnerability scan. Run mac-cleaner brew update to refresh metadata.')
            table(data if isinstance(data, list) else sorted(packages, key=lambda p: (p['group'], p['full_name'])))
        for warning in report['warnings']:
            print('Note: ' + warning, file=sys.stderr)
    except (APIError, OSError) as exc:
        sys.exit(str(exc))
