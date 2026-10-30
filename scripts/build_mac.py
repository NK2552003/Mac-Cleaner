#!/usr/bin/env python3
"""Build an offline native macOS app using the current Python architecture."""
import argparse
import os
from pathlib import Path
import platform
import re
import runpy
import plistlib
import shutil
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
app_version = runpy.run_path(str(root / 'mac_deep_cleaner/__init__.py'))['__version__']
parser = argparse.ArgumentParser()
parser.add_argument('--output', type=Path, default=root / 'dist')
parser.add_argument('--work', type=Path, default=root / 'build')
parser.add_argument('--identity', default='-', help='Developer ID Application identity; default is ad-hoc signing')
args = parser.parse_args()
if sys.platform != 'darwin':
    parser.error('Build on macOS.')
args.output = args.output.resolve()
args.work = args.work.resolve()
args.work.mkdir(parents=True, exist_ok=True)
args.output.mkdir(parents=True, exist_ok=True)
subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onedir', '--console',
                '--name', 'mac-deep-cleaner-engine', '--distpath', str(args.work / 'engine-dist'),
                '--workpath', str(args.work / 'pyinstaller'), '--specpath', str(args.work),
                '--add-data', f'{root / "mac_deep_cleaner/web"}:mac_deep_cleaner/web',
                '--add-data', f'{root / "assets"}:mac_deep_cleaner/assets',
                '--exclude-module', 'rich', '--exclude-module', 'questionary',
                *(['--codesign-identity', args.identity] if args.identity != '-' else []),
                str(root / 'mc.py')], cwd=root, check=True)
app = args.output / 'Mac Deep Cleaner.app'
if app.exists():
    shutil.rmtree(app)
contents = app / 'Contents'
(contents / 'MacOS').mkdir(parents=True)
resources = contents / 'Resources'
resources.mkdir()
shutil.copytree(args.work / 'engine-dist/mac-deep-cleaner-engine', resources / 'engine', symlinks=True)
arch = platform.machine()
# A bundled Homebrew Python can require a newer OS than the Swift shell.
# Derive the actual minimum from every shipped Mach-O, not the build host.
minimum = (14, 0)
for binary in (resources / 'engine').rglob('*'):
    if not binary.is_file() or binary.is_symlink():
        continue
    with binary.open('rb') as handle:
        magic = handle.read(4)
    if magic not in (b'\xcf\xfa\xed\xfe', b'\xfe\xed\xfa\xcf', b'\xca\xfe\xba\xbe'):
        continue
    result = subprocess.run(['xcrun', 'vtool', '-show-build', str(binary)], capture_output=True, text=True)
    for version in re.findall(r'minos\s+([0-9.]+)', result.stdout):
        minimum = max(minimum, tuple(int(n) for n in version.split('.')))
minimum_version = '.'.join(str(n) for n in minimum)
subprocess.run(['xcrun', 'swiftc', '-O', '-target', f'{arch}-apple-macosx{minimum_version}',
                str(root / 'desktop/main.swift'), str(root / 'desktop/window_chrome.swift'), '-o', str(contents / 'MacOS/mac-deep-cleaner')], check=True)
subprocess.run(['xcrun', 'swiftc', '-O', '-target', f'{arch}-apple-macosx{minimum_version}',
                str(root / 'desktop/app_icon.swift'), '-o', str(resources / 'engine/app-icon-helper')], check=True)
subprocess.run(['codesign', '--force', '--sign', args.identity, str(resources / 'engine/app-icon-helper')], check=True)
iconset = args.work / 'AppIcon.iconset'
subprocess.run(['xcrun', 'swift', str(root / 'desktop/make_icon.swift'), str(iconset), str(root / 'assets/app_icon.png')], check=True)
subprocess.run(['iconutil', '-c', 'icns', str(iconset), '-o', str(resources / 'AppIcon.icns')], check=True)
info = {'CFBundleName' : 'Mac Deep Cleaner', 'CFBundleDisplayName': 'Mac Deep Cleaner',
        'CFBundleIdentifier': 'com.macdeepcleaner.desktop', 'CFBundleExecutable': 'mac-deep-cleaner',
        'CFBundleIconFile': 'AppIcon', 'CFBundlePackageType': 'APPL', 'CFBundleShortVersionString': app_version, 'CFBundleVersion': app_version,
        'LSMinimumSystemVersion': minimum_version, 'NSHighResolutionCapable': True,
        'NSAppleEventsUsageDescription': 'Mac Deep Cleaner asks Finder to move only the files you review and approve to Trash.',
        'NSDocumentsFolderUsageDescription': 'Analyze storage and review cleanup in your Documents folder.',
        'NSDownloadsFolderUsageDescription': 'Analyze downloaded files and review cleanup.',
        'NSDesktopFolderUsageDescription': 'Analyze files on your Desktop and review cleanup.',
        'NSAppTransportSecurity': {'NSAllowsLocalNetworking': True},
        'NSHumanReadableCopyright': 'Mac Deep Cleaner'}
with (contents / 'Info.plist').open('wb') as handle:
    plistlib.dump(info, handle)
# Sign nested Python binaries first (PyInstaller did this), then the app wrapper.
subprocess.run(['codesign', '--force', '--sign', args.identity,
                *(['--options', 'runtime', '--timestamp'] if args.identity != '-' else ['--timestamp=none']),
                str(app)], check=True)
subprocess.run(['codesign', '--verify', '--deep', '--strict', str(app)], check=True)
result = subprocess.run([str(resources / 'engine/mac-deep-cleaner-engine'), '--version'], capture_output=True, text=True, check=True)
if result.stdout.strip() != f'mac-deep-cleaner {app_version}':
    raise RuntimeError(f'Bundled runtime startup check failed: {result.stdout}')
print(f'{app} ({arch}, macOS {minimum_version}+)')
