"""Startup and extension inspection, and slimming of disposable application copies."""

import glob
import json
import os
import platform
import plistlib
import secrets
import shutil
import subprocess
import sys
from pathlib import Path

from .common import dir_size, fingerprint
from .errors import APIError

BROWSERS = {
    "Chrome": ("Google Chrome", "Library/Application Support/Google/Chrome", "chrome://extensions"),
    "Arc": ("Arc", "Library/Application Support/Arc/User Data", "arc://extensions"),
    "Firefox": ("Firefox", "Library/Application Support/Firefox/Profiles", "about:addons"),
    "Safari": (
        "Safari",
        "Library/Containers/com.apple.Safari/Data/Library/Safari/AppExtensions",
        None,
    ),
}


def startup_items(home=None):
    home = Path(home or Path.home())
    result = []
    for base, editable in (
        (home / "Library/LaunchAgents", True),
        (Path("/Library/LaunchAgents"), False),
        (Path("/Library/LaunchDaemons"), False),
    ):
        for path in sorted(base.glob("*.plist"))[:300]:
            try:
                if path.resolve() != path or path.stat().st_size > 1_000_000:
                    continue
                value = plistlib.loads(path.read_bytes())
                label = value.get("Label", "")
                if not isinstance(label, str) or not label or "/" in label:
                    continue
                args = value.get("ProgramArguments", [])
                executable = value.get("Program") or (
                    args[0] if isinstance(args, list) and args else ""
                )
                reasons = []
                if value.get("RunAtLoad"):
                    reasons.append("starts when loaded at login")
                if value.get("KeepAlive"):
                    reasons.append("launchd keeps it running")
                if value.get("StartCalendarInterval") or value.get("StartInterval"):
                    reasons.append("runs on a schedule")
                result.append(
                    {
                        "path": str(path),
                        "label": label,
                        "program": str(executable),
                        "explanation": "; ".join(reasons)
                        or "starts on demand or from another trigger",
                        "editable": editable
                        and not label.startswith(("com.apple.", "com.macdeepcleaner.")),
                        "identity": fingerprint(str(path)),
                    }
                )
            except (OSError, ValueError, TypeError, AttributeError, plistlib.InvalidFileException):
                continue
    return result


def startup_change(item, enabled):
    if sys.platform != "darwin":
        raise APIError(400, "Startup controls require macOS.")
    current = next((i for i in startup_items() if i["path"] == item["path"]), None)
    if not current or not current["editable"] or current["identity"] != item["identity"]:
        raise APIError(409, "The startup item changed. Refresh and review it again.")
    target = f"gui/{os.getuid()}/" + item["label"]
    subprocess.run(
        ["/bin/launchctl", "enable" if enabled else "disable", target],
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    )
    return {
        "message": "Enabled for future launches."
        if enabled
        else "Disabled for future launches. A currently running process continues until logout."
    }


def browser_extensions(home=None):
    home = Path(home or Path.home())
    result = []
    for browser, (app, relative, url) in BROWSERS.items():
        base = home / relative
        extensions = []
        errors = []
        patterns = (
            ("*/extensions.json",) if browser == "Firefox" else ("*/Extensions/*/*/manifest.json",)
        )
        if browser != "Safari":
            for pattern in patterns:
                for raw in glob.glob(str(base / pattern))[:500]:
                    path = Path(raw)
                    try:
                        if path.resolve() != path or path.stat().st_size > 4_000_000:
                            continue
                        data = json.loads(path.read_text())
                        if browser == "Firefox":
                            for addon in data.get("addons", []):
                                if addon.get("type") == "extension":
                                    extensions.append(
                                        {
                                            "name": addon.get("defaultLocale", {}).get(
                                                "name", addon.get("id", "Extension")
                                            ),
                                            "version": addon.get("version", ""),
                                            "profile": path.parent.name,
                                        }
                                    )
                        else:
                            extensions.append(
                                {
                                    "name": data.get("name", path.parent.parent.name),
                                    "version": data.get("version", ""),
                                    "profile": path.parents[3].name,
                                }
                            )
                    except (OSError, ValueError, TypeError, AttributeError):
                        errors.append("Some extension metadata could not be read.")
        result.append(
            {
                "name": browser,
                "installed": base.exists(),
                "extensions": extensions,
                "notice": "Manage signed app extensions in Safari → Settings → Extensions."
                if browser == "Safari"
                else "Remove extensions in the browser so its profile stays consistent.",
                "errors": sorted(set(errors)),
            }
        )
    return result


def open_extensions(browser):
    if browser not in BROWSERS or sys.platform != "darwin":
        raise APIError(400, "Choose a supported browser on macOS.")
    app, _root, url = BROWSERS[browser]
    subprocess.run(
        ["/usr/bin/open", "-a", app, *([url] if url else [])],
        check=True,
        capture_output=True,
        timeout=10,
    )
    return {"ok": True}


def slimming_inventory(installed):
    result = []
    for name, bundle_id, raw in installed[:200]:
        path = Path(raw)
        if str(bundle_id).startswith("com.apple.") or path.resolve() != path:
            continue
        languages = []
        for language in sorted((path / "Contents/Resources").glob("*.lproj")):
            if language.resolve() == language:
                languages.append({"name": language.stem, "bytes": dir_size(str(language))})
        result.append(
            {
                "name": name,
                "path": raw,
                "languages": languages,
                "identity": fingerprint(raw),
                "size": dir_size(raw),
            }
        )
    return result


def slim_copy(item, keep):
    """No installed bundle is modified; an explicitly reviewed copy is ad-hoc signed."""
    if sys.platform != "darwin":
        raise APIError(400, "Application slimming requires macOS.")
    if not isinstance(keep, list) or any(not isinstance(k, str) or len(k) > 40 for k in keep):
        raise APIError(400, "Choose language names to retain.")
    source = Path(item["path"])
    if source.resolve() != source or fingerprint(str(source)) != item["identity"]:
        raise APIError(409, "The application changed after review.")
    destination_root = Path.home() / "Downloads"
    if destination_root.resolve() != destination_root:
        raise APIError(409, "Downloads cannot be a symbolic link.")
    if shutil.disk_usage(destination_root).free < item["size"] + 1_000_000_000:
        raise APIError(400, "An app copy plus 1 GB of free space is required.")
    destination = destination_root / ("MDC-Slimmed-" + secrets.token_hex(6))
    destination.mkdir(mode=0o700)
    copy = destination / source.name
    # ditto retains app metadata; the source is never an output argument.
    subprocess.run(
        ["/usr/bin/ditto", str(source), str(copy)], check=True, capture_output=True, timeout=600
    )
    # macOS resources use both legacy language names and BCP-47-like tags.
    # Retaining a language conservatively keeps its regional/script variants.
    aliases = {'english':'en', 'french':'fr', 'german':'de', 'spanish':'es',
               'italian':'it', 'japanese':'ja', 'korean':'ko', 'chinese':'zh',
               'dutch':'nl', 'portuguese':'pt', 'russian':'ru', 'arabic':'ar',
               'swedish':'sv', 'danish':'da', 'norwegian':'no', 'finnish':'fi',
               'polish':'pl', 'czech':'cs', 'greek':'el', 'turkish':'tr'}
    def language_key(value):
        value = value.strip().replace('_', '-').lower()
        return aliases.get(value, value.split('-')[0])
    retained = {language_key(value) for value in keep} | {'base', 'en'}
    removed, thinned = [], 0
    arch = platform.machine()
    for root, dirs, files in os.walk(copy, followlinks=False):
        dirs[:] = [d for d in dirs if not (Path(root) / d).is_symlink()]
        for name in list(dirs):
            path = Path(root) / name
            if (
                name.endswith(".lproj")
                and language_key(path.stem) not in retained
            ):
                shutil.rmtree(path)
                dirs.remove(name)
                removed.append(name)
        for name in files:
            path = Path(root) / name
            if path.is_symlink() or not path.is_file():
                continue
            with path.open("rb") as handle:
                magic = handle.read(4)
            if magic not in (
                b"\xca\xfe\xba\xbe",
                b"\xbe\xba\xfe\xca",
                b"\xca\xfe\xba\xbf",
                b"\xbf\xba\xfe\xca",
            ):
                continue
            info = subprocess.run(
                ["/usr/bin/lipo", "-archs", str(path)],
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )
            if info.returncode or arch not in info.stdout.split() or len(info.stdout.split()) < 2:
                continue
            temporary = path.with_name(".mdc-thin-" + secrets.token_hex(6))
            subprocess.run(
                ["/usr/bin/lipo", str(path), "-thin", arch, "-output", str(temporary)],
                check=True,
                capture_output=True,
                timeout=30,
            )
            shutil.copystat(path, temporary)
            os.replace(temporary, path)
            thinned += 1
    subprocess.run(
        ["/usr/bin/codesign", "--force", "--deep", "--sign", "-", str(copy)],
        check=True,
        capture_output=True,
        timeout=180,
    )
    return {
        "path": str(copy),
        "removed_languages": sorted(set(removed)),
        "thinned_binaries": thinned,
        "saved_bytes": max(0, item["size"] - dir_size(str(copy))),
        "message": "Created an ad-hoc signed copy. Test it before replacing anything; updates, entitlements, and notarization may not work. The installed app is unchanged.",
    }
