"""
Mac Deep Cleaner v1.2.0 — Cleaner Module
======================================
Handles deletion of orphan and junk files with safety checks,
audit logging, and optional staged-deletion (undo) support.

Changes from v1.2.0
---------------
- do_cleanup() now accepts an optional `session` parameter.
  When provided, files are moved to the staging area (undo.stage_file)
  instead of being permanently deleted.
- write_deletion_log() is unchanged — it logs staged moves too.
- All safety gates remain in place.
"""

from __future__ import annotations

from datetime import datetime
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from rich.console import Console
from rich.prompt import Confirm
from rich.table import Table

from constants import LOG_FILE
from config.models import JunkEntry, OrphanEntry
from core.safety import validate_path_for_deletion
from utils import bytes_human, safe_remove

logger = logging.getLogger(__name__)

console = Console()


def write_deletion_log(entries: List[Tuple[str, int]]) -> None:
    """Append a deletion record to the audit log file."""
    if not entries:
        return
    try:
        with open(LOG_FILE, "a") as f:
            f.write(f"\n{'=' * 60}\n")
            f.write(f"Mac Deep Cleaner v1.2.0 — Deletion Log\n")
            f.write(f"Timestamp: {datetime.now().isoformat()}\n")
            f.write(f"Items deleted: {len(entries)}\n")
            f.write(f"Total freed: {bytes_human(sum(s for _, s in entries))}\n")
            f.write(f"{'=' * 60}\n")
            for path_str, size in entries:
                f.write(f"  {bytes_human(size):>10}  {path_str}\n")
            f.write("\n")
    except OSError as exc:
        logger.debug("Failed to write deletion log: %s", exc)


def do_cleanup(
    orphans: Dict[str, List[OrphanEntry]],
    junk: List[JunkEntry],
    auto: bool = False,
    session=None,   # Optional[DeletionSession] — import avoided to prevent circular dep
) -> int:
    """
    Perform interactive or automatic cleanup.

    Args:
        orphans: Dict of app_name → list of OrphanEntry
        junk:    List of JunkEntry (only non-system items deleted)
        auto:    If True, delete everything without prompting
        session: If provided (DeletionSession), stage files for undo
                 instead of permanently deleting them.

    Returns:
        Total bytes freed (or staged).
    """
    freed = 0
    deleted: List[Tuple[str, int]] = []

    # Determine mode
    use_undo = session is not None
    if use_undo:
        from core.undo import stage_file

    console.rule("[bold]Cleanup", style="cyan")

    # ── Orphans ──────────────────────────────────────────────────────────
    if orphans:
        console.print("\n[bold]Orphaned app leftovers:[/bold]\n")

        sorted_apps = sorted(
            orphans.items(),
            key=lambda kv: sum(e.size for e in kv[1]),
            reverse=True,
        )

        for app_name, entries in sorted_apps:
            total = sum(e.size for e in entries)

            if auto:
                do_delete = True
            else:
                do_delete = Confirm.ask(
                    f"  {'Stage' if use_undo else 'Delete'} [bold red]{app_name}[/bold red] leftovers "
                    f"([yellow]{bytes_human(total)}[/yellow])?",
                    default=False,
                )

            if do_delete:
                for e in entries:
                    safe, reason = validate_path_for_deletion(e.path)
                    if not safe:
                        console.print(
                            f"  [yellow]⚠ Skipped[/yellow] {e.path.name} ({reason})"
                        )
                        continue

                    if use_undo:
                        ok, sz = stage_file(e.path, session, category="Orphan")
                    else:
                        ok, sz = safe_remove(e.path)

                    if ok:
                        freed += sz
                        deleted.append((str(e.path), sz))
                        verb = "Staged" if use_undo else "Deleted"
                        console.print(
                            f"  [green]✓ {verb}[/green]  {e.path.name}  "
                            f"([dim]{bytes_human(sz)}[/dim])"
                        )
                    else:
                        console.print(f"  [yellow]⚠ Failed[/yellow]  {e.path.name}")

    # ── User junk ────────────────────────────────────────────────────────
    user_junk = [j for j in junk if not j.is_system]
    if user_junk:
        junk_total = sum(j.size for j in user_junk)
        console.print(
            f"\n[bold]User junk[/bold]  "
            f"([yellow]{bytes_human(junk_total)}[/yellow] total)"
        )

        do_delete = auto or Confirm.ask(
            f"  {'Stage' if use_undo else 'Delete'} ALL user junk?",
            default=False,
        )

        if do_delete:
            for j in user_junk:
                safe, reason = validate_path_for_deletion(j.path)
                if not safe:
                    continue

                if use_undo:
                    ok, sz = stage_file(j.path, session, category="Junk")
                else:
                    ok, sz = safe_remove(j.path)

                if ok:
                    freed += sz
                    deleted.append((str(j.path), sz))

    # ── Audit log ────────────────────────────────────────────────────────
    write_deletion_log(deleted)

    # ── Save undo session manifest ────────────────────────────────────────
    if use_undo and session and deleted:
        session.save()
        console.print(
            f"\n  [dim]Staged session: {session.session_id[:8]}  "
            f"Restore with: mac-cleaner undo[/dim]"
        )

    return freed
