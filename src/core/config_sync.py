"""Multi-Mac config sync helpers."""

from __future__ import annotations

import json
import platform
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from constants import CONFIG_DIR


@dataclass
class SyncResult:
    """Summary of a sync operation."""
    success: bool
    message: str
    path: Optional[Path] = None
    details: list[str] = field(default_factory=list)


def default_sync_dir(prefer_icloud: bool = True) -> Path:
    """Return the default sync directory."""
    if prefer_icloud:
        icloud_root = Path.home() / "Library" / "Mobile Documents" / "com~apple~CloudDocs"
        if icloud_root.exists():
            return icloud_root / "MacCleaner"
    return CONFIG_DIR / "sync"


def _write_meta(dest: Path) -> None:
    meta = {
        "host": platform.node(),
        "platform": platform.platform(),
        "updated_at": datetime.now().isoformat(),
    }
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "sync_meta.json").write_text(json.dumps(meta, indent=2))


def export_config(
    dest_dir: Optional[Path] = None,
    include_history: bool = False,
    prefer_icloud: bool = True,
) -> SyncResult:
    """Export config to a sync directory."""
    dest = dest_dir or default_sync_dir(prefer_icloud=prefer_icloud)
    config_path = CONFIG_DIR / "config.yaml"

    if not config_path.exists():
        return SyncResult(False, "No config.yaml found to export", dest)

    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy2(config_path, dest / "config.yaml")

    if include_history:
        history = CONFIG_DIR / "history"
        if history.exists():
            shutil.copytree(history, dest / "history", dirs_exist_ok=True)

    _write_meta(dest)
    return SyncResult(True, "Config exported", dest)


def import_config(
    src_dir: Optional[Path] = None,
    prefer_icloud: bool = True,
    backup: bool = True,
) -> SyncResult:
    """Import config from a sync directory."""
    src = src_dir or default_sync_dir(prefer_icloud=prefer_icloud)
    src_cfg = src / "config.yaml"
    if not src_cfg.exists():
        return SyncResult(False, "No config.yaml found in sync directory", src)

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    dest_cfg = CONFIG_DIR / "config.yaml"
    if backup and dest_cfg.exists():
        backup_path = CONFIG_DIR / f"config.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}.yaml"
        shutil.copy2(dest_cfg, backup_path)

    shutil.copy2(src_cfg, dest_cfg)
    return SyncResult(True, "Config imported", src)


def sync_status(dest_dir: Optional[Path] = None, prefer_icloud: bool = True) -> SyncResult:
    """Return sync metadata if present."""
    dest = dest_dir or default_sync_dir(prefer_icloud=prefer_icloud)
    meta = dest / "sync_meta.json"
    if not meta.exists():
        return SyncResult(False, "No sync metadata found", dest)

    return SyncResult(True, meta.read_text().strip(), dest)
