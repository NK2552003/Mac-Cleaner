"""Menu bar companion helpers (SwiftBar/xbar plugin)."""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

from constants import CONFIG_DIR, HOME
from utils import bytes_human


SWIFTBAR_DIR = HOME / "Library" / "Application Support" / "SwiftBar" / "Plugins"
XBAR_DIR = HOME / "Library" / "Application Support" / "xbar" / "plugins"


@dataclass
class MenubarStatus:
    """Computed status for the menu bar plugin."""
    label: str
    subtitle: str
    orphan_bytes: int
    junk_bytes: int
    dev_junk_bytes: int
    scanned_at: str


def detect_plugin_dirs() -> Dict[str, Path]:
    """Return available plugin directories for menu bar tools."""
    dirs: Dict[str, Path] = {}
    if SWIFTBAR_DIR.exists():
        dirs["swiftbar"] = SWIFTBAR_DIR
    if XBAR_DIR.exists():
        dirs["xbar"] = XBAR_DIR
    return dirs


def _command_path() -> str:
    return shutil.which("mac-cleaner") or shutil.which("mdc") or "mac-cleaner"


def build_status_from_history() -> Optional[MenubarStatus]:
    """Use the most recent scan record to build a status."""
    try:
        from config.history import latest_scan
    except Exception:
        return None

    record = latest_scan()
    if record is None:
        return None

    orphan_bytes = record.orphan_bytes
    junk_bytes = record.junk_bytes
    dev_bytes = record.dev_junk_bytes
    total = orphan_bytes + junk_bytes + dev_bytes

    label = f"Cleaner: {bytes_human(total)}"
    subtitle = f"Last scan: {record.scanned_at:%Y-%m-%d %H:%M}"

    return MenubarStatus(
        label=label,
        subtitle=subtitle,
        orphan_bytes=orphan_bytes,
        junk_bytes=junk_bytes,
        dev_junk_bytes=dev_bytes,
        scanned_at=record.scanned_at.isoformat(),
    )


def format_swiftbar(status: MenubarStatus) -> str:
    """Format status as a SwiftBar/xbar-compatible script output."""
    cmd = _command_path()
    lines = [status.label, "---"]
    lines.append(status.subtitle)
    lines.append(f"Orphans: {bytes_human(status.orphan_bytes)}")
    lines.append(f"Junk: {bytes_human(status.junk_bytes)}")
    lines.append(f"Dev Junk: {bytes_human(status.dev_junk_bytes)}")
    lines.append("---")
    lines.append(
        f"Run scan | bash={cmd} param1=scan terminal=true refresh=true"
    )
    lines.append(
        f"Open history | bash={cmd} param1=history terminal=true"
    )
    return "\n".join(lines)


def install_plugin(
    target_dir: Path,
    interval_minutes: int = 15,
) -> Path:
    """Install a SwiftBar/xbar plugin script."""
    target_dir.mkdir(parents=True, exist_ok=True)
    filename = f"mac-cleaner.{interval_minutes}m.sh"
    path = target_dir / filename

    script = "\n".join([
        "#!/bin/sh",
        "# mac-cleaner menu bar status",
        f"{_command_path()} menubar status --format swiftbar",
        "",
    ])
    path.write_text(script)
    os.chmod(path, 0o755)
    return path


def remove_plugin(target_dir: Path) -> int:
    """Remove mac-cleaner plugins from a directory."""
    removed = 0
    if not target_dir.exists():
        return 0
    for child in target_dir.iterdir():
        if child.name.startswith("mac-cleaner.") and child.suffix == ".sh":
            try:
                child.unlink()
                removed += 1
            except OSError:
                continue
    return removed


def ensure_config_dir() -> Path:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    return CONFIG_DIR
