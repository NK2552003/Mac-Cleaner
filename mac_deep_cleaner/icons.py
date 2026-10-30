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
