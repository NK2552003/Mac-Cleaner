"""Read actual macOS application icons, including asset-catalog icons."""
import glob
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def application_icon(path, icon_name=''):
    """Prefer Launch Services' icon; use a bundle ICNS only as a fallback."""
    helper = Path(sys.executable).with_name('app-icon-helper')
    source = Path(__file__).resolve().parent.parent / 'desktop/app_icon.swift'
    command = [str(helper), path] if getattr(sys, 'frozen', False) and helper.is_file() else None
    if command is None and source.is_file() and Path('/usr/bin/xcrun').is_file():
        command = ['/usr/bin/xcrun', 'swift', str(source), path]
    if command:
        try:
            result = subprocess.run(command, capture_output=True, check=True, timeout=15)
            if result.stdout.startswith(b'\x89PNG\r\n\x1a\n') and len(result.stdout) <= 1_000_000:
                return result.stdout
        except (OSError, subprocess.SubprocessError):
            pass
    resources = os.path.join(path, 'Contents', 'Resources')
    candidates = [os.path.join(resources, icon_name), os.path.join(resources, icon_name + '.icns')] if icon_name else []
    candidates += sorted(glob.glob(os.path.join(resources, '*.icns')))[:1]
    src = next((p for p in candidates if p.endswith('.icns') and os.path.isfile(p)
                and os.path.realpath(p).startswith(os.path.realpath(resources) + os.sep)), None)
    if src:
        with tempfile.TemporaryDirectory(prefix='mac-deep-cleaner-icon-') as folder:
            target = os.path.join(folder, 'icon.png')
            try:
                subprocess.run(['/usr/bin/sips', '-s', 'format', 'png', '-Z', '128', src, '--out', target],
                               capture_output=True, check=True, timeout=10)
                with open(target, 'rb') as handle:
                    return handle.read(1_000_000)
            except (OSError, subprocess.SubprocessError):
                pass
    return None


def ghost_icon(path, bundle_id='', name=''):
    """Locate or extract the real app icon for an orphaned leftover file."""
    # 1. Search in ~/.Trash for the deleted .app
    trash = os.path.expanduser('~/.Trash')
    if os.path.isdir(trash):
        candidates = []
        if name:
            candidates.extend([f"{name}.app", f"{name.capitalize()}.app", f"{name.title()}.app", f"{name.lower()}.app"])
            spaced = name.replace('-', ' ').replace('_', ' ')
            candidates.extend([f"{spaced}.app", f"{spaced.title()}.app"])
        for cand in dict.fromkeys(candidates):
            cand_path = os.path.join(trash, cand)
            if os.path.isdir(cand_path):
                data = application_icon(cand_path)
                if data:
                    return data
        if bundle_id:
            try:
                for entry in os.listdir(trash):
                    if entry.endswith('.app'):
                        app_path = os.path.join(trash, entry)
                        try:
                            with open(os.path.join(app_path, 'Contents/Info.plist'), 'rb') as f:
                                import plistlib
                                info = plistlib.load(f)
                                if (info.get('CFBundleIdentifier') or '').lower() == bundle_id.lower():
                                    data = application_icon(app_path)
                                    if data:
                                        return data
                        except Exception:
                            pass
            except OSError:
                pass

    # 2. Try Launch Services / system with bundle identifier
    if bundle_id:
        data = application_icon(bundle_id)
        if data:
            return data

    # 3. Check if ghost path itself has an icon or is an app
    if os.path.exists(path):
        data = application_icon(path)
        if data:
            return data

    return None

