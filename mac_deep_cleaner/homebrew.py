"""Homebrew inventory, dependency explanations, and exact reviewed operations.

No brew-why dependency is needed. Homebrew's JSON and autoremove preview own the
installation facts; absence of a graph edge alone never authorizes removal.
"""
import hashlib
import json
import re
import threading
import time
from pathlib import Path

from .errors import APIError
from .system_tools import CommandRunner, executable

NAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9+_.@-]*(?:/[A-Za-z0-9][A-Za-z0-9+_.@-]*){0,2}\Z')
GROUPS = ('Requested', 'Dependencies', 'Removal candidates', 'Unknown origin', 'Casks')
ACTIONS = {'tidy', 'cleanup', 'upgrade', 'uninstall', 'pin', 'unpin', 'keep',
           'mark-dependency', 'update', 'doctor', 'service-start', 'service-stop', 'service-restart'}


def package_name(value):
    if not isinstance(value, str) or not NAME.fullmatch(value) or '..' in value.split('/'):
        raise APIError(400, 'Choose a valid installed Homebrew package.')
    return value


def reachable(start, edges):
    seen, pending = set(), list(start)
    while pending:
        key = pending.pop()
        if key in seen:
            continue
        seen.add(key)
        pending.extend(edges.get(key, []))
    return seen


def autoremove_names(output):
    """Accept the documented CLI preview shape; unknown output fails closed."""
    output = re.sub(r'\x1b\[[0-9;]*m', '', output).strip()
    if not output:
        return []
    lines = output.splitlines()
    match = re.fullmatch(r'(?:==> )?Would autoremove (\d+) unneeded formulae?:', lines[0].strip())
    if not match:
        raise APIError(502, 'Homebrew’s removal preview format was not recognized. No packages were selected.')
    names = [package_name(line.strip()) for line in lines[1:] if line.strip()]
    if len(names) != int(match.group(1)) or len(set(names)) != len(names):
        raise APIError(502, 'Homebrew’s removal preview was incomplete. Refresh before removing packages.')
    return names


def build_graph(info, orphan_names, services, sizes=None, removal_checks=True):
    """Pure graph builder, preserving formula/cask namespaces and tap identities."""
    if not isinstance(info, dict) or not isinstance(info.get('formulae'), list) or not isinstance(info.get('casks'), list):
        raise APIError(502, 'Homebrew returned an incomplete installed-package inventory.')
    records, raw, aliases = {}, {}, {}
    sizes = sizes or {}
    for kind, entries in (('formula', info['formulae']), ('cask', info['casks'])):
        for entry in entries:
            full = package_name(entry.get('full_name' if kind == 'formula' else 'full_token')
                                or entry.get('name' if kind == 'formula' else 'token'))
            name = package_name(entry.get('name' if kind == 'formula' else 'token') or full.split('/')[-1])
            key = kind + ':' + full
            installed = entry.get('installed')
            if kind == 'formula':
                if not isinstance(installed, list) or not installed:
                    raise APIError(502, f'Installation receipts are missing for {full}.')
                flags = [k.get('installed_on_request') for k in installed]
                requested = True if any(f is True for f in flags) else False if all(f is False for f in flags) else None
                versions = sorted({str(k.get('version', 'Unknown')) for k in installed})
            else:
                requested = True  # Casks are retained as roots regardless of install attribution.
                versions = [str(installed or 'Unknown')]
            if key in records:
                raise APIError(502, 'Duplicate package identities in the Homebrew inventory.')
            records[key] = {'id': key, 'name': name, 'full_name': full, 'kind': kind,
                'description': entry.get('desc') or '', 'tap': entry.get('tap') or 'Unknown tap',
                'versions': versions, 'latest': str(entry.get('versions', {}).get('stable') or entry.get('version') or ''),
                'requested': requested, 'pinned': bool(entry.get('pinned')), 'outdated': bool(entry.get('outdated')),
                'deprecated': bool(entry.get('deprecated')), 'disabled': bool(entry.get('disabled')),
                'keg_only': bool(entry.get('keg_only')), 'has_service': bool(entry.get('service')),
                'service': 'not registered', 'dependencies': [], 'runtime_dependencies': [],
                'required_by': [], 'runtime_required_by': [], 'roots': [], 'orphan': False,
                'size': sizes.get(key), 'size_scope': 'Cellar' if kind == 'formula' else 'Caskroom only',
                'group': 'Casks' if kind == 'cask' else 'Requested' if requested is True else 'Unknown origin' if requested is None else 'Dependencies'}
            raw[key] = entry
            for alias in [full, name, *entry.get('aliases', []), *entry.get('oldnames', []), *entry.get('old_tokens', [])]:
                aliases.setdefault((kind, alias), set()).add(key)

    def resolve(kind, name):
        exact = kind + ':' + name
        if exact in records:
            return exact
        matches = aliases.get((kind, name), set())
        if len(matches) == 1:
            return next(iter(matches))
        return None

    warnings = []
    for key, entry in raw.items():
        p = records[key]
        direct, runtime = set(), set()
        if p['kind'] == 'formula':
            for receipt in entry['installed']:
                deps = receipt.get('runtime_dependencies')
                if deps is None:
                    warnings.append(f'{p["full_name"]}: no installed runtime dependency receipt; using current formula metadata.')
                    removal_checks = False
                    deps = []
                for dep in deps:
                    dep_name = dep.get('full_name') or dep.get('name')
                    target = resolve('formula', dep_name) if isinstance(dep_name, str) else None
                    if target:
                        runtime.add(target)
                        if dep.get('declared_directly') is not False:
                            direct.add(target)
                    else:
                        warnings.append(f'{p["full_name"]}: missing or ambiguous installed dependency {dep_name}.')
                        removal_checks = False
            # Preserve current declared installed dependencies as a conservative supplement.
            for dep_name in entry.get('dependencies', []) + entry.get('recommended_dependencies', []) + entry.get('optional_dependencies', []):
                target = resolve('formula', dep_name)
                if target:
                    direct.add(target)
            if any(not receipt.get('poured_from_bottle', True) for receipt in entry['installed']):
                for dep_name in entry.get('build_dependencies', []):
                    target = resolve('formula', dep_name)
                    if target:
                        runtime.add(target)
        else:
            for kind in ('formula', 'cask'):
                for dep_name in (entry.get('depends_on') or {}).get(kind, []):
                    target = resolve(kind, dep_name)
                    if target:
                        direct.add(target)
                    else:
                        warnings.append(f'{p["full_name"]}: missing or ambiguous {kind} dependency {dep_name}.')
                        removal_checks = False
        p['dependencies'] = sorted(direct - {key})
        p['runtime_dependencies'] = sorted((runtime | direct) - {key})
        for target in p['dependencies']:
            records[target]['required_by'].append(key)
        for target in p['runtime_dependencies']:
            records[target]['runtime_required_by'].append(key)
    for service in services:
        target = resolve('formula', service.get('name', ''))
        if target:
            records[target]['service'] = service.get('status') or 'unknown'
            records[target]['has_service'] = True
    roots = [p['id'] for p in records.values() if p['requested'] is not False or p['pinned']
             or p['service'] not in ('not registered', 'none', 'stopped', 'unloaded')]
    edges = {k: p['runtime_dependencies'] for k, p in records.items()}
    retained = reachable(roots, edges)
    for root in roots:
        for key in reachable([root], edges) - {root}:
            records[key]['roots'].append(root)
    candidate_ids = set()
    for name in orphan_names:
        target = resolve('formula', name)
        if target is None:
            warnings.append(f'Homebrew preview references an unknown or ambiguous formula: {name}.')
            removal_checks = False
        else:
            candidate_ids.add(target)
    candidates = {key for key in candidate_ids if key not in retained and records[key]['requested'] is False}
    # Also keep anything needed by a package outside this exact candidate set.
    while True:
        protected = {key for key in candidates if set(records[key]['runtime_required_by']) - candidates}
        if not protected:
            break
        candidates -= protected
    for key, p in records.items():
        p['orphan'] = removal_checks and key in candidates
        if p['orphan']:
            p['group'] = 'Removal candidates'
        p['roots'].sort()
        p['required_by'].sort()
        p['runtime_required_by'].sort()
        p['shared'] = len(p['roots']) > 1
    return list(records.values()), warnings, removal_checks


def reverse_tree(packages, target, limit=250):
    by_id = {p['id']: p for p in packages}
    if target not in by_id:
        raise APIError(404, 'Package not found in this inventory.')
    rows, stack, expanded = [], [(target, 0, frozenset())], set()
    while stack and len(rows) < limit:
        key, depth, ancestors = stack.pop()
        cycle, repeated = key in ancestors, key in expanded
        rows.append({'id': key, 'name': by_id[key]['full_name'], 'kind': by_id[key]['kind'],
                     'depth': depth, 'cycle': cycle, 'repeated': repeated and not cycle})
        if cycle or repeated:
            continue
        expanded.add(key)
        for parent in reversed(by_id[key]['required_by']):
            stack.append((parent, depth + 1, ancestors | {key}))
    return {'rows': rows, 'truncated': bool(stack)}


class HomebrewManager:
    def __init__(self, runner=None, finder=executable):
        self.runner = runner or CommandRunner()
        self.finder = finder
        self.lock = threading.RLock()
        self.cached = None

    def _json(self, command):
        try:
            return json.loads(self.runner.text(command, timeout=120))
        except (ValueError, TypeError):
            raise APIError(502, 'Homebrew returned unreadable JSON. Run brew doctor or refresh.') from None

    def report(self, refresh=False, measure=True):
        with self.lock:
            if self.cached and not refresh:
                return self.cached
            brew = self.finder('brew')
            if not brew:
                return {'available': False, 'packages': [], 'warnings': [],
                        'message': 'Homebrew was not found. Install it from brew.sh, then refresh.'}
            prefix = self.runner.text([brew, '--prefix']).strip()
            cellar = self.runner.text([brew, '--cellar']).strip()
            caskroom = self.runner.text([brew, '--caskroom']).strip()
            for folder in (prefix, cellar, caskroom):
                if not Path(folder).is_absolute() or '\n' in folder:
                    raise APIError(502, 'Homebrew returned an invalid installation path.')
            info = self._json([brew, 'info', '--json=v2', '--installed'])
            warnings, checks = [], True
            try:
                orphan_names = autoremove_names(self.runner.text([brew, 'autoremove', '--dry-run'], timeout=120))
            except APIError as exc:
                orphan_names = []
                warnings.append(str(exc)); checks = False
            try:
                services = self._json([brew, 'services', 'list', '--json'])
                if not isinstance(services, list) or any(not isinstance(s, dict) or not isinstance(s.get('name'), str) for s in services):
                    raise APIError(502, 'Service status is unreadable.')
            except APIError as exc:
                services = []
                warnings.append(f'Cannot check background services: {exc}'); checks = False
            packages, graph_warnings, checks = build_graph(info, orphan_names, services, removal_checks=checks)
            warnings.extend(graph_warnings)
            try:
                outdated = self._json([brew, 'outdated', '--json=v2'])
                if not isinstance(outdated, dict) or not all(isinstance(outdated.get(k), list) for k in ('formulae', 'casks')):
                    raise APIError(502, 'Update status is unreadable.')
                for p in packages:
                    entries = outdated['formulae' if p['kind'] == 'formula' else 'casks']
                    match = next((e for e in entries if (e.get('full_name') or e.get('name') or e.get('token')) in (p['full_name'], p['name'])), None)
                    p['outdated'] = match is not None
                    if match:
                        p['latest'] = str(match.get('current_version') or p['latest'])
                update_status = True
            except APIError as exc:
                warnings.append(f'Cannot check updates: {exc}')
                update_status = False
            if measure and packages:
                roots = {'formula': Path(cellar), 'cask': Path(caskroom)}
                paths = {str(roots[p['kind']] / p['name']): p for p in packages}
                try:
                    output = self.runner.text(['/usr/bin/du', '-sk', *paths], timeout=120)
                    for line in output.splitlines():
                        count, path = line.split('\t', 1)
                        if path in paths and count.isdigit():
                            paths[path]['size'] = int(count) * 1024
                except (APIError, ValueError):
                    warnings.append('Some package sizes are unavailable. Cask sizes cover Caskroom only, not app bundles moved elsewhere.')
            stable = [{k: p[k] for k in ('id', 'versions', 'latest', 'requested', 'pinned', 'outdated',
                      'runtime_dependencies', 'service', 'orphan', 'disabled')} for p in packages]
            fingerprint = hashlib.sha256(json.dumps([brew, prefix, stable, checks, update_status], sort_keys=True).encode()).hexdigest()
            report = {'available': True, 'brew': brew, 'prefix': prefix, 'cellar': cellar,
                'caskroom': caskroom, 'checked_at': time.time(), 'packages': packages,
                'warnings': warnings, 'removal_checks': checks, 'update_status': update_status,
                'fingerprint': fingerprint, 'groups': list(GROUPS), 'stats': {
                    'total': len(packages), 'formulae': sum(p['kind'] == 'formula' for p in packages),
                    'casks': sum(p['kind'] == 'cask' for p in packages),
                    'requested': sum(p['kind'] == 'formula' and p['requested'] is True for p in packages),
                    'dependencies': sum(p['kind'] == 'formula' and p['requested'] is False for p in packages),
                    'orphans': sum(p['orphan'] for p in packages), 'outdated': sum(p['outdated'] for p in packages),
                    'size': sum(p['size'] or 0 for p in packages),
                    'orphan_size': sum(p['size'] or 0 for p in packages if p['orphan']),
                    'unmeasured': sum(p['size'] is None for p in packages)}}
            if measure:
                self.cached = report
            return report

    def explain(self, target):
        report = self.report()
        p = self.resolve(report, target)
        return {'package': p, 'tree': reverse_tree(report['packages'], p['id'])}

    @staticmethod
    def resolve(report, target):
        if not isinstance(target, str):
            raise APIError(400, 'Choose an installed package.')
        exact = [p for p in report['packages'] if p['id'] == target]
        matches = exact or [p for p in report['packages'] if target in (p['full_name'], p['name'])]
        if len(matches) != 1:
            raise APIError(400, 'Package missing or ambiguous. Use formula:name or cask:name from the inventory.')
        return matches[0]

    def plan(self, body):
        action = body.get('action')
        if not isinstance(action, str) or action not in ACTIONS:
            raise APIError(400, 'Choose an available Homebrew operation.')
        report = self.report(refresh=True, measure=False)
        if not report['available']:
            raise APIError(400, report['message'])
        brew, packages = report['brew'], report['packages']
        p = self.resolve(report, body.get('target')) if action not in ('tidy', 'cleanup', 'update', 'doctor') else None
        selected, preview, danger = [], '', False
        description = ''
        if action == 'tidy':
            if not report['removal_checks']:
                raise APIError(409, 'Dependency or service checks are incomplete. Removal is disabled.')
            selected = [p for p in packages if p['orphan']]
            if not selected:
                raise APIError(400, 'Homebrew reports no eligible unused dependencies. You can still review cache cleanup.')
            commands = [[brew, 'uninstall', '--formula', *[p['full_name'] for p in selected]]]
            title = 'Remove unused dependencies'; danger = True
            description = 'Permanently remove only the formulae listed below. Homebrew lists these as unused dependencies. Software outside Homebrew may still use them. Review cache cleanup separately afterward.'
        elif action == 'cleanup':
            preview = self.runner.text([brew, 'cleanup', '--dry-run'], timeout=120)
            commands = [[brew, 'cleanup']]; title = 'Clean Homebrew caches'; danger = True
            description = 'Permanently remove old package versions and cached downloads shown in Homebrew’s preview. Automatic dependency removal is disabled. Old versions may no longer be available for rollback.'
        elif action in ('update', 'doctor'):
            commands = [[brew, action]]
            title = 'Update Homebrew metadata' if action == 'update' else 'Homebrew health check'
            description = 'Download current Homebrew definitions and update Homebrew itself. Installed packages are not upgraded.' if action == 'update' else 'Check your Homebrew installation and report problems. Warnings may produce a nonzero exit status.'
        else:
            selected = [p]
            flag = '--formula' if p['kind'] == 'formula' else '--cask'
            name = p['full_name']
            if action == 'uninstall':
                if not report['removal_checks']:
                    raise APIError(409, 'Dependency or service checks are incomplete. Removal is disabled.')
                if p['runtime_required_by']:
                    raise APIError(409, 'Other installed packages depend on this package. Remove dependents first.')
                if p['pinned'] or p['service'] not in ('not registered', 'none', 'stopped', 'unloaded'):
                    raise APIError(409, 'Unpin this package and stop its registered service before uninstalling it.')
                commands = [[brew, 'uninstall', flag, name]]; title = f'Uninstall {name}'; danger = True
                description = 'Remove this installed package using Homebrew. No force, dependency bypass, or cask zap is used. Applications and scripts outside Homebrew may rely on it. Cask uninstallers can make their own system changes.'
            elif action == 'upgrade':
                if not report['update_status'] or not p['outdated'] or p['pinned']:
                    raise APIError(409, 'This package has no confirmed unpinned update. Refresh metadata or unpin it first.')
                preview = self.runner.text([brew, 'upgrade', '--dry-run', flag, name], timeout=120)
                commands = [[brew, 'upgrade', flag, name]]; title = f'Upgrade {name}'
                description = 'Upgrade this package and dependencies reported in the preview. Dependencies may also be installed. Package installers and post-install scripts can run. Automatic cache cleanup and dependent upgrades are disabled.'
            elif action in ('pin', 'unpin', 'keep', 'mark-dependency'):
                if p['kind'] != 'formula':
                    raise APIError(400, 'Pinning and install-intent editing are available for formulae in this app.')
                if action in ('pin', 'unpin'):
                    commands = [[brew, action, name]]; title = f'{action.capitalize()} {name}'
                    description = 'Prevent Homebrew upgrades for this formula.' if action == 'pin' else 'Allow Homebrew upgrades for this formula again.'
                else:
                    keep = action == 'keep'
                    commands = [[brew, 'tab', '--installed-on-request' if keep else '--no-installed-on-request', '--formula', name]]
                    title = f'{"Keep" if keep else "Mark as dependency:"} {name}'
                    description = 'Mark this formula as intentionally installed so autoremove keeps it.' if keep else 'Change the installation receipt to a dependency. It may become eligible for future autoremove. Nothing is removed now.'
            else:
                if p['kind'] != 'formula' or not p['has_service']:
                    raise APIError(400, 'This package has no Homebrew service definition.')
                verb = action.split('-', 1)[1]
                commands = [[brew, 'services', verb, name]]; title = f'{verb.capitalize()} {name} service'
                description = 'Manage this background service for your current user. Starting or restarting registers it at login; stopping unregisters it. System-wide services that require sudo are not managed here.'
        return {'title': title, 'description': description, 'commands': commands,
                'changes': action != 'doctor', 'danger': danger, 'phrase': 'REMOVE' if danger else '',
                'layout': [], 'packages': [{k: p[k] for k in ('id', 'full_name', 'kind', 'versions')} for p in selected],
                'preview': preview, 'fingerprint': report['fingerprint']}

    def invalidate(self):
        with self.lock:
            self.cached = None

    def brewfile(self):
        report = self.report()
        packages = report['packages']
        lines = ['# Exported by Mac Deep Cleaner. Package list, not a version lockfile.']
        taps = sorted({p['tap'] for p in packages} - {'homebrew/core', 'homebrew/cask', 'Unknown tap'})
        for tap in taps:
            lines.append('tap ' + json.dumps(package_name(tap)))
        for p in packages:
            if p['kind'] == 'cask' or p['requested'] is not False:
                lines.append(('cask ' if p['kind'] == 'cask' else 'brew ') + json.dumps(p['full_name']))
        return '\n'.join(lines) + '\n'
