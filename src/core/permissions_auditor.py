"""Permissions auditor for macOS TCC database."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from constants import HOME

USER_TCC_DB = HOME / "Library" / "Application Support" / "com.apple.TCC" / "TCC.db"
SYSTEM_TCC_DB = Path("/Library/Application Support/com.apple.TCC/TCC.db")


SERVICE_LABELS: Dict[str, str] = {
    "kTCCServiceSystemPolicyAllFiles": "Full Disk Access",
    "kTCCServiceAccessibility": "Accessibility",
    "kTCCServiceScreenCapture": "Screen Recording",
    "kTCCServiceAppleEvents": "Apple Events",
    "kTCCServiceDeveloperTool": "Developer Tools",
    "kTCCServiceListenEvent": "Input Monitoring",
    "kTCCServiceCamera": "Camera",
    "kTCCServiceMicrophone": "Microphone",
}

RISKY_SERVICES = {
    "kTCCServiceSystemPolicyAllFiles",
    "kTCCServiceAccessibility",
    "kTCCServiceScreenCapture",
    "kTCCServiceAppleEvents",
    "kTCCServiceDeveloperTool",
    "kTCCServiceListenEvent",
}


@dataclass
class PermissionEntry:
    """One row from the TCC access table."""
    service: str
    client: str
    client_type: int
    auth_value: int
    auth_reason: int
    auth_version: int
    last_modified: int

    @property
    def service_name(self) -> str:
        return SERVICE_LABELS.get(self.service, self.service)

    @property
    def allowed(self) -> bool:
        return int(self.auth_value) == 1


@dataclass
class PermissionsReport:
    """Summary of permissions by service."""
    entries: List[PermissionEntry]
    warnings: List[str] = field(default_factory=list)

    def by_service(self) -> Dict[str, List[PermissionEntry]]:
        grouped: Dict[str, List[PermissionEntry]] = {}
        for entry in self.entries:
            grouped.setdefault(entry.service, []).append(entry)
        return grouped


def _column_names(conn: sqlite3.Connection) -> Sequence[str]:
    rows = conn.execute("PRAGMA table_info(access)").fetchall()
    names: List[str] = []
    for row in rows:
        try:
            names.append(row["name"])
        except (KeyError, IndexError, TypeError):
            try:
                names.append(row[1])
            except (IndexError, TypeError):
                continue
    return names


def _row_value(row: sqlite3.Row, key: str, default: int = 0) -> int:
    try:
        value = row[key]
    except (KeyError, IndexError, TypeError):
        return default
    if value is None:
        return default
    return int(value)


def _read_access_rows(db_path: Path) -> List[PermissionEntry]:
    if not db_path.exists():
        return []

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    rows: List[sqlite3.Row]
    try:
        names = set(_column_names(conn))
        auth_col = None
        if "auth_value" in names:
            auth_col = "auth_value"
        elif "allowed" in names:
            auth_col = "allowed"

        if auth_col is None:
            return []

        select_cols = ["service", "client", auth_col]
        for optional in ["client_type", "auth_reason", "auth_version", "last_modified"]:
            if optional in names:
                select_cols.append(optional)

        rows = conn.execute(
            f"SELECT {', '.join(select_cols)} FROM access"
        ).fetchall()
    finally:
        conn.close()

    entries: List[PermissionEntry] = []
    for row in rows:
        auth_value = _row_value(row, "auth_value", _row_value(row, "allowed", 0))
        entries.append(PermissionEntry(
            service=str(row["service"]),
            client=str(row["client"]),
            client_type=_row_value(row, "client_type", 0),
            auth_value=auth_value,
            auth_reason=_row_value(row, "auth_reason", 0),
            auth_version=_row_value(row, "auth_version", 0),
            last_modified=_row_value(row, "last_modified", 0),
        ))
    return entries


def audit_permissions(
    include_system: bool = False,
    db_paths: Optional[List[Path]] = None,
) -> PermissionsReport:
    """Audit TCC permissions for the current user."""
    paths = db_paths or [USER_TCC_DB]
    if include_system:
        paths = paths + [SYSTEM_TCC_DB]

    entries: List[PermissionEntry] = []
    errors: List[str] = []
    for path in paths:
        try:
            entries.extend(_read_access_rows(path))
        except sqlite3.Error as exc:
            errors.append(f"{path}: {exc}")
            continue

    warnings: List[str] = []
    risky = [e for e in entries if e.service in RISKY_SERVICES and e.allowed]
    if risky:
        warnings.append(
            f"{len(risky)} app(s) have sensitive permissions (Full Disk Access, Accessibility, Screen Recording)"
        )
    if errors and not entries:
        warnings.append("Permissions database could not be read. Full Disk Access may be required.")

    return PermissionsReport(entries=entries, warnings=warnings)
