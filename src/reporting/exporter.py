"""
Mac Deep Cleaner v1.0.0 — Export Module
=====================================
Exports scan results to JSON or YAML format.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from rich.console import Console

from config.models import DevJunkEntry, JunkEntry, OrphanEntry
from utils import bytes_human

console = Console()


def export_json(
    orphans: Dict[str, List[OrphanEntry]],
    junk: List[JunkEntry],
    dev_junk: Optional[List[DevJunkEntry]],
    output_path: str,
) -> None:
    """Export full scan results to JSON."""
    data = {
        "tool": "Mac Deep Cleaner v1.0.0",
        "generated_at": datetime.now().isoformat(),
        "orphaned_apps": {
            name: {
                "total_size": sum(e.size for e in entries),
                "total_size_human": bytes_human(sum(e.size for e in entries)),
                "items": [e.to_dict() for e in entries],
            }
            for name, entries in orphans.items()
        },
        "junk": {
            "user_junk": [j.to_dict() for j in junk if not j.is_system],
            "system_caches": [j.to_dict() for j in junk if j.is_system],
        },
        "dev_junk": [j.to_dict() for j in (dev_junk or [])],
        "summary": {
            "orphan_app_count": len(orphans),
            "orphan_item_count": sum(len(v) for v in orphans.values()),
            "orphan_bytes": sum(sum(e.size for e in v) for v in orphans.values()),
            "orphan_size_human": bytes_human(
                sum(sum(e.size for e in v) for v in orphans.values())
            ),
            "user_junk_count": sum(1 for j in junk if not j.is_system),
            "user_junk_bytes": sum(j.size for j in junk if not j.is_system),
            "user_junk_size_human": bytes_human(
                sum(j.size for j in junk if not j.is_system)
            ),
            "system_cache_count": sum(1 for j in junk if j.is_system),
            "system_cache_bytes": sum(j.size for j in junk if j.is_system),
            "dev_junk_count": sum(1 for _ in (dev_junk or [])),
            "dev_junk_bytes": sum(j.size for j in (dev_junk or [])),
            "dev_junk_size_human": bytes_human(sum(j.size for j in (dev_junk or []))),
        },
    }

    try:
        with open(output_path, "w") as f:
            json.dump(data, f, indent=2, default=str)
        console.print(f"  [green]✓ Results exported to {output_path}[/green]")
    except OSError as e:
        console.print(f"  [red]✗ Failed to export: {e}[/red]")


def export_yaml(
    orphans: Dict[str, List[OrphanEntry]],
    junk: List[JunkEntry],
    dev_junk: Optional[List[DevJunkEntry]],
    output_path: str,
) -> None:
    """Export full scan results to YAML (requires pyyaml)."""
    try:
        import yaml
    except ImportError:
        console.print("[red]✗ PyYAML not installed. Run: pip install pyyaml[/red]")
        return

    data = {
        "tool": "Mac Deep Cleaner v1.0.0",
        "generated_at": datetime.now().isoformat(),
        "orphaned_apps": {
            name: [e.to_dict() for e in entries]
            for name, entries in orphans.items()
        },
        "junk": [j.to_dict() for j in junk],
        "dev_junk": [j.to_dict() for j in (dev_junk or [])],
    }

    try:
        with open(output_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
        console.print(f"  [green]✓ Results exported to {output_path}[/green]")
    except OSError as e:
        console.print(f"  [red]✗ Failed to export: {e}[/red]")
