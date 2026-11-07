"""Conservative profiles and declarative, non-executable JSON cleanup rules."""

import glob
import json
import os
from pathlib import Path

from .cleanup import guard_ok
from .common import dir_size
from .errors import APIError

PROFILES = {
    "minimal": {
        "name": "Minimal",
        "description": "Rebuildable system logs and app caches.",
        "categories": ["System Junk", "App Caches"],
    },
    "developer": {
        "name": "Developer",
        "description": "Minimal plus rebuildable development caches.",
        "categories": ["System Junk", "App Caches", "Developer & Pro Tools"],
    },
    "designer": {
        "name": "Designer",
        "description": "Rebuildable caches, including creative tools; keeps original media.",
        "categories": ["System Junk", "App Caches", "Developer & Pro Tools"],
    },
}
CREATIVE = ("adobe", "davinci", "resolve", "figma", "sketch", "blender", "affinity")


def profile_items(items, name):
    if not isinstance(name, str) or name not in PROFILES:
        raise APIError(400, "Choose minimal, developer, or designer.")
    categories = PROFILES[name]["categories"]
    return [
        i
        for i in items
        if i.category in categories
        and i.safety == "safe"
        and i.action == "trash"
        and not (i.protected or i.managed or i.manual or i.readonly or i.keep)
        and (
            name != "designer"
            or i.category != "Developer & Pro Tools"
            or any(word in (i.name + i.path).lower() for word in CREATIVE)
        )
    ]


def rules_file():
    return Path.home() / "Library/Application Support/Mac Deep Cleaner/rules.json"


def validate_rules(document):
    if (
        not isinstance(document, dict)
        or set(document) != {"rules"}
        or not isinstance(document["rules"], list)
        or len(document["rules"]) > 50
    ):
        raise APIError(400, "Use a JSON object with a rules array (at most 50 rules).")
    names = set()
    for rule in document["rules"]:
        if not isinstance(rule, dict) or set(rule) != {"name", "path", "reason"}:
            raise APIError(
                400, "Each rule needs only name, path, and reason. Commands are not supported."
            )
        if any(
            not isinstance(rule[k], str) or not rule[k].strip() or len(rule[k]) > 500 for k in rule
        ):
            raise APIError(400, "Rule fields must be nonempty strings of at most 500 characters.")
        pattern = rule["path"]
        # Restrict plugins to children of user caches; arbitrary home globs are too broad.
        if (
            not pattern.startswith("~/Library/Caches/")
            or ".." in Path(pattern).parts
            or "**" in pattern
            or "\x00" in pattern
            or len(Path(pattern).parts) < 5
            or any(c in Path(pattern).parts[3] for c in "*?[")
        ):
            raise APIError(
                400,
                "Rule paths must target children of one named ~/Library/Caches/<app>/ directory; recursive globs are not supported.",
            )
        if rule["name"] in names:
            raise APIError(400, "Rule names must be unique.")
        names.add(rule["name"])
    return document


def load_rules():
    try:
        return validate_rules(json.loads(rules_file().read_text()))
    except FileNotFoundError:
        return {"rules": []}


def scan_rules(scanner):
    try:
        rules = load_rules()["rules"]
    except (OSError, ValueError, APIError) as exc:
        scanner.say("Custom rules skipped: " + str(exc))
        return
    for rule in rules:
        for path in sorted(glob.glob(os.path.expanduser(rule["path"])))[:500]:
            if guard_ok(path):
                scanner.add(
                    category="Custom Rules",
                    name=rule["name"] + ": " + Path(path).name,
                    path=path,
                    size=dir_size(path),
                    safety="caution",
                    manual=True,
                    reason=rule["reason"],
                    regen="Custom rule; review its contents before moving to Trash.",
                )
