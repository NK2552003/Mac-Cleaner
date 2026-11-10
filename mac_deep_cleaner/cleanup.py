"""Cleanup primitives shared by the CLI and authenticated local application.

Only scanner-generated items are executable. Paths and identities are checked
again at execution; duplicate keepers and selected ancestors are protected.
"""
import hashlib
import os
import shlex
import shutil
import sqlite3
import stat
import subprocess

from .common import HOME, IS_MAC, SAFE, fingerprint, fmt

FORBIDDEN = {HOME, '/', '/Users', '/Applications', '/Library', '/System', '/private', '/usr', '/bin', '/var', '/opt'} | {
    os.path.join(HOME, d) for d in ('Documents', 'Desktop', 'Downloads', 'Pictures', 'Movies', 'Music', 'Library', 'Applications', 'Public')}
ALLOWED_COMMANDS = {('docker', 'system', 'prune', '-f'), ('xcrun', 'simctl', 'delete', 'unavailable')}


def eligible(it):
    return not (it.protected or it.managed)


def select_level(items, level):
    count = 0
    for it in items:
        if eligible(it) and (level == 'all' or it.safety == level):
            if level == SAFE and (it.manual or it.action != 'trash'):
                continue
            it.selected = True
            count += 1
    return count


def guard_ok(path):
    if not isinstance(path, str) or not os.path.isabs(path):
        return False
    p = os.path.abspath(path)
    real = os.path.realpath(p)
    forbidden = FORBIDDEN | {os.path.realpath(x) for x in FORBIDDEN}
    if p in forbidden or real in forbidden or os.path.islink(p):
        return False
    # Reject links in ancestors, even when both ends are within the home folder.
    if os.path.realpath(os.path.dirname(p)) != os.path.dirname(p):
        return False
    return p.startswith((HOME + os.sep, '/Applications/'))


def esc_as(p):
    return p.replace('\\', '\\\\').replace('"', '\\"')


def to_trash(path):
    if not guard_ok(path):
        return False, 'refused by safety guard'
    from .history import History
    try:
        History(HOME).move(path)
        return True, 'moved to Trash; restore from Cleanup history'
    except (OSError, sqlite3.Error) as exc:
        return False, str(exc)


def hard_delete(path):
    if not guard_ok(path):
        return False, 'refused by safety guard'
    try:
        if stat.S_ISDIR(os.lstat(path).st_mode):
            shutil.rmtree(path)
        else:
            os.unlink(path)
        return not os.path.lexists(path), 'deleted permanently'
    except OSError as exc:
        return False, str(exc)


def empty_dir(path):
    """Empty only the actual user Trash; do not follow a substituted directory."""
    if os.path.abspath(path) != os.path.join(HOME, '.Trash') or not guard_ok(path):
        return False, 'only the user Trash can be emptied'
    errors = []
    try:
        with os.scandir(path) as entries:
            for entry in entries:
                if entry.is_symlink():
                    os.unlink(entry.path)  # unlink the entry, never its destination
                else:
                    ok, message = hard_delete(entry.path)
                    if not ok:
                        errors.append(message)
    except OSError as exc:
        errors.append(str(exc))
    return not errors, '; '.join(errors) if errors else 'Trash emptied permanently'


def _digest(path):
    with open(path, 'rb') as handle:
        digest = hashlib.sha256()
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
        return digest.digest()


def validate_item(item, selected_paths=()):
    if not eligible(item):
        return 'protected or managed item'
    if item.action == 'root':
        return ''  # returned as an instruction, never executed
    if item.action == 'cmd':
        return '' if tuple(shlex.split(item.cmd)) in ALLOWED_COMMANDS else 'unsupported cleanup command'
    if item.action not in ('trash', 'empty', 'evict') or not guard_ok(item.path):
        return 'refused by safety guard'
    if item.action == 'empty' and item.path != os.path.join(HOME, '.Trash'):
        return 'only the user Trash can be emptied'
    if not item.fingerprint or fingerprint(item.path) != tuple(item.fingerprint):
        return 'item changed since the scan; rescan and review it again'
    if item.path.endswith('.app') and IS_MAC:
        try:
            processes = subprocess.run(['/bin/ps', '-axo', 'comm='], capture_output=True, text=True, check=True, timeout=5).stdout
        except (OSError, subprocess.SubprocessError):
            return 'could not check running applications; try again'
        if any(line.strip().startswith(item.path + os.sep) for line in processes.splitlines()):
            return 'application is running; quit it before removing it'
    if item.action == 'evict' and not item.path.startswith(os.path.join(HOME, 'Library/Mobile Documents/com~apple~CloudDocs') + os.sep):
        return 'only local iCloud Drive copies can be evicted'
    if item.keep:
        if any(item.keep == p or item.keep.startswith(p + os.sep) for p in selected_paths):
            return 'the retained duplicate is also selected for removal'
        if not item.keeper_fingerprint or fingerprint(item.keep) != tuple(item.keeper_fingerprint):
            return 'the retained duplicate changed or disappeared; rescan first'
        try:
            if os.path.islink(item.keep) or _digest(item.path) != _digest(item.keep):
                return 'duplicate content no longer matches the retained copy'
        except OSError:
            return 'could not verify the retained duplicate'
    return ''


def execute(items, permanent=False, dry_run=False, log=print, tick=None, candidate_check=None):
    """Serialize cleanup and optionally recheck candidates at each move boundary."""
    from .history import mutation_lock
    with mutation_lock(HOME):
        return _execute(items, permanent, dry_run, log, tick, candidate_check)


def _execute(items, permanent=False, dry_run=False, log=print, tick=None, candidate_check=None):
    """Return processed bytes, manual administrator commands, and failures.

    Processed bytes are estimates, not a promise of newly available disk space.
    Trash moves retain disk space until the user empties Trash.
    """
    chosen = [i for i in items if i.selected and eligible(i)]
    selected_paths = {i.path for i in chosen if i.path}
    keepers = {i.keep for i in chosen if i.keep}
    freed, roots, failures, completed = 0, [], [], []
    for item in sorted(chosen, key=lambda i: len(i.path)):
        if item.path and any(item.path == p or item.path.startswith(p + os.sep) for p in completed):
            if not dry_run:
                item.selected = False
            if tick:
                tick(item, None if dry_run else True, 'included in selected parent')
            continue
        error = validate_item(item, selected_paths)
        if item.path and any(k == item.path or k.startswith(item.path + os.sep) for k in keepers):
            error = 'this item contains a retained duplicate'
        if error:
            ok, message = False, error
        elif item.action == 'root':
            roots.append(item.cmd)
            if tick:
                tick(item, None, 'requires administrator action')
            continue
        elif dry_run:
            freed += item.size
            if item.path:
                completed.append(item.path)
            log(f'  would process: {item.name} ({fmt(item.size)})')
            if tick:
                tick(item, None, 'dry run')
            continue
        elif item.action in ('cmd', 'evict'):
            cmd = shlex.split(item.cmd) if item.action == 'cmd' else ['/usr/bin/brctl', 'evict', item.path]
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=900, check=False)
                ok, message = result.returncode == 0, result.stderr.strip() or 'completed'
            except (OSError, subprocess.TimeoutExpired) as exc:
                ok, message = False, str(exc)
        elif item.action == 'empty':
            ok, message = empty_dir(item.path)
        else:
            if candidate_check is not None and not candidate_check(item):
                ok, message = False, 'The cache changed or is no longer safe for automatic cleanup.'
            else:
                ok, message = hard_delete(item.path) if permanent else to_trash(item.path)
        log(f'  {"ok" if ok else "FAIL"} {item.name}: {message}')
        if tick:
            tick(item, ok, message)
        if ok:
            freed += item.size
            item.selected = False
            if item.path:
                completed.append(item.path)
        else:
            failures.append((item, message))
    return freed, roots, failures
