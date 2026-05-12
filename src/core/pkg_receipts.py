"""PKG receipt manager."""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class PkgReceipt:
    """A single pkg receipt entry."""
    identifier: str
    version: Optional[str] = None
    volume: Optional[str] = None
    location: Optional[str] = None
    install_time: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "identifier": self.identifier,
            "version": self.version,
            "volume": self.volume,
            "location": self.location,
            "install_time": self.install_time,
        }


def _run(args: List[str], timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def list_receipts(search: Optional[str] = None, limit: Optional[int] = None) -> List[str]:
    """List pkg receipt identifiers."""
    try:
        result = _run(["pkgutil", "--pkgs"], timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return []
    if result.returncode != 0:
        return []

    receipts = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if search:
        needle = search.lower()
        receipts = [r for r in receipts if needle in r.lower()]
    if limit is not None and limit > 0:
        receipts = receipts[:limit]
    return receipts


def get_receipt_info(identifier: str) -> Optional[PkgReceipt]:
    """Return detailed receipt info for a package id."""
    try:
        result = _run(["pkgutil", "--pkg-info", identifier], timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None

    data: Dict[str, str] = {}
    for line in result.stdout.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip().lower()] = value.strip()

    install_time = None
    if "install-time" in data:
        try:
            install_time = datetime.fromtimestamp(int(data["install-time"])).isoformat()
        except (ValueError, OSError):
            install_time = data.get("install-time")

    return PkgReceipt(
        identifier=identifier,
        version=data.get("version"),
        volume=data.get("volume"),
        location=data.get("location"),
        install_time=install_time,
    )


def forget_receipt(identifier: str) -> tuple[bool, str]:
    """Forget a pkg receipt."""
    try:
        result = _run(["pkgutil", "--forget", identifier], timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)
    if result.returncode == 0:
        return True, result.stdout.strip() or "receipt forgotten"
    return False, result.stderr.strip() or "pkgutil --forget failed"
