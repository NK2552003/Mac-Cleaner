"""Sleep and power optimizer helpers."""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from constants import CONFIG_DIR

logger = logging.getLogger(__name__)


@dataclass
class PowerProfile:
    """Parsed pmset custom settings."""
    battery: Dict[str, str]
    ac: Dict[str, str]


@dataclass
class PowerChange:
    """One recommended change."""
    key: str
    current: Optional[str]
    recommended: str
    scope: str  # "battery", "ac", or "all"


@dataclass
class ApplyResult:
    """Summary of apply/restore run."""
    success: bool
    message: str
    changes: List[PowerChange]


_RECOMMENDED: Dict[str, str] = {
    "displaysleep": "10",
    "sleep": "30",
    "powernap": "0",
    "tcpkeepalive": "1",
    "standby": "1",
    "standbydelayhigh": "86400",
    "standbydelaylow": "3600",
    "autopoweroff": "1",
    "autopoweroffdelay": "28800",
}

_PROFILE_PATH = CONFIG_DIR / "power_profile.json"


def _run(args: List[str], timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def parse_pmset_custom(output: str) -> PowerProfile:
    battery: Dict[str, str] = {}
    ac: Dict[str, str] = {}
    current: Optional[Dict[str, str]] = None

    for raw in output.splitlines():
        line = raw.strip()
        if not line:
            continue
        lower = line.lower()
        if lower.startswith("battery power"):
            current = battery
            continue
        if lower.startswith("ac power"):
            current = ac
            continue
        if current is None:
            continue
        parts = line.split()
        if len(parts) >= 2:
            key = parts[0]
            value = parts[-1]
            current[key] = value

    return PowerProfile(battery=battery, ac=ac)


def get_power_profile() -> Optional[PowerProfile]:
    try:
        result = _run(["pmset", "-g", "custom"], timeout=10)
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.debug("pmset failed: %s", exc)
        return None
    if result.returncode != 0:
        return None
    return parse_pmset_custom(result.stdout)


def save_profile(profile: PowerProfile, path: Path = _PROFILE_PATH) -> None:
    payload = {
        "battery": profile.battery,
        "ac": profile.ac,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))


def load_profile(path: Path = _PROFILE_PATH) -> Optional[PowerProfile]:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        return PowerProfile(battery=data.get("battery", {}), ac=data.get("ac", {}))
    except (json.JSONDecodeError, OSError):
        return None


def diff_recommendations(profile: PowerProfile, scope: str = "all") -> List[PowerChange]:
    changes: List[PowerChange] = []

    def _maybe_add(current_map: Dict[str, str], scope_label: str) -> None:
        for key, recommended in _RECOMMENDED.items():
            if key not in current_map:
                continue
            current = current_map.get(key)
            if current != recommended:
                changes.append(PowerChange(
                    key=key,
                    current=current,
                    recommended=recommended,
                    scope=scope_label,
                ))

    if scope in ("battery", "all"):
        _maybe_add(profile.battery, "battery" if scope == "battery" else "all")
    if scope in ("ac", "all"):
        _maybe_add(profile.ac, "ac" if scope == "ac" else "all")

    return changes


def apply_changes(changes: List[PowerChange]) -> ApplyResult:
    if not changes:
        return ApplyResult(True, "No changes required", changes)

    ok = True
    for change in changes:
        flag = "-a"
        if change.scope == "battery":
            flag = "-b"
        elif change.scope == "ac":
            flag = "-c"
        try:
            result = _run(["pmset", flag, change.key, change.recommended], timeout=10)
            if result.returncode != 0:
                ok = False
        except (OSError, subprocess.TimeoutExpired):
            ok = False

    return ApplyResult(ok, "Applied power settings" if ok else "Some settings failed", changes)


def apply_recommended(scope: str = "all") -> ApplyResult:
    profile = get_power_profile()
    if profile is None:
        return ApplyResult(False, "Unable to read current power settings", [])

    save_profile(profile)
    changes = diff_recommendations(profile, scope=scope)
    return apply_changes(changes)


def restore_profile(scope: str = "all") -> ApplyResult:
    saved = load_profile()
    if saved is None:
        return ApplyResult(False, "No saved power profile found", [])

    changes: List[PowerChange] = []

    def _build(map_data: Dict[str, str], scope_label: str) -> None:
        for key, value in map_data.items():
            changes.append(PowerChange(
                key=key,
                current=None,
                recommended=str(value),
                scope=scope_label,
            ))

    if scope in ("battery", "all"):
        _build(saved.battery, "battery" if scope == "battery" else "all")
    if scope in ("ac", "all"):
        _build(saved.ac, "ac" if scope == "ac" else "all")

    return apply_changes(changes)
