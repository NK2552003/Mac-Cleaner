"""Global dry-run helpers."""

from __future__ import annotations

from typing import Optional

import click
from rich.console import Console

DRY_RUN_KEY = "dry_run"


def set_dry_run(ctx: click.Context, value: bool) -> None:
    """Store dry-run flag in the Click context."""
    ctx.ensure_object(dict)
    ctx.obj[DRY_RUN_KEY] = bool(value)


def dry_run_enabled(ctx: Optional[click.Context]) -> bool:
    """Return True when global dry-run is enabled."""
    if ctx is None:
        return False
    obj = getattr(ctx, "obj", None) or {}
    return bool(obj.get(DRY_RUN_KEY, False))


def skip_if_dry_run(ctx: Optional[click.Context], console: Console, action: str) -> bool:
    """Print a warning and return True when dry-run blocks an action."""
    if dry_run_enabled(ctx):
        console.print(f"[yellow]Dry-run enabled; {action} skipped.[/yellow]")
        return True
    return False
