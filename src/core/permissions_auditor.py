"""Permissions auditor for macOS TCC database."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

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


def _read_access_rows(db_path: Path) -> List[PermissionEntry]:
    if not db_path.exists():
        return []

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT service, client, client_type, auth_value, auth_reason, auth_version, last_modified "
            "FROM access"
        ).fetchall()
    finally:
        conn.close()

    entries: List[PermissionEntry] = []
    for row in rows:
        entries.append(PermissionEntry(
            service=row["service"],
            client=row["client"],
            client_type=int(row["client_type"]),
            auth_value=int(row["auth_value"]),
            auth_reason=int(row["auth_reason"]),
            auth_version=int(row["auth_version"]),
            last_modified=int(row["last_modified"]),
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
    for path in paths:
        try:
            entries.extend(_read_access_rows(path))
        except sqlite3.Error:
            continue

    warnings: List[str] = []
    risky = [e for e in entries if e.service in RISKY_SERVICES and e.allowed]
    if risky:
        warnings.append(
            f"{len(risky)} app(s) have sensitive permissions (Full Disk Access, Accessibility, Screen Recording)"
        )

    return PermissionsReport(entries=entries, warnings=warnings)
