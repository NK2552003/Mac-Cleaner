"""
Backward-compatible shim for v1.5.0 reporter additions.

The project now consolidates all reporting helpers into:
    mac_cleaner.reporting.reporter

This module re-exports the merged functions so older imports keep working.
"""

from __future__ import annotations

from .reporter import (  # noqa: F401
    print_duplicate_report,
    print_large_file_report,
    print_symlink_report,
    print_ios_backup_report,
    print_language_pack_report,
    print_diff_report,
)
