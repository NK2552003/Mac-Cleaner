"""Restore checksum verification helpers."""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from core.undo import DeletionSession, TRASH_ROOT

logger = logging.getLogger(__name__)

_CHECKSUM_DIR = TRASH_ROOT / "checksums"


@dataclass
class VerificationEntry:
    """Checksum verification for one file."""
    original_path: str
    restored_path: str
    checksum_before: str
    checksum_after: str
    matched: bool


@dataclass
class VerificationResult:
    """Summary of restore verification."""
    restored: int = 0
    verified: int = 0
    mismatched: int = 0
    failed: int = 0
    bytes_restored: int = 0
    errors: List[str] = field(default_factory=list)
    entries: List[VerificationEntry] = field(default_factory=list)


def _sha256(path: Path, chunk_size: int = 1024 * 1024) -> Optional[str]:
    if not path.exists():
        return None
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(chunk_size), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError as exc:
        logger.debug("checksum failed for %s: %s", path, exc)
        return None


def _write_manifest(session: DeletionSession, entries: List[VerificationEntry]) -> None:
    _CHECKSUM_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "session_id": session.session_id,
        "created_at": datetime.now().isoformat(),
        "entries": [e.__dict__ for e in entries],
    }
    (_CHECKSUM_DIR / f"{session.session_id}.json").write_text(json.dumps(payload, indent=2))


def restore_with_verification(session: DeletionSession) -> VerificationResult:
    """Restore a session and verify checksums before/after move."""
    result = VerificationResult()

    for f in session.files:
        staging = Path(f.staging_path)
        original = Path(f.original_path)

        if not staging.exists():
            result.failed += 1
            result.errors.append(f"Missing staged file: {f.original_path}")
            continue

        checksum_before = _sha256(staging)
        if checksum_before is None:
            result.failed += 1
            result.errors.append(f"Checksum failed: {f.original_path}")
            continue

        original.parent.mkdir(parents=True, exist_ok=True)
        restored_path = original
        if original.exists():
            restored_path = original.with_name(original.name + ".restored")

        try:
            shutil.move(str(staging), str(restored_path))
        except (shutil.Error, OSError) as exc:
            result.failed += 1
            result.errors.append(f"Restore failed: {f.original_path} ({exc})")
            continue

        checksum_after = _sha256(restored_path)
        if checksum_after is None:
            result.failed += 1
            result.errors.append(f"Checksum failed after restore: {restored_path}")
            continue

        matched = checksum_before == checksum_after
        result.restored += 1
        result.verified += 1 if matched else 0
        result.mismatched += 0 if matched else 1
        result.bytes_restored += f.size
        result.entries.append(VerificationEntry(
            original_path=f.original_path,
            restored_path=str(restored_path),
            checksum_before=checksum_before,
            checksum_after=checksum_after,
            matched=matched,
        ))

    _write_manifest(session, result.entries)
    return result
